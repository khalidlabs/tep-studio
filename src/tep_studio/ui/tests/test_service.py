from __future__ import annotations

import io

import pandas as pd
import pytest

from tep_studio.ui import service
from tep_studio.ui.config import (
    BatchSpec,
    DisturbanceActivation,
    ScenarioConfig,
    StepTestSpec,
)


def test_run_closed_scenario_tiny() -> None:
    cfg = ScenarioConfig(loop_type="closed", horizon=0.5, control_interval=0.01)
    run = service.run_scenario(cfg)
    assert run.truncated and not run.terminated
    assert "measurement.reactor_pressure" in run.columns
    assert len(run.frame_records) > 0
    assert isinstance(run.metrics["iae"]["reactor_pressure"], float)
    assert run.record["process_description_hash"].startswith("sha256:")


def test_run_open_scenario_tiny() -> None:
    cfg = ScenarioConfig(loop_type="open", horizon=0.5, control_interval=0.01)
    run = service.run_scenario(cfg)
    assert not run.terminated  # 0.5 h is well before the ~3.2 h open-loop trip
    assert len(run.frame_records) > 0
    assert "iae" in run.metrics


def test_mv_step_test_changes_the_stepped_valve() -> None:
    cfg = ScenarioConfig(horizon=0.5, control_interval=0.01)
    spec = StepTestSpec(kind="mv", target="d_feed_valve", baseline=63.053, step_value=70.0, step_time=0.2)
    run = service.run_mv_step_test(cfg, spec)
    frame = run.to_frame()
    col = "implemented_action.d_feed_valve"
    assert frame[col].min() == pytest.approx(63.053, abs=0.5)
    assert frame[col].max() == pytest.approx(70.0, abs=0.5)


def test_setpoint_step_test_runs_closed_loop() -> None:
    cfg = ScenarioConfig(horizon=0.5, control_interval=0.01)
    spec = StepTestSpec(kind="setpoint", target="reactor_level", baseline=75.0, step_value=70.0, step_time=0.2)
    run = service.run_setpoint_step_test(cfg, spec)
    assert run.scenario.loop_type == "closed"
    assert len(run.frame_records) > 0


def test_batch_and_dataset_export() -> None:
    base = ScenarioConfig(loop_type="closed", horizon=0.3, control_interval=0.01)
    spec = BatchSpec(base=base, seeds=(1.0, 2.0), disturbance_grid=((), (DisturbanceActivation("idv_01"),)))
    batch, runs = service.run_batch(spec)
    assert len(runs) == 4
    assert len(batch.per_run_metrics) == 4

    payload, filename = service.build_dataset(runs, fmt="csv")
    assert filename.endswith(".csv")
    frame = pd.read_csv(io.BytesIO(payload))
    assert frame["run_id"].nunique() == 4
    # combined rows == sum of per-run rows
    assert len(frame) == sum(len(r.frame_records) for r in runs)


def test_run_batch_parallel_matches_sequential() -> None:
    # Parallel dataset generation must reproduce the sequential result, in config order.
    base = ScenarioConfig(loop_type="closed", horizon=0.3, control_interval=0.05)
    spec = BatchSpec(base=base, seeds=(1.0, 2.0, 3.0))
    _, seq = service.run_batch(spec, max_workers=1)
    _, par = service.run_batch(spec, max_workers=2)
    assert len(par) == len(seq) == 3
    for sequential_run, parallel_run in zip(seq, par):
        assert sequential_run.scenario.seed == parallel_run.scenario.seed
        assert sequential_run.final_time == parallel_run.final_time
        assert sequential_run.peak["reactor_pressure_max"] == parallel_run.peak["reactor_pressure_max"]


def test_determinism_with_fixed_seed() -> None:
    cfg = ScenarioConfig(loop_type="closed", horizon=0.4, control_interval=0.01, seed=1431655765.0)
    a = service.run_scenario(cfg)
    b = service.run_scenario(cfg)
    assert a.metrics["iae"]["reactor_pressure"] == b.metrics["iae"]["reactor_pressure"]
    assert a.peak == b.peak
