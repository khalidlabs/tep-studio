# Optimization

`OptimizationAdapter` supports deterministic finite-horizon rollout around the core simulator.

It is useful for MPC-style experiments, objective testing, and local finite-difference gradients.

## 1. Create the adapter

```python
import numpy as np
from tep_studio import OptimizationAdapter, TennesseeEastmanProcess

sim = TennesseeEastmanProcess()
sim.reset(seed=1431655765)

adapter = OptimizationAdapter(sim)
```

## 2. Roll out an action plan

An action plan has shape `(horizon, 12)`:

```python
action = np.array([
    63.053, 53.98, 24.644, 61.302, 22.21, 40.064,
    38.10, 46.534, 47.446, 41.106, 18.114, 50.0,
])

action_plan = np.tile(action, (5, 1))

rollout = adapter.rollout(action_plan, control_interval=0.001)

print(len(rollout.results))
print(rollout.objective)
print(rollout.terminated)
```

The adapter snapshots the simulator before the rollout and restores it afterward. The candidate rollout does not permanently advance `sim.time`.

## 3. Use a custom objective

```python
def objective(result):
    pressure_violation = max(0.0, -result.constraint_margins["reactor_pressure_high"])
    action_penalty = np.mean(((result.implemented_action - 50.0) / 50.0) ** 2)
    return 1000.0 * pressure_violation + action_penalty

adapter = OptimizationAdapter(sim, objective=objective)
rollout = adapter.rollout(action_plan, control_interval=0.001)
```

The objective receives each `AdvanceResult`, so it can use measurements, states, action saturation, constraint margins, shutdown status, and objective monitor terms.

## 4. Compute a finite-difference gradient

```python
gradient = adapter.finite_difference_gradient(
    action_plan[:1],
    control_interval=0.001,
    epsilon=1e-4,
)

print(gradient.shape)
```

Expected shape:

```text
(1, 12)
```

## Important limitation

The adapter declares:

```python
OptimizationAdapter.differentiability
```

Current value:

```text
finite_difference_only
```

The simulator includes event logic, hard shutdowns, random disturbances, and legacy native code. Do not assume automatic differentiation compatibility or globally smooth objectives.
