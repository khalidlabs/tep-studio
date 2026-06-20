"""Offline analysis helpers — step tests, scenarios, and dataset export (Dash-free).

A small, discoverable façade over the simulation-studio backend so control
theorists and process engineers can script step tests and build datasets without
running the web UI. Importing this module does **not** pull in Dash::

    from tep_studio.analysis import run_mv_step_test, ScenarioConfig, StepTestSpec

    cfg = ScenarioConfig(horizon=6.0, control_interval=0.01)
    spec = StepTestSpec(kind="mv", target="d_feed_valve", baseline=63.0,
                        step_value=66.0, step_time=1.0)
    result = run_mv_step_test(cfg, spec)
    frame = result.to_frame()           # tidy pandas DataFrame of the response

For closed-loop setpoint steps use :func:`run_setpoint_step_test`; for general
open/closed runs use :func:`run_scenario`; export one or more runs with
:func:`build_dataset`, and sweep with :func:`run_batch` / :class:`BatchSpec`.
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
]
