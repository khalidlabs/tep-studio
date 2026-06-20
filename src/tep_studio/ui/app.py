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
# on a dark background and be invisible). All global CSS lives here (not in an
# assets/ folder): the app is deployed from the installed wheel and pyproject ships
# no package-data, so an assets file would not reach the Hugging Face Space. The
# :root variables mirror the tokens in theme.py -- keep the two in sync.
_INDEX_STRING = """<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            :root{
                --bg:#eef1f5; --surface:#fff; --surface-alt:#f6f8fa; --border:#e2e6ec;
                --border-strong:#cfd5de; --text:#1f2733; --muted:#5a6573; --faint:#99a0ab;
                --primary:#6c4cf0; --primary-hover:#5a3ce0; --primary-active:#4a2fc0;
                --danger:#b22222; --focus:rgba(108,76,240,0.35); --radius:8px;
            }
            html, body { margin: 0; padding: 0; background: var(--bg);
                color: var(--text); font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
            * { box-sizing: border-box; }
            label, p, span, h1, h2, h3, h4, h5 { color: var(--text); }
            input, textarea { color: var(--text); background: #fff; }
            ::placeholder { color: var(--faint); }

            /* Buttons (className-driven so hover/focus/disabled states work) */
            .tep-btn{ border:1px solid transparent; border-radius:var(--radius); cursor:pointer;
                font-family:inherit; font-size:13px; line-height:1.2;
                transition:background .12s ease, box-shadow .12s ease, opacity .12s ease; }
            .tep-btn--primary{ background:var(--primary); color:#fff; }
            .tep-btn--primary:hover{ background:var(--primary-hover); }
            .tep-btn--primary:active{ background:var(--primary-active); }
            .tep-btn--secondary{ background:#fff; color:var(--text); border-color:var(--border); }
            .tep-btn--secondary:hover{ background:var(--surface-alt); border-color:var(--primary); }
            .tep-btn:focus-visible{ outline:none; box-shadow:0 0 0 3px var(--focus); }
            .tep-btn:disabled, .tep-btn[disabled]{ opacity:.5; cursor:not-allowed; }

            /* Inputs + dropdown focus rings */
            .tep-input, input[type="number"], input[type="text"]{ border:1px solid var(--border);
                border-radius:6px; padding:5px 8px; }
            .tep-input:focus, input:focus{ outline:none; border-color:var(--primary);
                box-shadow:0 0 0 3px var(--focus); }
            .Select-control{ border-radius:6px !important; border-color:var(--border) !important; }
            .is-focused:not(.is-open) > .Select-control{ border-color:var(--primary) !important;
                box-shadow:0 0 0 3px var(--focus) !important; }

            /* DataTable polish */
            .dash-table-container .dash-spreadsheet-container th{
                background:var(--surface-alt) !important; font-weight:600; }
            .dash-table-container .dash-spreadsheet-container tr:hover td{ background:#f3f6fb !important; }
            .dash-table-container .dash-filter input{ border:1px solid var(--border); border-radius:4px; }

            /* details/summary (Advanced solver) */
            details > summary{ cursor:pointer; font-weight:600; font-size:13px; color:var(--muted);
                padding:4px 0; list-style:none; }
            details > summary::-webkit-details-marker{ display:none; }
            details > summary::before{ content:"\\25B8"; display:inline-block; margin-right:6px;
                transition:transform .12s ease; }
            details[open] > summary::before{ transform:rotate(90deg); }

            /* Scrollbars */
            *::-webkit-scrollbar{ height:10px; width:10px; }
            *::-webkit-scrollbar-thumb{ background:var(--border-strong); border-radius:6px; }
            *::-webkit-scrollbar-track{ background:transparent; }

            /* Responsive: stack the fixed sidebar on narrow screens */
            @media (max-width:880px){
                .tep-row{ flex-direction:column !important; }
                .tep-col-left{ flex:1 1 auto !important; max-width:100% !important; }
            }
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
