# First Simulation

This page walks through a minimal simulation script.

## 1. Create the simulator

Start Python from the repository root:

```bash
PYTHONPATH=src python3
```

Import the simulator:

```python
from tep_studio import TEP_SCHEMA, TennesseeEastmanProcess
```

Create a simulator instance:

```python
sim = TennesseeEastmanProcess()
```

## 2. Reset the process

Reset initializes the native model and returns the first 41 measurements:

```python
obs, info = sim.reset(seed=1431655765)

print(obs.shape)
print(info["time"])
print(info["shutdown_status"])
```

Expected shape:

```text
(41,)
```

The status should show that the process has not terminated.

## 3. Define an action by manipulated-variable names

The simulator action is a 12-element manipulated-variable vector. Values are percentages and are clipped to the range `0` to `100`.

```python
action = TEP_SCHEMA.vector(
    "mvs",
    {
        "d_feed_valve": 63.053,
        "e_feed_valve": 53.98,
        "a_feed_valve": 24.644,
        "ac_feed_valve": 61.302,
        "compressor_recycle_valve": 22.21,
        "purge_valve": 40.064,
        "separator_underflow_valve": 38.10,
        "stripper_underflow_valve": 46.534,
        "stripper_steam_valve": 47.446,
        "reactor_cooling_water_valve": 41.106,
        "separator_cooling_water_valve": 18.114,
        "reactor_agitator_speed": 50.0,
    },
)
```

## 4. Advance one control interval

Advance the process by `0.01 h`:

```python
result = sim.advance(action, control_interval=0.01)

print(result.time_start, result.time_end)
print(result.measurements.shape)
print(result.state.shape)
print(result.shutdown_status)

measurements = TEP_SCHEMA.to_dict("measurements", result.measurements)
print(measurements["reactor_pressure"])
print(measurements["reactor_level"])
```

Expected shapes:

```text
(41,)
(50,)
```

The result is an end-of-interval record. The measurements and state are from `time_end`. The action and disturbances stored in the result are the inputs used over the interval from `time_start` to `time_end`.

## 5. Inspect safety margins

The simulator reports continuous margins for key operating limits:

```python
for name, margin in result.constraint_margins.items():
    print(name, margin)
```

A negative high-limit margin means the limit has been exceeded. For example, a negative `reactor_pressure_high` margin means reactor pressure is above the high-pressure limit.

## 6. Run until shutdown

The R12 open-loop action below is expected to produce a high reactor pressure shutdown:

```python
r12_action = TEP_SCHEMA.update_vector(
    "mvs",
    action,
    {
        "d_feed_valve": 63.53,
        "reactor_cooling_water_valve": 38.0,
    },
)

sim = TennesseeEastmanProcess()
sim.reset(seed=1431655765)

while sim.time < 5.0:
    result = sim.advance(r12_action, control_interval=0.01)
    if result.shutdown_status["terminated"]:
        print("terminated at h:", result.time)
        print(result.shutdown_status)
        break
```

Expected behavior in the current repository: termination near `1.07 h` with shutdown code `1` and the high reactor pressure message.
