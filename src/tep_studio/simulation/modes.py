"""Operating modes for the TEP — the six economic operating points (G/H product ratio
x production rate).

A mode is a controller-setpoint preset applied on top of the base steady state, not a
separate initial condition: every run starts from the base state and the closed loop
steers the plant to the selected operating point. This keeps mode selection simple and
free of precomputed data. Mode 1 is the base case (no overrides).
"""

from __future__ import annotations

import dataclasses as dc
from dataclasses import dataclass

from tep_studio.control import ControllerSetpoints

# Request value for the "max" modes; the controller caps it at the feasible throughput.
_MAX_PRODUCTION_RATE = 38.0


@dataclass(frozen=True)
class ModeInfo:
    key: str  # "mode1".."mode6"
    label: str
    product_mix: str  # G:H mass ratio, e.g. "50/50"
    production: str  # "base" | "max"


# Per-mode setpoint overrides on top of the base operating point. Mode 1 = base case.
_MODE_OVERRIDES: dict[str, dict[str, float]] = {
    "mode1": {},
    "mode2": {"pct_g": 11.66, "reactor_pressure": 2800.0, "reactor_level": 65.0, "reactor_temperature": 124.2},
    "mode3": {"pct_g": 90.09, "reactor_pressure": 2800.0, "reactor_level": 65.0, "reactor_temperature": 121.9},
    "mode4": {"pct_g": 53.35, "reactor_pressure": 2800.0, "reactor_level": 65.0, "reactor_temperature": 128.2, "production_rate": _MAX_PRODUCTION_RATE},
    "mode5": {"pct_g": 11.65, "reactor_pressure": 2800.0, "reactor_level": 65.0, "reactor_temperature": 124.6, "production_rate": _MAX_PRODUCTION_RATE},
    "mode6": {"pct_g": 90.07, "reactor_pressure": 2800.0, "reactor_level": 65.0, "reactor_temperature": 123.0, "production_rate": _MAX_PRODUCTION_RATE},
}

_MODE_META: dict[str, tuple[str, str, str]] = {
    "mode1": ("Mode 1 (base case)", "50/50", "base"),
    "mode2": ("Mode 2", "10/90", "base"),
    "mode3": ("Mode 3", "90/10", "base"),
    "mode4": ("Mode 4", "50/50", "max"),
    "mode5": ("Mode 5", "10/90", "max"),
    "mode6": ("Mode 6", "90/10", "max"),
}

MODE_KEYS: tuple[str, ...] = tuple(_MODE_OVERRIDES)
MODES: tuple[ModeInfo, ...] = tuple(ModeInfo(key, *_MODE_META[key]) for key in MODE_KEYS)

_base_setpoints_cache: ControllerSetpoints | None = None


def _base_setpoints() -> ControllerSetpoints:
    """The base-case controller setpoints (computed once from a clean reset)."""
    global _base_setpoints_cache
    if _base_setpoints_cache is None:
        from tep_studio.control import RickerMultiLoopController
        from tep_studio.simulation.core import TennesseeEastmanProcess

        sim = TennesseeEastmanProcess()
        measurements, _ = sim.reset()
        controller = RickerMultiLoopController()
        controller.reset(measurements)
        _base_setpoints_cache = controller.setpoints
    return _base_setpoints_cache


def mode_info(mode: str) -> ModeInfo:
    if mode not in _MODE_OVERRIDES:
        raise KeyError(f"Unknown mode {mode!r}; expected one of {MODE_KEYS}.")
    return ModeInfo(mode, *_MODE_META[mode])


def mode_setpoints(mode: str) -> ControllerSetpoints:
    """The controller setpoints that define ``mode`` (base setpoints + the mode overrides)."""
    if mode not in _MODE_OVERRIDES:
        raise KeyError(f"Unknown mode {mode!r}; expected one of {MODE_KEYS}.")
    values = dc.asdict(_base_setpoints())
    values.update(_MODE_OVERRIDES[mode])
    return ControllerSetpoints(**values)


def available_modes() -> tuple[str, ...]:
    return MODE_KEYS
