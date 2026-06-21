"""Unit tests for the MCP tool implementations (no ``mcp`` SDK required)."""

from __future__ import annotations

import pytest

from tep_studio.agent import mcp_server as m


def _tiny_closed() -> dict:
    """A fast, stable closed-loop config for smoke-testing the run path."""
    return {"name": "t", "loop_type": "closed", "horizon": 0.2, "control_interval": 0.05}


def test_describe_plant_catalogs():
    info = m.describe_plant()
    assert len(info["disturbances"]) == 28
    assert len(info["manipulated_variables"]) == 12
    assert len(info["measurements"]) == 41
    assert "mode1" in info["modes"]
    assert info["disturbances"][0]["name"] == "idv_01"
    assert "reactor_pressure" in {v["name"] for v in info["measurements"]}
    assert "loop_type" in info["scenario_config_fields"]


def test_run_scenario_ok_and_reproducible():
    out = m.run_scenario(_tiny_closed())
    assert out["ok"] is True
    assert out["run_id"].startswith("closed_")
    assert out["loop_type"] == "closed"
    assert out["mode"] == "mode1"
    # The exact config is echoed for reproducibility and round-trips through the schema.
    assert out["config"]["horizon"] == 0.2
    from tep_studio.ui import ScenarioConfig

    ScenarioConfig.from_dict(out["config"])  # must validate


def test_run_scenario_invalid_disturbance_is_a_repairable_error():
    out = m.run_scenario({**_tiny_closed(), "disturbances": [{"idv": "idv_99"}]})
    assert out["ok"] is False
    assert "idv_99" in out["error"]
    assert "hint" in out


def test_run_scenario_rejects_runaway_horizon():
    out = m.run_scenario({"horizon": 10_000})
    assert out["ok"] is False
    assert "horizon" in out["error"]


def test_get_run_and_series_roundtrip():
    run_id = m.run_scenario(_tiny_closed())["run_id"]

    got = m.get_run(run_id)
    assert got["ok"] is True
    assert any(c.startswith("measurement.") for c in got["measurement_columns"])

    series = m.get_run_series(run_id, ["reactor_pressure"], max_points=50)
    assert series["ok"] is True
    assert len(series["time_h"]) == len(series["series"]["reactor_pressure"])
    assert series["n_points"] <= 50
    # full column names resolve too
    assert m.get_run_series(run_id, ["measurement.reactor_pressure"])["ok"] is True


def test_get_run_unknown_id():
    out = m.get_run("nope")
    assert out["ok"] is False
    assert "known_run_ids" in out


def test_get_run_series_unknown_variable():
    run_id = m.run_scenario(_tiny_closed())["run_id"]
    out = m.get_run_series(run_id, ["not_a_variable"])
    assert out["ok"] is False
    assert "available_measurements" in out


def test_list_and_compare_runs():
    a = m.run_scenario({**_tiny_closed(), "name": "a"})["run_id"]
    b = m.run_scenario({**_tiny_closed(), "name": "b"})["run_id"]

    listed = m.list_runs()
    assert listed["ok"] is True
    assert {a, b} <= {r["run_id"] for r in listed["runs"]}

    cmp = m.compare_runs([a, b, "ghost"])
    assert {r["run_id"] for r in cmp["runs"]} == {a, b}
    assert cmp["missing_run_ids"] == ["ghost"]


def test_build_server_registers_tools():
    pytest.importorskip("mcp")
    server = m.build_server()
    assert server is not None
