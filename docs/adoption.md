# Adoption Workflow

This page is the shortest reproducible path from a clean environment to an
auditable TEP Studio run. It also identifies the software boundary, public APIs,
and storage formats so that the example can be adapted without reading the native
C implementation.

## 1. Install the interface you need

TEP Studio requires Python 3.10 or newer. A source installation compiles the
bundled C kernel through CFFI, so it also requires a C compiler and standard Python
build tools.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -e .            # core Python, CLI, Gymnasium, data, optimization
python3 -m pip install -e ".[agent]"  # optional MCP server
python3 -m pip install -e ".[ui]"     # optional Dash/Plotly Studio
```

On Windows PowerShell, activate the environment with
`.\.venv\Scripts\Activate.ps1` instead.

The core dependencies are NumPy, SciPy, pandas, Gymnasium, Matplotlib, and CFFI.
The optional agent interface uses the Python MCP SDK, while the bundled chat
adapter also declares the Anthropic SDK; the optional browser interface uses Dash
and Plotly. Exact lower bounds are declared in
`pyproject.toml` and resolved versions can be captured with
`python3 -m pip freeze`.

## 2. Export and validate the process description

The description is executable metadata, not a copied documentation table. Export
the complete canonical JSON together with its content hash and generated checks:

```bash
tep describe --out process_description.json
```

The output contains:

- every state, measurement, manipulated variable, disturbance, and monitor;
- names, units, roles, bounds, legacy identifiers, aliases, online availability,
  analyzer timing, and disturbance metadata;
- requested- and implemented-action semantics and native stochastic-seed scope;
- a `sha256:` process-description hash and a validation result whose `ok` field
  must be `true`.

The same objects are available in Python:

```python
from tep_studio import TEP_SCHEMA, TennesseeEastmanProcess
from tep_studio.control import process_description_hash

assert TEP_SCHEMA.validate()["ok"]
assert TennesseeEastmanProcess().validate()["ok"]
print(process_description_hash())
```

## 3. Run and export a reproducible scenario

Use a native stochastic seed and write the named trajectory to a portable file:

```bash
tep run \
  --loop closed \
  --mode mode1 \
  --horizon 6 \
  --control-interval 0.01 \
  --seed 20260830 \
  --idv idv_01@1.0 \
  --out idv01_run.csv
```

For a multi-seed dataset, use `tep dataset`; Parquet is selected when the output
name ends in `.parquet` and CSV otherwise.

```bash
tep dataset --seeds 1,2,3 --horizon 6 --out three_seed_runs.parquet
```

Record the command, package version (`tep version`), exported process-description
hash, seed, solver, fixed step, control interval, mode, and disturbance schedule
with any reported result.

## 4. Choose a public interface

| Need | Interface | Entry point |
| --- | --- | --- |
| Direct numerical stepping | Python process core | `TennesseeEastmanProcess.reset/advance/snapshot/restore` |
| Closed-loop scenarios | Python controller API | `ClosedLoopSimulation.run` |
| RL interaction | Gymnasium | `gymnasium.make("TennesseeEastman-v0")` |
| Named trajectory data | Python/CLI | `TrajectoryDataset`, `tep run`, `tep dataset` |
| Finite-horizon optimization | Python | `OptimizationAdapter` |
| Reasoning-model access | MCP over standard I/O | `tep-mcp` |
| Interactive exploration | Dash/Plotly | `tep ui` |

All interfaces derive names and bounds from `TEP_SCHEMA`; they do not maintain
separate variable catalogs.

## 5. Connect an MCP client

After installing the `agent` extra, configure an MCP-compatible client to launch:

```json
{
  "mcpServers": {
    "tep-studio": {
      "command": "tep-mcp"
    }
  }
}
```

The server exposes six tools: `describe_plant`, `run_scenario`, `get_run`,
`get_run_series`, `list_runs`, and `compare_runs`. A client should call
`describe_plant` before constructing a scenario. See the [agent guide](agent.md)
for the request fields and an alternative `python -m` launch command.

## 6. Understand storage and deployment

No external database, message broker, or cloud service is required. The numerical
kernel and Python interfaces run in-process. CLI trajectories are ordinary CSV,
Parquet, JSON, or NPZ files depending on the workflow. The MCP toolset keeps a
bounded process-local run cache; restart the server to clear it, and export any run
needed for durable provenance.

The native extension is platform-specific. Rebuild it after moving a source
checkout to another operating system or CPU architecture. The public boundary is
the Python API and process description; CFFI is an internal bridge to the bundled
legacy kernel.

## 7. Acceptance checks

Before using the simulator in a study or adapter, require all of the following:

```bash
tep version
tep describe --out process_description.json
python3 -m pytest -q src/tep_studio/simulation/tests/test_schema_metadata.py
python3 -m tep_studio.simulation.examples.r12_open_loop
```

The description validation must report `ok: true`. The R12 example should end near
1.07 h with a high-reactor-pressure shutdown. These checks establish installation,
schema/kernel agreement, deterministic execution, and event reporting; they do not
validate every operating mode or every downstream controller, estimator, or agent.
