from __future__ import annotations

from typing import Any, Callable

import gymnasium as gym
import numpy as np

from tep_studio.simulation.core import AdvanceResult, TennesseeEastmanProcess

RewardFn = Callable[[AdvanceResult], float]

# Setpoint-level action: the agent drives the decentralized controller's setpoints
# instead of valves. These are the controllable controlled-variable setpoints (the
# derived ya/yac trims are held at their reset defaults). (low, high) bounds frame the
# action space; values map to ``ControllerSetpoints`` fields of the same name.
SETPOINT_ACTION_BOUNDS: dict[str, tuple[float, float]] = {
    "production_rate": (10.0, 40.0),
    "pct_g": (5.0, 95.0),
    "reactor_pressure": (2700.0, 2900.0),
    "reactor_level": (30.0, 90.0),
    "reactor_temperature": (115.0, 135.0),
    "separator_level": (30.0, 90.0),
    "stripper_level": (30.0, 90.0),
}


class GymTEPEnv(gym.Env):
    """Gymnasium environment wrapping the modified Tennessee Eastman Process.

    - **Observation**: the 41 published measurements (``Box(41,)``), not the internal
      50-state vector — the controller/plant boundary holds for RL agents too.
    - **Action**: the 12 manipulated-variable valve positions, ``Box(0, 100, (12,))``;
      out-of-range actions are clipped by the simulator.
    - **Reward**: by default ``-production_cost`` over the step (a cost-minimisation
      task). Pass ``reward_fn`` to shape your own reward from the full
      :class:`~tep_studio.AdvanceResult` (measurements, constraint margins,
      objective terms, shutdown status).
    - **Episode end**: ``terminated`` on a plant shutdown, ``truncated`` at ``horizon``.

    Register-free use is also supported::

        import gymnasium as gym
        env = gym.make("TennesseeEastman-v0", horizon=24.0)
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        *,
        control_interval: float = 0.01,
        horizon: float = 24.0,
        seed_value: float | None = None,
        simulator: TennesseeEastmanProcess | None = None,
        reward_fn: RewardFn | None = None,
        action_level: str = "direct_mv",
        setpoint_fields: tuple[str, ...] = ("production_rate", "pct_g"),
        mode: str = "mode1",
        render_mode: str | None = None,
    ) -> None:
        super().__init__()
        if action_level not in ("direct_mv", "setpoint"):
            raise ValueError("action_level must be 'direct_mv' or 'setpoint'.")
        self.simulator = simulator or TennesseeEastmanProcess()
        self.control_interval = float(control_interval)
        self.horizon = float(horizon)
        self.seed_value = seed_value
        # Optional custom reward; when None the default cost-minimisation reward is used.
        self.reward_fn = reward_fn
        self.action_level = action_level
        self.setpoint_fields = tuple(setpoint_fields)
        self.mode = mode
        self.render_mode = render_mode
        self.observation_space = gym.spaces.Box(low=-np.inf, high=np.inf, shape=(41,), dtype=np.float64)
        self._controller = None
        if action_level == "direct_mv":
            self.action_space = gym.spaces.Box(low=0.0, high=100.0, shape=(12,), dtype=np.float64)
        else:  # setpoint level: the agent drives the Ricker controller's setpoints
            unknown = [f for f in self.setpoint_fields if f not in SETPOINT_ACTION_BOUNDS]
            if unknown:
                raise ValueError(f"Unknown setpoint_fields {unknown}; choose from {tuple(SETPOINT_ACTION_BOUNDS)}.")
            low = np.array([SETPOINT_ACTION_BOUNDS[f][0] for f in self.setpoint_fields], dtype=np.float64)
            high = np.array([SETPOINT_ACTION_BOUNDS[f][1] for f in self.setpoint_fields], dtype=np.float64)
            self.action_space = gym.spaces.Box(low=low, high=high, dtype=np.float64)
        self._last_obs: np.ndarray | None = None

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        options = options or {}
        effective_seed = self.seed_value if seed is None else float(seed)
        obs, info = self.simulator.reset(
            mode=options.get("mode", self.mode),
            seed=effective_seed,
            initial_state=options.get("initial_state"),
            disturbances=options.get("disturbances"),
            ms_flag=options.get("ms_flag"),
        )
        if self.action_level == "setpoint":
            from tep_studio.control import RickerMultiLoopController

            self._controller = RickerMultiLoopController(enable_composition=True, enable_overrides=True)
            self._controller.reset(obs, time=self.simulator.time)
        self._last_obs = obs.astype(np.float64, copy=True)
        return self._last_obs, info

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if self.action_level == "setpoint":
            import dataclasses as _dc

            updates = {field: float(value) for field, value in zip(self.setpoint_fields, np.asarray(action, dtype=float))}
            self._controller.setpoints = _dc.replace(self._controller.setpoints, **updates)
            mv_action, _ = self._controller.compute_action(self._last_obs, time=self.simulator.time)
        else:
            mv_action = action
        result = self.simulator.advance(mv_action, control_interval=self.control_interval)
        obs = result.measurements.astype(np.float64, copy=True)
        terminated = bool(result.shutdown_status["terminated"])
        truncated = bool(result.time >= self.horizon and not terminated)
        production_cost_rate = float(result.objective_terms["production_cost_internal_per_hour"])
        production_cost_interval = production_cost_rate * result.control_interval
        reward = self.reward_fn(result) if self.reward_fn is not None else -production_cost_interval
        info = {
            "time": result.time,
            "implemented_action": result.implemented_action.copy(),
            "constraint_margins": result.constraint_margins,
            "events": result.events,
            "shutdown_status": result.shutdown_status,
            "solver_stats": result.solver_stats,
            "objective_terms": result.objective_terms,
            "reward_terms": {
                "production_cost_internal_per_hour": production_cost_rate,
                "production_cost_interval": production_cost_interval,
            },
        }
        self._last_obs = obs
        return obs, float(reward), terminated, truncated, info
