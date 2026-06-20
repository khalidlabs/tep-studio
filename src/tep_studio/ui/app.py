"""Dash application factory for the TEP interface.

The synchronous server keeps run artifacts in a process-local ``RunStore`` (so they
persist across callbacks). Runs at the Explore fidelity (Δt = 0.01 h) take only a
few seconds, so a ``dcc.Loading`` spinner is sufficient; the ``background`` flag is
accepted for forward-compatibility (diskcache background callbacks) but the default
synchronous path is the supported one.
"""

from __future__ import annotations


# Explicit light theme so the app is readable regardless of the OS/browser dark
# mode (Dash leaves the body transparent, so default black text would otherwise sit
# on a dark background and be invisible).
_INDEX_STRING = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            html, body { margin: 0; padding: 0; background: #eef1f5;
                color: #1f2733; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
            * { box-sizing: border-box; }
            label, p, span, h1, h2, h3, h4, h5 { color: #1f2733; }
            input, textarea { color: #1f2733; background: #fff; }
            ::placeholder { color: #99a0ab; }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>{%config%}{%scripts%}{%renderer%}</footer>
    </body>
</html>"""


def create_app(*, background: bool = False, store=None, capacity: int = 50):
    from dash import Dash

    from tep_studio.ui.callbacks import register_callbacks
    from tep_studio.ui.layout import build_layout
    from tep_studio.ui.store import RunStore

    app = Dash(__name__, title="TEP Simulation Studio", suppress_callback_exceptions=True)
    app.index_string = _INDEX_STRING
    run_store = store or RunStore(capacity=capacity)
    app.layout = build_layout()
    register_callbacks(app, run_store)
    app.run_store = run_store  # keep a reference for tests / embedding
    return app
