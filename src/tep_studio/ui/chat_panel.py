"""The Assistant tab — a natural-language front-end to the studio.

The chat uses the same :class:`~tep_studio.agent.tools.TepToolset` the MCP server
exposes, bound to the app's ``RunStore``. When the assistant runs a scenario, the
run is cached in that store and the callback writes ``active-run`` / ``session-runs``
(both ``allow_duplicate`` writers), so the Simulate plots and the Compare / Record
lists refresh exactly as if the run had been launched from the form. Runs created
in a turn are also rendered inline with the real :mod:`tep_studio.ui.figures` grid.

``anthropic`` is only touched when the user sends a message (via
:func:`tep_studio.agent.chat.respond`), so this tab renders without the ``agent``
extra installed; a missing key/package surfaces as a friendly status line.
"""

from __future__ import annotations

from dash import Input, Output, State, dcc, html, no_update
from dash.exceptions import PreventUpdate

from tep_studio.ui import figures, theme
from tep_studio.ui.widgets import DEFAULT_PLOT_VARS

_HINT = (
    "Ask in plain English, e.g. “Run Mode 1 closed-loop with IDV13 starting at 2 h for "
    "10 hours and tell me the peak reactor pressure,” or “compare that to the same run "
    "without the disturbance.” The assistant configures and runs the simulator, and the "
    "plots below / the Simulate tab update with its runs."
)

_USER_BUBBLE = {
    "alignSelf": "flex-end", "maxWidth": "78%", "background": theme.PRIMARY_SOFT,
    "color": theme.TITLE, "padding": "8px 12px", "borderRadius": "12px 12px 2px 12px",
    "fontSize": theme.FS_MD, "whiteSpace": "pre-wrap",
}
_ASSISTANT_BUBBLE = {
    "alignSelf": "flex-start", "maxWidth": "88%", "background": theme.SURFACE_ALT,
    "color": theme.TEXT, "padding": "8px 12px", "borderRadius": "12px 12px 12px 2px",
    "fontSize": theme.FS_MD,
}
_ERR_BUBBLE = {**_ASSISTANT_BUBBLE, "background": "#fef2f2", "color": theme.DANGER}


def _hint_div() -> html.Div:
    """The initial placeholder; reused by 'New chat' to restore a clean transcript."""
    return html.Div(_HINT, id="chat-hint", style={"color": theme.TEXT_MUTED, "fontSize": theme.FS_SM})


def chat_tab() -> html.Div:
    return html.Div(
        [
            dcc.Store(id="chat-history", data=[]),
            dcc.Store(id="chat-scroll-dummy"),
            html.Div(
                [
                    html.H4("Assistant", style={"margin": 0}),
                    html.Button(
                        "New chat", id="chat-new-btn", n_clicks=0, className=theme.BTN_SECONDARY_CLASS,
                        style={**theme.BTN_SECONDARY, "padding": "4px 14px", "fontSize": theme.FS_SM, "whiteSpace": "nowrap"},
                    ),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": theme.SP_1},
            ),
            html.Div(
                [
                    html.B("Experimental — "),
                    "the in-app assistant is still in development and not fully reliable yet; it may "
                    "misread requests or stumble on complex ones. For dependable runs use the Simulate tab, "
                    "or drive the simulator from your own client via the ",
                    dcc.Link("MCP server guide", href="/mcp",
                             style={"color": theme.WARNING, "fontWeight": "600", "textDecoration": "underline"}),
                    ".",
                ],
                style={**theme.banner_style("warning"), "marginBottom": theme.SP_2},
            ),
            html.Div(
                "Drive the simulator in plain English — describe a scenario and the assistant "
                "configures it, runs it, and plots the result for you.",
                style={"fontSize": theme.FS_SM, "color": theme.TEXT_MUTED, "marginBottom": theme.SP_2},
            ),
            html.Div(
                [
                    dcc.Input(
                        id="chat-api-key", type="password", placeholder="Anthropic API key (sk-ant-…)",
                        debounce=True, className="tep-input", style={**theme.INPUT, "width": "100%"},
                    ),
                    html.Div(
                        "Used only for this session's requests and never stored. Get a key at console.anthropic.com "
                        "(or set ANTHROPIC_API_KEY on the server).",
                        style={"fontSize": theme.FS_XS, "color": theme.TEXT_MUTED, "marginTop": theme.SP_1},
                    ),
                ],
                style={"marginBottom": theme.SP_2},
            ),
            html.Div(
                [_hint_div()],
                id="chat-log",
                style={
                    "display": "flex", "flexDirection": "column", "gap": theme.SP_2,
                    "minHeight": "320px", "maxHeight": "60vh", "overflowY": "auto",
                    "padding": theme.SP_3, "border": f"1px solid {theme.BORDER}",
                    "borderRadius": theme.RADIUS_SM, "background": theme.SURFACE,
                },
            ),
            html.Div(
                [
                    dcc.Textarea(
                        id="chat-input", placeholder="Ask the assistant to run or compare scenarios…",
                        style={"flex": "1 1 auto", "height": "60px", "resize": "vertical",
                               "border": f"1px solid {theme.BORDER}", "borderRadius": theme.RADIUS_SM,
                               "padding": theme.SP_2, "fontFamily": theme.FONT_FAMILY, "fontSize": theme.FS_MD},
                    ),
                    html.Button("Send", id="chat-send-btn", n_clicks=0, className=theme.BTN_PRIMARY_CLASS,
                                style={**theme.BTN_PRIMARY, "height": "60px", "marginLeft": theme.SP_2}),
                ],
                style={"display": "flex", "alignItems": "stretch", "marginTop": theme.SP_2},
            ),
            html.Div(id="chat-status", style=theme.status_style("muted")),
        ],
        style=theme.CARD,
    )


def _user_bubble(text: str) -> html.Div:
    return html.Div(text, style=_USER_BUBBLE)


def _assistant_bubble(text: str) -> html.Div:
    return html.Div(dcc.Markdown(text, style={"margin": 0}), style=_ASSISTANT_BUBBLE)


def _run_figure(run) -> html.Div:
    """Render a created run with the real trajectory grid (same as the Simulate tab)."""
    setpoints = (run.record or {}).get("setpoints")
    fig = figures.trajectory_grid(
        run.to_frame(), DEFAULT_PLOT_VARS, setpoints=setpoints, show_limits=True,
        shutdown_time=run.final_time if run.terminated else None,
    )
    outcome = f"shutdown at {run.final_time:.2f} h" if run.terminated else f"ran {run.final_time:.1f} h"
    caption = f"{run.scenario.name} · {run.run_id} · {outcome} · peak reactor P = {run.peak.get('reactor_pressure_max', 0):.0f} kPa"
    return html.Div(
        [
            html.Div(caption, style={"fontSize": theme.FS_XS, "color": theme.TEXT_MUTED, "marginBottom": theme.SP_1}),
            dcc.Graph(figure=fig, config=theme.GRAPH_CONFIG, style={"height": "320px"}),
        ],
        style={"alignSelf": "stretch", "border": f"1px solid {theme.BORDER}", "borderRadius": theme.RADIUS_SM,
               "padding": theme.SP_2, "background": theme.SURFACE_ALT},
    )


def _strip_hint(children) -> list:
    """Drop the initial placeholder so the first message starts a clean transcript."""
    out = []
    for child in children or []:
        if isinstance(child, dict) and child.get("props", {}).get("id") == "chat-hint":
            continue
        out.append(child)
    return out


def register_chat_callbacks(app, store) -> None:
    """Wire the Assistant tab. ``store`` is the app's RunStore (shared with the studio)."""
    from tep_studio.agent.chat import respond
    from tep_studio.agent.tools import TepToolset

    toolset = TepToolset(store=store)

    # Disable Send the moment it is clicked (re-enabled by the server callback below).
    app.clientside_callback(
        "function(n){ return !!n; }",
        Output("chat-send-btn", "disabled", allow_duplicate=True),
        Input("chat-send-btn", "n_clicks"),
        prevent_initial_call=True,
    )

    # Keep the transcript pinned to the newest message as it grows. The second pass
    # (setTimeout) catches the run-figure plots, which finish rendering after the patch.
    app.clientside_callback(
        """
        function(children) {
            var el = document.getElementById('chat-log');
            if (el) {
                requestAnimationFrame(function(){ el.scrollTop = el.scrollHeight; });
                setTimeout(function(){ el.scrollTop = el.scrollHeight; }, 220);
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output("chat-scroll-dummy", "data"),
        Input("chat-log", "children"),
        prevent_initial_call=True,
    )

    # "New chat" — reset the transcript, history, and status to a clean slate
    # (the API key and any unsent input are left untouched).
    @app.callback(
        Output("chat-log", "children", allow_duplicate=True),
        Output("chat-history", "data", allow_duplicate=True),
        Output("chat-status", "children", allow_duplicate=True),
        Input("chat-new-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def _new_chat(_n):
        return [_hint_div()], [], ""

    @app.callback(
        Output("chat-log", "children"),
        Output("chat-history", "data"),
        Output("chat-input", "value"),
        Output("chat-status", "children"),
        Output("active-run", "data", allow_duplicate=True),
        Output("session-runs", "data", allow_duplicate=True),
        Output("chat-send-btn", "disabled", allow_duplicate=True),
        Input("chat-send-btn", "n_clicks"),
        State("chat-input", "value"),
        State("chat-history", "data"),
        State("chat-log", "children"),
        State("session-runs", "data"),
        State("chat-api-key", "value"),
        prevent_initial_call=True,
    )
    def _send(n, text, history, log_children, session, api_key):
        text = (text or "").strip()
        if not text:
            raise PreventUpdate
        log = _strip_hint(log_children)

        try:
            turn = respond(history or [], text, toolset, api_key=(api_key or "").strip() or None)
        except Exception as exc:  # missing key/package, API error — keep the UI alive
            bubble = html.Div(f"⚠ Assistant unavailable: {exc}", style=_ERR_BUBBLE)
            return log + [_user_bubble(text), bubble], history or [], "", "", no_update, no_update, False

        bubbles = [_user_bubble(text), _assistant_bubble(turn.assistant_text)]
        created_summaries = []
        for run_id in turn.created_run_ids:
            run = store.get(run_id)
            if run is not None:
                bubbles.append(_run_figure(run))
                created_summaries.append(run.summary())

        active_out = turn.created_run_ids[-1] if turn.created_run_ids else no_update
        session_out = ((session or []) + created_summaries) if created_summaries else no_update
        if created_summaries:
            status = f"ran {len(created_summaries)} simulation(s) — also on the Simulate / Compare tabs"
        elif turn.tool_calls:
            status = "used tools: " + ", ".join(dict.fromkeys(turn.tool_calls))
        else:
            status = ""
        return log + bubbles, turn.history, "", status, active_out, session_out, False
