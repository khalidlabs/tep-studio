"""GymTEPEnv reward and render_mode: a custom reward_fn overrides the default cost reward."""

from __future__ import annotations

import numpy as np
import pytest

from tep_studio import GymTEPEnv


def _default_reward(result) -> float:
    return -float(result.objective_terms["production_cost_internal_per_hour"]) * result.control_interval


def test_default_reward_unchanged_when_reward_fn_none() -> None:
    action = np.full(12, 50.0)
    env_a = GymTEPEnv(control_interval=0.05)
    env_a.reset(seed=0)
    env_b = GymTEPEnv(control_interval=0.05, reward_fn=_default_reward)
    env_b.reset(seed=0)
    reward_a = env_a.step(action)[1]
    reward_b = env_b.step(action)[1]
    assert reward_a == pytest.approx(reward_b)


def test_custom_reward_overrides_default() -> None:
    env = GymTEPEnv(control_interval=0.05, reward_fn=lambda result: 7.0)
    env.reset(seed=0)
    assert env.step(np.full(12, 50.0))[1] == 7.0


def test_render_mode_accepted() -> None:
    env = GymTEPEnv(render_mode="human")
    assert env.render_mode == "human"
