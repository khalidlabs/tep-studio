"""Operating modes for the TEP — the six economic operating points (G/H product ratio
x production rate).

Most modes are a controller-setpoint preset applied on top of the base steady state: the
run starts from the base state and the closed loop steers the plant to the operating point.
The 90/10 modes (3 and 6) are the exception — their extreme composition cannot be reached
from the base case without tripping on reactor pressure, so they start from a bundled
90/10 operating-point state and the controller holds it. Mode 1 is the base case.
"""

from __future__ import annotations

import dataclasses as dc
from dataclasses import dataclass

import numpy as np

from tep_studio.control import ControllerSetpoints

# "Max"-production modes attempt a modest increase above the base rate; a feed then
# saturates, capping the achievable throughput at the constraint.
_MAX_PRODUCTION_FACTOR = 1.10

# Full 50-element plant state at the 90/10 (mass %G) operating point. The base case cannot
# be steered to 90 %G in closed loop without a high-pressure trip, so modes 3 and 6 start
# here and the controller holds the point (reactor pressure ~2799 kPa, %G ~90.1, prod ~18).
_MODE3_INITIAL_STATE = np.array([
    9.833059595633491, 15.818863237372002, 3.244913342233391, 0.7214900357282344, 5.078176310823953,
    2.3178125529229834, 290.7649079400237, 33.409493306315, 2.6191862636065864, 56.07378925669175,
    90.19588548753497, 18.5135888527456, 0.47022360194109875, 3.522842312312024, 1.6095821373257755,
    106.8082691597968, 9.347524950173677, 0.6294636728262546, 0.45779081107908093, 0.008495098468059108,
    0.9627765511353865, 0.027263648701851616, 0.15461456381467636, 0.06857969265485978, 87.10114965093514,
    7.901080003491627, 0.3638050171755673, 94.64346074481878, 88.8638153761146, 57.599219161550714,
    40.561843547239384, 12.505104041822435, 4.132971735539365, 21.443863597176012, 1.1207348491128424,
    0.6352809507090715, 101.88085116273128, 45.57033615920578, 88.95389613828291, 8.619853039212328,
    19.327542107010533, 51.25960760926869, 76.94884066473048, 8.762833216457446, 29.163675060014086,
    39.44928308624537, 0.9999999999999963, 35.57823123175531, 89.22458855710266, 99.99999999999999,
])

# Modes that start from the bundled 90/10 state rather than the base case.
_PRESET_STATE_MODES = ("mode3", "mode6")


@dataclass(frozen=True)
class ModeInfo:
    key: str  # "mode1".."mode6"
    label: str
    product_mix: str  # G:H mass ratio, e.g. "50/50"
    production: str  # "base" | "max"


# Per-mode setpoint overrides on top of the base operating point, for the modes reached by
# steering from the base case. Mode 1 = base case; modes 3/6 derive setpoints from the
# bundled 90/10 state instead (see ``_mode3_setpoints``).
_MODE_OVERRIDES: dict[str, dict[str, float]] = {
    "mode1": {},
    "mode2": {"pct_g": 11.66, "reactor_pressure": 2800.0, "reactor_level": 65.0, "reactor_temperature": 124.2},
    "mode4": {"pct_g": 53.35, "reactor_pressure": 2800.0, "reactor_level": 65.0, "reactor_temperature": 128.2},
    "mode5": {"pct_g": 11.65, "reactor_pressure": 2800.0, "reactor_level": 65.0, "reactor_temperature": 124.6},
}

_MODE_META: dict[str, tuple[str, str, str]] = {
    "mode1": ("Mode 1 (base case)", "50/50", "base"),
    "mode2": ("Mode 2", "10/90", "base"),
    "mode3": ("Mode 3", "90/10", "base"),
    "mode4": ("Mode 4", "50/50", "max"),
    "mode5": ("Mode 5", "10/90", "max"),
    "mode6": ("Mode 6", "90/10", "max"),
}

MODE_KEYS: tuple[str, ...] = tuple(_MODE_META)
MODES: tuple[ModeInfo, ...] = tuple(ModeInfo(key, *_MODE_META[key]) for key in MODE_KEYS)

_base_setpoints_cache: ControllerSetpoints | None = None
_mode3_setpoints_cache: ControllerSetpoints | None = None


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


def _mode3_setpoints() -> ControllerSetpoints:
    """The 90/10 operating-point setpoints, derived once from the bundled state so they
    are exactly consistent with it (the controller holds the point with no offset)."""
    global _mode3_setpoints_cache
    if _mode3_setpoints_cache is None:
        from tep_studio.control import RickerMultiLoopController
        from tep_studio.simulation.core import TennesseeEastmanProcess

        sim = TennesseeEastmanProcess()
        measurements, _ = sim.reset(initial_state=_MODE3_INITIAL_STATE)
        controller = RickerMultiLoopController()
        controller.reset(measurements)
        _mode3_setpoints_cache = controller.setpoints
    return _mode3_setpoints_cache


def mode_info(mode: str) -> ModeInfo:
    if mode not in _MODE_META:
        raise KeyError(f"Unknown mode {mode!r}; expected one of {MODE_KEYS}.")
    return ModeInfo(mode, *_MODE_META[mode])


def mode_initial_state(mode: str) -> np.ndarray | None:
    """The full 50-element initial state for ``mode``, or ``None`` to start from the base
    case (modes steered from base). Modes 3 and 6 start from the bundled 90/10 state."""
    if mode not in _MODE_META:
        raise KeyError(f"Unknown mode {mode!r}; expected one of {MODE_KEYS}.")
    if mode in _PRESET_STATE_MODES:
        return _MODE3_INITIAL_STATE.copy()
    return None


def mode_setpoints(mode: str) -> ControllerSetpoints:
    """The controller setpoints that define ``mode``."""
    if mode not in _MODE_META:
        raise KeyError(f"Unknown mode {mode!r}; expected one of {MODE_KEYS}.")
    if mode in _PRESET_STATE_MODES:  # 90/10: derive from the bundled operating point
        sp = _mode3_setpoints()
        if _MODE_META[mode][2] == "max":  # mode 6 attempts a modest increase over mode 3
            sp = dc.replace(sp, production_rate=sp.production_rate * _MAX_PRODUCTION_FACTOR)
        return sp
    values = dc.asdict(_base_setpoints())
    values.update(_MODE_OVERRIDES[mode])
    if _MODE_META[mode][2] == "max":  # attempt a modest production increase over base
        values["production_rate"] = values["production_rate"] * _MAX_PRODUCTION_FACTOR
    return ControllerSetpoints(**values)


def available_modes() -> tuple[str, ...]:
    return MODE_KEYS
