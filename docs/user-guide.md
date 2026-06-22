# User Guide

## Process Core

Use `TennesseeEastmanProcess` for direct simulation:

```python
import numpy as np
from tep_studio import TEP_SCHEMA, TennesseeEastmanProcess

sim = TennesseeEastmanProcess()
obs, info = sim.reset(seed=1431655765)

action = np.full(12, 50.0)
result = sim.advance(action, control_interval=0.01)
```

`reset` currently supports Mode 1 initial conditions unless a full 50-state `initial_state` is supplied. `advance` currently supports `action_level="direct_mv"` only.

## Named Inputs and Outputs

Use `TEP_SCHEMA` when you want to avoid memorizing array positions. These helpers do not add controller logic; they only translate between process names and the direct vectors used by the simulator.

```python
base_action = TEP_SCHEMA.vector(
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

action = TEP_SCHEMA.update_vector(
    "mvs",
    base_action,
    {"reactor_cooling_water_valve": 38.0},
)

result = sim.advance(action, control_interval=0.01)
measurements = TEP_SCHEMA.to_dict("measurements", result.measurements)

print(measurements["reactor_pressure"])
print(measurements["reactor_temperature"])
```

For a user-written feedback script, calculate the next direct-MV values outside the simulator and pass the resulting vector to `advance()`:

```python
measurements = TEP_SCHEMA.to_dict("measurements", obs)
action = base_action.copy()

while sim.time < 1.0:
    pressure = measurements["reactor_pressure"]
    coolant = action[TEP_SCHEMA.index("mvs", "reactor_cooling_water_valve")]
    action = TEP_SCHEMA.update_vector(
        "mvs",
        action,
        {"reactor_cooling_water_valve": coolant - 0.01 * (2800.0 - pressure)},
    )
    result = sim.advance(action, control_interval=0.01)
    measurements = TEP_SCHEMA.to_dict("measurements", result.measurements)
    if result.shutdown_status["terminated"]:
        break
```

## Action Semantics

The current control authority is direct manipulated-variable authority:

- The requested action must have shape `(12,)`.
- Requested values are clipped to the range `0.0` to `100.0`.
- `requested_action` records the raw external request.
- `implemented_action` records the clipped action applied to the native process model.
- The implemented action and disturbance vector are held constant over the interval.

## Shutdown Handling

Shutdowns are process events, not generic integration failures. The result contains:

```python
result.shutdown_status
result.events
result.constraint_margins
```

Constraint margins include high and low margins for reactor level, separator level, and stripper level, plus high margins for reactor pressure and reactor temperature.

## Gymnasium Environment

`GymTEPEnv` exposes the simulator through the Gymnasium API:

```python
from tep_studio import GymTEPEnv

env = GymTEPEnv(control_interval=0.01, horizon=24.0)
obs, info = env.reset(seed=123)
next_obs, reward, terminated, truncated, step_info = env.step(env.action_space.sample())
```

The action space is a 12-dimensional `Box(0.0, 100.0)`. The observation space is a 41-dimensional box containing standard measurements. Process shutdown maps to `terminated`; horizon exhaustion maps to `truncated` only if the process has not already terminated.

The built-in reward is a demonstration reward. Benchmark studies should define task-specific rewards, constraints, baselines, and scenario splits.

## Trajectory Data

`TrajectoryDataset` converts `AdvanceResult` objects into named data tables:

```python
from tep_studio import TrajectoryDataset

dataset = TrajectoryDataset.from_results(
    results,
    run_id="run_001",
    scenario_id="mode1_short",
)

frame = dataset.to_pandas()
Y, y_columns = dataset.to_numpy("measurements")
U, u_columns = dataset.to_numpy("implemented_actions")
```

Generated rows are end-of-interval samples. If a dataset includes an initial row, it has `is_initial=True` and zero interval length. Otherwise, each row contains the measurements, state, implemented action, disturbance vector, and termination status at the end of the interval that produced that row.

## Optimization

`OptimizationAdapter` evaluates finite-horizon action plans from a simulator snapshot and restores the original simulator state afterward:

```python
import numpy as np
from tep_studio import OptimizationAdapter, TennesseeEastmanProcess

sim = TennesseeEastmanProcess()
sim.reset(seed=1431655765)

adapter = OptimizationAdapter(sim)
actions = np.full((3, 12), 50.0)
rollout = adapter.rollout(actions, control_interval=0.001)
gradient = adapter.finite_difference_gradient(actions[:1], control_interval=0.001)
```

The differentiability declaration is `finite_difference_only`. Event logic, clipping, shutdowns, and legacy native code mean the interface does not claim global smooth differentiability or automatic-differentiation compatibility.

## Closed-Loop Control

The base-case plant is open-loop unstable and trips on high reactor pressure within a few hours. The `tep_studio.control` package adds the Ricker (1996) decentralized multiloop PI controller, which stabilizes it:

```python
from tep_studio.control import ClosedLoopSimulation

result = ClosedLoopSimulation(control_interval=0.0005, horizon=48.0).run()
print(result.stabilized)  # True: ran the horizon without a shutdown
```

The controller consumes only published measurements (no plant-state leakage), initializes bumplessly from the Mode-1 state, and emits a reproducible experiment record. See [Closed-Loop Control](control.md) for the loop structure, overrides, disturbance rejection, and configuration flags.

## Simulation Studio

For interactive use, the `tep_studio.ui` package provides a Dash + Plotly web interface for open/closed-loop runs, disturbance scenarios, dataset generation, run comparison, and scenario save/load:

```bash
python3 -m pip install -e ".[ui]"
python3 -m tep_studio.ui          # or: tep-ui ; opens http://127.0.0.1:8050
```

The interface is a thin layer over a Dash-free, importable backend (`from tep_studio.ui import run_scenario, ScenarioConfig, build_dataset`), so the same runs and exports are scriptable. See [Interface (Studio)](ui.md).
