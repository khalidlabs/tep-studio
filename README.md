# TEP Studio

This repository contains a schema-driven Python implementation of the modified Tennessee Eastman Process in `temexd_mod`. Simulation code lives in `src/tep_studio/simulation/`; `src/tep_studio/__init__.py` re-exports the public API.

The Python package keeps the original `temexd_mod.c` equations as the numerical source of truth by compiling a native CFFI extension, then exposes process-aware Python contracts for:

- process-core use through `TennesseeEastmanProcess`
- Gymnasium RL/control interaction through `GymTEPEnv`
- causal trajectory datasets through `TrajectoryDataset`
- deterministic rollout and finite-difference optimization through `OptimizationAdapter`
- closed-loop decentralized control through `ClosedLoopSimulation` and `RickerMultiLoopController`
- an interactive Dash + Plotly interface for runs, disturbances, and dataset generation (`tep_studio.ui`)

## Quickstart

```bash
pip install tep-studio            # add [ui] for the web Simulation Studio
```

```python
import tep_studio as tep
tep.quickstart()                                  # short closed-loop smoke run

import gymnasium                                   # a registered RL environment
env = gymnasium.make("TennesseeEastman-v0", horizon=24.0)

from tep_studio import ClosedLoopSimulation     # the stabilized closed loop
result = ClosedLoopSimulation(horizon=24.0).run()
```

Or from the terminal: `tep run --horizon 24 --idv idv_01@1.0`, `tep list disturbances`,
`tep ui`. See the [Cookbook](docs/cookbook.md) for task recipes.

## Build

`pip install tep-studio` downloads the source distribution and compiles the native
extension on your machine, so it needs a C compiler and the standard Python build
tools (`gcc` or `clang` on Linux and macOS; the Visual Studio Build Tools on
Windows). The instructions below cover building from a source checkout, which runs
the same compile step.

The build requires `setuptools>=68` (declared in `pyproject.toml`). The recommended
path is an editable install, which uses build isolation to provision the correct
build dependencies automatically:

```bash
python3 -m pip install -e .
```

If your environment blocks build isolation (for example, an offline machine), first
ensure the build tools are current, then install without isolation:

```bash
python3 -m pip install -U "setuptools>=68" wheel cffi
python3 -m pip install -e . --no-build-isolation
```

To build the native extension in place instead of installing, the same
`setuptools>=68` requirement applies (older setuptools mis-places the compiled
artifact under the `src/` layout):

```bash
python3 -m pip install -U "setuptools>=68"
python3 setup.py build_ext --inplace
```

The compiled `_tep_native` extension is platform-specific and is not tracked in
version control. After moving the repository to a new machine or operating system,
rebuild it with one of the commands above before importing the package.

## Smoke Test

```bash
PYTHONPATH=src python3 src/tep_studio/simulation/examples/r12_open_loop.py
PYTHONPATH=src python3 -m pytest -q
```

The R12 open-loop example should terminate near 1.07 h with a high reactor pressure shutdown.

## Validation

```bash
PYTHONPATH=src python3 -m tep_studio.simulation.validation run --suite local
PYTHONPATH=src python3 -m tep_studio.simulation.validation run --suite steady_state
PYTHONPATH=src python3 -m tep_studio.simulation.validation run --suite mat_states
PYTHONPATH=src python3 -m tep_studio.simulation.validation run --suite all --solvers RK23 RK45
PYTHONPATH=src python3 -m tep_studio.simulation.validation figures
PYTHONPATH=src python3 -m tep_studio.simulation.validation report
```

Validation artifacts are written under `src/tep_studio/simulation/validation_outputs/`. The steady-state suite exports the Ricker (1995) Table 2/3 references, compares the simulator base case against the reported Downs and Vogel steady state, and marks optimized modes 1-6 as reference-only unless their electronic 50-state vectors are supplied. The MAT-state suite evaluates the bundled Simulink `CSTATE` vectors for Mode 1, Mode 3, and Skogestad Mode 1 and writes paper-ready comparison tables and figures. Add `--download-external` to cache public reference metadata and files where available.

## Closed-Loop Control

The base-case plant is open-loop unstable and trips on high reactor pressure within a few hours. The `tep_studio.control` package adds the Ricker (1996) decentralized multiloop PI strategy, which stabilizes the plant for the full horizon:

```bash
PYTHONPATH=src python3 src/tep_studio/control/examples/ricker_mode1_closed_loop.py
```

```python
from tep_studio.control import ClosedLoopSimulation

result = ClosedLoopSimulation(control_interval=0.0005, horizon=48.0).run()
assert result.stabilized  # ran the horizon without a shutdown
```

The controller is separate from the simulator core and consumes only published measurements (no plant-state leakage). It reproduces the loop pairings and gains from Ricker's runnable `MultiLoop_mode1.mdl`, initializes bumplessly from the Mode-1 state, and emits a reproducible experiment record. See `docs/control.md` for the loop structure, overrides, disturbance rejection, and configuration flags.

## Interface (Simulation Studio)

An interactive Dash + Plotly web interface for running, visualizing, and exporting simulations. It covers open/closed-loop runs, disturbance scenarios, dataset generation, run comparison, and scenario save/load:

```bash
python3 -m pip install -e ".[ui]"
python3 -m tep_studio.ui          # or: tep-ui ; opens http://127.0.0.1:8050
```

The interface is a thin layer over a Dash-free, importable backend (`from tep_studio.ui import run_scenario, ScenarioConfig, build_dataset`), so the same runs and exports are scriptable. See `docs/ui.md`.

## Online Documentation

The online documentation source is in `docs/` and is configured by `mkdocs.yml`. It is written as a practical step-by-step guide for new users and is based on the simulator supplement:

```bash
python3 -m pip install -e ".[docs]"
python3 -m mkdocs serve
python3 -m mkdocs build --strict
```

(Append `--no-build-isolation` to the install command if your environment blocks
build isolation, after upgrading the build tools as described under [Build](#build).)

The local server defaults to <http://127.0.0.1:8000/>. Start with `docs/getting-started.md`, then run the walkthrough in `docs/first-simulation.md`.
