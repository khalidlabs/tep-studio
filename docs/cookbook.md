# Cookbook

Short, copy-paste recipes for the most common tasks. Each assumes the package is
installed (`pip install tep-studio`, or `pip install -e .` from a checkout). If you
run from a source checkout without installing, prefix commands with `PYTHONPATH=src`.

## Check that the plant runs (and is stabilized)

```python
import tep_studio as tep

tep.quickstart()  # short closed-loop run; prints stabilized + peak reactor pressure
```

For a full run you control:

```python
from tep_studio import ClosedLoopSimulation

result = ClosedLoopSimulation(horizon=24.0).run()
print(result.stabilized, result.peak["reactor_pressure_max"])
```

## Discover the variables you can touch

```python
import tep_studio as tep

tep.list_measurements()           # 41 (name, unit, description) — observations / CVs
tep.list_manipulated_variables()  # 12 (name, unit, description) — the action vector
tep.list_disturbances()           # 28 (name, description) — IDVs you can inject
tep.list_setpoints()              # closed-loop setpoint field names
```

From the terminal: `tep list disturbances` (or `measurements`, `mvs`, `setpoints`).

## Change a setpoint

Setpoints are a frozen `ControllerSetpoints`; copy-and-replace the field you want,
then hand the controller to the runner:

```python
import dataclasses
from tep_studio import ClosedLoopSimulation, RickerMultiLoopController, TennesseeEastmanProcess

sim = TennesseeEastmanProcess()
meas, _ = sim.reset()
controller = RickerMultiLoopController()
controller.reset(meas)                      # seeds default setpoints from the Mode-1 state
controller.setpoints = dataclasses.replace(controller.setpoints, production_rate=24.0)

result = ClosedLoopSimulation(simulator=sim, controller=controller, horizon=24.0).run()
```

## Inject a disturbance (IDV)

```python
from tep_studio.analysis import DisturbanceActivation, ScenarioConfig, run_scenario

cfg = ScenarioConfig(
    horizon=12.0,
    disturbances=(DisturbanceActivation(idv="idv_01", start_time=1.0),),  # A/C ratio step at 1 h
)
run = run_scenario(cfg)
print(run.metrics["iae"]["reactor_pressure"])
```

Terminal equivalent: `tep run --horizon 12 --idv idv_01@1.0`. See
`control/examples/disturbance_scenario.py`.

## Run a step test

Open-loop MV step (response only, no model identification):

```python
from tep_studio.analysis import ScenarioConfig, StepTestSpec, run_mv_step_test

cfg = ScenarioConfig(loop_type="open", horizon=1.0, control_interval=0.01)
spec = StepTestSpec(kind="mv", target="d_feed_valve", baseline=63.0, step_value=70.0, step_time=0.25)
frame = run_mv_step_test(cfg, spec).to_frame()
```

Closed-loop setpoint step:

```python
from tep_studio.analysis import ScenarioConfig, StepTestSpec, run_setpoint_step_test

cfg = ScenarioConfig(loop_type="closed", horizon=8.0)
spec = StepTestSpec(kind="setpoint", target="reactor_level", baseline=75.0, step_value=70.0, step_time=1.0)
frame = run_setpoint_step_test(cfg, spec).to_frame()
```

See `control/examples/mv_step_test.py`.

## Train an RL agent

The Gymnasium environment registers itself on `import tep_studio`:

```python
import gymnasium, tep_studio

env = gymnasium.make("TennesseeEastman-v0", horizon=24.0)
obs, info = env.reset(seed=0)
obs, reward, terminated, truncated, info = env.step(env.action_space.sample())
```

Shape your own reward from the full step result, and train with stable-baselines3
(`pip install stable-baselines3`):

```python
def reward_fn(result):  # result is an AdvanceResult
    return (3000.0 - float(result.measurements[6])) / 3000.0  # stay off the pressure trip

env = gymnasium.make("TennesseeEastman-v0", reward_fn=reward_fn)
```

See `simulation/examples/rl_training.py`.

## Linearize the plant (control theory)

A discrete-time local model `x_{k+1} - x* ≈ A (x_k - x*) + B (u_k - u*)`:

```python
from tep_studio import OptimizationAdapter, TennesseeEastmanProcess

sim = TennesseeEastmanProcess(rtol=1e-9, atol=1e-11)  # tight tolerances → clean Jacobian
sim.reset(mode="mode1")
x0, u0 = sim.state.copy(), sim.state[38:50].copy()
A, B = OptimizationAdapter(sim).linearize(x0, u0, control_interval=0.001)
# A is (50, 50), B is (50, 12); use for eigenvalues, controllability, LQR, ...
```

For small intervals the continuous Jacobian is `A_continuous ≈ (A - I) / control_interval`.

## Bring your own controller

`ClosedLoopSimulation` accepts anything satisfying the `Controller` protocol
(`setpoints`, `reset`, `compute_action`); no subclassing. The PI primitives
(`DiscretePI`, `VelocityPI`) are reusable building blocks. A worked example that
swaps in a custom reactor-temperature loop is in `control/examples/custom_controller.py`.

## Export a dataset

One run to CSV/Parquet:

```python
from tep_studio.analysis import ScenarioConfig, build_dataset, run_scenario

run = run_scenario(ScenarioConfig(horizon=12.0))
payload, filename = build_dataset([run], fmt="csv")       # or fmt="parquet"
open(filename, "wb").write(payload)
```

A multi-seed batch from the terminal: `tep dataset --seeds 1,2,3 --horizon 12 --out data.csv`.
Batch jobs are independent, so `tep dataset` runs them across all CPU cores by default
(pass `-j N` to cap workers, or `-j 1` for sequential). In Python the same applies:
`run_batch(spec, max_workers=N)` (`None` = all cores). For lower-level, per-step control
see [Working with Data](data.md) and `TrajectoryDataset`.

## Speed vs. fidelity (the integrator)

Simulations use a fast fixed-step RK4 integrator by default: ~8× faster than the
adaptive SciPy solver, and faithful to the model's 0.0005 h design step (it matches RK45
to ~0.001%). For an adaptive reference solve, request RK45:

```python
from tep_studio import TennesseeEastmanProcess
sim = TennesseeEastmanProcess(solver_method="RK45")    # adaptive; rtol/atol now apply

from tep_studio.analysis import ScenarioConfig
ScenarioConfig(solver_method="RK45")                   # for run_scenario / run_batch
```

From the terminal: `tep run --solver RK45` / `tep dataset --solver RK45`. Note: `rtol`/`atol`
affect only the SciPy methods; the fixed-step `RK4`/`Euler` ignore them. Keep the default
`fixed_step=0.0005`: the model is stiff, so coarser substeps are rejected (loud error).

## Use the command line

```bash
tep run --horizon 24 --idv idv_06@2.0 --setpoint production_rate=24 --out run.csv
tep dataset --seeds 1,2,3 --horizon 12 --out dataset.csv
tep list disturbances
tep version
```

## Launch the web Simulation Studio

```bash
pip install "tep-studio[ui]"
tep ui                 # or: python -m tep_studio.ui ; opens http://127.0.0.1:8050
```

See the [Interface (Studio)](ui.md) page for the tabs and workflow.
