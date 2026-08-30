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

from dataclasses import asdict
from statistics import fmean
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

# Closed-loop setpoint metadata: each operator target, the measurement it is
# regulated to (``measured_as`` — often a *different* name than the setpoint, which
# is why naive lookups fail), its unit, and behaviour notes. Sourced from the Ricker
# controller's loop pairings (control/controller.py, control/registry.py).
_SETPOINT_INFO = {
    "reactor_level": {"measured_as": "reactor_level", "unit": "%", "note": "reactor liquid level"},
    "reactor_pressure": {"measured_as": "reactor_pressure", "unit": "kPa gauge", "note": "reactor pressure; the plant trips at ~3000 kPa"},
    "reactor_temperature": {"measured_as": "reactor_temperature", "unit": "deg C", "note": "reactor temperature"},
    "separator_level": {"measured_as": "separator_level", "unit": "%", "note": "separator liquid level"},
    "stripper_level": {"measured_as": "stripper_level", "unit": "%", "note": "stripper liquid level"},
    "pct_g": {"measured_as": "stripper_underflow_G_concentration", "unit": "mol %", "note": "%G in the product; needs enable_pct_g_feedback (off by default)"},
    "production_rate": {
        "measured_as": "stripper_underflow",
        "unit": "m3/h",
        "note": "plant throughput = stripper underflow (stream 11). SLOW, rate-limited setpoint: it ramps gradually toward the target, so give it a long horizon to arrive.",
    },
    "ya": {"measured_as": None, "unit": "mol %", "note": "reactor-feed mol% A (derived from feed analysis; no single measurement column)"},
    "yac": {"measured_as": None, "unit": "mol %", "note": "reactor-feed mol% A+C (derived; no single measurement column)"},
}

# Setpoint name -> the frame column that measures it (for get_run_series aliasing).
_SETPOINT_TO_COLUMN = {k: f"measurement.{v['measured_as']}" for k, v in _SETPOINT_INFO.items() if v.get("measured_as")}


def _setpoint_catalog() -> list[dict]:
    """Setpoint fields enriched with unit, Mode-1 nominal, measured-as column, and notes."""
    import dataclasses as _dc

    from tep_studio.simulation.modes import mode_setpoints

    nominal = _dc.asdict(mode_setpoints("mode1"))
    catalog = []
    for name in setpoint_fields():
        info = _SETPOINT_INFO.get(name, {})
        catalog.append(
            {
                "name": name,
                "unit": info.get("unit"),
                "nominal_mode1": round(float(nominal[name]), 3) if name in nominal else None,
                "measured_as": info.get("measured_as"),
                "note": info.get("note"),
            }
        )
    return catalog

INSTRUCTIONS = """\
TEP Studio — drive the modified Tennessee Eastman Process simulator by tool calls.

Workflow:
1. Call `describe_plant` first to learn the disturbances (IDVs), measurements,
   manipulated variables, setpoints, operating modes, and ScenarioConfig fields.
2. Build a ScenarioConfig dict and call `run_scenario`. Names and bounds are
   validated; on an error, read the message and fix the dict (valid IDV names are
   idv_01..idv_28; IDV activations are binary 0 or 1; MVs are 0..100%).
3. Inspect with `get_run` / `get_run_series` and contrast scenarios with
   `compare_runs`. Use `run_sweep` for a predeclared set of matched scenarios or
   stochastic seeds. Reference prior runs by the `run_id` you got back.

Key facts to reason with:
- The base plant (mode1) is OPEN-LOOP UNSTABLE and trips on high reactor pressure
  (~3000 kPa) within ~1 h. Use loop_type="closed" (the built-in Ricker PI
  controller) for runs that survive the horizon.
- IDV disturbances are BINARY and LATCHED: 0 is off, 1 is on, and once activated
  at `start_time` they stay on. Intermediate values are invalid; they are not
  partial-severity disturbances.
- Evaluate safety against every published constraint and its minimum margin, not
  reactor pressure alone. A negative margin is a constraint violation.
- Setpoints are closed-loop targets (see describe_plant.setpoints for unit, Mode-1
  nominal, and the `measured_as` signal). `production_rate` is the stripper-underflow
  throughput (m3/h) and is SLOW/rate-limited — give it a long horizon to reach a new
  value. A setpoint's measured signal often has a different name (its `measured_as`,
  e.g. production_rate -> stripper_underflow); get_run_series also accepts the
  setpoint name and maps it for you.
- Always report the exact config you ran (it is returned for reproducibility).
- In run metadata, `truncated=true` means the requested horizon was reached without
  a shutdown; it does not mean that the simulation output was cut off.
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
    "seed": "optional native stochastic seed (float or null) for measurement noise and enabled stochastic disturbances",
    "disturbances": (
        "list of {idv, magnitude, start_time (h)}; magnitude is a compatibility field "
        "restricted to binary 0 (off) or 1 (on), and active IDVs are latched"
    ),
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
            "disturbances": [
                {
                    "name": variable.name,
                    "legacy_symbol": variable.legacy_symbol,
                    "description": variable.description,
                    "activation_values": [0, 1],
                    "latched": True,
                    "root_cause_status": variable.root_cause_status,
                    "perturbation_model": variable.perturbation_model,
                }
                for variable in TEP_SCHEMA.disturbances
            ],
            "manipulated_variables": [
                {"name": n, "unit": u, "description": d} for n, u, d in list_manipulated_variables()
            ],
            "measurements": [{"name": n, "unit": u, "description": d} for n, u, d in list_measurements()],
            "setpoints": _setpoint_catalog(),
            "constraints": [asdict(constraint) for constraint in TEP_SCHEMA.constraints],
            "disturbance_input_semantics": TEP_SCHEMA.disturbance_input_semantics,
            "scenario_config_fields": _SCENARIO_CONFIG_FIELDS,
            "notes": (
                "mode1 is open-loop unstable (trips ~3000 kPa within ~1 h); use loop_type='closed'. "
                "IDV disturbances are binary latched activations: magnitude must be 0 or 1. MVs are in 0..100%. "
                "Setpoints are closed-loop targets; a setpoint's measured signal is its 'measured_as' "
                "column (e.g. production_rate -> measurement.stripper_underflow). production_rate is "
                "slow/rate-limited — allow a long horizon for it to reach a new target."
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

    def run_sweep(self, configs: list[dict], seeds: list[float] | None = None) -> dict:
        """Run matched scenario configurations over an optional common seed set.

        Each configuration is validated as in ``run_scenario``. Supplying ``seeds``
        repeats every configuration at every listed native stochastic seed while
        holding the other fields fixed. The response includes run summaries and
        per-configuration shutdown, pressure, and worst constraint-margin aggregates.
        At most 90 runs may be requested so every result remains inspectable.
        """
        if not configs:
            return {"ok": False, "error": "configs must contain at least one scenario configuration"}
        seed_values: list[float | None] = list(seeds) if seeds else [None]
        total = len(configs) * len(seed_values)
        available = self.store.capacity - len(self.store.ids())
        if total > 90 or total > available:
            return {
                "ok": False,
                "error": f"sweep requests {total} runs but at most {min(90, available)} can be retained; reduce configs or seeds",
            }

        groups: list[dict[str, Any]] = []
        all_runs: list[dict[str, Any]] = []
        for config_index, source in enumerate(configs):
            group_runs: list[dict[str, Any]] = []
            for seed_index, seed in enumerate(seed_values):
                config = dict(source)
                if seeds:
                    config["seed"] = float(seed) if seed is not None else None
                base_name = str(config.get("name", f"scenario_{config_index + 1}"))
                config["name"] = f"{base_name}_seed_{seed_index}" if seeds else base_name
                outcome = self.run_scenario(config)
                if not outcome.get("ok"):
                    return {
                        "ok": False,
                        "error": f"config {config_index}, seed {seed!r}: {outcome.get('error', 'run failed')}",
                        "completed_runs": all_runs,
                    }
                group_runs.append(outcome)
                all_runs.append(outcome)
            groups.append(self._sweep_group(config_index, source, group_runs))
        return {
            "ok": True,
            "config_count": len(configs),
            "seeds": list(seeds or []),
            "run_count": len(all_runs),
            "groups": groups,
            "runs": [self._compact_sweep_run(run) for run in all_runs],
        }

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

    def compare_runs(self, run_ids: list[str], reference_run_id: str | None = None) -> dict:
        """Compare runs, safety margins, and measurement deviations side by side.

        The first run is the reference unless ``reference_run_id`` is supplied.
        For runs with common recorded times, all common measurements receive a
        maximum absolute reference-relative deviation.
        """
        rows, missing = [], []
        results: dict[str, Any] = {}
        for run_id in run_ids:
            result = self.store.get(run_id)
            if result is None:
                missing.append(run_id)
                continue
            row = dict(result.summary())
            row["shutdown"] = result.shutdown
            rows.append(row)
            results[run_id] = result
        out: dict[str, Any] = {"ok": bool(rows), "runs": rows}
        reference_id = reference_run_id or (rows[0]["run_id"] if rows else None)
        if reference_id is not None and reference_id in results:
            reference = results[reference_id]
            out["reference_run_id"] = reference_id
            out["measurement_max_abs_delta_vs_reference"] = {
                run_id: _measurement_max_abs_delta(reference, result)
                for run_id, result in results.items()
                if run_id != reference_id
            }
        elif reference_run_id is not None:
            missing.append(reference_run_id)
        if missing:
            out["missing_run_ids"] = list(dict.fromkeys(missing))
        if not rows:
            out["error"] = "no valid run_ids"
        return out

    @staticmethod
    def _sweep_group(config_index: int, source: dict, runs: list[dict[str, Any]]) -> dict[str, Any]:
        peaks = [float(run["peak_reactor_pressure"]) for run in runs if run.get("peak_reactor_pressure") is not None]
        constraint_names = {name for run in runs for name in run.get("minimum_constraint_margins", {})}
        return {
            "config_index": config_index,
            "source_config": source,
            "run_ids": [run["run_id"] for run in runs],
            "shutdown_count": sum(bool(run.get("terminated")) for run in runs),
            "constraint_violation_run_count": sum(int(run.get("constraint_violation_steps", 0)) > 0 for run in runs),
            "peak_reactor_pressure": {
                "min": min(peaks) if peaks else None,
                "mean": fmean(peaks) if peaks else None,
                "max": max(peaks) if peaks else None,
            },
            "worst_minimum_constraint_margins": {
                name: min(float(run["minimum_constraint_margins"][name]) for run in runs)
                for name in sorted(constraint_names)
            },
        }

    @staticmethod
    def _compact_sweep_run(run: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": run["run_id"],
            "name": run["name"],
            "seed": run["config"].get("seed"),
            "terminated": run["terminated"],
            "time_to_shutdown": run.get("time_to_shutdown"),
            "peak_reactor_pressure": run.get("peak_reactor_pressure"),
            "constraint_violation_steps": run.get("constraint_violation_steps", 0),
            "minimum_constraint_margins": run.get("minimum_constraint_margins", {}),
        }

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
                "name": "run_sweep",
                "description": self.run_sweep.__doc__,
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "configs": {"type": "array", "items": {"type": "object"}, "minItems": 1},
                        "seeds": {"type": "array", "items": {"type": "number"}},
                    },
                    "required": ["configs"],
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
                    "properties": {
                        "run_ids": {"type": "array", "items": {"type": "string"}},
                        "reference_run_id": {"type": "string"},
                    },
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
        if name == "run_sweep":
            return self.run_sweep(args.get("configs", []), args.get("seeds"))
        if name == "get_run":
            return self.get_run(args.get("run_id", ""))
        if name == "get_run_series":
            return self.get_run_series(args.get("run_id", ""), args.get("variables", []), int(args.get("max_points", 200)))
        if name == "list_runs":
            return self.list_runs()
        if name == "compare_runs":
            return self.compare_runs(args.get("run_ids", []), args.get("reference_run_id"))
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
    """Map a requested variable to an actual frame column.

    Accepts a full column, a bare measurement name, a closed-loop **setpoint name**
    (mapped to the signal it regulates, e.g. ``production_rate`` ->
    ``measurement.stripper_underflow``), or ``time``.
    """
    if var in columns:
        return var
    alias = _SETPOINT_TO_COLUMN.get(var)
    if alias and alias in columns:
        return alias
    for prefix in _COLUMN_PREFIXES:
        candidate = f"{prefix}.{var}"
        if candidate in columns:
            return candidate
    return None


def _measurement_max_abs_delta(reference: Any, candidate: Any) -> dict[str, float]:
    """Compare common measurement columns at common recorded times."""
    reference_frame = reference.to_frame().set_index("time")
    candidate_frame = candidate.to_frame().set_index("time")
    common_times = reference_frame.index.intersection(candidate_frame.index)
    common_columns = sorted(
        set(column for column in reference_frame.columns if column.startswith("measurement."))
        & set(column for column in candidate_frame.columns if column.startswith("measurement."))
    )
    if common_times.empty:
        return {}
    deltas: dict[str, float] = {}
    for column in common_columns:
        difference = (
            candidate_frame.loc[common_times, column].astype(float)
            - reference_frame.loc[common_times, column].astype(float)
        ).abs()
        deltas[column.removeprefix("measurement.")] = round(float(difference.max()), 6)
    return deltas
