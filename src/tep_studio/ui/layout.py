"""Dash layout factories for the TEP interface (one builder per tab).

Styling comes from ``tep_studio.ui.theme`` (tokens + helper dicts); the CSS
pseudo-states for buttons/inputs/tables live in ``app._INDEX_STRING``. Component
ids are stable contracts consumed by ``callbacks.py`` and pinned by the smoke test.
"""

from __future__ import annotations

from dash import dash_table, dcc, html

from tep_studio.control.tuning import tuning_rows
from tep_studio.ui import theme
from tep_studio.ui.config import setpoint_fields
from tep_studio.ui.widgets import (
    DEFAULT_PLOT_VARS,
    disturbance_options,
    measurement_options,
    mode_options,
    mv_sliders,
    setpoint_inputs,
)


def _field(label: str, control) -> html.Div:
    label_style = {"fontSize": theme.FS_SM, "fontWeight": "500", "color": theme.TEXT, "display": "block", "marginBottom": theme.SP_1}
    return html.Div([html.Label(label, style=label_style), control], style={"marginBottom": theme.SP_3})


def _button(label: str, btn_id: str, *, primary: bool = True, **kwargs) -> html.Button:
    cls = theme.BTN_PRIMARY_CLASS if primary else theme.BTN_SECONDARY_CLASS
    style = {**(theme.BTN_PRIMARY if primary else theme.BTN_SECONDARY), **kwargs.pop("style", {})}
    return html.Button(label, id=btn_id, n_clicks=0, className=cls, style=style, **kwargs)


def _table(table_id: str, **extra) -> dash_table.DataTable:
    """A consistently styled, sortable + filterable DataTable."""
    return dash_table.DataTable(
        id=table_id,
        page_size=8,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": theme.SURFACE_ALT, "fontWeight": "600", "border": f"1px solid {theme.BORDER}"},
        style_cell={"fontSize": theme.FS_SM, "padding": "6px 10px", "fontFamily": theme.FONT_FAMILY, "border": f"1px solid {theme.BORDER}", "textAlign": "left"},
        style_data_conditional=[
            {"if": {"filter_query": "{peak_reactor_pressure} >= 3000", "column_id": "peak_reactor_pressure"}, "color": theme.DANGER, "fontWeight": "700"},
        ],
        **extra,
    )


def _advanced_solver() -> html.Details:
    """Collapsible numeric-solver controls (native <details>, zero-dependency)."""
    return html.Details(
        [
            html.Summary("Advanced solver"),
            _field("Solver", dcc.Dropdown(id="solver-method", clearable=False, value="RK4", options=[
                {"label": "RK4 (fast, fixed-step)", "value": "RK4"},
                {"label": "Euler (fixed-step)", "value": "Euler"},
                {"label": "RK45 (adaptive)", "value": "RK45"},
                {"label": "RK23 (adaptive)", "value": "RK23"},
            ])),
            _field("rtol (adaptive only)", dcc.Input(id="rtol", type="number", value=1e-6, step="any", min=0, className="tep-input", style=theme.INPUT)),
            _field("atol (adaptive only)", dcc.Input(id="atol", type="number", value=1e-8, step="any", min=0, className="tep-input", style=theme.INPUT)),
            _field("fixed_step (h)", dcc.Input(id="fixed-step", type="number", value=0.0005, step="any", min=1e-5, className="tep-input", style=theme.INPUT)),
            _field("record_every (0 = auto)", dcc.Input(id="record-every", type="number", value=0, step=1, min=0, className="tep-input", style=theme.INPUT)),
        ],
        style={"marginTop": theme.SP_2, "marginBottom": theme.SP_2},
    )


def _advanced_initial_state() -> html.Details:
    """Collapsible custom-initial-state editor (default: the operating mode's state)."""
    caption = {"fontSize": theme.FS_SM, "color": theme.TEXT_MUTED, "marginBottom": theme.SP_2}
    return html.Details(
        [
            html.Summary("Initial state"),
            html.Div("Start the plant from a custom 50-element state instead of the mode default.", style=caption),
            _field("Source", dcc.RadioItems(id="initial-state-source", options=[
                {"label": " Mode default", "value": "mode"},
                {"label": " Custom vector", "value": "custom"},
            ], value="mode", inline=True)),
            _button("Load current mode's state", "load-mode-state-btn", primary=False, style={"marginBottom": theme.SP_2}),
            dcc.Textarea(
                id="initial-state-text", placeholder="50 numbers — JSON list or comma/space separated",
                style={"width": "100%", "height": "120px", "fontFamily": theme.FONT_MONO, "fontSize": theme.FS_XS,
                       "border": f"1px solid {theme.BORDER}", "borderRadius": theme.RADIUS_SM, "padding": theme.SP_2},
            ),
            html.Div(id="initial-state-msg", style={"fontSize": theme.FS_SM, "color": theme.TEXT_MUTED, "marginTop": theme.SP_1}),
        ],
        style={"marginTop": theme.SP_2, "marginBottom": theme.SP_2},
    )


def _advanced_tuning() -> html.Details:
    """Collapsible editable table of every controller tuning parameter (default: Ricker Mode-1)."""
    caption = {"fontSize": theme.FS_SM, "color": theme.TEXT_MUTED, "marginBottom": theme.SP_2}
    return html.Details(
        [
            html.Summary("Controller tuning"),
            html.Div("PI gains, override limits, and setpoint ramp rates. Edit a value to override it; Reset restores the defaults.", style=caption),
            dash_table.DataTable(
                id="tuning-table",
                data=tuning_rows(),
                columns=[
                    {"name": "group", "id": "group", "editable": False},
                    {"name": "parameter", "id": "parameter", "editable": False},
                    {"name": "value", "id": "value", "editable": True, "type": "numeric"},
                ],
                editable=True,
                page_size=12,
                style_table={"overflowX": "auto"},
                style_header={"backgroundColor": theme.SURFACE_ALT, "fontWeight": "600", "border": f"1px solid {theme.BORDER}"},
                style_cell={"fontSize": theme.FS_XS, "padding": "4px 8px", "fontFamily": theme.FONT_MONO, "border": f"1px solid {theme.BORDER}", "textAlign": "left"},
                style_data_conditional=[{"if": {"column_id": "value"}, "backgroundColor": theme.PRIMARY_SOFT}],
            ),
            _button("Reset to defaults", "reset-tuning-btn", primary=False, style={"marginTop": theme.SP_2}),
        ],
        style={"marginTop": theme.SP_2, "marginBottom": theme.SP_2},
    )


def _config_card() -> html.Div:
    return html.Div(
        [
            html.H4("Run configuration", style={"marginTop": 0}),
            _field("Operating mode", dcc.Dropdown(id="mode-select", options=mode_options(), value="mode1", clearable=False)),
            _field("Loop", dcc.RadioItems(id="loop-type", options=[{"label": " Closed loop", "value": "closed"}, {"label": " Open loop", "value": "open"}], value="closed", inline=True)),
            _field("Horizon (h)", dcc.Input(id="horizon", type="number", value=12.0, min=0.1, step="any", className="tep-input", style=theme.INPUT)),
            _field("Fidelity", dcc.RadioItems(id="ci-preset", options=[{"label": " Explore (Δt=0.01 h)", "value": 0.01}, {"label": " Fidelity (Δt=0.0005 h)", "value": 0.0005}], value=0.01)),
            _field("Seed (optional)", dcc.Input(id="seed", type="number", step="any", placeholder="none", className="tep-input", style=theme.INPUT)),
            _field("Controller", dcc.Checklist(id="ctrl-flags", options=[{"label": " composition", "value": "composition"}, {"label": " overrides", "value": "overrides"}, {"label": " %G feedback", "value": "pct_g_feedback"}], value=["composition", "overrides"])),
            html.Div(setpoint_inputs(), id="closed-controls", style={**theme.CARD, "display": "block"}),
            html.Div(mv_sliders(), id="open-controls", style={**theme.CARD, "display": "none"}),
            html.H4("Disturbances"),
            _field("Active IDVs", dcc.Dropdown(id="dist-select", options=disturbance_options(), multi=True, placeholder="none")),
            _field("Activation time (h)", dcc.Input(id="dist-start", type="number", value=1.0, min=0, step="any", className="tep-input", style=theme.INPUT)),
            html.Div(id="dist-mag-container", style={"marginBottom": theme.SP_2}),
            _advanced_initial_state(),
            _advanced_tuning(),
            _advanced_solver(),
            _button("Run simulation", "run-btn"),
            html.Div(id="run-status", style=theme.status_style("muted")),
            html.Div(id="run-banner", style=theme.HIDDEN),
            html.Hr(),
            html.Div([
                _button("Save scenario", "save-scenario-btn", primary=False, style={"marginRight": theme.SP_2}),
                dcc.Upload(_button("Load scenario", "load-scenario-btn", primary=False), id="scenario-upload", accept=".json"),
            ]),
            dcc.Download(id="scenario-download"),
        ],
        className="tep-col-left",
        style={**theme.CARD, **theme.COL_LEFT},
    )


def _graph_panel(graph_id: str, *, grow: int, basis: str, min_height: str) -> html.Div:
    """A flex-growing graph cell so the plots column fills the matched column height.
    Extra space is split by ``grow`` (the MV plot is given the larger share)."""
    return html.Div(
        dcc.Loading(
            dcc.Graph(id=graph_id, config=theme.GRAPH_CONFIG, responsive=True, style={"height": "100%"}),
            parent_style={"height": "100%"},
        ),
        style={"flex": f"{grow} 1 {basis}", "minHeight": min_height, "marginTop": theme.SP_2},
    )


def _simulate_tab() -> html.Div:
    return html.Div(
        [
            _config_card(),
            html.Div(
                [
                    _field("Variables to plot", dcc.Dropdown(id="plot-vars", options=measurement_options(), value=DEFAULT_PLOT_VARS, multi=True)),
                    dcc.Checklist(id="plot-toggles", options=[{"label": " setpoints", "value": "setpoints"}, {"label": " limits", "value": "limits"}], value=["setpoints", "limits"], inline=True),
                    # The plots column stretches to the configuration column's height (row
                    # alignItems=stretch); the two graphs then fill it, with the MV plot
                    # claiming the larger share of the extra space (grow 2 vs 1).
                    _graph_panel("trajectory-graph", grow=1, basis="520px", min_height="300px"),
                    _graph_panel("mv-graph", grow=2, basis="300px", min_height="260px"),
                ],
                style={**theme.CARD, **theme.COL_RIGHT, "display": "flex", "flexDirection": "column"},
            ),
        ],
        className="tep-row",
        style={**theme.ROW, "alignItems": "stretch"},
    )


def _dataset_tab() -> html.Div:
    sweep_options = (
        [{"label": f"setpoints.{f}", "value": f"setpoints.{f}"} for f in setpoint_fields()]
        + [{"label": "horizon", "value": "horizon"}, {"label": "control_interval", "value": "control_interval"}, {"label": "fixed_step", "value": "fixed_step"}]
    )
    return html.Div(
        [
            html.Div(
                [
                    html.H4("Export dataset", style={"marginTop": 0}),
                    _field("Runs to include", dcc.Checklist(id="dataset-runs", options=[], value=[])),
                    _field("Format", dcc.RadioItems(id="dataset-format", options=[{"label": " CSV", "value": "csv"}, {"label": " Parquet", "value": "parquet"}, {"label": " JSON", "value": "json"}], value="csv", inline=True)),
                    _button("Build & download", "build-dataset-btn"),
                    dcc.Download(id="dataset-download"),
                ],
                className="tep-col-left",
                style={**theme.CARD, **theme.COL_LEFT},
            ),
            html.Div(
                [
                    html.H4("Batch generation", style={"marginTop": 0}),
                    _field("Seeds (comma-separated)", dcc.Input(id="batch-seeds", type="text", value="1, 2, 3", className="tep-input", style=theme.INPUT_WIDE)),
                    _field("Sweep parameter (optional)", dcc.Dropdown(id="batch-field", options=sweep_options, placeholder="none")),
                    _field("Sweep values (comma-separated)", dcc.Input(id="batch-values", type="text", placeholder="e.g. 22, 28, 32", className="tep-input", style=theme.INPUT_WIDE)),
                    _button("Run batch", "run-batch-btn"),
                    html.Div(id="batch-status", style=theme.status_style("muted")),
                    html.Div(id="batch-banner", style=theme.HIDDEN),
                    dcc.Loading(_table("batch-table")),
                    html.Div([
                        _button("Download combined dataset", "batch-dataset-btn", primary=False, style={"marginRight": theme.SP_2}),
                        _button("Download metrics CSV", "batch-metrics-btn", primary=False),
                    ], style={"marginTop": theme.SP_2}),
                    dcc.Download(id="batch-dataset-download"),
                    dcc.Download(id="batch-metrics-download"),
                ],
                style={**theme.CARD, **theme.COL_RIGHT},
            ),
        ],
        className="tep-row",
        style=theme.ROW,
    )


def _compare_tab() -> html.Div:
    return html.Div(
        [
            html.Div([
                html.H4("Compare runs", style={"marginTop": 0, "display": "inline-block"}),
                _button("Clear all runs", "clear-runs-btn", primary=False, style={"marginLeft": theme.SP_4}),
                dcc.Clipboard(id="copy-runids", title="Copy all run IDs", style={"display": "inline-block", "marginLeft": theme.SP_3, "cursor": "pointer", "color": theme.PRIMARY}),
                html.Div(id="store-capacity", style=theme.status_style("muted")),
            ]),
            _table("compare-table"),
            _field("Overlay variables", dcc.Dropdown(id="compare-var", options=measurement_options(), value=["measurement.reactor_pressure"], multi=True)),
            dcc.Loading(dcc.Graph(id="compare-graph", config=theme.GRAPH_CONFIG, style={"height": "520px"})),
        ],
        style=theme.CARD,
    )


def _record_tab() -> html.Div:
    return html.Div(
        [
            html.H4("Metrics & experiment record", style={"marginTop": 0}),
            html.Div([
                _field("Run", dcc.Dropdown(id="record-run", options=[], placeholder="run a simulation first")),
                dcc.Clipboard(id="copy-active-id", title="Copy run ID", style={"display": "inline-block", "marginLeft": theme.SP_2, "cursor": "pointer", "color": theme.PRIMARY}),
            ], style={"display": "flex", "alignItems": "center", "gap": theme.SP_2}),
            html.Div(id="metrics-panel"),
            html.H4("Experiment record (P6)"),
            _button("Download record JSON", "download-record-btn", primary=False),
            dcc.Download(id="record-download"),
            html.Pre(id="record-json", style={"background": theme.SURFACE_ALT, "padding": "10px", "borderRadius": theme.RADIUS_SM, "overflowX": "auto", "fontSize": theme.FS_XS, "maxHeight": "420px", "fontFamily": theme.FONT_MONO}),
        ],
        style=theme.CARD,
    )


def _about_page() -> html.Div:
    """A standalone information page on the Tennessee Eastman process (routed at /about)."""
    h2 = {"color": theme.TITLE, "fontSize": theme.FS_XL, "fontWeight": "600", "marginTop": theme.SP_5, "marginBottom": theme.SP_2}
    h3 = {"color": theme.TITLE, "fontSize": theme.FS_LG, "fontWeight": "600", "marginTop": theme.SP_4, "marginBottom": theme.SP_1}
    para = {"color": theme.TEXT, "fontSize": theme.FS_MD, "lineHeight": "1.65", "marginBottom": theme.SP_2}
    ul = {"color": theme.TEXT, "fontSize": theme.FS_MD, "lineHeight": "1.65", "marginTop": 0, "marginBottom": theme.SP_2, "paddingLeft": "20px"}
    mono = {"fontFamily": theme.FONT_MONO, "fontSize": theme.FS_SM, "background": theme.SURFACE_ALT, "padding": "10px 12px", "borderRadius": theme.RADIUS_SM, "lineHeight": "1.8", "margin": f"0 0 {theme.SP_2} 0", "whiteSpace": "pre", "overflowX": "auto"}

    return html.Div(
        [
            dcc.Link("← Back to the studio", href="/", style={"color": theme.PRIMARY, "textDecoration": "none", "fontSize": theme.FS_MD, "fontWeight": "500"}),
            html.H1("The Tennessee Eastman Process", style={"color": theme.TITLE, "fontSize": "26px", "fontWeight": "700", "marginTop": theme.SP_3, "marginBottom": theme.SP_2}),
            html.P(
                "The Tennessee Eastman Process (TEP) is a realistic, open-loop-unstable model of an industrial "
                "chemical plant. It was published by Downs and Vogel (1993) as a plant-wide control and monitoring "
                "challenge — a real Eastman Chemical process with the proprietary chemistry and components disguised. "
                "It has since become the standard testbed for process control, fault detection and diagnosis, and, more "
                "recently, reinforcement learning.",
                style=para,
            ),

            html.H2("The plant", style=h2),
            html.P("Five unit operations, linked by a tight gas recycle:", style=para),
            html.Ul(
                [
                    html.Li([html.B("Reactor"), " — a two-phase, exothermic gas–liquid reactor where the products form; cooled by internal cooling water."]),
                    html.Li([html.B("Condenser"), " — partially condenses the reactor effluent."]),
                    html.Li([html.B("Vapour–liquid separator"), " — splits condensed liquid from the uncondensed gas."]),
                    html.Li([html.B("Recycle compressor"), " — returns unreacted gas to the reactor."]),
                    html.Li([html.B("Product stripper"), " — strips remaining light components; the liquid products leave its base."]),
                ],
                style=ul,
            ),
            html.P("Non-condensable gas and the inert component are vented through a purge to keep pressure and inerts in check.", style=para),

            html.H2("Chemistry", style=h2),
            html.P("Four irreversible, exothermic, gas-phase reactions convert gaseous reactants into two liquid products plus a byproduct:", style=para),
            html.Div("A + C + D  →  G   (liquid product)\nA + C + E  →  H   (liquid product)\nA + E      →  F   (byproduct)\n3 D        →  2 F  (byproduct)", style=mono),
            html.P(
                "Eight components: reactants A, C, D, E; inert B; byproduct F; products G and H. Rates follow Arrhenius "
                "kinetics, so the reactor temperature shifts product selectivity — lower temperature favours G, higher favours H.",
                style=para,
            ),

            html.H2("Feeds, products, and operating modes", style=h2),
            html.P(
                "Four gaseous feeds enter the loop — pure A, pure D, pure E, and a combined A+C stream. Production is the "
                "liquid G/H leaving the stripper. The economics of a run are set by the G:H mass ratio and the production "
                "rate, which define six standard operating modes:",
                style=para,
            ),
            html.Ul(
                [
                    html.Li("50/50 G:H — at base rate (Mode 1) and at maximum rate (Mode 4)"),
                    html.Li("10/90 G:H — at base rate (Mode 2) and at maximum rate (Mode 5)"),
                    html.Li("90/10 G:H — at base rate (Mode 3) and at maximum rate (Mode 6)"),
                ],
                style=ul,
            ),

            html.H2("Variables", style=h2),
            html.Ul(
                [
                    html.Li([html.B("41 measurements (XMEAS)"), " — 22 sampled continuously (flows, levels, pressures, temperatures) and 19 composition readings from gas chromatographs on the reactor feed, the purge, and the product, with realistic analyzer dead time."]),
                    html.Li([html.B("12 manipulated variables (XMV)"), " — the feed, purge, and product valves; the recycle and stripper-steam valves; the reactor and condenser cooling-water valves; and the reactor agitator speed."]),
                    html.Li([html.B("Process disturbances (IDV)"), " — 20 in the original problem (feed-composition steps, reaction-kinetics drift, sticking valves, loss of A feed, …); this simulator exposes 28."]),
                ],
                style=ul,
            ),

            html.H2("The control challenge", style=h2),
            html.P(
                "The plant is open-loop unstable: with the valves held fixed it trips within about an hour. A controller "
                "must hold it inside hard operating limits — reactor pressure below roughly 3000 kPa, bounded "
                "temperatures and liquid levels — or a safety interlock shuts the plant down, all while minimizing "
                "operating cost and rejecting disturbances. The tight material recycle couples every unit, so single-loop "
                "tuning interacts plant-wide. That combination of instability, hard constraints, and interaction is what "
                "makes the TEP a demanding and enduring benchmark.",
                style=para,
            ),

            html.H2("How the TEP is used", style=h2),
            html.Ul(
                [
                    html.Li([html.B("Fault detection & diagnosis"), " — the canonical labeled benchmark (fault-free plus per-disturbance datasets)."]),
                    html.Li([html.B("Control benchmarking"), " — PID, decentralized multiloop, and model-predictive control."]),
                    html.Li([html.B("Reinforcement learning"), " — a hard, safety-constrained continuous-control environment."]),
                    html.Li([html.B("Operator training & plant-wide research"), " — multimode operation, transfer learning, and real-time optimization."]),
                ],
                style=ul,
            ),

            html.H2("In this studio", style=h2),
            html.P(
                "Run any of the six operating modes open- or closed-loop, inject timed disturbances, edit the initial "
                "state and the controller tuning, compare runs side by side, and export tidy datasets for machine "
                "learning — all from the Simulate, Dataset, Compare, and Metrics / Record tabs.",
                style=para,
            ),

            html.Hr(style={"border": "none", "borderTop": f"1px solid {theme.BORDER}", "margin": f"{theme.SP_5} 0 {theme.SP_3}"}),
            html.P("Reference: J. J. Downs and E. F. Vogel, “A plant-wide industrial process control problem,” Computers & Chemical Engineering 17(3), 1993.", style={**para, "fontSize": theme.FS_SM, "color": theme.TEXT_MUTED}),
            dcc.Link("← Back to the studio", href="/", style={"color": theme.PRIMARY, "textDecoration": "none", "fontSize": theme.FS_MD, "fontWeight": "500"}),
        ],
        style={**theme.CARD, "maxWidth": "820px", "margin": "0 auto", "padding": "24px 32px 32px"},
    )


def _main_tabs() -> dcc.Tabs:
    return dcc.Tabs(
        id="tabs",
        value="simulate",
        children=[
            dcc.Tab(label="Simulate", value="simulate", children=_simulate_tab(), style=theme.TAB, selected_style=theme.TAB_SELECTED),
            dcc.Tab(label="Dataset", value="dataset", children=_dataset_tab(), style=theme.TAB, selected_style=theme.TAB_SELECTED),
            dcc.Tab(label="Compare", value="compare", children=_compare_tab(), style=theme.TAB, selected_style=theme.TAB_SELECTED),
            dcc.Tab(label="Metrics / Record", value="record", children=_record_tab(), style=theme.TAB, selected_style=theme.TAB_SELECTED),
        ],
        style={"marginBottom": theme.SP_3},
    )


def build_layout() -> html.Div:
    about_link = {"color": theme.PRIMARY, "textDecoration": "none", "fontSize": theme.FS_MD, "fontWeight": "500", "whiteSpace": "nowrap", "marginTop": "4px"}
    return html.Div(
        [
            dcc.Location(id="url"),
            dcc.Store(id="session-runs", storage_type="session", data=[]),
            dcc.Store(id="active-run", storage_type="memory"),
            dcc.Store(id="batch-store", storage_type="memory"),
            html.Div(
                [
                    html.Div(
                        [
                            html.H1("Tennessee Eastman Process — Simulation Studio", className="tep-title"),
                            html.Div("Open / closed-loop runs · disturbances · dataset generation", className="tep-subtitle"),
                        ]
                    ),
                    dcc.Link("About the TEP →", href="/about", style=about_link),
                ],
                className="tep-header",
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start", "gap": theme.SP_4},
            ),
            html.Div(_main_tabs(), id="main-view"),
            html.Div(_about_page(), id="about-view", style=theme.HIDDEN),
        ],
        style={"maxWidth": "1280px", "margin": "0 auto", "padding": "16px 20px 40px", "fontFamily": theme.FONT_FAMILY},
    )
