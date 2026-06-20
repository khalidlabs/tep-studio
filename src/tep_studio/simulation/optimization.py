from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.typing import ArrayLike

from tep_studio.simulation.core import AdvanceResult, TennesseeEastmanProcess


@dataclass(frozen=True)
class RolloutResult:
    results: tuple[AdvanceResult, ...]
    objective: float
    terminated: bool


class OptimizationAdapter:
    differentiability = "finite_difference_only"

    def __init__(
        self,
        simulator: TennesseeEastmanProcess,
        *,
        objective: Callable[[AdvanceResult], float] | None = None,
    ) -> None:
        self.simulator = simulator
        self.objective = objective or self._default_objective

    def rollout(self, actions: ArrayLike, *, control_interval: float) -> RolloutResult:
        action_matrix = np.asarray(actions, dtype=np.float64)
        if action_matrix.ndim != 2 or action_matrix.shape[1] != 12:
            raise ValueError("actions must have shape (horizon, 12).")
        snapshot = self.simulator.snapshot()
        results: list[AdvanceResult] = []
        objective = 0.0
        try:
            for action in action_matrix:
                result = self.simulator.advance(action, control_interval=control_interval)
                results.append(result)
                objective += float(self.objective(result))
                if result.shutdown_status["terminated"]:
                    break
        finally:
            self.simulator.restore(snapshot)
        return RolloutResult(tuple(results), objective=objective, terminated=bool(results and results[-1].shutdown_status["terminated"]))

    def finite_difference_gradient(
        self,
        actions: ArrayLike,
        *,
        control_interval: float,
        epsilon: float = 1e-4,
    ) -> np.ndarray:
        base = np.asarray(actions, dtype=np.float64)
        gradient = np.zeros_like(base)
        for index in np.ndindex(base.shape):
            plus = base.copy()
            minus = base.copy()
            plus[index] += epsilon
            minus[index] -= epsilon
            f_plus = self.rollout(plus, control_interval=control_interval).objective
            f_minus = self.rollout(minus, control_interval=control_interval).objective
            gradient[index] = (f_plus - f_minus) / (2.0 * epsilon)
        return gradient

    def linearize(
        self,
        state0: ArrayLike,
        action0: ArrayLike,
        *,
        control_interval: float,
        epsilon: float = 1e-5,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Discrete-time linear state-space model around an operating point.

        Central-differences the one-step map ``x_{k+1} = advance(x_k, u_k)`` over a
        single ``control_interval`` (hours) to return ``(A, B)`` such that::

            x_{k+1} - x* ≈ A (x_k - x*) + B (u_k - u*)

        where ``x`` is the 50-element state and ``u`` the 12 manipulated variables, so
        ``A`` is ``(50, 50)`` and ``B`` is ``(50, 12)``. This is the *discrete-time*
        model; for a small interval the continuous Jacobian is
        ``A_continuous ≈ (A - I) / control_interval``.

        Use it for offline local analysis — eigenvalues/poles, controllability,
        LQR/pole-placement design. Accuracy is limited by the simulator's solver
        tolerances (``rtol``/``atol``); for a clean Jacobian wrap a tight-tolerance
        :class:`~tep_studio.TennesseeEastmanProcess`. Perturbations are scaled
        relative to each coordinate, ``h = epsilon * max(1, |value|)``. The simulator
        is restored to ``state0`` on return; this does not give a controller access to
        the true model (it is an analysis tool, not a control input).
        """
        x0 = np.asarray(state0, dtype=np.float64)
        u0 = np.asarray(action0, dtype=np.float64)
        if x0.shape != (50,):
            raise ValueError(f"state0 must have shape (50,), got {x0.shape}.")
        if u0.shape != (12,):
            raise ValueError(f"action0 must have shape (12,), got {u0.shape}.")

        base = self.simulator.snapshot()

        def next_state(state: np.ndarray, action: np.ndarray) -> np.ndarray:
            self.simulator.restore(base)
            self.simulator.state = np.ascontiguousarray(state, dtype=np.float64)
            self.simulator.kernel.state = self.simulator.state.copy()
            result = self.simulator.advance(action, control_interval=control_interval)
            return result.state

        try:
            a_matrix = np.zeros((50, 50), dtype=np.float64)
            for j in range(50):
                h = epsilon * max(1.0, abs(float(x0[j])))
                plus = x0.copy()
                minus = x0.copy()
                plus[j] += h
                minus[j] -= h
                a_matrix[:, j] = (next_state(plus, u0) - next_state(minus, u0)) / (2.0 * h)

            b_matrix = np.zeros((50, 12), dtype=np.float64)
            for j in range(12):
                h = epsilon * max(1.0, abs(float(u0[j])))
                plus = u0.copy()
                minus = u0.copy()
                plus[j] += h
                minus[j] -= h
                b_matrix[:, j] = (next_state(x0, plus) - next_state(x0, minus)) / (2.0 * h)
        finally:
            self.simulator.restore(base)
        return a_matrix, b_matrix

    @staticmethod
    def _default_objective(result: AdvanceResult) -> float:
        return float(result.objective_terms["production_cost_internal_per_hour"]) * result.control_interval
