"""Closed-loop performance metrics, accumulated at full resolution.

The accumulator is fed every control step (regardless of trajectory downsampling)
so IAE/ISE, constraint-violation counts, production, and operating cost are exact
rather than sampled. Regulatory performance -- the CPI's primary concern -- is
emphasised: integral errors on the controlled variables plus a count of constraint
violations and the time to any shutdown.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tep_studio.simulation.core import AdvanceResult
from tep_studio.simulation.schema import TEP_SCHEMA

# Controlled variables tracked for IAE/ISE: (label, measurement index, setpoint attribute).
_CV_SPECS = (
    ("reactor_level", 7, "reactor_level"),
    ("reactor_pressure", 6, "reactor_pressure"),
    ("reactor_temperature", 8, "reactor_temperature"),
    ("separator_level", 11, "separator_level"),
    ("stripper_level", 14, "stripper_level"),
    ("production_rate", 16, "production_rate"),
)


@dataclass
class MetricsAccumulator:
    """Integrates regulatory error and constraint metrics over a closed-loop run."""

    setpoints: object  # ControllerSetpoints
    iae: dict[str, float] = field(default_factory=dict)
    ise: dict[str, float] = field(default_factory=dict)
    _elapsed: float = 0.0
    _production_time: float = 0.0
    _operating_cost: float = 0.0
    constraint_violation_steps: int = 0
    constraint_violation_time_h: float = 0.0
    constraint_min_margins: dict[str, float] = field(default_factory=dict)
    measurement_min: dict[str, float] = field(default_factory=dict)
    measurement_max: dict[str, float] = field(default_factory=dict)
    time_to_shutdown: float | None = None

    def __post_init__(self) -> None:
        self.iae = {label: 0.0 for label, _, _ in _CV_SPECS}
        self.ise = {label: 0.0 for label, _, _ in _CV_SPECS}
        self.constraint_min_margins = {constraint.name: float("inf") for constraint in TEP_SCHEMA.constraints}
        self.measurement_min = {name: float("inf") for name in TEP_SCHEMA.names("measurements")}
        self.measurement_max = {name: float("-inf") for name in TEP_SCHEMA.names("measurements")}

    def update(self, result: AdvanceResult) -> None:
        dt = result.control_interval
        meas = result.measurements
        for label, idx, sp_attr in _CV_SPECS:
            error = float(meas[idx]) - float(getattr(self.setpoints, sp_attr))
            self.iae[label] += abs(error) * dt
            self.ise[label] += error * error * dt
        for name, margin in result.constraint_margins.items():
            self.constraint_min_margins[name] = min(self.constraint_min_margins[name], float(margin))
        if any(margin < 0.0 for margin in result.constraint_margins.values()):
            self.constraint_violation_steps += 1
            self.constraint_violation_time_h += dt
        for name, value in zip(TEP_SCHEMA.names("measurements"), meas):
            numeric = float(value)
            self.measurement_min[name] = min(self.measurement_min[name], numeric)
            self.measurement_max[name] = max(self.measurement_max[name], numeric)
        self._operating_cost += float(result.objective_terms.get("operating_cost_internal_per_hour", 0.0)) * dt
        self._production_time += float(meas[16]) * dt
        self._elapsed += dt
        if self.time_to_shutdown is None and result.shutdown_status["terminated"]:
            self.time_to_shutdown = result.time

    def finalize(self) -> dict[str, float | None | dict[str, float]]:
        production_mean = self._production_time / self._elapsed if self._elapsed > 0 else 0.0
        return {
            "iae": dict(self.iae),
            "ise": dict(self.ise),
            "constraint_violation_steps": self.constraint_violation_steps,
            "constraint_violation_time_h": self.constraint_violation_time_h,
            "constraint_min_margins": dict(self.constraint_min_margins),
            "measurement_min": dict(self.measurement_min),
            "measurement_max": dict(self.measurement_max),
            "time_to_shutdown": self.time_to_shutdown,
            "operating_cost_total": self._operating_cost,
            "production_rate_mean": production_mean,
            "elapsed_hours": self._elapsed,
        }
