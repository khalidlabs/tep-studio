# Closed-Loop Control

The base-case TEP is **open-loop unstable**: held at constant inputs it trips on high
reactor pressure within a few hours. The `tep_studio.control` package adds a
decentralized multiloop PI controller (N. L. Ricker, *Decentralized control of the
Tennessee Eastman Challenge Process*, J. Proc. Cont. 6(4), 1996) that keeps the plant
on its operating point.

The controller is separate from the simulator core (principle P2) and consumes only
published measurements — never the internal 50-state vector (principle P5).

## 1. Stabilize the plant

```python
from tep_studio.control import ClosedLoopSimulation

result = ClosedLoopSimulation(control_interval=0.0005, horizon=48.0).run()

print(result.stabilized)                       # True
print(result.terminated, result.truncated)     # False True  (ran the horizon, no shutdown)
print(result.peak["reactor_pressure_max"])     # ~2709 kPa  (trip is 3000)
```

`stabilized` is `True` when the run reaches the horizon without a shutdown. The
runner separates **termination** (an endogenous plant shutdown) from **truncation**
(reaching the horizon), matching the simulator's lifecycle semantics (principle P3).

!!! note "Control interval"
    The reference uses a fixed `Ts_base = 0.0005 h` sample period. Running
    `control_interval = 0.0005` reproduces it most closely. The PI loops use the
    actual elapsed time in their integral term, so a coarser interval still behaves
    sensibly (faster, lower fidelity).

## 2. Control structure

The strategy is encoded declaratively in `RICKER_MODE1` (see
`tep_studio/control/registry.py`). Every loop is resolved by schema *name*, not
array index.

| Group | Controlled variable | Manipulated / target |
|-------|---------------------|----------------------|
| Reactor temperature | `reactor_temperature` | reactor cooling-water valve |
| Reactor pressure | `reactor_pressure` | purge ratio `r5` (**not** the recycle valve) |
| Reactor level | `reactor_level` | separator-temperature setpoint (cascade) |
| Separator temperature | `separator_temperature` | condenser cooling-water valve |
| Separator / stripper level | `separator_level`, `stripper_level` | underflow ratios `r6`, `r7` |
| Production rate | `stripper_underflow` | production index `Fp` (scales all feeds) |
| Feed flows | `feed_*_flow` | feed valves (setpoint = ratio × `Fp`) |
| %G / reactant trims | `%G`, `yA`, `yAC` | feed-ratio trims `r1`..`r4` |

The reactor-level loop sets the separator-temperature setpoint, which drives the
condenser coolant — the cascade that regulates reactor inventory.

## 3. Setpoints and configuration

By default the controller seeds bumpless setpoints from the Mode-1 initial state, so
the first action matches the base-case valve positions (no startup bump). Override
them explicitly:

```python
import dataclasses as dc
from tep_studio import TennesseeEastmanProcess
from tep_studio.control import RickerMultiLoopController, ClosedLoopSimulation

sim = TennesseeEastmanProcess()
meas0, _ = sim.reset(mode="mode1")
defaults = RickerMultiLoopController(); defaults.reset(meas0)

setpoints = dc.replace(defaults.setpoints, production_rate=28.0)   # demand more throughput
controller = RickerMultiLoopController(setpoints=setpoints, enable_overrides=True)
result = ClosedLoopSimulation(simulator=sim, controller=controller, horizon=24.0).run()
```

Feature flags:

- `enable_composition` (default `True`) — the stable yA/yAC reactant-ratio trims and
  the %G feedforward.
- `enable_pct_g_feedback` (default `False`) — the %G→`Eadj` feedback loop. **Off by
  default:** its feedforward constants were tuned for the *original* TEP (`temex.c`),
  while this package wraps the *modified* TEP (`temexd_mod.c`), whose composition
  dynamics differ. Enabling it without retuning destabilizes the plant.
- `enable_overrides` (default `False`) — the high-reactor-pressure override (cuts the
  production index) and high-reactor-level override (recycle valve).

## 4. Overrides

The decentralized loops hold pressure well, so the high-pressure override is a
last-resort safety net that rarely fires. Under a strong upset it activates and caps
pressure below the 3000 kPa trip:

```python
import numpy as np
idv13 = np.zeros(28); idv13[12] = 1.0   # reaction-kinetics drift

controller = RickerMultiLoopController(setpoints=setpoints, enable_overrides=True)
result = ClosedLoopSimulation(simulator=sim, controller=controller, horizon=8.0).run(disturbances=idv13)
fired = any(d.overrides_active.get("high_pressure_to_production") for d in result.diagnostics)
```

!!! warning "Override parameters"
    The Mode-1 override thresholds/gains are **not** in the reference `.mdl` files
    (only Mode 3's coolant→recycle override is). The values in `RICKER_MODE1` follow
    Ricker (1996) §4 and are tuned to hold the 3000 kPa limit; retune them for a
    different plant or operating point.

## 5. Disturbance rejection

```python
import numpy as np
def idv(i): v = np.zeros(28); v[i - 1] = 1.0; return v

result = ClosedLoopSimulation(horizon=24.0).run(disturbances=idv(1))   # A/C ratio step
```

IDV(1), IDV(8) and IDV(13) are rejected indefinitely. IDV(6) (total A-feed loss) is
among the hardest TEP disturbances: the controller sustains the plant well past the
open-loop shutdown time but cannot hold it indefinitely.

A time-varying schedule is also supported:

```python
schedule = lambda t: idv(8) if t >= 1.0 else np.zeros(28)
result = ClosedLoopSimulation(horizon=24.0).run(disturbance_schedule=schedule)
```

## 6. Views, metrics, and the experiment record

The run carries auditable artifacts for data-driven studies:

```python
from tep_studio.control import build_experiment_record, online_control_view

result = ClosedLoopSimulation(horizon=24.0).run()

# Regulatory metrics, accumulated at full resolution (not downsampled):
print(result.metrics["iae"]["reactor_pressure"])
print(result.metrics["constraint_violation_steps"])
print(result.metrics["production_rate_mean"])

# Causal online view (only the measurements the controller may read at time k):
view = online_control_view(result.results[-1].measurements)

# Reproducible record (principle P6): source revision, process/config hashes,
# seed, solver settings, setpoints, gains, metrics, and the model-leakage policy.
record = build_experiment_record(result, controller, simulator=sim)
print(record.to_json())
```

## 7. Run the example

```bash
PYTHONPATH=src python3 src/tep_studio/control/examples/ricker_mode1_closed_loop.py
```

It runs the closed loop for 24 h, prints the stability outcome and metrics, and emits
the experiment record.

## 8. Paper-style figures

Render the closed-loop figures (PNG/PDF/SVG plus a source CSV each), alongside the
base-case validation figures:

```bash
PYTHONPATH=src python3 -m tep_studio.control.figures
```

This writes to `src/tep_studio/simulation/validation_outputs/figures/`:

- `fig_open_vs_closed_pressure` — open-loop pressure runaway/shutdown vs the flat closed-loop trace.
- `fig_closed_loop_stabilization` — 48 h multi-panel trajectory of the controlled variables.
- `fig_disturbance_rejection` — reactor pressure and level under IDV(1), IDV(8), IDV(13) stepped at 1 h.
- `fig_pressure_override` — the high-pressure override capping the reactor under a kinetics upset at high throughput.
