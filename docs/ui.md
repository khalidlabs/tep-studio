# Interface (Simulation Studio)

A Dash + Plotly web interface for running, visualizing, and exporting TEP
simulations interactively — open/closed-loop runs, disturbance scenarios, step
tests, dataset generation, run comparison, and scenario save/load.

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
  activation time — they step on at that time.
- **Plot**: choose which measurements to show; setpoints (dotted) and constraint
  limits (dashed, e.g. the 3000 kPa reactor-pressure trip) are overlaid, and a
  marker is drawn at any shutdown. A manipulated-variable panel is shown below.
- **Save / Load scenario**: download the current configuration as JSON, or upload
  one to reproduce a run exactly.

### Step Test
Apply a step to a manipulated variable (open loop) or a controller setpoint (closed
loop) at a chosen time and view the drive signal and the measured response. (This
visualizes the response; it does not fit a process model.)

### Dataset
Select stored runs and export them as **CSV** or **Parquet** (one tidy table with
`run_id`/`scenario_id` columns). The **Batch** panel sweeps seeds and, optionally,
one parameter (e.g. `setpoints.production_rate` over several values), producing many
runs plus a per-run metrics table — download the combined dataset and the metrics.

### Compare
Overlay a chosen variable across every stored run (e.g. with vs without a
disturbance, or two controller configurations).

### Metrics / Record
For the selected run: regulatory metrics (IAE per controlled variable, constraint
violations, time-to-shutdown, operating cost, mean production) and the reproducible
**experiment record** (P6: source revision, process/config hashes, seed, solver
settings, setpoints, model-leakage policy) — downloadable as JSON.

## Programmatic backend

The interface is a thin layer over a Dash-free, importable backend, so the same
runs and exports are scriptable without the browser:

```python
from tep_studio.ui import ScenarioConfig, run_scenario, build_dataset

run = run_scenario(ScenarioConfig(loop_type="closed", horizon=24.0, control_interval=0.0005))
print(run.metrics["iae"]["reactor_pressure"], run.peak["reactor_pressure_max"])

payload, filename = build_dataset([run], fmt="csv")
open(filename, "wb").write(payload)
```

`ScenarioConfig` is the unit of save/load and batch sweeps; it validates IDV / MV /
setpoint names against the schema and is JSON round-trippable.
