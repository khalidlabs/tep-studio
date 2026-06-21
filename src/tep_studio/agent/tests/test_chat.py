"""Tests for the shared toolset specs/dispatch and the chat tool-use loop.

The chat loop is exercised with a *fake* Anthropic client (a scripted sequence of
responses), so no API key or network is needed; the tool calls run the real
simulator through the toolset.
"""

from __future__ import annotations

import pytest

from tep_studio.agent.chat import make_client, respond
from tep_studio.agent.tools import TepToolset


def _tiny_closed() -> dict:
    return {"name": "t", "loop_type": "closed", "horizon": 0.2, "control_interval": 0.05}


# -- fake Anthropic client -------------------------------------------------
class _FakeResp:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, scripted):
        self._scripted = scripted
        self.calls = 0

    def create(self, **_kwargs):
        resp = self._scripted[self.calls]
        self.calls += 1
        return resp


class _FakeClient:
    def __init__(self, scripted):
        self.messages = _FakeMessages(scripted)


def test_tool_specs_shape():
    specs = TepToolset().tool_specs()
    names = {s["name"] for s in specs}
    assert names == {"describe_plant", "run_scenario", "get_run", "get_run_series", "list_runs", "compare_runs"}
    for s in specs:
        assert s["description"] and s["input_schema"]["type"] == "object"
    run = next(s for s in specs if s["name"] == "run_scenario")
    assert run["input_schema"]["required"] == ["config"]


def test_dispatch_routes_to_tools():
    ts = TepToolset()
    assert len(ts.dispatch("describe_plant", {})["disturbances"]) == 28
    out = ts.dispatch("run_scenario", {"config": _tiny_closed()})
    assert out["ok"] is True
    assert ts.dispatch("get_run", {"run_id": out["run_id"]})["ok"] is True
    assert ts.dispatch("nope", {})["ok"] is False


def test_respond_runs_tools_and_reports_created_runs():
    ts = TepToolset()
    scripted = [
        _FakeResp(
            [{"type": "tool_use", "id": "t1", "name": "run_scenario", "input": {"config": _tiny_closed()}}],
            stop_reason="tool_use",
        ),
        _FakeResp([{"type": "text", "text": "Done — the closed loop stayed stable."}], stop_reason="end_turn"),
    ]
    turn = respond([], "run a short closed-loop scenario", ts, client=_FakeClient(scripted))

    assert turn.tool_calls == ["run_scenario"]
    assert len(turn.created_run_ids) == 1
    assert turn.created_run_ids[0] in ts.store.ids()
    assert "stable" in turn.assistant_text
    # history: user, assistant(tool_use), user(tool_result), assistant(text)
    assert len(turn.history) == 4
    assert turn.history[0]["role"] == "user"
    assert turn.history[-1]["content"][0]["type"] == "text"


def test_make_client_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        make_client()
