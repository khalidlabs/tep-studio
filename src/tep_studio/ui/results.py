"""Compact, serializable per-run artifacts.

A ``RunResult`` holds a *downsampled* tidy frame (as records) plus full-resolution
metrics -- never the raw ``AdvanceResult`` stream -- so it is cheap to cache
server-side and to ship to the browser. This module is Dash-free.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from tep_studio.ui.config import ScenarioConfig


@dataclass(frozen=True)
class RunResult:
    run_id: str
    scenario: ScenarioConfig
    frame_records: list[dict]  # downsampled tidy frame (TrajectoryDataset.to_pandas() rows)
    columns: list[str]
    metrics: dict  # full-resolution IAE/ISE/violations/cost
    peak: dict  # constraint extremes over the full run
    terminated: bool
    truncated: bool
    final_time: float
    n_steps: int
    shutdown: dict | None  # last shutdown_status if terminated
    record: dict | None  # parsed ExperimentRecord JSON (closed loop only)
    created_at: str

    def to_frame(self):
        import pandas as pd

        return pd.DataFrame(self.frame_records, columns=self.columns)

    def summary(self) -> dict:
        """A small, JSON-safe dict for the session store / Compare table."""
        metrics = self.metrics if isinstance(self.metrics, dict) else {}
        iae = metrics.get("iae", {})
        ise = metrics.get("ise", {})
        return {
            "run_id": self.run_id,
            "name": self.scenario.name,
            "loop_type": self.scenario.loop_type,
            "horizon": self.scenario.horizon,
            "terminated": self.terminated,
            "final_time": round(self.final_time, 3),
            "peak_reactor_pressure": _round(self.peak.get("reactor_pressure_max")),
            "iae_reactor_pressure": _round(iae.get("reactor_pressure"), 3),
            "ise_reactor_pressure": _round(ise.get("reactor_pressure"), 3),
            "time_to_shutdown": _round(metrics.get("time_to_shutdown"), 3),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class BatchResult:
    batch_id: str
    label: str
    run_ids: tuple[str, ...]
    per_run_metrics: list[dict]  # one row per run: scenario knobs + scalar metrics


def _round(value, ndigits: int = 1):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), ndigits)
