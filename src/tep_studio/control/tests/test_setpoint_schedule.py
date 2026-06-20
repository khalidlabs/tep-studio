from __future__ import annotations

import dataclasses as dc

from tep_studio import TennesseeEastmanProcess
from tep_studio.control.controller import RickerMultiLoopController
from tep_studio.control.runner import ClosedLoopSimulation


def _default_setpoints():
    sim = TennesseeEastmanProcess()
    meas0, _ = sim.reset(mode="mode1")
    ctl = RickerMultiLoopController()
    ctl.reset(meas0)
    return ctl.setpoints


def test_setpoint_step_moves_controlled_variable() -> None:
    base = _default_setpoints()
    target = dc.replace(base, reactor_pressure=base.reactor_pressure - 60.0)
    schedule = lambda t: target if t >= 1.0 else base  # noqa: E731

    stepped = ClosedLoopSimulation(
        controller=RickerMultiLoopController(setpoints=base),
        control_interval=0.0005,
        horizon=8.0,
    ).run(setpoint_schedule=schedule, record_every=2000)

    held = ClosedLoopSimulation(
        controller=RickerMultiLoopController(setpoints=base),
        control_interval=0.0005,
        horizon=8.0,
    ).run(record_every=2000)

    p_stepped = float(stepped.results[-1].measurements[6])
    p_held = float(held.results[-1].measurements[6])
    # The held run stays near the original pressure setpoint; the stepped run is pulled down.
    assert abs(p_held - base.reactor_pressure) < 25.0
    assert p_stepped < p_held - 20.0


def test_omitting_schedule_reproduces_default_behavior() -> None:
    base = _default_setpoints()
    a = ClosedLoopSimulation(controller=RickerMultiLoopController(setpoints=base), control_interval=0.0005, horizon=4.0).run(record_every=4000)
    b = ClosedLoopSimulation(controller=RickerMultiLoopController(setpoints=base), control_interval=0.0005, horizon=4.0).run(setpoint_schedule=None, record_every=4000)
    assert float(a.results[-1].measurements[6]) == float(b.results[-1].measurements[6])
