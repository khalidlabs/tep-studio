from __future__ import annotations

import pytest

from tep_studio.ui.config import (
    BatchSpec,
    DisturbanceActivation,
    ScenarioConfig,
    StepTestSpec,
)


def test_default_roundtrip() -> None:
    cfg = ScenarioConfig()
    assert ScenarioConfig.from_json(cfg.to_json()) == cfg


def test_full_roundtrip() -> None:
    cfg = ScenarioConfig(
        name="demo",
        loop_type="closed",
        horizon=8.0,
        control_interval=0.001,
        seed=1431655765.0,
        disturbances=(DisturbanceActivation("idv_08", 1.0, 1.0), DisturbanceActivation("idv_13")),
        setpoints={"reactor_pressure": 2700.0, "production_rate": 28.0},
        enable_overrides=True,
        step_test=StepTestSpec("setpoint", "reactor_level", 75.0, 70.0, 2.0),
    )
    assert ScenarioConfig.from_json(cfg.to_json()) == cfg


def test_resolved_record_every() -> None:
    assert ScenarioConfig(control_interval=0.01).resolved_record_every() == 5
    assert ScenarioConfig(control_interval=0.0005).resolved_record_every() == 100
    assert ScenarioConfig(control_interval=0.01, record_every=3).resolved_record_every() == 3


@pytest.mark.parametrize(
    "patch",
    [
        {"loop_type": "sideways"},
        {"mode": "mode7"},
        {"horizon": 0.0},
        {"disturbances": [{"idv": "idv_99"}]},
        {"disturbances": [{"idv": "idv_01", "magnitude": 5.0}]},
        {"setpoints": {"not_a_field": 1.0}},
        {"manual_mvs": {"not_a_valve": 50.0}},
        {"manual_mvs": {"purge_valve": 150.0}},
        {"step_test": {"kind": "mv", "target": "reactor_pressure", "baseline": 0, "step_value": 1, "step_time": 1}},
    ],
)
def test_from_dict_rejects_invalid(patch: dict) -> None:
    base = ScenarioConfig().to_dict()
    base.update(patch)
    with pytest.raises(ValueError):
        ScenarioConfig.from_dict(base)


def test_batch_expand_counts_and_roundtrip() -> None:
    base = ScenarioConfig(loop_type="closed", horizon=1.0)
    spec = BatchSpec(
        base=base,
        seeds=(1.0, 2.0),
        disturbance_grid=((), (DisturbanceActivation("idv_01"),)),
        param_grid={"setpoints.production_rate": (22.0, 28.0)},
        label="sweep",
    )
    configs = spec.expand()
    assert len(configs) == 2 * 2 * 2  # seeds x disturbance sets x param values
    assert all(c.setpoints and "production_rate" in c.setpoints for c in configs)
    assert {c.seed for c in configs} == {1.0, 2.0}
    # round-trip
    assert BatchSpec.from_dict(spec.to_dict()).expand() == configs
