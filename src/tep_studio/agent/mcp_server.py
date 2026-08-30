"""A Model Context Protocol (MCP) server exposing the TEP simulator as tools.

The tools are the shared :class:`~tep_studio.agent.tools.TepToolset` bound to a
process-local store; the server factory (:func:`build_server`) and entry point
(:func:`main`) import ``mcp`` lazily, so the tool functions remain importable and
unit-testable without the ``mcp`` SDK installed.

Run with the ``tep-mcp`` console script (stdio transport) after ``pip install
".[agent]"``. Point any MCP client at it via the standard mcpServers config:

    {"mcpServers": {"tep-studio": {"command": "tep-mcp"}}}
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from tep_studio.agent.tools import INSTRUCTIONS, TepToolset

# One process-local toolset/store per server process (one client session each).
_TOOLSET = TepToolset(capacity=100)

# Module-level tool callables (bound to the shared toolset) — the MCP tool names
# and the unit-test entry points.
describe_plant = _TOOLSET.describe_plant
run_scenario = _TOOLSET.run_scenario
run_sweep = _TOOLSET.run_sweep
get_run = _TOOLSET.get_run
get_run_series = _TOOLSET.get_run_series
list_runs = _TOOLSET.list_runs
compare_runs = _TOOLSET.compare_runs


def _traced_tool(fn, trace_path: Path):
    """Wrap one MCP tool with append-only observable request/result tracing."""
    @wraps(fn)
    def traced(*args, **kwargs):
        request = {"args": args, "kwargs": kwargs}
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            _append_trace(trace_path, {"event": "tool_error", "tool": fn.__name__, "request": request, "error": f"{type(exc).__name__}: {exc}"})
            raise
        _append_trace(trace_path, {"event": "tool_exchange", "tool": fn.__name__, "request": request, "result": result})
        return result
    return traced


def _append_trace(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **payload}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def build_server():
    """Construct the FastMCP server with all tools registered. Imports ``mcp`` lazily."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("tep-studio", instructions=INSTRUCTIONS)
    functions = (describe_plant, run_scenario, run_sweep, get_run, get_run_series, list_runs, compare_runs)
    trace_value = os.environ.get("TEP_MCP_TRACE_PATH")
    if trace_value:
        trace_path = Path(trace_value).expanduser().resolve()
        _append_trace(trace_path, {"event": "server_started", "instructions": INSTRUCTIONS, "tools": [fn.__name__ for fn in functions]})
        functions = tuple(_traced_tool(fn, trace_path) for fn in functions)
    for fn in functions:
        server.tool()(fn)
    return server


def main() -> None:
    """Entry point for the ``tep-mcp`` console script (stdio transport)."""
    build_server().run()


if __name__ == "__main__":
    main()
