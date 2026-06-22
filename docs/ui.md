# Interface (Simulation Studio)

A Dash + Plotly web interface for running, visualizing, and exporting TEP
simulations interactively: open/closed-loop runs, disturbance scenarios, dataset
generation, run comparison, and scenario save/load.

## Install and launch

```bash
python3 -m pip install -e ".[ui]"
python3 -m tep_studio.ui            # or: tep-ui
```

Then open <http://127.0.0.1:8050>. Options: `--host`, `--port`, `--debug`.

## Tabs

### Simulate
Configure and run a scenario, then read the trajectory interactively.

- **Loop**: closed loop (decentralized controller) or open loop (manual valves).
- **Fidelity**: *Explore* (Δt = 0.01 h, a few seconds) or *Fidelity* (Δt = 0.0005 h,
  matching the reference). Horizon is the main driver of run time.
- **Controller** (closed loop): toggle composition trims, overrides, and the %G
  feedback; edit the nine setpoints directly.
- **Open loop**: 12 valve sliders (default = the Mode-1 base case `u0`).
- **Disturbances**: pick any of the 28 IDVs (shown with descriptions) and an
  activation time; they step on at that time. A magnitude input (0–1) appears
  for each selected IDV (default 1.0), so you can apply partial disturbances.
- **Advanced solver** (collapsible): choose the integrator (`RK4` or `Euler`
  fixed-step, or `RK45` / `RK23` adaptive SciPy) and set `rtol` / `atol`
  (adaptive only), the `fixed_step` substep, and `record_every` (0 = auto
  downsampling). The defaults reproduce the standard run, so you only open this when
  you need to.
- **Plot**: choose which measurements to show; setpoints (dotted) and constraint
  limits (dashed, e.g. the 3000 kPa reactor-pressure trip) are overlaid, and a
  marker is drawn at any shutdown. A manipulated-variable panel is shown below.
- **Save / Load scenario**: download the current configuration as JSON, or upload
  one to reproduce a run exactly. (Loading restores the solver/record settings and
  the disturbance selection; per-disturbance magnitudes currently reset to 1.0.)
- If a run can't start (for example, an invalid configuration), a red banner
  explains why instead of failing silently. The same applies to batch runs.

### Dataset
Select stored runs and export them as CSV, Parquet, or JSON (one tidy
table with `run_id`/`scenario_id` columns). The Batch panel sweeps seeds and,
optionally, one parameter (either a setpoint, e.g. `setpoints.production_rate`, or a
top-level numeric field such as `horizon`, `control_interval`, `fixed_step`) over several
values, producing many runs plus a per-run metrics table; download the combined
dataset and the metrics.

### Compare
Overlay one or more variables across every stored run (e.g. with vs without a
disturbance, or two controller configurations); selecting several variables stacks
one panel per variable. The run table is sortable and filterable, a clipboard button
copies all run IDs, and a capacity indicator shows how many runs are cached
(`used/cap`) and warns as the in-memory store nears or hits its limit (oldest runs
are then evicted, LRU).

### Metrics / Record
For the selected run, a metric-card grid summarizes the outcome: terminated / final
time, time-to-shutdown, peak reactor pressure and its margin to the 3000 kPa
trip, level margins, constraint violations, operating cost, and mean production. These sit
above a per-controlled-variable table of IAE and ISE. A clipboard button copies
the run ID. Below it, the reproducible experiment record (P6: source revision,
process/config hashes, seed, solver settings, setpoints, model-leakage policy) is
shown and downloadable as JSON.

## Look and layout

A single light theme is defined in `tep_studio/ui/theme.py`: color, typography, and
spacing tokens, shared component styles, and a registered `"tep"` Plotly template so
the chrome and the plots share one palette, with the global CSS in the app's index
template. The layout is responsive: the configuration sidebar stacks above the
results on narrow screens (below ~880 px), and every plot exports a high-resolution
PNG from its toolbar.

## Programmatic backend

The interface is a thin layer over a Dash-free, importable backend, so the same
runs and exports are scriptable without the browser:

```python
from tep_studio.ui import ScenarioConfig, run_scenario, build_dataset

run = run_scenario(ScenarioConfig(loop_type="closed", horizon=24.0, control_interval=0.0005))
print(run.metrics["iae"]["reactor_pressure"], run.metrics["ise"]["reactor_pressure"])
print(run.metrics["time_to_shutdown"], run.peak["reactor_pressure_max"])

payload, filename = build_dataset([run], fmt="json")   # or "csv" / "parquet"
open(filename, "wb").write(payload)
```

`ScenarioConfig` is the unit of save/load and batch sweeps; it validates IDV / MV /
setpoint names against the schema and is JSON round-trippable. `run.metrics` holds
`iae` and `ise` per controlled variable plus `time_to_shutdown`, and `build_dataset`
accepts `fmt="csv"`, `"parquet"`, or `"json"`.
