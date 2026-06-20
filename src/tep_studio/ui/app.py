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
                --bg:#f6f7f9; --surface:#fff; --surface-alt:#f3f4f6; --border:#e5e7eb;
                --border-strong:#d1d5db; --text:#1f2937; --title:#111827; --muted:#6b7280;
                --faint:#9ca3af; --primary:#334155; --primary-hover:#1e293b; --primary-active:#0f172a;
                --primary-soft:#f1f5f9; --focus:rgba(51,65,85,0.35);
                --radius:10px; --radius-sm:6px; --ch:34px;
            }
            html, body { margin:0; padding:0; min-height:100vh; color:var(--text);
                background:var(--bg);
                font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                -webkit-font-smoothing:antialiased; -moz-osx-font-smoothing:grayscale; }
            * { box-sizing: border-box; }
            label, p, span { color: var(--text); }
            input, textarea { color: var(--text); background: #fff; }
            ::placeholder { color: var(--faint); }
            input[type="radio"], input[type="checkbox"]{ accent-color:var(--primary); width:15px; height:15px;
                vertical-align:-2px; cursor:pointer; }
            ::selection{ background:var(--primary-soft); }

            /* Header: a plain title block with a divider (chrome recedes) */
            .tep-header{ margin-bottom:20px; padding-bottom:16px; border-bottom:1px solid var(--border); }
            .tep-title{ margin:0; color:var(--title); font-size:20px; font-weight:600; letter-spacing:-0.01em; }
            .tep-subtitle{ color:var(--muted); font-size:13px; margin-top:4px; }

            /* Section headings: small, muted, uppercase captions */
            h4{ font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.06em;
                color:var(--muted); margin:0 0 10px 0; }

            /* Tabs: a bottom-bordered bar, accent underline on the active tab */
            #tabs{ display:flex !important; gap:2px; border-bottom:1px solid var(--border); }
            #tabs .tab{ margin-bottom:-1px !important; transition:color .12s ease; }
            #tabs .tab:hover:not(.tab--selected){ color:var(--text) !important; }

            /* Controls: one height, one border, one radius */
            .tep-input, input[type="number"], input[type="text"]{ height:var(--ch); border:1px solid var(--border);
                border-radius:var(--radius-sm); padding:0 10px; background:#fff; font-size:13px;
                transition:border-color .12s ease, box-shadow .12s ease; }
            .tep-input:focus, input[type="number"]:focus, input[type="text"]:focus{ outline:none;
                border-color:var(--primary); box-shadow:0 0 0 3px var(--focus); }
            .Select-control{ min-height:var(--ch) !important; border-radius:var(--radius-sm) !important;
                border-color:var(--border) !important; }
            .is-focused:not(.is-open) > .Select-control{ border-color:var(--primary) !important;
                box-shadow:0 0 0 3px var(--focus) !important; }
            .Select--multi .Select-value{ background:var(--primary-soft) !important; color:var(--primary) !important;
                border:1px solid #cbd5e1 !important; border-radius:4px !important; }
            .Select--multi .Select-value-icon{ border-right-color:#cbd5e1 !important; }

            /* Buttons: flat, single accent; primary is the strongest element */
            .tep-btn{ height:var(--ch); padding:0 14px; border:1px solid transparent; border-radius:var(--radius-sm);
                cursor:pointer; font-family:inherit; font-size:13px; font-weight:500; line-height:1;
                transition:background .12s ease, box-shadow .12s ease, border-color .12s ease; }
            .tep-btn--primary{ background:var(--primary); color:#fff; font-weight:600; }
            .tep-btn--primary:hover{ background:var(--primary-hover); }
            .tep-btn--primary:active{ background:var(--primary-active); }
            .tep-btn--secondary{ background:#fff; color:var(--text); border-color:var(--border); }
            .tep-btn--secondary:hover{ background:var(--surface-alt); }
            .tep-btn:focus-visible{ outline:none; box-shadow:0 0 0 3px var(--focus); }
            .tep-btn:disabled, .tep-btn[disabled]{ opacity:.5; cursor:not-allowed; }

            /* DataTable: quiet header, accent-tinted row hover */
            .dash-table-container .dash-spreadsheet-container th{
                background:var(--surface-alt) !important; font-weight:600; color:var(--title) !important; }
            .dash-table-container .dash-spreadsheet-container tr:hover td{ background:var(--primary-soft) !important; }
            .dash-table-container .dash-filter input{ border:1px solid var(--border); border-radius:4px; }

            /* details/summary (Advanced solver) as a caption-style disclosure */
            details{ border:1px solid var(--border); border-radius:var(--radius-sm); padding:8px 12px; background:var(--surface-alt); }
            details > summary{ cursor:pointer; font-size:11px; font-weight:600; text-transform:uppercase;
                letter-spacing:.06em; color:var(--muted); list-style:none; }
            details[open] > summary{ color:var(--primary); margin-bottom:6px; }
            details > summary::-webkit-details-marker{ display:none; }
            details > summary::before{ content:"\\25B8"; display:inline-block; margin-right:7px;
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
