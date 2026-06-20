# TEP Studio

This documentation explains how to use the Python simulator for the modified Tennessee Eastman Process (TEP).

It assumes you are comfortable copying commands into a terminal, but it does not assume prior knowledge of the codebase, process simulation, reinforcement learning, or MkDocs.

## What the simulator provides

The package wraps the legacy `temexd_mod.c` Tennessee Eastman model through a native CFFI extension and exposes practical Python interfaces for:

- direct process simulation with `TennesseeEastmanProcess`;
- Gymnasium-style control experiments with `GymTEPEnv`;
- named trajectory datasets with `TrajectoryDataset`;
- deterministic finite-horizon rollout with `OptimizationAdapter`;
- closed-loop decentralized control with `ClosedLoopSimulation` and `RickerMultiLoopController`;
- an interactive Dash + Plotly interface (the "Simulation Studio") for runs, step tests, disturbances, and dataset generation;
- validation runs, metrics, figures, reports, and manifests.

The simulator does not define a complete benchmark by itself. A study still needs to define the task objective, constraints, disturbance policy, train/test split, baselines, and evaluation protocol.

## Quickstart by audience

Install with `pip install tep-studio` (add `[ui]` for the web studio), then pick the path that matches your work — and keep the [Cookbook](cookbook.md) handy for task recipes.

- **Process / control engineers** — run the closed loop, inject disturbances, change setpoints, plot, and export data. Start with `python -c "import tep_studio as t; t.quickstart()"`, then [Closed-Loop Control](control.md) and the [Interface (Studio)](ui.md). The `tep` command-line tool (`tep run`, `tep dataset`, `tep list`) covers no-code runs.
- **ML / RL researchers** — `import tep_studio` registers a standard Gymnasium environment: `gymnasium.make("TennesseeEastman-v0")`, with a configurable `reward_fn`. See [Gymnasium and RL](gymnasium.md) and [Working with Data](data.md).
- **Control theorists** — get a local linear state-space model with `OptimizationAdapter.linearize(...)`, run step tests via `tep_studio.analysis`, and bring your own controller through the `Controller` protocol. See [Optimization](optimization.md) and the [Cookbook](cookbook.md).

## Recommended reading path

1. Read [Getting Started](getting-started.md) and install the package.
2. Run [First Simulation](first-simulation.md) to make sure the simulator works.
3. Keep the [Cookbook](cookbook.md) open for copy-paste recipes for common tasks.
4. Read [Core Concepts](concepts.md) to understand states, measurements, actions, disturbances, shutdowns, and intervals.
5. Use [Working with Data](data.md) if you need CSV, pandas, supervised learning, system identification, or offline RL data.
6. Use [Gymnasium and RL](gymnasium.md) if you want an environment with `reset()` and `step()`.
7. Use [Optimization](optimization.md) for deterministic rollout, finite-difference gradients, and linearization.
8. Use [Closed-Loop Control](control.md) to stabilize the plant with the decentralized controller.
9. Use the [Interface (Studio)](ui.md) to run, visualize, and export simulations interactively.
10. Use [Validation](validation.md) before relying on results in a report or paper.

## Current scope

The current high-level simulator API supports Mode 1 initialization by default. Other operating points can be supplied through an explicit 50-state initial vector. The current action interface uses direct manipulated-variable authority: each action is a 12-element vector of valve or manipulated-variable values, clipped to the 0 to 100 percent range before being applied.

The strongest current validation evidence is base-case agreement, local trajectory behavior checks, R12 high-pressure shutdown behavior, solver replay checks, and MAT-state operating-point checks. Full independent transient validation across all modes, disturbances, controller configurations, and shutdown trajectories is not yet complete.
