"""Reinforcement-learning ergonomics for the TEP environment.

A small library of reward presets (pure functions of :class:`AdvanceResult`), a
vectorized-environment helper, and an offline-RL transition exporter. Builds on
:class:`~tep_studio.simulation.gym_env.GymTEPEnv` and ``TrajectoryDataset`` frames.
Dash-free.
"""

from __future__ import annotations

from typing import Callable, Iterable

import numpy as np

from tep_studio.simulation.core import AdvanceResult
from tep_studio.simulation.schema import TEP_SCHEMA

RewardFn = Callable[[AdvanceResult], float]

# ControllerSetpoints field -> measurement name (for tracking rewards).
_SETPOINT_TO_MEAS = {
    "reactor_pressure": "reactor_pressure",
    "reactor_level": "reactor_level",
    "reactor_temperature": "reactor_temperature",
    "separator_level": "separator_level",
    "stripper_level": "stripper_level",
    "production_rate": "stripper_underflow",
    "pct_g": "stripper_underflow_G_concentration",
}


# -- reward presets --------------------------------------------------------
def economic_reward() -> RewardFn:
    """Minimise operating cost (the default): ``-production_cost`` over the step."""

    def reward(result: AdvanceResult) -> float:
        return -float(result.objective_terms["production_cost_internal_per_hour"]) * result.control_interval

    return reward


def tracking_reward(targets: dict[str, float], *, weights: dict[str, float] | None = None) -> RewardFn:
    """Negative weighted squared error of controlled variables vs ``targets``.

    ``targets`` maps setpoint field names (e.g. ``production_rate``, ``pct_g``) to values.
    """
    indices = {field: TEP_SCHEMA.index("measurements", _SETPOINT_TO_MEAS[field]) for field in targets}
    weights = weights or {field: 1.0 for field in targets}

    def reward(result: AdvanceResult) -> float:
        total = 0.0
        for field, target in targets.items():
            error = float(result.measurements[indices[field]]) - float(target)
            total += float(weights.get(field, 1.0)) * error * error
        return -total

    return reward


def safety_reward(*, scale: float = 1.0) -> RewardFn:
    """Reward distance from the nearest hard constraint (penalises approaching limits)."""

    def reward(result: AdvanceResult) -> float:
        margins = result.constraint_margins
        return scale * float(min(margins.values())) if margins else 0.0

    return reward


def move_suppression_reward(*, weight: float = 1.0) -> RewardFn:
    """Penalise manipulated-variable movement between steps (stateful closure)."""
    previous: dict[str, np.ndarray] = {}

    def reward(result: AdvanceResult) -> float:
        action = np.asarray(result.implemented_action, dtype=float)
        last = previous.get("action")
        previous["action"] = action
        if last is None:
            return 0.0
        return -weight * float(np.sum((action - last) ** 2))

    return reward


def weighted_reward(*components: tuple[RewardFn, float]) -> RewardFn:
    """Linear combination of reward functions: ``sum(weight * fn(result))``."""

    def reward(result: AdvanceResult) -> float:
        return float(sum(weight * fn(result) for fn, weight in components))

    return reward


# -- vectorized environments ----------------------------------------------
def make_vec_env(n: int, *, asynchronous: bool = False, **env_kwargs):
    """Build a Gymnasium vector env of ``n`` independent :class:`GymTEPEnv` instances.

    Each sub-env owns its own simulator (state-isolated), so Sync/Async vectorization is
    safe. Returns a ``gymnasium.vector.SyncVectorEnv`` (or ``AsyncVectorEnv``).
    """
    import gymnasium as gym

    from tep_studio.simulation.gym_env import GymTEPEnv

    def factory():
        return GymTEPEnv(**env_kwargs)

    if asynchronous:
        return gym.vector.AsyncVectorEnv([factory for _ in range(n)])
    return gym.vector.SyncVectorEnv([factory for _ in range(n)])


# -- offline-RL transition export -----------------------------------------
def to_transitions(runs, *, reward_fn: Callable[[dict], float] | None = None) -> dict[str, np.ndarray]:
    """Convert stored run(s) into an offline-RL transition dataset.

    Returns a dict of arrays ``obs, action, reward, next_obs, terminated, truncated``
    with causal alignment: ``action[k]`` is the manipulated variables applied over the
    interval from ``obs[k]`` to ``next_obs[k]``. Reward defaults to ``-production_cost``
    per step (override with ``reward_fn`` taking the next-step frame row as a dict).
    """
    from tep_studio.ui.results import RunResult

    if isinstance(runs, RunResult):
        runs = [runs]
    obs_list, act_list, rew_list, next_list, term_list = [], [], [], [], []
    for run in runs:
        frame = run.to_frame()
        if len(frame) < 2:
            continue
        meas_cols = [c for c in frame.columns if c.startswith("measurement.")]
        act_cols = [c for c in frame.columns if c.startswith("implemented_action.")]
        cost_col = "objective.production_cost_internal_per_hour"
        meas = frame[meas_cols].to_numpy(dtype=float)
        acts = frame[act_cols].to_numpy(dtype=float)
        for k in range(len(frame) - 1):
            row_next = frame.iloc[k + 1]
            obs_list.append(meas[k])
            act_list.append(acts[k + 1])  # the action applied during interval k -> k+1
            next_list.append(meas[k + 1])
            term_list.append(bool(row_next.get("terminated_at_end", False)))
            if reward_fn is not None:
                rew_list.append(float(reward_fn(row_next.to_dict())))
            elif cost_col in frame.columns:
                rew_list.append(-float(row_next[cost_col]) * float(row_next.get("control_interval", 0.0)))
            else:
                rew_list.append(0.0)
    n = len(obs_list)
    return {
        "obs": np.asarray(obs_list, dtype=float).reshape(n, -1),
        "action": np.asarray(act_list, dtype=float).reshape(n, -1),
        "reward": np.asarray(rew_list, dtype=float),
        "next_obs": np.asarray(next_list, dtype=float).reshape(n, -1),
        "terminated": np.asarray(term_list, dtype=bool),
        "truncated": np.zeros(n, dtype=bool),
    }


def write_transitions(transitions: dict[str, np.ndarray], path: str, *, fmt: str = "npz") -> str:
    """Write a transition dataset to ``.npz`` (default) or ``.parquet``."""
    if fmt == "npz":
        np.savez(path, **transitions)
        return path
    if fmt == "parquet":
        import pandas as pd

        columns = {}
        for key in ("obs", "action", "next_obs"):
            arr = transitions[key]
            for j in range(arr.shape[1]):
                columns[f"{key}_{j}"] = arr[:, j]
        columns["reward"] = transitions["reward"]
        columns["terminated"] = transitions["terminated"]
        columns["truncated"] = transitions["truncated"]
        pd.DataFrame(columns).to_parquet(path, index=False)
        return path
    raise ValueError(f"Unknown fmt {fmt!r}; expected npz|parquet.")
