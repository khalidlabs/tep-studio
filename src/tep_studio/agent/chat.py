"""A minimal Anthropic tool-use loop over the shared :class:`TepToolset`.

:func:`respond` runs one assistant turn: it sends the conversation plus the tool
specs to the Anthropic Messages API, executes any tool calls against the toolset
(reusing the exact tools the MCP server exposes), and loops until the model stops
requesting tools. It returns the updated (JSON-serializable) message history, the
assistant's text, and the ids of any runs created this turn — so the studio can
refresh its figures.

``anthropic`` is imported lazily, and a ``client`` may be injected (tests pass a
fake), so this module imports without the ``agent`` extra installed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from tep_studio.agent.tools import INSTRUCTIONS, TepToolset

DEFAULT_MODEL = "claude-sonnet-4-6"  # fast + strong at tool use; override via TEP_AGENT_MODEL


@dataclass
class ChatTurn:
    history: list[dict]
    assistant_text: str
    created_run_ids: list[str] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)


def make_client(api_key: str | None = None):
    """Construct an Anthropic client (lazy import). Raises a clear error if unconfigured."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it (or pass api_key=) to use the assistant."
        )
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError("The 'anthropic' package is required; install with: pip install 'tep-studio[agent]'.") from exc
    return anthropic.Anthropic(api_key=key)


def respond(
    history: list[dict],
    user_text: str,
    toolset: TepToolset,
    *,
    client=None,
    api_key: str | None = None,
    model: str | None = None,
    max_iters: int = 8,
    max_tokens: int = 1024,
) -> ChatTurn:
    """Run one assistant turn with tool use and return a :class:`ChatTurn`."""
    client = client or make_client(api_key)
    model = model or os.environ.get("TEP_AGENT_MODEL", DEFAULT_MODEL)
    tools = toolset.tool_specs()

    messages: list[dict] = list(history) + [{"role": "user", "content": user_text}]
    created: list[str] = []
    calls: list[str] = []
    texts: list[str] = []

    for _ in range(max_iters):
        resp = client.messages.create(
            model=model, max_tokens=max_tokens, system=INSTRUCTIONS, tools=tools, messages=messages
        )
        content = _content_to_dicts(resp.content)
        messages.append({"role": "assistant", "content": content})
        texts.extend(b.get("text", "") for b in content if b.get("type") == "text")

        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        if getattr(resp, "stop_reason", None) != "tool_use" or not tool_uses:
            break

        results = []
        for tu in tool_uses:
            calls.append(tu["name"])
            result = toolset.dispatch(tu["name"], tu.get("input", {}))
            if tu["name"] == "run_scenario" and result.get("ok"):
                created.append(result["run_id"])
            results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": json.dumps(result)})
        messages.append({"role": "user", "content": results})

    assistant_text = "\n".join(t for t in texts if t).strip() or "(no text response)"
    return ChatTurn(history=messages, assistant_text=assistant_text, created_run_ids=created, tool_calls=calls)


def _content_to_dicts(content) -> list[dict]:
    """Normalize Anthropic content blocks (SDK objects or dicts) to plain JSON dicts."""
    out: list[dict] = []
    for block in content:
        if isinstance(block, dict):
            out.append(block)
        elif hasattr(block, "model_dump"):
            out.append(block.model_dump())
        else:  # minimal fallback
            out.append({"type": getattr(block, "type", "text"), "text": getattr(block, "text", "")})
    return out
