from __future__ import annotations

import dataclasses as dc

import numpy as np
import pytest

from tep_studio import TennesseeEastmanProcess
from tep_studio.control.controller import RickerMultiLoopController
from tep_studio.control.runner import ClosedLoopSimulation

IDV13 = np.zeros(28)
IDV13[12] = 1.0  # reaction-kinetics drift: a pressure-stressing disturbance


def _meas_with(base: np.ndarray, **by_name) -> np.ndarray:
    from tep_studio import TEP_SCHEMA

    meas = base.copy()
    for name, value in by_name.items():
        meas[TEP_SCHEMA.index("measurements", name)] = value
    return meas


def _ready_controller(**kwargs) -> tuple[RickerMultiLoopController, np.ndarray]:
    sim = TennesseeEastmanProcess()
    meas0, _ = sim.reset(mode="mode1")
    ctl = RickerMultiLoopController(enable_overrides=True, **kwargs)
    ctl.reset(meas0)
    return ctl, meas0


def test_pressure_override_math() -> None:
    ctl, meas0 = _ready_controller()
    # gain 1.5, threshold 2900: 60 kPa over -> cut Fp by 1.5*60 = 90.
    fp, active = ctl._apply_pressure_override(100.0, _meas_with(meas0, reactor_pressure=2960.0), {})
    assert active["high_pressure_to_production"] is True
    assert fp == pytest.approx(10.0)
    # Below threshold: untouched, not active.
    fp2, active2 = ctl._apply_pressure_override(100.0, _meas_with(meas0, reactor_pressure=2850.0), {})
    assert fp2 == 100.0
    assert active2["high_pressure_to_production"] is False


def test_level_override_math() -> None:
    ctl, meas0 = _ready_controller()
    action = np.full(12, 50.0)
    recycle_idx = ctl._vi["compressor_recycle_valve"]
    # gain 2.0, threshold 90: level 95 -> reduce recycle by 2*5 = 10.
    out, active = ctl._apply_level_override(action.copy(), _meas_with(meas0, reactor_level=95.0), {})
    assert active["high_level_to_recycle"] is True
    assert out[recycle_idx] == pytest.approx(40.0)
    out2, active2 = ctl._apply_level_override(action.copy(), _meas_with(meas0, reactor_level=80.0), {})
    assert out2[recycle_idx] == 50.0
    assert active2["high_level_to_recycle"] is False


def test_pressure_override_caps_pressure_under_stress() -> None:
    sim = TennesseeEastmanProcess()
    meas0, _ = sim.reset(mode="mode1")
    base = RickerMultiLoopController()
    base.reset(meas0)
    hi = dc.replace(base.setpoints, production_rate=32.0)  # demand high throughput

    def run(overrides: bool):
        # Pinned to adaptive RK45: this stress scenario rides the pressure constraint, where
        # the override threshold was tuned. The default 1-substep RK4 (at this fine 0.0005 h
        # interval) is slightly less accurate near the instability and undershoots the peak.
        ctl = RickerMultiLoopController(setpoints=hi, enable_overrides=overrides)
        # The controller rate-limits the production setpoint; seed the ramp at the demand so
        # the high-throughput pressure stress is exercised within this short horizon (the
        # gradual ramp would otherwise never reach it in 5 h).
        original_reset = ctl.reset

        def reset_then_demand(measurements, *, time: float = 0.0) -> None:
            original_reset(measurements, time=time)
            ctl._ramped_production = 32.0

        ctl.reset = reset_then_demand
        return ClosedLoopSimulation(
            simulator=TennesseeEastmanProcess(solver_method="RK45"),
            controller=ctl,
            control_interval=0.0005,
            horizon=5.0,
        ).run(disturbances=IDV13, record_every=2000)

    without = run(False)
    with_ovr = run(True)
    fired = any(d.overrides_active.get("high_pressure_to_production") for d in with_ovr.diagnostics)
    assert fired, "override should activate when pressure exceeds the threshold"
    assert with_ovr.peak["reactor_pressure_max"] < without.peak["reactor_pressure_max"]
    assert with_ovr.peak["reactor_pressure_max"] < 3000.0


def test_overrides_do_not_fire_or_harm_at_base_case() -> None:
    result = ClosedLoopSimulation(
        controller=RickerMultiLoopController(enable_overrides=True),
        control_interval=0.0005,
        horizon=6.0,
    ).run(record_every=2000)
    assert result.stabilized
    assert not any(d.overrides_active.get("high_pressure_to_production") for d in result.diagnostics)
    assert result.peak["reactor_pressure_max"] < 2900.0  # never reaches the override threshold
