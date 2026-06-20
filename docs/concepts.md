# Core Concepts

This page explains the simulator vocabulary used throughout the code and documentation.

## Process model

The numerical model comes from `temexd_mod/temexd_mod.c`. The Python package does not replace those equations. It wraps them through CFFI and adds named Python contracts around them.

The main layers are:

| Layer | Main file | Purpose |
| --- | --- | --- |
| Native kernel | `native.py`, `_cffi_build.py`, `temexd_mod.c` | Calls the legacy model, derivatives, outputs, shutdown status, and native snapshots. |
| Schema | `schema.py` | Names states, measurements, manipulated variables, disturbances, and monitor arrays. |
| Core simulator | `core.py` | Provides `reset()`, `advance()`, `snapshot()`, `restore()`, and `validate()`. |
| Gym adapter | `gym_env.py` | Exposes Gymnasium `reset()` and `step()`. |
| Dataset adapter | `dataset.py` | Converts simulator results into named pandas, NumPy, CSV, or Parquet data. |
| Optimization adapter | `optimization.py` | Provides deterministic rollout and finite-difference gradients. |
| Control | `control/` | Decentralized multiloop PI controller (Ricker 1996) that closes the loop on measurements only. |
| Interface | `ui/` | Dash + Plotly "Simulation Studio" over a Dash-free backend for runs, step tests, and dataset generation. |
| Validation | `validation/` | Generates trajectories, metrics, figures, reports, and manifests. |

Separately, the `research/schema/` directory holds the machine-readable process-description JSON Schema (`research/schema/process_description.schema.json`) and a minimal non-TEP example (`research/schema/examples/cstr_minimal.json`) — the design-principles deliverable, distinct from the in-code `TEP_SCHEMA` documented in [Schema Reference](reference/schema.md).

## State

The process state is a 50-element vector. It contains physical holdups, internal energies, temperatures, and manipulated-variable states. The ordering follows the legacy model, while the schema gives each entry a readable name.

You usually do not need to edit the state directly. You mostly read it from `result.state` or pass a full 50-element vector to `reset(initial_state=...)` when reproducing a specific operating point.

## Measurements

The standard observation vector has 41 measurements. It includes flows, pressures, temperatures, levels, compressor work, and analyzer compositions.

Use:

```python
result.measurements
```

For names:

```python
from tep_studio import TEP_SCHEMA

measurement_names = TEP_SCHEMA.names("measurements")
```

## Actions

An action is a 12-element manipulated-variable vector. In the current implementation, the action directly specifies manipulated-variable values.

Important details:

- each action entry is a percentage;
- requested values are clipped to `0` to `100`;
- `result.requested_action` stores what the controller asked for;
- `result.implemented_action` stores what the simulator actually applied.

Recording both is important. A controller may request an infeasible action, but the process only sees the clipped action.

You can build or update action vectors by manipulated-variable name:

```python
action = TEP_SCHEMA.vector("mvs", {"reactor_cooling_water_valve": 38.0})
action = TEP_SCHEMA.update_vector("mvs", action, {"purge_valve": 40.0})
```

If no base vector is provided, unspecified entries are zero. Use `update_vector()` when you want to preserve existing valve settings.

## Disturbances

The disturbance vector has 28 entries named `idv_01` through `idv_28`. You can pass a disturbance vector to `reset()` or `advance()`:

```python
disturbances = np.zeros(28)
disturbances[0] = 1.0

sim.reset(disturbances=disturbances)
result = sim.advance(action, control_interval=0.01, disturbances=disturbances)
```

The meaning of each disturbance is listed in [Process Schema](reference/schema.md).

## Control intervals

Every call to `advance()` moves the process from `time_start` to `time_end`.

```python
result = sim.advance(action, control_interval=0.01)
print(result.time_start)
print(result.time_end)
```

Rows generated from `AdvanceResult` are end-of-interval rows:

- measurements are from `time_end`;
- state is from `time_end`;
- actions are the inputs used during `time_start` to `time_end`;
- disturbances are the disturbances used during `time_start` to `time_end`.

This convention matters when building supervised-learning or offline-RL transitions.

Within each interval the kernel ODEs are integrated by the configured `solver_method`. The
default is a fast fixed-step **RK4** (`fixed_step=0.0005` h, the stiff model's design step) —
roughly 8× faster than the adaptive SciPy solvers and matching them to ~0.001%. Pass
`solver_method="RK45"` (or `"RK23"`, etc.) for an adaptive solve where `rtol`/`atol` apply;
those tolerances are ignored by the fixed-step `"RK4"`/`"Euler"` methods, and a `fixed_step`
far above the stiffness floor is rejected with a clear error.

## Shutdowns and events

A process shutdown is not treated as a numerical solver failure. It is reported in:

```python
result.shutdown_status
result.events
```

A shutdown status contains:

| Field | Meaning |
| --- | --- |
| `code` | Native shutdown code. |
| `message` | Human-readable shutdown message. |
| `terminated` | `True` if the process has shut down. |

The Gymnasium adapter maps shutdowns to `terminated=True`.

## Snapshots and replay

`snapshot()` stores native model memory, state, time, manipulated variables, and disturbances. `restore()` returns the simulator to that exact point.

```python
snapshot = sim.snapshot()
first = sim.advance(action, control_interval=0.001)

sim.restore(snapshot)
second = sim.advance(action, control_interval=0.001)
```

This is useful for scenario branching, deterministic replay, and finite-horizon optimization.
