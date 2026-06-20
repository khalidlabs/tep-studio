from __future__ import annotations

import numpy as np
import pytest

from tep_studio import GymTEPEnv, OptimizationAdapter, TEP_SCHEMA, TennesseeEastmanProcess, TrajectoryDataset


R12_ACTION = np.array(
    [63.53, 53.98, 24.644, 61.302, 22.21, 40.064, 38.1, 46.534, 47.446, 38.0, 18.114, 50.0],
    dtype=np.float64,
)


def test_schema_counts() -> None:
    assert len(TEP_SCHEMA.states) == 50
    assert len(TEP_SCHEMA.manipulated_variables) == 12
    assert len(TEP_SCHEMA.disturbances) == 28
    assert len(TEP_SCHEMA.measurements) == 41
    assert len(TEP_SCHEMA.additional_measurements) == 32
    assert len(TEP_SCHEMA.disturbance_monitors) == 21
    assert len(TEP_SCHEMA.process_monitors) == 62
    assert len(TEP_SCHEMA.concentration_monitors) == 96
    assert TEP_SCHEMA.measurements[22].name == "reactor_feed_A_concentration"
    assert TEP_SCHEMA.measurements[22].legacy_symbol == "XMEAS(23)"
    assert TEP_SCHEMA.measurements[40].name == "stripper_underflow_H_concentration"
    assert TEP_SCHEMA.process_monitors[60].name == "operating_cost_measured_per_hour"


def test_schema_named_lookup_helpers() -> None:
    assert TEP_SCHEMA.index("measurements", "reactor_pressure") == 6
    assert TEP_SCHEMA.index("measurement", "reactor_pressure") == 6
    assert TEP_SCHEMA.index("mvs", "reactor_cooling_water_valve") == 9
    assert TEP_SCHEMA.index("disturbance", "idv_01") == 0
    assert TEP_SCHEMA.variable("mv", "purge_valve").unit == "%"

    with pytest.raises(KeyError, match="Unknown measurements variable"):
        TEP_SCHEMA.index("measurements", "not_a_measurement")

    with pytest.raises(KeyError, match="Unknown schema role"):
        TEP_SCHEMA.names("not_a_role")


def test_schema_named_vector_helpers() -> None:
    action = TEP_SCHEMA.vector(
        "mvs",
        {
            "d_feed_valve": 63.053,
            "e_feed_valve": 53.98,
            "a_feed_valve": 24.644,
            "ac_feed_valve": 61.302,
            "compressor_recycle_valve": 22.21,
            "purge_valve": 40.064,
            "separator_underflow_valve": 38.10,
            "stripper_underflow_valve": 46.534,
            "stripper_steam_valve": 47.446,
            "reactor_cooling_water_valve": 41.106,
            "separator_cooling_water_valve": 18.114,
            "reactor_agitator_speed": 50.0,
        },
    )
    np.testing.assert_allclose(
        action,
        np.array([63.053, 53.98, 24.644, 61.302, 22.21, 40.064, 38.10, 46.534, 47.446, 41.106, 18.114, 50.0]),
    )

    updated = TEP_SCHEMA.update_vector("mvs", action, {"reactor_cooling_water_valve": 38.0})
    assert updated[TEP_SCHEMA.index("mvs", "reactor_cooling_water_valve")] == 38.0
    assert action[TEP_SCHEMA.index("mvs", "reactor_cooling_water_valve")] == 41.106

    measurement_dict = TEP_SCHEMA.to_dict("measurements", np.arange(41, dtype=np.float64))
    assert measurement_dict["feed_A_flow"] == 0.0
    assert measurement_dict["reactor_pressure"] == 6.0

    with pytest.raises(ValueError, match="Expected shape"):
        TEP_SCHEMA.vector("mvs", np.zeros(11))


def test_reset_and_advance_shapes() -> None:
    sim = TennesseeEastmanProcess()
    obs, info = sim.reset(seed=1431655765)
    assert obs.shape == (41,)
    assert info["shutdown_status"]["terminated"] is False

    result = sim.advance(R12_ACTION, control_interval=0.001)
    assert result.time_start == 0.0
    assert result.time_end == result.time
    assert result.control_interval == 0.001
    assert result.state.shape == (50,)
    assert result.measurements.shape == (41,)
    assert result.additional_measurements.shape == (32,)
    assert result.disturbance_monitors.shape == (21,)
    assert result.process_monitors.shape == (62,)
    assert result.concentration_monitors.shape == (96,)
    assert result.objective_terms["production_cost_internal_per_hour"] > 0.0
    assert result.objective_terms["operating_cost_internal_per_hour"] == result.objective_terms["production_cost_internal_per_hour"]
    assert result.solver_stats["success"] is True


def test_snapshot_restore_replay() -> None:
    sim = TennesseeEastmanProcess()
    sim.reset(seed=1431655765)
    snapshot = sim.snapshot()

    first = sim.advance(R12_ACTION, control_interval=0.001)
    sim.restore(snapshot)
    second = sim.advance(R12_ACTION, control_interval=0.001)

    np.testing.assert_allclose(first.state, second.state, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(first.measurements, second.measurements, rtol=0.0, atol=0.0)


def test_r12_shutdown_maps_to_termination() -> None:
    sim = TennesseeEastmanProcess()
    sim.reset(seed=1431655765)

    result = None
    while sim.time < 5.0:
        result = sim.advance(R12_ACTION, control_interval=0.01)
        if result.shutdown_status["terminated"]:
            break

    assert result is not None
    assert result.shutdown_status["terminated"] is True
    assert result.shutdown_status["code"] == 1.0
    assert "High Reactor Pressure" in result.shutdown_status["message"]
    assert 0.9 <= result.time <= 1.3


def test_dataset_and_optimization_adapter() -> None:
    sim = TennesseeEastmanProcess()
    sim.reset(seed=1431655765)
    result = sim.advance(R12_ACTION, control_interval=0.001)

    dataset = TrajectoryDataset.from_results([result])
    frame = dataset.to_pandas()
    matrix, columns = dataset.to_numpy("measurements")
    assert frame.shape[0] == 1
    assert {"time_start", "time_end", "control_interval", "terminated_at_end", "is_initial"} <= set(frame.columns)
    assert "objective.production_cost_internal_per_hour" in frame.columns
    assert frame.loc[0, "time"] == frame.loc[0, "time_end"]
    assert bool(frame.loc[0, "is_initial"]) is False
    assert matrix.shape == (1, 41)
    assert len(columns) == 41

    adapter = OptimizationAdapter(sim)
    rollout = adapter.rollout(np.tile(R12_ACTION, (2, 1)), control_interval=0.001)
    assert len(rollout.results) == 2
    assert np.isfinite(rollout.objective)
    expected_objective = sum(
        result.objective_terms["production_cost_internal_per_hour"] * result.control_interval for result in rollout.results
    )
    assert rollout.objective == expected_objective


def test_gym_api() -> None:
    env = GymTEPEnv(control_interval=0.001, horizon=0.01)
    obs, info = env.reset(seed=123)
    next_obs, reward, terminated, truncated, step_info = env.step(R12_ACTION)

    assert obs.shape == env.observation_space.shape
    assert next_obs.shape == env.observation_space.shape
    assert isinstance(reward, float)
    assert terminated is False
    assert truncated is False
    assert reward == -step_info["reward_terms"]["production_cost_interval"]
    assert "shutdown_status" in step_info
    assert "shutdown_status" in info
