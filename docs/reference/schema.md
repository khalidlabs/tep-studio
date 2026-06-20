# Process Schema

`TEP_SCHEMA` turns legacy arrays into named process quantities.

```python
from tep_studio import TEP_SCHEMA
```

This page documents the **in-code** schema (the runtime name↔index map). It is distinct from the standalone JSON Schema deliverable under `research/schema/` (`research/schema/process_description.schema.json` + `research/schema/examples/cstr_minimal.json`), which is the machine-readable process-description format described by the design principles.

## Schema counts

| Group | Count | Use |
| --- | ---: | --- |
| States | 50 | Dynamic state vector. |
| Standard measurements | 41 | Main observation vector. |
| Manipulated variables | 12 | Direct action vector. |
| Disturbances | 28 | Disturbance activation vector. |
| Additional measurements | 32 | Modified-TEP additional measurement array. |
| Disturbance monitors | 21 | Noise-free disturbance monitor outputs. |
| Process monitors | 62 | Internal process monitor outputs, including operating-cost entries. |
| Concentration monitors | 96 | Component concentration monitor outputs. |

## Variable metadata

Each variable stores:

| Field | Meaning |
| --- | --- |
| `name` | Python-friendly variable name. |
| `unit` | Reported unit. |
| `role` | Variable group. |
| `index` | Zero-based Python index. |
| `description` | Process description. |
| `lower`, `upper`, `nominal` | Optional bound and nominal metadata. |
| `available_online` | Whether the variable is available online according to the schema. |
| `legacy_symbol`, `legacy_index` | Original legacy identifier when available. |
| `stream`, `component`, `physical_type` | Process context when available. |
| `measurement_noise`, `sample_period` | Measurement annotations when available. |

## Manipulated variables

| Index | Name | Description |
| ---: | --- | --- |
| 0 | `d_feed_valve` | Valve position for feed component D, stream 2. |
| 1 | `e_feed_valve` | Valve position for feed component E, stream 3. |
| 2 | `a_feed_valve` | Valve position for feed component A, stream 1. |
| 3 | `ac_feed_valve` | Valve position for feed components A and C, stream 4. |
| 4 | `compressor_recycle_valve` | Compressor recycle valve position. |
| 5 | `purge_valve` | Purge valve position, stream 9. |
| 6 | `separator_underflow_valve` | Separator underflow valve position, stream 10. |
| 7 | `stripper_underflow_valve` | Stripper underflow valve position, stream 11. |
| 8 | `stripper_steam_valve` | Stripper steam valve position. |
| 9 | `reactor_cooling_water_valve` | Reactor cooling-water outlet valve position. |
| 10 | `separator_cooling_water_valve` | Separator cooling-water outlet valve position. |
| 11 | `reactor_agitator_speed` | Reactor agitator speed. |

## Standard measurements

| Index | Name | Unit |
| ---: | --- | --- |
| 0 | `feed_A_flow` | kscmh |
| 1 | `feed_D_flow` | kg/h |
| 2 | `feed_E_flow` | kg/h |
| 3 | `feed_AC_flow` | kscmh |
| 4 | `recycle_flow` | kscmh |
| 5 | `reactor_feed_flow` | kscmh |
| 6 | `reactor_pressure` | kPa gauge |
| 7 | `reactor_level` | % |
| 8 | `reactor_temperature` | degC |
| 9 | `purge_flow` | kscmh |
| 10 | `separator_temperature` | degC |
| 11 | `separator_level` | % |
| 12 | `separator_pressure` | kPa gauge |
| 13 | `separator_underflow` | m3/h |
| 14 | `stripper_level` | % |
| 15 | `stripper_pressure` | kPa gauge |
| 16 | `stripper_underflow` | m3/h |
| 17 | `stripper_temperature` | degC |
| 18 | `stripper_steam_flow` | kg/h |
| 19 | `compressor_work` | kW |
| 20 | `reactor_cooling_water_outlet_temperature_meas` | degC |
| 21 | `condenser_cooling_water_outlet_temperature` | degC |
| 22-27 | `reactor_feed_*_concentration` | mol % |
| 28-35 | `purge_*_concentration` | mol % |
| 36-40 | `stripper_underflow_*_concentration` | mol % |

## Disturbances

| Index | Name | Description |
| ---: | --- | --- |
| 0 | `idv_01` | A/C ratio of stream 4, B composition constant. |
| 1 | `idv_02` | B composition of stream 4, A/C ratio constant. |
| 2 | `idv_03` | D feed temperature. |
| 3 | `idv_04` | Reactor cooling-water inlet temperature. |
| 4 | `idv_05` | Separator cooling-water inlet temperature. |
| 5 | `idv_06` | A feed loss. |
| 6 | `idv_07` | C header pressure loss. |
| 7 | `idv_08` | Random A/B/C composition of stream 4. |
| 8 | `idv_09` | Random D feed temperature. |
| 9 | `idv_10` | Random C feed temperature. |
| 10 | `idv_11` | Random reactor cooling-water inlet temperature. |
| 11 | `idv_12` | Random separator cooling-water inlet temperature. |
| 12 | `idv_13` | Reaction kinetics drift. |
| 13 | `idv_14` | Reactor cooling-water valve stiction. |
| 14 | `idv_15` | Separator cooling-water valve stiction. |
| 15 | `idv_16` | Random stripper heat-transfer deviation. |
| 16 | `idv_17` | Random reactor heat-transfer deviation. |
| 17 | `idv_18` | Random condenser heat-transfer deviation. |
| 18 | `idv_19` | Valve stiction group. |
| 19 | `idv_20` | Unknown random disturbance. |
| 20 | `idv_21` | Random A feed temperature. |
| 21 | `idv_22` | Random E feed temperature. |
| 22 | `idv_23` | Random A feed pressure/flow. |
| 23 | `idv_24` | Random D feed pressure/flow. |
| 24 | `idv_25` | Random E feed pressure/flow. |
| 25 | `idv_26` | Random A and C feed pressure/flow. |
| 26 | `idv_27` | Random reactor cooling-water pressure/flow. |
| 27 | `idv_28` | Random condenser cooling-water pressure/flow. |

## Print schema names

Use this when you need exact column names:

```python
for variable in TEP_SCHEMA.measurements:
    print(variable.index, variable.name, variable.unit)
```

## Named vector helpers

Use the schema helpers to avoid hard-coded array positions:

```python
reactor_pressure_index = TEP_SCHEMA.index("measurements", "reactor_pressure")
reactor_pressure = result.measurements[reactor_pressure_index]

measurements = TEP_SCHEMA.to_dict("measurements", result.measurements)
print(measurements["reactor_pressure"])
```

Build a direct manipulated-variable vector by name:

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

Update selected entries while preserving the rest of a vector:

```python
next_action = TEP_SCHEMA.update_vector(
    "mvs",
    action,
    {"reactor_cooling_water_valve": 38.0},
)
```

The helpers only translate names and array positions. They do not implement feedback control or change the simulator clipping behavior.
