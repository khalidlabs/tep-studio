# LLM / Agent Integration

TEP Studio exposes the simulator to language models as a small set of tools
grounded in the process schema, so an agent can configure, run, and inspect
simulations the same way a person uses the studio. Two surfaces share one toolset:

- an MCP (Model Context Protocol) server, `tep-mcp`, for any MCP-compatible client;
  and
- an Assistant tab in the web studio: a chat that drives the real figures.

Both use `tep_studio.agent.tools.TepToolset`, so the tools behave the same either
way.

## Install

```bash
pip install "tep-studio[agent]"          # adds the mcp and anthropic packages
pip install "tep-studio[ui,agent]"       # also the web studio (for the Assistant tab)
```

The tool logic needs only the core dependencies. `mcp` is used by the server and
`anthropic` by the chat loop; both are imported lazily.

## The tools

| Tool | Purpose |
| --- | --- |
| `describe_plant` | The schema catalog: disturbances (IDVs), measurements, manipulated variables, setpoints, modes, and the `ScenarioConfig` fields. Call this first. |
| `run_scenario(config)` | Validate a `ScenarioConfig` dict, run it, and return a `run_id` and a compact summary. The exact config is echoed back for reproducibility. |
| `get_run(run_id)` | Summary, config, and available plot columns for a prior run. |
| `get_run_series(run_id, variables)` | Downsampled time series for named variables. |
| `list_runs` / `compare_runs(run_ids)` | List and contrast cached runs. |

A few choices keep this reliable rather than free-form:

- Names come from `TEP_SCHEMA`, and `describe_plant` reports exactly what is valid,
  so the model configures from the catalog instead of guessing.
- Validation doubles as the repair loop. `run_scenario` calls
  `ScenarioConfig.from_dict`, which checks names and bounds and returns a
  descriptive error (`{"ok": false, "error": ...}`) the model can read, fix, and
  retry.
- Tools return a `run_id` and a small summary, not raw trajectories. Runs are
  cached server-side, and series are fetched on demand.

## MCP server

Run the server over stdio:

```bash
tep-mcp
```

Then add it to your MCP client's configuration. Most clients use the standard
`mcpServers` block:

```json
{ "mcpServers": { "tep-studio": { "command": "tep-mcp" } } }
```

Restart the client and the TEP tools appear. Then ask, for example:

> Describe the plant, then run Mode 1 closed-loop with IDV13 starting at 2 h for
> 10 hours and tell me the peak reactor pressure. Compare it to the same run
> without the disturbance.

The agent calls `describe_plant`, builds a `ScenarioConfig`, runs it, and reads the
summaries back, fixing its own config if a name or bound is wrong.

## Assistant tab (in the studio)

Launch the studio and open the Assistant tab:

```bash
export ANTHROPIC_API_KEY=sk-ant-...      # required for the assistant
python -m tep_studio.ui                  # or: tep-ui
```

The chat uses the same tools, bound to the studio's run store. When the assistant
runs a scenario, the run is cached and the Simulate plots, Compare table, and
Metrics/Record lists refresh as if you had launched it from the form; the run is
also drawn inline in the chat with the real trajectory grid. Without a key (or the
`agent` extra) the tab still renders and shows a status line; only sending a message
needs the key. You can also paste the key into the Assistant tab instead of setting
the environment variable. Set `TEP_AGENT_MODEL` to choose which model the assistant
uses.

## Programmatic use

The toolset works directly, without MCP or the chat loop:

```python
from tep_studio.agent.tools import TepToolset

tools = TepToolset()
tools.describe_plant()["disturbances"][:2]
out = tools.run_scenario({"loop_type": "closed", "horizon": 10,
                          "disturbances": [{"idv": "idv_13", "start_time": 2.0}]})
print(out["run_id"], out["peak_reactor_pressure"], out["shutdown"])
series = tools.get_run_series(out["run_id"], ["reactor_pressure"])
```

To drive a model yourself, `TepToolset.tool_specs()` returns Messages-API tool
definitions and `TepToolset.dispatch(name, arguments)` executes a tool call;
`tep_studio.agent.chat.respond(history, text, toolset)` runs a full tool-use turn.

## Safety notes

This is a simulation front-end: the tools configure and run the model, they do not
actuate anything real. Horizons are capped for interactive use, and the model never
moves valves directly; it builds validated scenarios. For control-in-the-loop
research, drive the registered Gymnasium environment instead.
