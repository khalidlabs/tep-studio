"""OptimizationAdapter.linearize: shapes, finiteness, one-step reconstruction."""

from __future__ import annotations

import numpy as np

from tep_studio import OptimizationAdapter, TennesseeEastmanProcess


def test_linearize_shapes_and_reconstruction() -> None:
    # A tight-tolerance adaptive simulator gives a clean finite-difference Jacobian
    # (rtol/atol only affect the SciPy methods; the default RK4 ignores them).
    sim = TennesseeEastmanProcess(solver_method="RK45", rtol=1e-9, atol=1e-11)
    sim.reset(mode="mode1")
    x0 = sim.state.copy()
    u0 = sim.state[38:50].copy()
    control_interval = 0.001

    a_matrix, b_matrix = OptimizationAdapter(sim).linearize(x0, u0, control_interval=control_interval)
    assert a_matrix.shape == (50, 50)
    assert b_matrix.shape == (50, 12)
    assert np.isfinite(a_matrix).all() and np.isfinite(b_matrix).all()

    # The linear model should explain almost all of the one-step response to an input bump.
    du = np.zeros(12)
    du[0] = 0.5
    snapshot = sim.snapshot()
    sim.state = x0.copy()
    sim.kernel.state = x0.copy()
    actual = sim.advance(u0 + du, control_interval=control_interval).state
    sim.restore(snapshot)

    predicted = x0 + b_matrix @ du
    response = float(np.linalg.norm(actual - x0))
    error = float(np.linalg.norm(predicted - actual))
    assert response > 1e-6
    assert error / response < 0.05


def test_linearize_rejects_bad_shapes() -> None:
    sim = TennesseeEastmanProcess()
    sim.reset(mode="mode1")
    adapter = OptimizationAdapter(sim)
    import pytest

    with pytest.raises(ValueError):
        adapter.linearize(np.zeros(49), np.zeros(12), control_interval=0.001)
    with pytest.raises(ValueError):
        adapter.linearize(sim.state, np.zeros(11), control_interval=0.001)
