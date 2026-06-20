# Gymnasium and RL

`GymTEPEnv` wraps the simulator in a Gymnasium-compatible environment.

## 1. Create the environment

```python
import numpy as np
from tep_studio import GymTEPEnv

env = GymTEPEnv(control_interval=0.01, horizon=24.0)
```

## 2. Reset

```python
obs, info = env.reset(seed=123)

print(obs.shape)
print(info["shutdown_status"])
```

Expected observation shape:

```text
(41,)
```

## 3. Step

```python
action = np.array([
    63.053, 53.98, 24.644, 61.302, 22.21, 40.064,
    38.10, 46.534, 47.446, 41.106, 18.114, 50.0,
])

next_obs, reward, terminated, truncated, step_info = env.step(action)

print(reward)
print(terminated, truncated)
print(step_info["constraint_margins"])
```

The environment uses the Gymnasium five-return step signature:

```python
obs, reward, terminated, truncated, info = env.step(action)
```

## Action and observation spaces

The action space is:

```python
env.action_space
```

It is a 12-dimensional `Box` from `0` to `100`.

The observation space is:

```python
env.observation_space
```

It is a 41-dimensional `Box`.

## Termination and truncation

The environment uses:

- `terminated=True` when the process shuts down;
- `truncated=True` when the horizon is reached and the process has not already terminated.

This distinction is important for RL algorithms. A process shutdown is an endogenous process event. A horizon cutoff is an experiment-design choice.

## Default reward

The built-in reward is only a demonstration reward. It penalizes reactor pressure limit violation and action deviation from 50 percent.

For a real control or RL study, define your own reward and document:

- economic objective or tracking objective;
- safety constraints;
- shutdown handling;
- disturbance distribution;
- initial-condition distribution;
- baseline controllers;
- train, validation, and test scenarios.
