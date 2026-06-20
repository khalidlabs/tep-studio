from __future__ import annotations

import numpy as np
import pytest

from tep_studio.control.controller import RickerMultiLoopController
from tep_studio.control.runner import ClosedLoopSimulation


def _idv(index_1based: int) -> np.ndarray:
    v = np.zeros(28)
    v[index_1based - 1] = 1.0
    return v


@pytest.mark.parametrize("idv, name", [(1, "AC_ratio_step"), (8, "random_ABC_comp"), (13, "kinetics_drift")])
def test_disturbance_is_rejected(idv: int, name: str) -> None:
    result = ClosedLoopSimulation(
        controller=RickerMultiLoopController(enable_overrides=True),
        control_interval=0.0005,
        horizon=8.0,
    ).run(disturbances=_idv(idv), record_every=4000)
    assert not result.terminated, name
    assert result.peak["reactor_pressure_max"] < 3000.0
    for cv in ("reactor_level", "separator_level", "stripper_level"):
        assert result.peak[f"{cv}_min"] > 0.0
        assert result.peak[f"{cv}_max"] < 100.0


def test_severe_a_feed_loss_outlasts_open_loop() -> None:
    # IDV(6) is a total loss of the A feed -- one of the hardest TEP disturbances.
    # The controller sustains the plant well past the ~3.2 h open-loop base-case
    # shutdown even though it cannot hold it indefinitely.
    result = ClosedLoopSimulation(
        controller=RickerMultiLoopController(enable_overrides=True),
        control_interval=0.0005,
        horizon=6.0,
    ).run(disturbances=_idv(6), record_every=4000)
    assert result.final_time > 3.2


def test_steady_state_parity_with_mode1_base_case() -> None:
    result = ClosedLoopSimulation(control_interval=0.0005, horizon=10.0).run(record_every=2000)
    last = result.results[-1].measurements
    assert abs(float(last[7]) - 75.0) < 3.0  # reactor level near base 75 %
    assert abs(float(last[6]) - 2705.0) < 60.0  # reactor pressure near base
    assert abs(float(last[8]) - 120.4) < 2.0  # reactor temperature
    assert 21.0 < float(last[16]) < 25.0  # production near nominal ~22.95
