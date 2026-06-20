from __future__ import annotations

import json

from tep_studio import TennesseeEastmanProcess
from tep_studio.control.config import config_hash, controller_config, process_description_hash
from tep_studio.control.controller import RickerMultiLoopController
from tep_studio.control.experiment import build_experiment_record
from tep_studio.control.runner import ClosedLoopSimulation


def _run(**controller_kwargs):
    sim = TennesseeEastmanProcess()
    ctl = RickerMultiLoopController(**controller_kwargs)
    runner = ClosedLoopSimulation(simulator=sim, controller=ctl, control_interval=0.0005, horizon=2.0)
    return runner.run(), ctl, sim


def test_metrics_are_populated_on_a_stable_run() -> None:
    result, _, _ = _run()
    metrics = result.metrics
    assert set(metrics["iae"]) >= {"reactor_pressure", "reactor_level", "production_rate"}
    assert metrics["time_to_shutdown"] is None  # stabilized
    assert metrics["constraint_violation_steps"] == 0
    assert metrics["production_rate_mean"] > 0.0


def test_termination_distinct_from_truncation_on_forced_shutdown() -> None:
    # The %G feedback (tuned for the original TEP) destabilizes the modified plant:
    # a clean way to exercise endogenous termination vs horizon truncation.
    result, _, _ = _run(enable_pct_g_feedback=True)
    assert result.terminated
    assert not result.truncated
    assert result.metrics["time_to_shutdown"] is not None


def test_experiment_record_round_trips_to_json() -> None:
    result, ctl, sim = _run()
    record = build_experiment_record(result, ctl, simulator=sim)
    payload = json.loads(record.to_json())  # must be strict, valid JSON
    assert payload["process_description_hash"].startswith("sha256:")
    assert payload["controller_config_hash"].startswith("sha256:")
    assert payload["action_authority"] == "direct_mv"
    assert payload["model_leakage_policy"]["controller_may_use_true_model"] is False
    assert payload["git_revision"]  # captured (revision or "unknown")
    assert "iae" in payload["metrics"]
    assert payload["truncated"] is True


def test_config_hash_is_sensitive_to_gains_and_flags() -> None:
    base = controller_config(RickerMultiLoopController())
    same = controller_config(RickerMultiLoopController())
    assert config_hash(base) == config_hash(same)
    changed = controller_config(RickerMultiLoopController(enable_overrides=True))
    assert config_hash(base) != config_hash(changed)


def test_process_description_hash_stable() -> None:
    assert process_description_hash() == process_description_hash()
    assert process_description_hash().startswith("sha256:")
