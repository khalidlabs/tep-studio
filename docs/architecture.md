# Architecture

The implementation uses a narrow numerical core and task-specific adapters. The process core is separate from the reinforcement-learning environment, trajectory dataset object, optimizer, and validation runner. This prevents downstream workflows from inventing their own naming, action, event, or termination conventions.

## Layer Overview

| Layer | Module or artifact | Responsibility |
| --- | --- | --- |
| Native TEP kernel | `native.py`, `_cffi_build.py`, `temexd_mod/temexd_mod.c` | Wrap the legacy modified TEP equations, reset state, derivative calls, output calls, shutdown status, and model-byte snapshots. |
| Machine-readable schema | `schema.py` | Define names, roles, units, indices, bounds, descriptions, and online availability. |
| Simulator core | `core.py` | Provide `reset`, `advance`, `snapshot`, `restore`, and `validate`. |
| Online interaction adapter | `gym_env.py` | Expose a Gymnasium-compatible reset/step interface. |
| Trajectory adapter | `dataset.py` | Convert `AdvanceResult` objects into pandas, NumPy, CSV, and Parquet data products. |
| Optimization adapter | `optimization.py` | Support finite-horizon rollout and finite-difference gradients. |
| Control layer | `control/` | Decentralized multiloop PI controller (Ricker 1996) that closes the loop on published measurements only. |
| Interface | `ui/` | Dash + Plotly "Simulation Studio" over a Dash-free, importable backend (`ui/service.py`) for runs, disturbances, and dataset generation. |
| Validation framework | `validation/` (writes the gitignored, generated `validation_outputs/`) | Run validation suites and write metrics, figures, reports, trajectories, and manifests. |

## Dependency Direction

```text
temexd_mod.c -> native.py -> core.py -> gym_env.py
                              |       -> dataset.py
schema.py --------------------|       -> optimization.py
                                      -> control/ -> ui/
                                      -> validation/
```

`native.py` and `schema.py` feed `core.py`. The Gymnasium, dataset, optimization, control, UI, and validation layers consume the core. The UI's backend (`ui/service.py`) sits on top of both the core and the control layer. Task-specific adapters are not the source of process truth.

## Control Layer

The `control/` package is a consumer of the core, not part of it, following the same separation the design principles call for. It drives the documented `advance(action, action_level="direct_mv")` interface and reads only `AdvanceResult.measurements`, never `state` (no plant-state leakage).

| Module | Responsibility |
| --- | --- |
| `pi.py` | Positional and velocity discrete-PI primitives with saturated-state anti-windup. |
| `loops.py`, `registry.py` | Declarative Mode-1 loop table (`RICKER_MODE1`): gains, reset times, pairings, overrides, resolved by schema name. |
| `controller.py` | `RickerMultiLoopController`: per-step orchestration and bumpless initialization. |
| `runner.py` | `ClosedLoopSimulation`: couples controller and core; records a trajectory and full-resolution metrics; separates termination from truncation. |
| `views.py` | Causal `online_control_view` vs offline `diagnostic_view`. |
| `metrics.py`, `experiment.py`, `config.py` | IAE/ISE/violation metrics and a reproducible experiment record (source revision, hashes, seed, solver, model-leakage policy). |

See [Closed-Loop Control](control.md) for usage.

## Interface Layer

The `ui/` package is the "Simulation Studio", a Dash + Plotly web app over a deliberately Dash-free, importable backend, so the same runs and exports are scriptable without a browser.

| Module | Responsibility |
| --- | --- |
| `config.py` | `ScenarioConfig`/`BatchSpec` — the JSON-round-trippable unit of save/load and batch sweeps, validated against the schema. |
| `service.py` | UI-agnostic backend: `run_scenario`, `run_mv_step_test`, `run_setpoint_step_test`, `build_dataset`, `run_batch`. |
| `figures.py` | Plotly figure builders (trajectory grid, MV panel, compare overlay, step response). |
| `results.py`, `store.py` | Compact `RunResult` artifacts and a server-side run cache. |
| `app.py`, `layout.py`, `widgets.py`, `callbacks.py` | The thin Dash app: `create_app`, schema-driven widgets, and callbacks. Dash is imported lazily so `import tep_studio` works without the `ui` extra. |

See [Interface (Studio)](ui.md) for usage.

## Native Boundary

The native layer preserves the legacy model and exposes only the functions needed by the Python simulator:

| Native function | Purpose |
| --- | --- |
| `tep_create`, `tep_destroy` | Allocate and free native model state. |
| `tep_reset` | Initialize the modified TEP model with optional initial state, seed, and measurement/noise flag. |
| `tep_set_inputs` | Set 12 manipulated variables and 28 disturbance activations. |
| `tep_derivatives` | Evaluate the 50-state derivative vector. |
| `tep_outputs` | Evaluate standard measurements and monitor arrays. |
| `tep_shutdown_code`, `tep_shutdown_message` | Read process shutdown status. |
| `tep_model_size`, `tep_get_model_bytes`, `tep_set_model_bytes` | Snapshot and restore native model memory. |

The C layer remains responsible for derivatives, outputs, internal model state, and shutdown status. The Python layer is responsible for names, metadata, trajectory formats, interaction semantics, and experiment records.

## Advance Result

Every successful `advance` call returns an `AdvanceResult`. It is the typed contract between the core simulator and its adapters.

| Field | Meaning |
| --- | --- |
| `time`, `time_end` | End time of the interval in hours. `time` is a compatibility alias. |
| `time_start`, `control_interval` | Start time and length of the control interval. |
| `state` | 50-element state vector at `time_end`. |
| `measurements` | 41 standard TEP measurements. |
| `additional_measurements` | 32 additional modified-TEP outputs. |
| `disturbance_monitors` | 21 noise-free disturbance monitor outputs. |
| `process_monitors` | 62 process monitor outputs. |
| `concentration_monitors` | 96 component concentration monitor outputs. |
| `requested_action`, `implemented_action` | Raw requested action and clipped action applied to the process. |
| `disturbances` | 28-element disturbance vector used for the interval. |
| `constraint_margins` | Named safety margins. |
| `events`, `shutdown_status` | Structured process events and shutdown status. |
| `solver_stats` | Integration method, success flag, message, and evaluation counts. |
| `objective_terms` | Cost-related monitor terms exposed by the process core. |
