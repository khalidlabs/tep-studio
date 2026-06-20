"""Closed-loop runner: couples the decentralized controller to the simulator.

The loop is deliberately simple -- ``compute_action(measurements) -> advance(...)``
at a fixed control interval -- and records a named, time-aligned trajectory plus a
clean separation of endogenous *termination* (a plant shutdown) from exogenous
*truncation* (reaching the horizon), matching the schema's ``lifecycle`` split.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from numpy.typing import ArrayLike

from tep_studio.control.controller import (
    Controller,
    ControllerSetpoints,
    ControlStepDiagnostics,
    RickerMultiLoopController,
)
from tep_studio.control.metrics import MetricsAccumulator
from tep_studio.simulation.core import AdvanceResult, TennesseeEastmanProcess

DisturbanceSchedule = Callable[[float], ArrayLike]
SetpointSchedule = Callable[[float], ControllerSetpoints]


@dataclass(frozen=True)
class ClosedLoopResult:
    """Outcome of a closed-loop run."""

    results: tuple[AdvanceResult, ...]  # recorded steps (possibly downsampled)
    diagnostics: tuple[ControlStepDiagnostics, ...]
    terminated: bool  # endogenous: a plant shutdown occurred
    truncated: bool  # exogenous: the horizon was reached without shutdown
    n_steps: int
    final_time: float
    control_interval: float
    horizon: float
    peak: dict[str, float] = field(default_factory=dict)  # constraint extremes over the FULL run
    metrics: dict[str, object] = field(default_factory=dict)  # IAE/ISE/violations/cost over the FULL run

    @property
    def stabilized(self) -> bool:
        return self.truncated and not self.terminated


class ClosedLoopSimulation:
    """Run the Ricker decentralized controller against the TEP simulator."""

    def __init__(
        self,
        *,
        simulator: TennesseeEastmanProcess | None = None,
        controller: Controller | None = None,
        control_interval: float = 0.0005,
        horizon: float = 48.0,
    ) -> None:
        self.sim = simulator or TennesseeEastmanProcess()
        self.controller = controller or RickerMultiLoopController()
        self.control_interval = float(control_interval)
        self.horizon = float(horizon)

    def run(
        self,
        *,
        seed: float | None = None,
        disturbances: ArrayLike | None = None,
        disturbance_schedule: DisturbanceSchedule | None = None,
        setpoint_schedule: SetpointSchedule | None = None,
        record_every: int = 1,
    ) -> ClosedLoopResult:
        """Run the closed loop to ``horizon`` and return a :class:`ClosedLoopResult`.

        Args:
            seed: measurement-noise seed for a reproducible run.
            disturbances: a constant 28-element IDV vector applied for the whole run.
            disturbance_schedule: ``time(h) -> 28-element IDV vector`` for timed/latched
                disturbances (takes precedence over ``disturbances``).
            setpoint_schedule: ``time(h) -> ControllerSetpoints`` for setpoint changes /
                step tests; metrics stay referenced to the INITIAL setpoints.
            record_every: keep every Nth step in the returned trajectory (full-resolution
                metrics and peaks are accumulated regardless of this thinning).

        Returns:
            A :class:`ClosedLoopResult`; ``.stabilized`` is True when the horizon was
            reached without a plant shutdown.
        """
        meas, _ = self.sim.reset(mode="mode1", seed=seed)
        self.controller.reset(meas, time=self.sim.time)
        # Metrics are seeded from the INITIAL setpoints; for a setpoint step test that
        # means post-step IAE measures the excursion against the pre-step reference.
        metrics = MetricsAccumulator(setpoints=self.controller.setpoints)

        results: list[AdvanceResult] = []
        diagnostics: list[ControlStepDiagnostics] = []
        peak = {
            "reactor_pressure_max": float(meas[6]),
            "reactor_level_min": float(meas[7]),
            "reactor_level_max": float(meas[7]),
            "separator_level_min": float(meas[11]),
            "separator_level_max": float(meas[11]),
            "stripper_level_min": float(meas[14]),
            "stripper_level_max": float(meas[14]),
        }

        terminated = False
        step = 0
        eps = self.control_interval * 1e-6
        while self.sim.time < self.horizon - eps:
            if setpoint_schedule is not None:
                self.controller.setpoints = setpoint_schedule(self.sim.time)
            action, diag = self.controller.compute_action(meas, time=self.sim.time)
            idv = self._disturbances(self.sim.time, disturbances, disturbance_schedule)
            result = self.sim.advance(action, control_interval=self.control_interval, disturbances=idv)
            meas = result.measurements
            metrics.update(result)
            self._track_peak(peak, meas)
            if step % record_every == 0 or result.shutdown_status["terminated"]:
                results.append(result)
                diagnostics.append(diag)
            step += 1
            if result.shutdown_status["terminated"]:
                terminated = True
                break

        return ClosedLoopResult(
            results=tuple(results),
            diagnostics=tuple(diagnostics),
            terminated=terminated,
            truncated=not terminated,
            n_steps=step,
            final_time=self.sim.time,
            control_interval=self.control_interval,
            horizon=self.horizon,
            peak=peak,
            metrics=metrics.finalize(),
        )

    @staticmethod
    def _disturbances(
        time: float,
        static: ArrayLike | None,
        schedule: DisturbanceSchedule | None,
    ) -> np.ndarray | None:
        if schedule is not None:
            return np.asarray(schedule(time), dtype=np.float64)
        if static is not None:
            return np.asarray(static, dtype=np.float64)
        return None

    @staticmethod
    def _track_peak(peak: dict[str, float], meas: np.ndarray) -> None:
        peak["reactor_pressure_max"] = max(peak["reactor_pressure_max"], float(meas[6]))
        peak["reactor_level_min"] = min(peak["reactor_level_min"], float(meas[7]))
        peak["reactor_level_max"] = max(peak["reactor_level_max"], float(meas[7]))
        peak["separator_level_min"] = min(peak["separator_level_min"], float(meas[11]))
        peak["separator_level_max"] = max(peak["separator_level_max"], float(meas[11]))
        peak["stripper_level_min"] = min(peak["stripper_level_min"], float(meas[14]))
        peak["stripper_level_max"] = max(peak["stripper_level_max"], float(meas[14]))
