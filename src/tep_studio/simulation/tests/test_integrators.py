"""Fixed-step RK4 integrator: fidelity vs RK45, default, stability guard, determinism."""

from __future__ import annotations

import numpy as np
import pytest

from tep_studio import TennesseeEastmanProcess
from tep_studio.control import ClosedLoopSimulation
from tep_studio.control.registry import RICKER_MODE1

_U0 = np.array(RICKER_MODE1.nominal.u0)


def _closed_loop_final_state(solver_method: str, horizon: float = 2.0):
    sim = TennesseeEastmanProcess(solver_method=solver_method)
    result = ClosedLoopSimulation(simulator=sim, control_interval=0.01, horizon=horizon).run(seed=0)
    return sim.state.copy(), result


def test_rk4_is_default() -> None:
    sim = TennesseeEastmanProcess()
    assert sim.solver_method == "RK4"
    assert sim.fixed_step == 0.0005


def test_rk4_matches_rk45_closed_loop() -> None:
    state_rk4, result_rk4 = _closed_loop_final_state("RK4")
    state_rk45, result_rk45 = _closed_loop_final_state("RK45")
    assert result_rk4.stabilized and result_rk45.stabilized
    assert result_rk4.peak["reactor_pressure_max"] < 3000.0
    rel = float(np.max(np.abs(state_rk4 - state_rk45) / (np.abs(state_rk45) + 1e-9)))
    assert rel < 1e-4, f"RK4 vs RK45 final state differs by {rel:.2e} (>0.01%)"


def test_rk45_path_still_works() -> None:
    sim = TennesseeEastmanProcess(solver_method="RK45")
    sim.reset()
    result = sim.advance(_U0, control_interval=0.01)
    assert result.solver_stats["method"] == "RK45"
    assert result.solver_stats["success"] is True


def test_rk4_solver_stats() -> None:
    sim = TennesseeEastmanProcess()  # RK4 default
    sim.reset()
    result = sim.advance(_U0, control_interval=0.01)
    assert result.solver_stats["method"] == "RK4"
    assert result.solver_stats["success"] is True
    assert result.solver_stats["nfev"] == 80  # 20 substeps (0.01/0.0005) x 4 stages


def test_too_coarse_fixed_step_raises() -> None:
    # A substep far above the ~0.0005 h stiffness floor diverges; the finite-value guard
    # must turn that into a loud RuntimeError rather than silent garbage.
    sim = TennesseeEastmanProcess(solver_method="RK4", fixed_step=0.005)
    sim.reset()
    with pytest.raises(RuntimeError):
        sim.advance(_U0, control_interval=0.5)  # 100 coarse substeps -> non-finite


def test_rk4_is_deterministic() -> None:
    def run() -> np.ndarray:
        sim = TennesseeEastmanProcess()
        sim.reset(seed=0)
        for _ in range(20):
            sim.advance(_U0, control_interval=0.01)
        return sim.state.copy()

    np.testing.assert_array_equal(run(), run())
