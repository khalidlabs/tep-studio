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

from tep_studio.agent.tools import INSTRUCTIONS, TepToolset

# One process-local toolset/store per server process (one client session each).
_TOOLSET = TepToolset(capacity=100)

# Module-level tool callables (bound to the shared toolset) — the MCP tool names
# and the unit-test entry points.
describe_plant = _TOOLSET.describe_plant
run_scenario = _TOOLSET.run_scenario
get_run = _TOOLSET.get_run
get_run_series = _TOOLSET.get_run_series
list_runs = _TOOLSET.list_runs
compare_runs = _TOOLSET.compare_runs


def build_server():
    """Construct the FastMCP server with all tools registered. Imports ``mcp`` lazily."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("tep-studio", instructions=INSTRUCTIONS)
    for fn in (describe_plant, run_scenario, get_run, get_run_series, list_runs, compare_runs):
        server.tool()(fn)
    return server


def main() -> None:
    """Entry point for the ``tep-mcp`` console script (stdio transport)."""
    build_server().run()


if __name__ == "__main__":
    main()
