from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("gymnasium")

from tep_studio.simulation import rl
from tep_studio.simulation.gym_env import GymTEPEnv
from tep_studio.ui.config import ScenarioConfig
from tep_studio.ui.service import run_scenario


def _step_reward(reward_fn):
    env = GymTEPEnv(control_interval=0.05, horizon=0.5, reward_fn=reward_fn)
    env.reset(seed=0)
    _, reward, _, _, _ = env.step(np.full(12, 50.0))
    return reward


def test_reward_presets_are_deterministic() -> None:
    for factory in (rl.economic_reward, rl.safety_reward):
        assert _step_reward(factory()) == _step_reward(factory())
    tracking = rl.tracking_reward({"production_rate": 22.9, "pct_g": 53.8})
    assert _step_reward(tracking) == _step_reward(rl.tracking_reward({"production_rate": 22.9, "pct_g": 53.8}))


def test_weighted_reward_combines() -> None:
    combo = rl.weighted_reward((rl.economic_reward(), 1.0), (rl.safety_reward(), 0.0))
    assert _step_reward(combo) == _step_reward(rl.economic_reward())


def test_setpoint_level_env_steps_and_respects_bounds() -> None:
    env = GymTEPEnv(control_interval=0.05, horizon=0.5, action_level="setpoint", setpoint_fields=("production_rate", "pct_g"))
    assert env.action_space.shape == (2,)
    obs, _ = env.reset(seed=0)
    obs2, reward, terminated, truncated, info = env.step(np.array([23.0, 53.0]))
    assert obs2.shape == (41,)
    mv = info["implemented_action"]
    assert np.all(mv >= 0.0) and np.all(mv <= 100.0)


def test_vector_env_matches_sequential() -> None:
    import gymnasium as gym

    vec = rl.make_vec_env(2, control_interval=0.05, horizon=0.5)
    assert isinstance(vec, gym.vector.SyncVectorEnv)
    vec.reset(seed=0)
    action = np.full((2, 12), 50.0)
    obs, reward, term, trunc, info = vec.step(action)
    assert obs.shape == (2, 41) and reward.shape == (2,)

    single = GymTEPEnv(control_interval=0.05, horizon=0.5)
    single.reset(seed=0)
    obs_s, reward_s, _, _, _ = single.step(np.full(12, 50.0))
    np.testing.assert_allclose(obs[0], obs_s, rtol=1e-6)


def test_to_transitions_shapes_and_alignment() -> None:
    run = run_scenario(ScenarioConfig(horizon=1.0, control_interval=0.01))
    transitions = rl.to_transitions(run)
    n = transitions["obs"].shape[0]
    assert transitions["obs"].shape == (n, 41)
    assert transitions["action"].shape == (n, 12)
    assert transitions["next_obs"].shape == (n, 41)
    assert transitions["reward"].shape == (n,)
    assert transitions["terminated"].shape == (n,)
    assert n >= 1
