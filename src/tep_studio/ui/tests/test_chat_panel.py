from __future__ import annotations

import pytest

pytest.importorskip("dash")


def _string_ids(component) -> set[str]:
    found: set[str] = set()
    cid = getattr(component, "id", None)
    if isinstance(cid, str):
        found.add(cid)
    children = getattr(component, "children", None)
    if children is not None:
        if not isinstance(children, (list, tuple)):
            children = [children]
        for child in children:
            found |= _string_ids(child)
    return found


def test_assistant_tab_is_wired_into_the_app() -> None:
    from tep_studio.ui import create_app

    app = create_app()
    ids = _string_ids(app.layout)
    assert {"chat-log", "chat-input", "chat-send-btn", "chat-status", "chat-history"} <= ids
    # the send callback must be registered (Output chat-log.children)
    assert any("chat-log.children" in key for key in app.callback_map), "chat send callback not registered"


def test_chat_tab_builds_without_agent_extra() -> None:
    # The tab renders even if anthropic/mcp are absent (they are touched only on send).
    from tep_studio.ui.chat_panel import chat_tab

    assert _string_ids(chat_tab()) >= {"chat-log", "chat-input", "chat-send-btn"}
