# Public API

The top-level package exports the main user-facing classes:

```python
from tep_studio import (
    AdvanceResult,
    ClosedLoopSimulation,
    GymTEPEnv,
    OptimizationAdapter,
    ProcessSchema,
    RickerMultiLoopController,
    TEP_SCHEMA,
    TennesseeEastmanProcess,
    TrajectoryDataset,
)
```

The closed-loop control and interface layers have their own public APIs, summarized at the end of this page: [`tep_studio.control`](#tep_studiocontrol) and [`tep_studio.ui`](#tep_studioui).

## `TennesseeEastmanProcess`

Core process simulator.

### Create

```python
sim = TennesseeEastmanProcess(
    solver_method="RK45",
    rtol=1e-6,
    atol=1e-8,
)
```

### Reset

```python
obs, info = sim.reset(
    mode="mode1",
    seed=1431655765,
    initial_state=None,
    disturbances=None,
    ms_flag=None,
)
```

Returns:

- `obs`: 41-element measurement vector;
- `info`: dictionary with time, schema, implemented action, disturbances, margins, shutdown status, and solver stats.

### Advance

```python
result = sim.advance(
    action,
    control_interval=0.01,
    action_level="direct_mv",
    disturbances=None,
)
```

Returns an `AdvanceResult`.

### Snapshot and restore

```python
snapshot = sim.snapshot()
sim.restore(snapshot)
```

Use this for deterministic replay and candidate rollout.

### Validate dimensions

```python
checks = sim.validate()
```

Checks schema/kernel dimensions for states, manipulated variables, disturbances, and measurements.

## `AdvanceResult`

Returned by `TennesseeEastmanProcess.advance()`.

Fields:

| Field | Meaning |
| --- | --- |
| `time_start` | Start time of the interval. |
| `time_end` | End time of the interval. |
| `control_interval` | Requested interval length. |
| `state` | 50-element state at `time_end`. |
| `measurements` | 41 standard measurements at `time_end`. |
| `requested_action` | 12-element raw requested action. |
| `implemented_action` | 12-element clipped action applied to the process. |
| `disturbances` | 28-element disturbance vector. |
| `constraint_margins` | Named operating-limit margins. |
| `events` | Structured process event records. |
| `shutdown_status` | Shutdown code, message, and termination flag. |
| `solver_stats` | Solver method, success flag, message, and evaluation counts. |
| `objective_terms` | Operating-cost monitor terms exposed by the core. |

## `TrajectoryDataset`

Converts results into tabular data.

```python
dataset = TrajectoryDataset.from_results(
    results,
    run_id="run_001",
    scenario_id="mode1_short",
)

frame = dataset.to_pandas()
matrix, columns = dataset.to_numpy("measurements")
dataset.to_csv("trajectory.csv")
dataset.to_parquet("trajectory.parquet")
```

Supported NumPy views:

- `measurements`;
- `states`;
- `requested_actions`;
- `implemented_actions`;
- `disturbances`.

## `GymTEPEnv`

Gymnasium-compatible environment.

```python
env = GymTEPEnv(control_interval=0.01, horizon=24.0)
obs, info = env.reset(seed=123)
next_obs, reward, terminated, truncated, info = env.step(action)
```

The action space is 12-dimensional. The observation space is 41-dimensional.

## `OptimizationAdapter`

Finite-horizon rollout and finite-difference gradient helper.

```python
adapter = OptimizationAdapter(sim)
rollout = adapter.rollout(action_plan, control_interval=0.001)
gradient = adapter.finite_difference_gradient(action_plan, control_interval=0.001)
```

The adapter restores the simulator after each rollout.

## `TEP_SCHEMA`

Machine-readable process schema.

```python
from tep_studio import TEP_SCHEMA

state_names = TEP_SCHEMA.names("states")
measurement_names = TEP_SCHEMA.names("measurements")
mv_names = TEP_SCHEMA.names("manipulated_variables")
disturbance_names = TEP_SCHEMA.names("disturbances")
```

Named lookup helpers:

```python
pressure_index = TEP_SCHEMA.index("measurements", "reactor_pressure")
coolant_mv = TEP_SCHEMA.variable("mvs", "reactor_cooling_water_valve")
```

Vector helpers:

```python
action = TEP_SCHEMA.vector(
    "mvs",
    {
        "purge_valve": 40.064,
        "reactor_cooling_water_valve": 38.0,
    },
)

next_action = TEP_SCHEMA.update_vector(
    "mvs",
    action,
    {"reactor_cooling_water_valve": 41.106},
)

measurements = TEP_SCHEMA.to_dict("measurements", result.measurements)
reactor_pressure = measurements["reactor_pressure"]
```

Common role aliases include `measurement`, `measurements`, `mv`, `mvs`, `manipulated_variable`, `manipulated_variables`, `state`, `states`, `disturbance`, and `disturbances`.

## `tep_studio.control`

The decentralized control package. See [Closed-Loop Control](../control.md) for the loop structure and usage.

```python
from tep_studio.control import (
    ClosedLoopSimulation,    # couples controller + core; .run() -> ClosedLoopResult
    ClosedLoopResult,        # trajectory, metrics, peak, terminated/truncated, stabilized
    RickerMultiLoopController,  # the controller; reset(meas0) then compute_action(meas, time=t)
    ControllerSetpoints,     # frozen setpoint bundle (reactor_level, production_rate, %G, ...)
    ControlStepDiagnostics,  # per-step setpoints, loop outputs, active overrides
    RICKER_MODE1,            # the Mode-1 loop registry (gains, reset times, pairings)
    MetricsAccumulator,      # IAE/ISE/constraint-violation metrics
    DiscretePI, VelocityPI,  # the PI primitives (positional + velocity form)
    online_control_view,     # the 16 measurements the controller may use (P5 boundary)
    diagnostic_view,         # full offline view (state + events)
    build_experiment_record, # reproducible P6 record (revision, hashes, seed, solver)
    controller_config, process_description_hash,
)

result = ClosedLoopSimulation(control_interval=0.0005, horizon=48.0).run()
result.stabilized              # bool: ran the horizon without a shutdown
result.peak["reactor_pressure_max"]
result.metrics["iae"]["reactor_level"]
```

`compute_action` accepts only measurements (never `state`), enforcing the controller-is-not-the-plant boundary at the type level.

## `tep_studio.ui`

The Simulation Studio and its Dash-free backend. See [Interface (Studio)](../ui.md). The backend is importable without the `ui` extra; `create_app` imports Dash lazily.

```python
from tep_studio.ui import (
    ScenarioConfig,          # frozen, JSON-round-trippable run spec (the save/load unit)
    StepTestSpec,            # an MV or setpoint step
    DisturbanceActivation,   # a latched, timed IDV
    BatchSpec,               # seeds x disturbance x parameter sweep
    RunResult, BatchResult,  # compact, serializable run artifacts
    run_scenario,            # run one open/closed-loop scenario -> RunResult
    run_mv_step_test,        # open-loop MV step
    run_setpoint_step_test,  # closed-loop setpoint step
    build_dataset,           # (runs, fmt="csv"|"parquet") -> (payload_bytes, filename)
    run_batch,               # run a BatchSpec -> (BatchResult, list[RunResult])
    create_app,              # build the Dash app (requires the `ui` extra)
)

run = run_scenario(ScenarioConfig(loop_type="closed", horizon=12.0, control_interval=0.01))
payload, filename = build_dataset([run], fmt="csv")
```

Launch the interface with `python3 -m tep_studio.ui` or the `tep-ui` console script (installed with `pip install -e ".[ui]"`).
