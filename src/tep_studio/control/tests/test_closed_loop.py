from __future__ import annotations

import inspect
import os

import numpy as np
import pytest

from tep_studio import TennesseeEastmanProcess
from tep_studio.control.controller import RickerMultiLoopController
from tep_studio.control.registry import RICKER_MODE1
from tep_studio.control.runner import ClosedLoopSimulation
from tep_studio.control.views import diagnostic_view, online_control_view

U0 = np.array(RICKER_MODE1.nominal.u0, dtype=np.float64)


def test_closed_loop_stabilizes_base_case() -> None:
    # The headline result: the plant that shuts down open-loop runs the horizon.
    result = ClosedLoopSimulation(control_interval=0.0005, horizon=12.0).run()
    assert result.stabilized
    assert not result.terminated
    assert result.peak["reactor_pressure_max"] < 3000.0
    for cv in ("reactor_level", "separator_level", "stripper_level"):
        assert result.peak[f"{cv}_min"] > 0.0
        assert result.peak[f"{cv}_max"] < 100.0


def test_open_loop_dies_but_closed_loop_survives_past_it() -> None:
    # Open loop at the base-case inputs is unstable and shuts down within ~2 h.
    sim = TennesseeEastmanProcess()
    sim.reset(mode="mode1")
    open_loop_terminated = False
    open_loop_time = None
    while sim.time < 5.0:
        res = sim.advance(U0, control_interval=0.01)
        if res.shutdown_status["terminated"]:
            open_loop_terminated = True
            open_loop_time = res.time
            break
    assert open_loop_terminated, "base-case open loop should be unstable"
    assert open_loop_time < 5.0

    # Closed loop comfortably passes the open-loop shutdown time.
    closed = ClosedLoopSimulation(control_interval=0.0005, horizon=5.0).run()
    assert not closed.terminated
    assert closed.final_time >= 5.0 - 1e-6


def test_controller_first_action_is_bumpless() -> None:
    sim = TennesseeEastmanProcess()
    meas0, _ = sim.reset(mode="mode1")
    ctl = RickerMultiLoopController()
    ctl.reset(meas0, time=0.0)
    action, _ = ctl.compute_action(meas0, time=0.0)
    assert np.max(np.abs(action - U0)) < 0.5  # first action ~= base-case MVs


def test_compute_action_consumes_only_measurements() -> None:
    # P5 / no model leakage: the control interface takes measurements, not plant state.
    params = inspect.signature(RickerMultiLoopController.compute_action).parameters
    assert "measurements" in params
    assert "state" not in params


def test_online_view_excludes_state_and_diagnostic_view_includes_it() -> None:
    sim = TennesseeEastmanProcess()
    meas0, _ = sim.reset(mode="mode1")
    online = online_control_view(meas0)
    # Online view is a small set of named measurements -- never the 50-state vector.
    assert "reactor_pressure" in online
    assert len(online) < 25
    assert all(isinstance(v, float) for v in online.values())

    result = sim.advance(U0, control_interval=0.001)
    diag = diagnostic_view(result)
    assert len(diag["state"]) == 50  # full internal state available offline only


@pytest.mark.skipif(not os.environ.get("RUN_SLOW"), reason="slow full-horizon run; set RUN_SLOW=1")
def test_closed_loop_full_horizon() -> None:
    # Manuscript-artifact run at full control fidelity (Ts_base). Opt-in via RUN_SLOW=1.
    result = ClosedLoopSimulation(control_interval=0.0005, horizon=48.0).run(record_every=2000)
    assert result.stabilized
    assert result.peak["reactor_pressure_max"] < 3000.0
