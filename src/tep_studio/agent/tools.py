"""The shared TEP toolset — one implementation, two surfaces.

:class:`TepToolset` wraps the Dash-free :mod:`tep_studio.ui` backend as a small set
of LLM-callable tools (describe / run / inspect / compare), each grounded in the
process schema. The same object backs:

- the MCP server (:mod:`tep_studio.agent.mcp_server`), and
- the in-studio chat panel (:mod:`tep_studio.ui.chat_panel`),

so an agent drives the simulator the same way whether it speaks MCP or the
Anthropic Messages API. The toolset holds a :class:`~tep_studio.ui.store.RunStore`;
pass the app's store to share runs with the rest of the studio.

This module imports only core dependencies (no ``mcp``/``anthropic``/Dash), so the
tool logic is unit-testable on its own.
"""

from __future__ import annotations

from typing import Any

from tep_studio import (
    TEP_SCHEMA,
    list_disturbances,
    list_manipulated_variables,
    list_measurements,
)
from tep_studio.ui import ScenarioConfig
from tep_studio.ui import run_scenario as _run_scenario
from tep_studio.ui.config import setpoint_fields
from tep_studio.ui.store import RunStore

# Guard rails for interactive use (a runaway horizon would block the event loop).
MAX_HORIZON_H = 200.0
MAX_SERIES_POINTS = 2000

_MODES = ("mode1", "mode2", "mode3", "mode4", "mode5", "mode6")
_SOLVERS = ("RK4", "Euler", "RK45", "RK23")
_COLUMN_PREFIXES = (
    "measurement",
    "state",
    "requested_action",
    "implemented_action",
    "disturbance",
    "objective",
)

INSTRUCTIONS = """\
TEP Studio — drive the modified Tennessee Eastman Process simulator by tool calls.

Workflow:
1. Call `describe_plant` first to learn the disturbances (IDVs), measurements,
   manipulated variables, setpoints, operating modes, and ScenarioConfig fields.
2. Build a ScenarioConfig dict and call `run_scenario`. Names and bounds are
   validated; on an error, read the message and fix the dict (valid IDV names are
   idv_01..idv_28; magnitudes are 0..1; MVs are 0..100%).
3. Inspect with `get_run` / `get_run_series` and contrast scenarios with
   `compare_runs`. Reference prior runs by the `run_id` you got back.

Key facts to reason with:
- The base plant (mode1) is OPEN-LOOP UNSTABLE and trips on high reactor pressure
  (~3000 kPa) within ~1 h. Use loop_type="closed" (the built-in Ricker PI
  controller) for runs that survive the horizon.
- IDV disturbances are LATCHED: once activated at `start_time` they stay on.
- Always report the exact config you ran (it is returned for reproducibility).
- Keep horizons modest (a few to a few tens of hours) for interactive use.
"""

_SCENARIO_CONFIG_FIELDS = {
    "name": "label for the run (str)",
    "mode": f"operating mode, one of {list(_MODES)} (mode1 = Downs & Vogel base case)",
    "loop_type": "'closed' (Ricker PI controller) or 'open' (manual/held valves)",
    "horizon": "simulated duration in hours (float, > 0)",
    "control_interval": "control/sampling interval in hours (default 0.01)",
    "solver_method": f"integrator, one of {list(_SOLVERS)} (RK4 = fast fixed-step default)",
    "fixed_step": "RK4/Euler substep in hours (default 0.0005; the model is stiff)",
    "seed": "optional measurement-noise seed (float or null) for reproducibility",
    "disturbances": "list of {idv, magnitude (0..1), start_time (h)}; IDVs are latched",
    "setpoints": "closed-loop only: {setpoint_field: value} overrides (see setpoints list)",
    "enable_composition": "closed-loop composition control on/off (default true)",
    "enable_overrides": "high-pressure/level safety overrides on/off",
    "enable_pct_g_feedback": "%G composition feedforward on/off (default false; needs retuning)",
    "manual_mvs": "open-loop only: {mv_name: 0..100} valve overrides",
    "controller_tuning": "closed-loop only: {param_path: value} over the Ricker registry defaults",
    "step_test": "optional {kind: 'mv'|'setpoint', target, baseline, step_value, step_time}",
}


class TepToolset:
    """LLM-callable tools over a shared :class:`RunStore`."""

    def __init__(self, store: RunStore | None = None, *, capacity: int = 100) -> None:
        self.store = store if store is not None else RunStore(capacity=capacity)
        self._descs = {name: desc for name, desc in list_disturbances()}

    # -- tools -------------------------------------------------------------
    def describe_plant(self) -> dict:
        """Describe the simulator: disturbances, measurements, manipulated variables,
        setpoints, operating modes, solvers, and the ScenarioConfig fields.

        Call this first. The returned names are exactly what `run_scenario` validates
        against, so configure runs from this catalog rather than guessing.
        """
        return {
            "plant": "Modified Tennessee Eastman Process (Downs & Vogel; modified kernel by Bathelt, Ricker & Jelali, 2015)",
            "modes": list(_MODES),
            "loop_types": ["closed", "open"],
            "solver_methods": list(_SOLVERS),
            "disturbances": [{"name": n, "description": d} for n, d in list_disturbances()],
            "manipulated_variables": [
                {"name": n, "unit": u, "description": d} for n, u, d in list_manipulated_variables()
            ],
            "measurements": [{"name": n, "unit": u} for n, u, _ in list_measurements()],
            "setpoints": list(setpoint_fields()),
            "scenario_config_fields": _SCENARIO_CONFIG_FIELDS,
            "notes": (
                "mode1 is open-loop unstable (trips ~3000 kPa within ~1 h); use loop_type='closed'. "
                "IDV disturbances are latched. magnitude in 0..1, MVs in 0..100%."
            ),
        }

    def run_scenario(self, config: dict) -> dict:
        """Run one TEP simulation from a ScenarioConfig dict and return a run_id + summary.

        `config` keys are described by `describe_plant` (scenario_config_fields). Names and
        bounds are validated; on failure this returns {"ok": false, "error": ...} with a
        descriptive message so you can fix the dict and retry. The exact config that ran is
        echoed back under "config" for reproducibility. Use a closed loop for stable runs.
        """
        try:
            cfg = ScenarioConfig.from_dict(config or {})
        except (ValueError, TypeError, KeyError) as exc:
            return {
                "ok": False,
                "error": str(exc),
                "hint": "Call describe_plant for valid disturbance/MV/setpoint names and ScenarioConfig fields.",
            }
        if cfg.horizon > MAX_HORIZON_H:
            return {
                "ok": False,
                "error": f"horizon {cfg.horizon} h exceeds the interactive limit of {MAX_HORIZON_H} h; use a smaller horizon.",
            }
        result = _run_scenario(cfg)
        self.store.put(result)
        return {"ok": True, **self._summary(result)}

    def get_run(self, run_id: str) -> dict:
        """Fetch the summary, exact config, and available plot columns for a prior run_id."""
        result = self.store.get(run_id)
        if result is None:
            return {"ok": False, "error": f"unknown run_id {run_id!r}", "known_run_ids": self.store.ids()}
        summary = self._summary(result)
        summary["ok"] = True
        summary["measurement_columns"] = [c for c in result.columns if c.startswith("measurement.")]
        return summary

    def get_run_series(self, run_id: str, variables: list[str], max_points: int = 200) -> dict:
        """Return downsampled time series for the named variables of a prior run.

        `variables` may be bare names ("reactor_pressure") or full columns
        ("measurement.reactor_pressure", "implemented_action.reactor_cooling"). The series
        is downsampled to at most `max_points` points so it is cheap to read.
        """
        result = self.store.get(run_id)
        if result is None:
            return {"ok": False, "error": f"unknown run_id {run_id!r}", "known_run_ids": self.store.ids()}
        columns = list(result.columns)
        resolved: dict[str, str] = {}
        unknown: list[str] = []
        for var in variables:
            col = _resolve_column(columns, var)
            (resolved.__setitem__(var, col) if col else unknown.append(var))
        if not resolved:
            return {
                "ok": False,
                "error": f"none of {variables} match a column",
                "available_measurements": [c[len("measurement.") :] for c in columns if c.startswith("measurement.")],
            }
        frame = result.to_frame()
        n = len(frame)
        cap = max(2, min(int(max_points), MAX_SERIES_POINTS))
        stride = max(1, -(-n // cap))  # ceil division -> at most `cap` points
        view = frame.iloc[::stride]
        out: dict[str, Any] = {
            "ok": True,
            "run_id": run_id,
            "n_points": int(len(view)),
            "downsampled_from": int(n),
            "time_h": [round(float(t), 4) for t in view["time"].tolist()],
            "series": {var: [round(float(v), 5) for v in view[col].tolist()] for var, col in resolved.items()},
        }
        if unknown:
            out["unresolved"] = unknown
        return out

    def list_runs(self) -> dict:
        """List the cached runs (most-recent last) with one-line summaries."""
        runs = []
        for run_id in self.store.ids():
            result = self.store.get(run_id)
            if result is not None:
                runs.append(result.summary())
        return {"ok": True, "count": len(runs), "runs": runs}

    def compare_runs(self, run_ids: list[str]) -> dict:
        """Compare prior runs side by side (summaries: shutdown, final time, peak pressure, IAE/ISE)."""
        rows, missing = [], []
        for run_id in run_ids:
            result = self.store.get(run_id)
            if result is None:
                missing.append(run_id)
                continue
            row = dict(result.summary())
            row["shutdown"] = result.shutdown
            rows.append(row)
        out: dict[str, Any] = {"ok": bool(rows), "runs": rows}
        if missing:
            out["missing_run_ids"] = missing
        if not rows:
            out["error"] = "no valid run_ids"
        return out

    # -- Anthropic / MCP integration --------------------------------------
    def tool_specs(self) -> list[dict]:
        """Anthropic Messages-API tool definitions (name / description / input_schema)."""
        return [
            {
                "name": "describe_plant",
                "description": self.describe_plant.__doc__,
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "run_scenario",
                "description": self.run_scenario.__doc__,
                "input_schema": {
                    "type": "object",
                    "properties": {"config": {"type": "object", "description": "ScenarioConfig dict (see describe_plant.scenario_config_fields)"}},
                    "required": ["config"],
                },
            },
            {
                "name": "get_run",
                "description": self.get_run.__doc__,
                "input_schema": {"type": "object", "properties": {"run_id": {"type": "string"}}, "required": ["run_id"]},
            },
            {
                "name": "get_run_series",
                "description": self.get_run_series.__doc__,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "run_id": {"type": "string"},
                        "variables": {"type": "array", "items": {"type": "string"}},
                        "max_points": {"type": "integer", "default": 200},
                    },
                    "required": ["run_id", "variables"],
                },
            },
            {
                "name": "list_runs",
                "description": self.list_runs.__doc__,
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "compare_runs",
                "description": self.compare_runs.__doc__,
                "input_schema": {
                    "type": "object",
                    "properties": {"run_ids": {"type": "array", "items": {"type": "string"}}},
                    "required": ["run_ids"],
                },
            },
        ]

    def dispatch(self, name: str, arguments: dict) -> dict:
        """Execute a tool call by name with keyword arguments (used by the chat loop)."""
        args = dict(arguments or {})
        if name == "describe_plant":
            return self.describe_plant()
        if name == "run_scenario":
            return self.run_scenario(args.get("config", {}))
        if name == "get_run":
            return self.get_run(args.get("run_id", ""))
        if name == "get_run_series":
            return self.get_run_series(args.get("run_id", ""), args.get("variables", []), int(args.get("max_points", 200)))
        if name == "list_runs":
            return self.list_runs()
        if name == "compare_runs":
            return self.compare_runs(args.get("run_ids", []))
        return {"ok": False, "error": f"unknown tool {name!r}"}

    # -- helpers ----------------------------------------------------------
    def _summary(self, result: Any) -> dict:
        """A compact, JSON-safe summary of a RunResult (no trajectory)."""
        summary = dict(result.summary())  # run_id, name, loop_type, horizon, terminated, ...
        summary.update(
            {
                "mode": result.scenario.mode,
                "truncated": result.truncated,
                "n_steps": result.n_steps,
                "shutdown": result.shutdown,
                "active_disturbances": [
                    {
                        "idv": d.idv,
                        "magnitude": d.magnitude,
                        "start_time_h": d.start_time,
                        "description": self._descs.get(d.idv, ""),
                    }
                    for d in result.scenario.disturbances
                ],
                "config": result.scenario.to_dict(),
            }
        )
        return summary


def _resolve_column(columns: list[str], var: str) -> str | None:
    """Map a requested variable to an actual frame column (full, bare, or 'time')."""
    if var in columns:
        return var
    for prefix in _COLUMN_PREFIXES:
        candidate = f"{prefix}.{var}"
        if candidate in columns:
            return candidate
    return None
