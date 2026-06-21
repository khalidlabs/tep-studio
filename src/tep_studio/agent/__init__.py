"""LLM agent integration for TEP Studio (optional ``agent`` extra).

Exposes the simulator as a Model Context Protocol (MCP) server so an LLM can
configure, run, and inspect simulations through tool calls grounded in the
process schema. The tool *implementations* (`describe_plant`, `run_scenario`,
`get_run`, `get_run_series`, `list_runs`, `compare_runs`) are plain functions
over the Dash-free :mod:`tep_studio.ui` backend and import only core
dependencies; only :func:`build_server` / :func:`main` import the ``mcp`` SDK,
and they do so lazily. This keeps the module importable (and unit-testable)
without the ``agent`` extra installed.

Run the server with ``tep-mcp`` (stdio transport) once ``pip install
".[agent]"`` has provided the ``mcp`` package.
"""

from __future__ import annotations

from tep_studio.agent.mcp_server import (
    build_server,
    compare_runs,
    describe_plant,
    get_run,
    get_run_series,
    list_runs,
    main,
    run_scenario,
)

__all__ = [
    "build_server",
    "main",
    "describe_plant",
    "run_scenario",
    "get_run",
    "get_run_series",
    "list_runs",
    "compare_runs",
]
