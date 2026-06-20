from __future__ import annotations

import plotly.graph_objects as go
import pytest

from tep_studio.ui import figures, service
from tep_studio.ui.config import ScenarioConfig, StepTestSpec
from tep_studio.ui.service import default_setpoints


@pytest.fixture(scope="module")
def closed_run():
    return service.run_scenario(ScenarioConfig(loop_type="closed", horizon=0.4, control_interval=0.01))


def test_trajectory_grid_traces_and_overlays(closed_run) -> None:
    variables = [
        "measurement.reactor_pressure",
        "measurement.reactor_level",
        "measurement.reactor_temperature",
        "measurement.separator_level",
    ]
    fig = figures.trajectory_grid(closed_run.to_frame(), variables, setpoints=default_setpoints(), show_limits=True)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 4
    assert len(fig.layout.shapes) > 0  # setpoint dotted + limit dashed lines


def test_trajectory_grid_shutdown_vline(closed_run) -> None:
    fig = figures.trajectory_grid(closed_run.to_frame(), ["measurement.reactor_pressure"], show_limits=False, shutdown_time=0.2)
    assert len(fig.layout.shapes) >= 1  # the shutdown vline


def test_mv_panel(closed_run) -> None:
    fig = figures.mv_panel(closed_run.to_frame(), ["d_feed_valve", "reactor_cooling_water_valve"])
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_compare_overlay() -> None:
    r1 = service.run_scenario(ScenarioConfig(name="a", horizon=0.3, control_interval=0.01))
    r2 = service.run_scenario(ScenarioConfig(name="b", horizon=0.3, control_interval=0.01))
    fig = figures.compare_overlay([r1, r2], "reactor_pressure")
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2


def test_default_figures_do_not_persist_axes(closed_run) -> None:
    # As the app calls them (no uirevision), the figures must not persist their axes,
    # so every run re-autoranges to its own data.
    frame = closed_run.to_frame()
    assert figures.trajectory_grid(frame, ["measurement.reactor_pressure"]).layout.uirevision is None
    assert figures.mv_panel(frame, ["d_feed_valve"]).layout.uirevision is None
    assert figures.compare_overlay([closed_run], "measurement.reactor_pressure").layout.uirevision is None


def test_step_response_two_panels() -> None:
    spec = StepTestSpec(kind="mv", target="d_feed_valve", baseline=63.053, step_value=70.0, step_time=0.2)
    run = service.run_mv_step_test(ScenarioConfig(horizon=0.4, control_interval=0.01), spec)
    fig = figures.step_response(run.to_frame(), "measurement.feed_D_flow", "implemented_action.d_feed_valve", 0.2)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 2
