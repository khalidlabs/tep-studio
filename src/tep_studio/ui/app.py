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
                --bg:#f4f5fb; --surface:#fff; --surface-alt:#f6f7fc; --border:#e7e9f2;
                --border-strong:#d3d7e6; --text:#1c2333; --title:#0f1426; --muted:#5b6478;
                --faint:#99a0b4; --primary:#6d5cf5; --primary-hover:#5b48ec;
                --primary-active:#4a39d4; --grad:linear-gradient(135deg,#6d5cf5 0%,#8b5cf6 100%);
                --danger:#d92d20; --focus:rgba(109,92,245,0.30); --radius:14px; --radius-sm:9px;
                --shadow:0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06);
            }
            html, body { margin:0; padding:0; min-height:100vh; color:var(--text);
                background:linear-gradient(180deg,#f7f8fd 0%, #edeefb 100%) fixed;
                font-family: system-ui, -apple-system, "Segoe UI", Roboto, Inter, sans-serif;
                -webkit-font-smoothing:antialiased; -moz-osx-font-smoothing:grayscale; }
            * { box-sizing: border-box; }
            label, p, span, h1, h2, h3, h4, h5 { color: var(--text); }
            input, textarea { color: var(--text); background: #fff; }
            ::placeholder { color: var(--faint); }
            input[type="radio"], input[type="checkbox"]{ accent-color:var(--primary); width:15px; height:15px;
                vertical-align:-2px; cursor:pointer; }
            ::selection{ background:rgba(109,92,245,.18); }

            /* Header banner */
            .tep-header{ display:flex; align-items:center; gap:16px; padding:20px 24px; margin-bottom:20px;
                background:linear-gradient(120deg,#6d5cf5 0%,#8b5cf6 55%,#a855f7 100%);
                border-radius:18px; box-shadow:0 12px 30px rgba(109,92,245,.28); }
            .tep-logo{ flex:none; width:48px; height:48px; border-radius:14px; display:flex;
                align-items:center; justify-content:center; font-size:26px; background:rgba(255,255,255,.18);
                box-shadow: inset 0 0 0 1px rgba(255,255,255,.25); }
            .tep-title{ margin:0; color:#fff; font-size:22px; font-weight:800; letter-spacing:-0.02em; }
            .tep-subtitle{ color:rgba(255,255,255,.85); font-size:13px; margin-top:3px; }

            /* Section headings get a small accent bar */
            h4{ font-size:15px; font-weight:700; color:var(--title); letter-spacing:-0.01em;
                display:flex; align-items:center; }
            h4::before{ content:""; flex:none; display:inline-block; width:4px; height:15px; border-radius:2px;
                background:var(--grad); margin-right:9px; }

            /* Tabs as a segmented pill bar (#tabs is Dash's .tab-container) */
            #tabs{ display:inline-flex !important; gap:4px; padding:5px; background:var(--surface);
                border:1px solid var(--border); border-radius:16px; box-shadow:var(--shadow); }
            #tabs .tab{ border:none !important; transition:background .12s ease, color .12s ease; }
            #tabs .tab:hover:not(.tab--selected){ background:var(--surface-alt) !important; color:var(--title) !important; }

            /* Buttons (className-driven so hover/focus/disabled states work) */
            .tep-btn{ border:1px solid transparent; border-radius:var(--radius-sm); cursor:pointer;
                font-family:inherit; font-size:13px; line-height:1.2;
                transition:transform .1s ease, box-shadow .12s ease, background .12s ease, filter .12s ease; }
            .tep-btn--primary{ background:var(--grad); color:#fff; box-shadow:0 1px 2px rgba(16,24,40,.12); }
            .tep-btn--primary:hover{ filter:brightness(1.05); transform:translateY(-1px);
                box-shadow:0 6px 16px rgba(109,92,245,.35); }
            .tep-btn--primary:active{ transform:translateY(0); filter:brightness(.97); }
            .tep-btn--secondary{ background:#fff; color:var(--text); border-color:var(--border); }
            .tep-btn--secondary:hover{ background:var(--surface-alt); border-color:var(--primary); color:var(--primary); }
            .tep-btn:focus-visible{ outline:none; box-shadow:0 0 0 3px var(--focus); }
            .tep-btn:disabled, .tep-btn[disabled]{ opacity:.5; cursor:not-allowed; transform:none; box-shadow:none; }

            /* Inputs + dropdown focus rings */
            .tep-input, input[type="number"], input[type="text"]{ border:1px solid var(--border);
                border-radius:var(--radius-sm); padding:7px 10px; background:#fff;
                transition:border-color .12s ease, box-shadow .12s ease; }
            .tep-input:focus, input[type="number"]:focus, input[type="text"]:focus{ outline:none;
                border-color:var(--primary); box-shadow:0 0 0 3px var(--focus); }
            .Select-control{ border-radius:var(--radius-sm) !important; border-color:var(--border) !important; min-height:38px; }
            .is-focused:not(.is-open) > .Select-control{ border-color:var(--primary) !important;
                box-shadow:0 0 0 3px var(--focus) !important; }
            .Select--multi .Select-value{ background:rgba(109,92,245,.10) !important; color:var(--primary) !important;
                border:1px solid rgba(109,92,245,.25) !important; border-radius:6px !important; }
            .Select--multi .Select-value-icon{ border-right-color:rgba(109,92,245,.25) !important; }

            /* DataTable polish */
            .dash-table-container .dash-spreadsheet-container .dash-spreadsheet-inner table{ border-radius:10px; overflow:hidden; }
            .dash-table-container .dash-spreadsheet-container th{
                background:var(--surface-alt) !important; font-weight:600; color:var(--title) !important; }
            .dash-table-container .dash-spreadsheet-container tr:hover td{ background:#f3f3fd !important; }
            .dash-table-container .dash-filter input{ border:1px solid var(--border); border-radius:5px; }

            /* details/summary (Advanced solver) */
            details{ border:1px solid var(--border); border-radius:var(--radius-sm); padding:8px 12px; background:var(--surface-alt); }
            details > summary{ cursor:pointer; font-weight:600; font-size:13px; color:var(--muted);
                list-style:none; }
            details[open] > summary{ color:var(--primary); margin-bottom:6px; }
            details > summary::-webkit-details-marker{ display:none; }
            details > summary::before{ content:"\\25B8"; display:inline-block; margin-right:7px;
                transition:transform .12s ease; }
            details[open] > summary::before{ transform:rotate(90deg); }

            /* Plotly card chrome */
            .js-plotly-plot{ border-radius:10px; }

            /* Scrollbars */
            *::-webkit-scrollbar{ height:10px; width:10px; }
            *::-webkit-scrollbar-thumb{ background:var(--border-strong); border-radius:6px; }
            *::-webkit-scrollbar-thumb:hover{ background:#b9bed1; }
            *::-webkit-scrollbar-track{ background:transparent; }

            /* Responsive: stack the fixed sidebar on narrow screens */
            @media (max-width:880px){
                .tep-row{ flex-direction:column !important; }
                .tep-col-left{ flex:1 1 auto !important; max-width:100% !important; }
                .tep-header{ padding:16px 18px; }
                .tep-title{ font-size:19px; }
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
