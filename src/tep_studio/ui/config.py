"""Scenario configuration objects -- the unit of save/load AND batch sweep.

All dataclasses are frozen and JSON round-trippable. ``ScenarioConfig.from_dict``
validates against the schema (IDV / MV / setpoint names, bounds, Mode-1-only core)
so a hand-edited or uploaded scenario file fails loudly rather than at run time.
This module is Dash-free.
"""

from __future__ import annotations

import dataclasses as dc
import itertools
import json
from dataclasses import dataclass, field

from tep_studio.control.controller import ControllerSetpoints
from tep_studio.simulation.schema import TEP_SCHEMA

SCHEMA_VERSION = 1


def setpoint_fields() -> tuple[str, ...]:
    return tuple(f.name for f in dc.fields(ControllerSetpoints))


@dataclass(frozen=True)
class DisturbanceActivation:
    """A single disturbance switched on at ``start_time`` (TEP IDVs are latched)."""

    idv: str  # schema name, e.g. "idv_01"
    magnitude: float = 1.0  # 0..1 (most IDVs are 0/1 switches)
    start_time: float = 0.0  # hours


@dataclass(frozen=True)
class StepTestSpec:
    kind: str  # "mv" (open loop) | "setpoint" (closed loop)
    target: str  # MV schema name (mv) or ControllerSetpoints field (setpoint)
    baseline: float
    step_value: float
    step_time: float


@dataclass(frozen=True)
class ScenarioConfig:
    name: str = "scenario"
    mode: str = "mode1"
    loop_type: str = "closed"  # "open" | "closed"
    horizon: float = 12.0
    control_interval: float = 0.01
    record_every: int = 0  # 0 -> auto (~one recorded point per 0.05 h)
    solver_method: str = "RK4"  # fast fixed-step default; "RK45"/"RK23" use adaptive SciPy
    rtol: float = 1e-6  # SciPy-only (inert for the fixed-step "RK4"/"Euler" methods)
    atol: float = 1e-8
    fixed_step: float = 0.0005  # RK4 substep (hours); the model is stiff near this value
    seed: float | None = None
    disturbances: tuple[DisturbanceActivation, ...] = ()
    setpoints: dict[str, float] | None = None  # closed loop; None -> seed from Mode-1 state
    enable_composition: bool = True
    enable_overrides: bool = False
    enable_pct_g_feedback: bool = False
    manual_mvs: dict[str, float] | None = None  # open loop; None -> nominal u0
    step_test: StepTestSpec | None = None

    # -- derived ----------------------------------------------------------
    def resolved_record_every(self) -> int:
        if self.record_every and self.record_every > 0:
            return int(self.record_every)
        return max(1, int(round(0.05 / self.control_interval)))

    # -- validation -------------------------------------------------------
    def validate(self) -> None:
        errors: list[str] = []
        if self.loop_type not in ("open", "closed"):
            errors.append(f"loop_type must be 'open' or 'closed', got {self.loop_type!r}")
        if self.mode not in ("mode1", "mode2", "mode3", "mode4", "mode5", "mode6"):
            errors.append(f"mode must be one of mode1..mode6, got {self.mode!r}")
        if self.horizon <= 0:
            errors.append("horizon must be > 0")
        if self.control_interval <= 0:
            errors.append("control_interval must be > 0")

        idv_names = set(TEP_SCHEMA.names("disturbances"))
        for dst in self.disturbances:
            if dst.idv not in idv_names:
                errors.append(f"unknown disturbance {dst.idv!r}")
            if not 0.0 <= dst.magnitude <= 1.0:
                errors.append(f"disturbance {dst.idv} magnitude {dst.magnitude} out of [0,1]")
            if dst.start_time < 0:
                errors.append(f"disturbance {dst.idv} start_time must be >= 0")

        sp_fields = set(setpoint_fields())
        if self.setpoints:
            for key in self.setpoints:
                if key not in sp_fields:
                    errors.append(f"unknown setpoint field {key!r}")

        mv_names = set(TEP_SCHEMA.names("manipulated_variables"))
        if self.manual_mvs:
            for key, value in self.manual_mvs.items():
                if key not in mv_names:
                    errors.append(f"unknown manipulated variable {key!r}")
                elif not 0.0 <= value <= 100.0:
                    errors.append(f"MV {key} value {value} out of [0,100]")

        if self.step_test is not None:
            st = self.step_test
            if st.kind not in ("mv", "setpoint"):
                errors.append(f"step_test.kind must be 'mv' or 'setpoint', got {st.kind!r}")
            elif st.kind == "mv" and st.target not in mv_names:
                errors.append(f"step_test target {st.target!r} is not a manipulated variable")
            elif st.kind == "setpoint" and st.target not in sp_fields:
                errors.append(f"step_test target {st.target!r} is not a setpoint field")

        if errors:
            raise ValueError("Invalid ScenarioConfig: " + "; ".join(errors))

    # -- serialization ----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "name": self.name,
            "mode": self.mode,
            "loop_type": self.loop_type,
            "horizon": self.horizon,
            "control_interval": self.control_interval,
            "record_every": self.record_every,
            "solver_method": self.solver_method,
            "rtol": self.rtol,
            "atol": self.atol,
            "fixed_step": self.fixed_step,
            "seed": self.seed,
            "disturbances": [dc.asdict(d) for d in self.disturbances],
            "setpoints": self.setpoints,
            "enable_composition": self.enable_composition,
            "enable_overrides": self.enable_overrides,
            "enable_pct_g_feedback": self.enable_pct_g_feedback,
            "manual_mvs": self.manual_mvs,
            "step_test": dc.asdict(self.step_test) if self.step_test else None,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> "ScenarioConfig":
        cfg = cls(
            name=d.get("name", "scenario"),
            mode=d.get("mode", "mode1"),
            loop_type=d.get("loop_type", "closed"),
            horizon=float(d.get("horizon", 12.0)),
            control_interval=float(d.get("control_interval", 0.01)),
            record_every=int(d.get("record_every", 0)),
            solver_method=d.get("solver_method", "RK4"),
            rtol=float(d.get("rtol", 1e-6)),
            atol=float(d.get("atol", 1e-8)),
            fixed_step=float(d.get("fixed_step", 0.0005)),
            seed=None if d.get("seed") is None else float(d["seed"]),
            disturbances=tuple(DisturbanceActivation(**x) for x in d.get("disturbances", [])),
            setpoints=None if d.get("setpoints") is None else {k: float(v) for k, v in d["setpoints"].items()},
            enable_composition=bool(d.get("enable_composition", True)),
            enable_overrides=bool(d.get("enable_overrides", False)),
            enable_pct_g_feedback=bool(d.get("enable_pct_g_feedback", False)),
            manual_mvs=None if d.get("manual_mvs") is None else {k: float(v) for k, v in d["manual_mvs"].items()},
            step_test=StepTestSpec(**d["step_test"]) if d.get("step_test") else None,
        )
        cfg.validate()
        return cfg

    @classmethod
    def from_json(cls, text: str) -> "ScenarioConfig":
        return cls.from_dict(json.loads(text))


@dataclass(frozen=True)
class BatchSpec:
    """A sweep over a base scenario -- seeds x disturbance sets x a parameter grid."""

    base: ScenarioConfig
    seeds: tuple[float, ...] = ()
    disturbance_grid: tuple[tuple[DisturbanceActivation, ...], ...] = ()
    param_grid: dict[str, tuple[float, ...]] = field(default_factory=dict)  # e.g. {"setpoints.production_rate": (22, 28)}
    label: str = "batch"

    def expand(self) -> list[ScenarioConfig]:
        seeds = self.seeds or (self.base.seed,)
        dgrid = self.disturbance_grid or (self.base.disturbances,)
        keys = list(self.param_grid)
        combos = list(itertools.product(*(self.param_grid[k] for k in keys))) if keys else [()]
        out: list[ScenarioConfig] = []
        for i, (seed, dist, combo) in enumerate(itertools.product(seeds, dgrid, combos)):
            cfg = dc.replace(self.base, seed=seed, disturbances=tuple(dist), name=f"{self.label}_{i:03d}")
            cfg = _apply_overrides(cfg, dict(zip(keys, combo)))
            cfg.validate()
            out.append(cfg)
        return out

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "base": self.base.to_dict(),
            "seeds": list(self.seeds),
            "disturbance_grid": [[dc.asdict(d) for d in group] for group in self.disturbance_grid],
            "param_grid": {k: list(v) for k, v in self.param_grid.items()},
            "label": self.label,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: dict) -> "BatchSpec":
        return cls(
            base=ScenarioConfig.from_dict(d["base"]),
            seeds=tuple(float(s) for s in d.get("seeds", [])),
            disturbance_grid=tuple(
                tuple(DisturbanceActivation(**x) for x in group) for group in d.get("disturbance_grid", [])
            ),
            param_grid={k: tuple(float(x) for x in v) for k, v in d.get("param_grid", {}).items()},
            label=d.get("label", "batch"),
        )


def _apply_overrides(cfg: ScenarioConfig, overrides: dict[str, float]) -> ScenarioConfig:
    """Apply dotted-path overrides like ``setpoints.production_rate`` or a top-level field."""
    setpoints = dict(cfg.setpoints) if cfg.setpoints else None
    top: dict[str, object] = {}
    for key, value in overrides.items():
        if key.startswith("setpoints."):
            setpoints = setpoints or {}
            setpoints[key.split(".", 1)[1]] = float(value)
        else:
            top[key] = value
    if setpoints is not None:
        top["setpoints"] = setpoints
    return dc.replace(cfg, **top)
