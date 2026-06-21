# LLM / Agent Integration

TEP Studio exposes the simulator to large language models as a small set of
**tools grounded in the process schema**, so an agent can configure, run, and
inspect simulations the same way a person uses the studio. There are two surfaces
over one shared toolset:

- a **Model Context Protocol (MCP) server** (`tep-mcp`) for MCP clients such as
  Claude Desktop, Claude Code, or any agent framework; and
- an **Assistant tab** inside the web studio — chat that drives the real figures.

Both are backed by `tep_studio.agent.tools.TepToolset`, so the tools behave
identically whichever surface you use.

## Install

```bash
pip install "tep-studio[agent]"          # mcp + anthropic
pip install "tep-studio[ui,agent]"       # also the web studio (for the Assistant tab)
```

The tool *logic* needs only the core dependencies; `mcp` is used by the server and
`anthropic` by the chat loop, both imported lazily.

## The tools

| Tool | Purpose |
| --- | --- |
| `describe_plant` | The schema catalog — disturbances (IDVs), measurements, manipulated variables, setpoints, modes, and the `ScenarioConfig` fields. **Call this first.** |
| `run_scenario(config)` | Validate a `ScenarioConfig` dict, run it, and return a `run_id` + compact summary. The exact config is echoed back for reproducibility. |
| `get_run(run_id)` | Summary, config, and available plot columns for a prior run. |
| `get_run_series(run_id, variables)` | Downsampled time series for named variables. |
| `list_runs` / `compare_runs(run_ids)` | List and contrast cached runs. |

Three properties make this more than a chatbot:

- **Schema-grounded.** Names come from `TEP_SCHEMA`; `describe_plant` tells the
  model exactly what is valid.
- **Validation is the repair loop.** `run_scenario` calls
  `ScenarioConfig.from_dict`, which validates names and bounds and returns a
  descriptive error (`{"ok": false, "error": ...}`) the model can fix and retry.
- **Summaries + handles, never raw trajectories.** Runs are cached server-side;
  tools return a `run_id` and a small summary, and series are fetched on demand.

## MCP server

Run the server (stdio transport):

```bash
tep-mcp
```

Connect a client. **Claude Desktop** (`claude_desktop_config.json`):

```json
{ "mcpServers": { "tep-studio": { "command": "tep-mcp" } } }
```

**Claude Code:**

```bash
claude mcp add tep-studio -- tep-mcp
```

Then ask, for example:

> Describe the plant, then run Mode 1 closed-loop with IDV13 starting at 2 h for
> 10 hours and tell me the peak reactor pressure. Compare it to the same run
> without the disturbance.

The agent calls `describe_plant`, builds a `ScenarioConfig`, runs it, and reads
the summaries back — fixing its own config if a name or bound is wrong.

## Assistant tab (in the studio)

Launch the studio and open the **Assistant** tab:

```bash
export ANTHROPIC_API_KEY=sk-ant-...      # required for the assistant
python -m tep_studio.ui                  # or: tep-ui
```

The chat uses the same tools, bound to the studio's run store. When the assistant
runs a scenario, the run is cached and the **Simulate plots, Compare table, and
Metrics/Record lists refresh** exactly as if you had launched it from the form —
and the run is rendered inline in the chat with the real trajectory grid. Without
a key (or the `agent` extra), the tab still renders and shows a friendly status
line; only sending a message needs the key.

Set `TEP_AGENT_MODEL` to choose the model (default: `claude-sonnet-4-6`).

## Programmatic use

The toolset is usable directly, without MCP or the chat loop:

```python
from tep_studio.agent.tools import TepToolset

tools = TepToolset()
tools.describe_plant()["disturbances"][:2]
out = tools.run_scenario({"loop_type": "closed", "horizon": 10,
                          "disturbances": [{"idv": "idv_13", "start_time": 2.0}]})
print(out["run_id"], out["peak_reactor_pressure"], out["shutdown"])
series = tools.get_run_series(out["run_id"], ["reactor_pressure"])
```

To drive a model yourself, `TepToolset.tool_specs()` returns Anthropic-format tool
definitions and `TepToolset.dispatch(name, arguments)` executes a tool call;
`tep_studio.agent.chat.respond(history, text, toolset)` runs a full tool-use turn.

## Safety notes

This is a **simulation** front-end: the tools configure and run the model, they do
not actuate anything real. Horizons are capped for interactive use, and the model
never manipulates valves directly — it builds validated scenarios. For
control-in-the-loop research, drive the registered Gymnasium environment instead.
