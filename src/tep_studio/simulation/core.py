from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike
from scipy.integrate import solve_ivp

from tep_studio.simulation.native import NativeSnapshot, NativeTEPKernel
from tep_studio.simulation.schema import TEP_SCHEMA, ProcessSchema

# Integrators handled by an in-process fixed-step loop (no SciPy); any other method is
# delegated to scipy.integrate.solve_ivp (adaptive).
_FIXED_STEP_METHODS = frozenset({"RK4", "Euler"})


@dataclass(frozen=True)
class AdvanceResult:
    time: float
    time_start: float
    time_end: float
    control_interval: float
    state: np.ndarray
    measurements: np.ndarray
    additional_measurements: np.ndarray
    disturbance_monitors: np.ndarray
    process_monitors: np.ndarray
    concentration_monitors: np.ndarray
    requested_action: np.ndarray
    implemented_action: np.ndarray
    disturbances: np.ndarray
    constraint_margins: dict[str, float]
    events: tuple[dict[str, Any], ...]
    shutdown_status: dict[str, Any]
    solver_stats: dict[str, Any]
    objective_terms: dict[str, float]


class TennesseeEastmanProcess:
    """Schema-driven Python interface around the modified TEP process kernel."""

    def __init__(
        self,
        *,
        schema: ProcessSchema = TEP_SCHEMA,
        ms_flag: int = 0x0F,
        solver_method: str = "RK4",
        rtol: float = 1e-6,
        atol: float = 1e-8,
        fixed_step: float = 0.0005,
    ) -> None:
        self.schema = schema
        self.ms_flag = ms_flag
        # The default integrator is fixed-step RK4 at `fixed_step` hours — ~8x faster than
        # the adaptive SciPy solvers and faithful to the stiff model's 0.0005 h design step.
        # rtol/atol apply only to SciPy methods ("RK45"/"RK23"/...); they are inert for the
        # fixed-step methods ("RK4"/"Euler").
        self.solver_method = solver_method
        self.rtol = rtol
        self.atol = atol
        self.fixed_step = float(fixed_step)
        self.kernel = NativeTEPKernel()
        self.state = np.zeros(50, dtype=np.float64)
        self.time = 0.0
        self._last_result: AdvanceResult | None = None

    def reset(
        self,
        *,
        mode: str = "mode1",
        initial_state: ArrayLike | None = None,
        seed: float | None = None,
        disturbances: ArrayLike | None = None,
        ms_flag: int | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """Initialise the plant and return ``(measurements, info)``.

        Args:
            mode: operating point ``"mode1"``..``"mode6"``; an unknown mode raises
                ``NotImplementedError``. Modes 3 and 6 (90/10) load a bundled
                operating-point state; the others start from the base case.
            initial_state: optional full 50-element state to start from (overrides the
                mode's default; defaults to the base steady state).
            seed: optional measurement-noise seed for reproducibility.
            disturbances: optional 28-element IDV activation vector (defaults to none).
            ms_flag: measurement/feature bitmask forwarded to the kernel.

        Returns:
            ``measurements`` — the 41 published measurements (names via
            :func:`tep_studio.list_measurements`) — and ``info``, a dict with ``time``
            (hours), ``constraint_margins``, ``shutdown_status``, ``objective_terms`` and
            the applied ``disturbances``.
        """
        valid_modes = ("mode1", "mode2", "mode3", "mode4", "mode5", "mode6")
        if mode not in valid_modes:
            raise NotImplementedError(f"Unknown mode {mode!r}; expected one of {valid_modes} or an explicit initial_state.")
        # Most modes start from the base steady state and are realised by the controller's
        # setpoints; the 90/10 modes (3, 6) start from a bundled operating-point state that
        # the base case cannot be steered to without tripping. An explicit initial_state wins.
        if initial_state is None:
            from tep_studio.simulation.modes import mode_initial_state

            initial_state = mode_initial_state(mode)
        if ms_flag is not None:
            self.ms_flag = int(ms_flag)
        self.state = self.kernel.reset(initial_state=initial_state, seed=seed, ms_flag=self.ms_flag)
        self.time = 0.0
        idv = np.zeros(28, dtype=np.float64) if disturbances is None else self._array(disturbances, 28)
        self.kernel.set_inputs(self.state[38:50], idv)
        outputs = self.kernel.outputs(self.time, self.state)
        info = self._info(outputs, requested_action=self.state[38:50], idv=idv, solver_stats={})
        return outputs["measurements"].copy(), info

    def advance(
        self,
        action: ArrayLike,
        *,
        control_interval: float,
        action_level: str = "direct_mv",
        disturbances: ArrayLike | None = None,
    ) -> AdvanceResult:
        """Integrate the plant forward by ``control_interval`` hours under ``action``.

        Args:
            action: the 12 manipulated variables (valve positions, agitator speed), each
                clamped to ``[0, 100]`` before use (names via
                :func:`tep_studio.list_manipulated_variables`).
            control_interval: integration horizon for this step, in **hours**; the kernel
                ODEs are integrated with the configured ``solver_method`` (default
                fixed-step ``"RK4"``; ``"RK45"``/``"RK23"`` use adaptive SciPy stepping).
            action_level: only ``"direct_mv"`` (direct valve authority) is implemented.
            disturbances: optional 28-element IDV vector; if omitted the previous IDV
                setting is held.

        Returns:
            An :class:`AdvanceResult` with the new ``measurements`` and ``state``, the
            ``requested``/``implemented`` action, ``constraint_margins``, ``events``,
            ``shutdown_status`` (whose ``terminated`` flag flips on a plant trip),
            ``solver_stats`` and ``objective_terms``.
        """
        if action_level != "direct_mv":
            raise NotImplementedError("Only direct manipulated-variable authority (action_level='direct_mv') is supported.")
        requested_action = self._array(action, 12)
        implemented_action = np.clip(requested_action, 0.0, 100.0)
        idv = self.kernel.idv if disturbances is None else self._array(disturbances, 28)
        self.kernel.set_inputs(implemented_action, idv)

        start = self.time
        interval = float(control_interval)
        end = start + interval
        native_snapshot = self.kernel.snapshot()

        if self.solver_method in _FIXED_STEP_METHODS:
            new_state, n_substeps = self._integrate_fixed(start, end)
            if not np.isfinite(new_state).all():
                self.kernel.restore(native_snapshot)
                raise RuntimeError(
                    f"Fixed-step {self.solver_method} integration diverged "
                    f"(control_interval={interval}, fixed_step={self.fixed_step}); "
                    "reduce fixed_step or use an adaptive solver_method (e.g. 'RK45')."
                )
            solver_stats = {
                "method": self.solver_method,
                "success": True,
                "message": f"fixed-step {self.solver_method} (h={self.fixed_step})",
                "nfev": n_substeps * (4 if self.solver_method == "RK4" else 1),
                "njev": None,
                "nlu": None,
            }
        else:
            def rhs(t: float, y: np.ndarray) -> np.ndarray:
                return self.kernel.derivatives(t, y)

            solution = solve_ivp(
                rhs,
                (start, end),
                self.state,
                method=self.solver_method,
                rtol=self.rtol,
                atol=self.atol,
            )
            if not solution.success:
                self.kernel.restore(native_snapshot)
                raise RuntimeError(f"TEP integration failed: {solution.message}")
            new_state = np.ascontiguousarray(solution.y[:, -1], dtype=np.float64)
            solver_stats = {
                "method": self.solver_method,
                "success": bool(solution.success),
                "message": solution.message,
                "nfev": int(solution.nfev),
                "njev": None if solution.njev is None else int(solution.njev),
                "nlu": None if solution.nlu is None else int(solution.nlu),
            }

        self.state = new_state
        self.time = end
        self.kernel.state = self.state.copy()
        self.kernel.time = self.time
        outputs = self.kernel.outputs(self.time, self.state)

        shutdown_code, shutdown_message = self.kernel.shutdown_status()
        events = self._events(shutdown_code, shutdown_message)
        result = AdvanceResult(
            time=self.time,
            time_start=start,
            time_end=self.time,
            control_interval=interval,
            state=self.state.copy(),
            measurements=outputs["measurements"].copy(),
            additional_measurements=outputs["additional_measurements"].copy(),
            disturbance_monitors=outputs["disturbance_monitors"].copy(),
            process_monitors=outputs["process_monitors"].copy(),
            concentration_monitors=outputs["concentration_monitors"].copy(),
            requested_action=requested_action.copy(),
            implemented_action=implemented_action.copy(),
            disturbances=idv.copy(),
            constraint_margins=self._constraint_margins(outputs["measurements"]),
            events=events,
            shutdown_status={"code": shutdown_code, "message": shutdown_message, "terminated": shutdown_code != 0.0},
            solver_stats=solver_stats,
            objective_terms=self._objective_terms(outputs),
        )
        self._last_result = result
        return result

    def _integrate_fixed(self, start: float, end: float) -> tuple[np.ndarray, int]:
        """Integrate the kernel ODEs from ``start`` to ``end`` with a fixed-step method.

        Returns ``(final_state, n_substeps)``. RK4 (4th order) is the default; Euler is
        available for parity with the legacy fixed-step reference. The substep is
        ``self.fixed_step`` h — the model is stiff near 0.0005 h, so coarser steps diverge
        (caught by the caller's finite-value guard).
        """
        n = max(1, int(round((end - start) / self.fixed_step)))
        h = (end - start) / n
        deriv = self.kernel.derivatives
        y = self.state
        t = start
        # A too-coarse step makes the stiff model overflow to inf/nan; suppress the
        # intermediate FP warnings — the caller's finite-value guard reports it cleanly.
        with np.errstate(over="ignore", invalid="ignore"):
            if self.solver_method == "Euler":
                for _ in range(n):
                    y = y + h * deriv(t, y)
                    t += h
            else:  # RK4
                for _ in range(n):
                    k1 = deriv(t, y)
                    k2 = deriv(t + 0.5 * h, y + (0.5 * h) * k1)
                    k3 = deriv(t + 0.5 * h, y + (0.5 * h) * k2)
                    k4 = deriv(t + h, y + h * k3)
                    y = y + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
                    t += h
        return np.ascontiguousarray(y, dtype=np.float64), n

    def snapshot(self) -> NativeSnapshot:
        self.kernel.state = self.state.copy()
        self.kernel.time = self.time
        return self.kernel.snapshot()

    def restore(self, snapshot: NativeSnapshot) -> None:
        self.kernel.restore(snapshot)
        self.state = snapshot.state.copy()
        self.time = float(snapshot.time)

    def validate(self) -> dict[str, Any]:
        checks = {
            "state_count": len(self.schema.states) == 50,
            "mv_count": len(self.schema.manipulated_variables) == 12,
            "disturbance_count": len(self.schema.disturbances) == 28,
            "measurement_count": len(self.schema.measurements) == 41,
        }
        return {"ok": all(checks.values()), "checks": checks}

    def _info(
        self,
        outputs: dict[str, np.ndarray],
        *,
        requested_action: np.ndarray,
        idv: np.ndarray,
        solver_stats: dict[str, Any],
    ) -> dict[str, Any]:
        code, message = self.kernel.shutdown_status()
        return {
            "time": self.time,
            "schema": self.schema.name,
            "implemented_action": requested_action.copy(),
            "disturbances": idv.copy(),
            "constraint_margins": self._constraint_margins(outputs["measurements"]),
            "shutdown_status": {"code": code, "message": message, "terminated": code != 0.0},
            "solver_stats": solver_stats,
            "objective_terms": self._objective_terms(outputs),
        }

    @staticmethod
    def _constraint_margins(measurements: np.ndarray) -> dict[str, float]:
        return {
            "reactor_pressure_high": 3000.0 - float(measurements[6]),
            "reactor_level_high": 100.0 - float(measurements[7]),
            "reactor_level_low": float(measurements[7]),
            "reactor_temperature_high": 175.0 - float(measurements[8]),
            "separator_level_high": 100.0 - float(measurements[11]),
            "separator_level_low": float(measurements[11]),
            "stripper_level_high": 100.0 - float(measurements[14]),
            "stripper_level_low": float(measurements[14]),
        }

    @staticmethod
    def _events(code: float, message: str) -> tuple[dict[str, Any], ...]:
        if code == 0.0:
            return ()
        return ({"type": "shutdown", "code": code, "message": message},)

    @staticmethod
    def _objective_terms(outputs: dict[str, np.ndarray]) -> dict[str, float]:
        monitors = outputs["process_monitors"]
        production_cost_measured_per_hour = float(monitors[60]) if monitors.size > 60 else 0.0
        production_cost_internal_per_hour = float(monitors[61]) if monitors.size > 61 else 0.0
        return {
            "production_cost_measured_per_product": float(monitors[58]) if monitors.size > 58 else 0.0,
            "production_cost_internal_per_product": float(monitors[59]) if monitors.size > 59 else 0.0,
            "production_cost_measured_per_hour": production_cost_measured_per_hour,
            "production_cost_internal_per_hour": production_cost_internal_per_hour,
            "operating_cost_measured_per_hour": production_cost_measured_per_hour,
            "operating_cost_internal_per_hour": production_cost_internal_per_hour,
        }

    @staticmethod
    def _array(values: ArrayLike, length: int) -> np.ndarray:
        array = np.asarray(values, dtype=np.float64)
        if array.shape != (length,):
            raise ValueError(f"Expected shape ({length},), got {array.shape}.")
        return np.ascontiguousarray(array, dtype=np.float64)
