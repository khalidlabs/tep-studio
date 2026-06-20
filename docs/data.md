# Working with Data

Use `TrajectoryDataset` when you want simulator results as a table.

## 1. Generate a short trajectory

```python
import numpy as np
from tep_studio import TennesseeEastmanProcess, TrajectoryDataset

action = np.array([
    63.053, 53.98, 24.644, 61.302, 22.21, 40.064,
    38.10, 46.534, 47.446, 41.106, 18.114, 50.0,
])

sim = TennesseeEastmanProcess()
sim.reset(seed=1431655765)

results = []
for _ in range(25):
    result = sim.advance(action, control_interval=0.01)
    results.append(result)
    if result.shutdown_status["terminated"]:
        break
```

## 2. Convert results into a dataset

```python
dataset = TrajectoryDataset.from_results(
    results,
    run_id="run_001",
    scenario_id="mode1_short",
)

frame = dataset.to_pandas()
print(frame.shape)
print(frame.columns[:10])
```

The current one-step result has columns for:

- run and scenario IDs;
- sample index;
- `time`, `time_start`, `time_end`, and `control_interval`;
- shutdown status;
- 41 measurements;
- 50 states;
- 12 requested actions;
- 12 implemented actions;
- 28 disturbances.

## 3. Save to CSV

```python
dataset.to_csv("mode1_short.csv")
```

CSV is the most portable format and is easy to inspect in spreadsheet tools.

## 4. Save to Parquet

```python
dataset.to_parquet("mode1_short.parquet")
```

Parquet requires an installed Parquet engine such as `pyarrow` or `fastparquet`. If this fails, use CSV or install one of those packages.

## 5. Get NumPy arrays

```python
Y, y_columns = dataset.to_numpy("measurements")
X, x_columns = dataset.to_numpy("states")
U, u_columns = dataset.to_numpy("implemented_actions")
D, d_columns = dataset.to_numpy("disturbances")
```

The column names are returned with the arrays so you can keep track of physical meaning.

## 6. Build supervised-learning samples

The safest rule is: use past measurements and the action for the next interval to predict the next measurement.

```python
measurement_cols = [c for c in frame.columns if c.startswith("measurement.")]
input_cols = [c for c in frame.columns if c.startswith("implemented_action.")]

window = 5
features = []
targets = []

for k in range(window - 1, len(frame) - 1):
    y_hist = frame.loc[k - window + 1:k, measurement_cols].to_numpy()
    u_next_interval = frame.loc[k + 1, input_cols].to_numpy()
    y_next = frame.loc[k + 1, measurement_cols].to_numpy()

    features.append(np.concatenate([y_hist.ravel(), u_next_interval]))
    targets.append(y_next)

X = np.asarray(features, dtype=float)
Y_next = np.asarray(targets, dtype=float)
```

Do not include future measurements or future disturbances unless your task explicitly says they are available forecasts.

## 7. Build offline-RL transitions

```python
transitions = []

for k in range(len(frame) - 1):
    obs = frame.loc[k, measurement_cols].to_numpy(dtype=float)

    interval = frame.loc[k + 1]
    action = interval[input_cols].to_numpy(dtype=float)
    next_obs = interval[measurement_cols].to_numpy(dtype=float)
    terminated = bool(interval["terminated_at_end"])
    truncated = False

    reward = -float(np.mean(((action - 50.0) / 50.0) ** 2))

    info = {
        "time_start": float(interval["time_start"]),
        "time_end": float(interval["time_end"]),
        "shutdown_code": float(interval["shutdown_code"]),
    }

    transitions.append((obs, action, reward, next_obs, terminated, truncated, info))
```

This reward is only an example. For a real study, define the reward, constraints, disturbance policy, data coverage, and evaluation procedure before training.
