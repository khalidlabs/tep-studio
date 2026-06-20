"""Reinforcement learning on the Tennessee Eastman environment.

The environment registers itself on ``import tep_studio``, so
``gymnasium.make("TennesseeEastman-v0")`` works out of the box. This script always
runs a dependency-free random-policy rollout and, if stable-baselines3 is installed,
also trains a small PPO agent with a custom (shaped) reward.

Optional trainer:  pip install stable-baselines3
Usage:
    PYTHONPATH=src python3 src/tep_studio/simulation/examples/rl_training.py
"""

from __future__ import annotations

import gymnasium

import tep_studio  # noqa: F401  -- importing registers "TennesseeEastman-v0"


def keep_pressure_low(result) -> float:
    """Example shaped reward: stay off the 3000 kPa pressure trip, cheaply.

    Receives the full :class:`~tep_studio.AdvanceResult`, so any measurement,
    constraint margin, or objective term is fair game for reward engineering.
    """
    pressure = float(result.measurements[6])  # reactor_pressure
    cost_rate = float(result.objective_terms["production_cost_internal_per_hour"])
    pressure_margin = (3000.0 - pressure) / 3000.0
    return pressure_margin - 0.01 * cost_rate * result.control_interval


def random_rollout() -> None:
    env = gymnasium.make("TennesseeEastman-v0", horizon=4.0, control_interval=0.05)
    _, info = env.reset(seed=0)
    total, terminated, truncated = 0.0, False, False
    while not (terminated or truncated):
        _, reward, terminated, truncated, info = env.step(env.action_space.sample())
        total += reward
    print(f"random rollout: return={total:.2f} terminated={terminated} truncated={truncated} t={info['time']:.2f} h")


def train_ppo() -> None:
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.env_util import make_vec_env
    except ImportError:
        print("stable-baselines3 not installed; skipping PPO (pip install stable-baselines3).")
        return
    env = make_vec_env(
        "TennesseeEastman-v0",
        n_envs=1,
        env_kwargs={"horizon": 4.0, "control_interval": 0.05, "reward_fn": keep_pressure_low},
    )
    model = PPO("MlpPolicy", env, n_steps=128, verbose=0)
    model.learn(total_timesteps=256)
    print("PPO: trained 256 timesteps (demo only — raise total_timesteps for real runs).")


def main() -> None:
    random_rollout()
    train_ppo()


if __name__ == "__main__":
    main()
