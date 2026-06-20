"""User-friendly Dash + Plotly interface for the TEP simulator (optional ``ui`` extra).

The backend (`config`, `service`, `figures`, `results`, `store`) is Dash-free and
importable without the ``ui`` extra; only :func:`create_app` (and `app`/`callbacks`)
import Dash, and they do so lazily. This keeps ``import tep_studio`` working for
users who have not installed the UI dependencies.
"""

from __future__ import annotations

from tep_studio.ui.config import (
    BatchSpec,
    DisturbanceActivation,
    ScenarioConfig,
    StepTestSpec,
)
from tep_studio.ui.results import BatchResult, RunResult
from tep_studio.ui.service import (
    build_dataset,
    run_batch,
    run_mv_step_test,
    run_scenario,
    run_setpoint_step_test,
)


def create_app(*args, **kwargs):
    """Build the Dash application. Imports Dash only when called."""
    from tep_studio.ui.app import create_app as _factory

    return _factory(*args, **kwargs)


__all__ = [
    "ScenarioConfig",
    "StepTestSpec",
    "DisturbanceActivation",
    "BatchSpec",
    "RunResult",
    "BatchResult",
    "run_scenario",
    "run_mv_step_test",
    "run_setpoint_step_test",
    "build_dataset",
    "run_batch",
    "create_app",
]
