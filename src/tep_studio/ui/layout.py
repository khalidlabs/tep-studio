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
from tep_studio.simulation.excitation import SIGNAL_TYPES
from tep_studio.simulation.schema import TEP_SCHEMA
from tep_studio.ui.about_content import ABOUT_SECTIONS
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


def _excitation_card() -> html.Div:
    """Designed plant-test (system-identification) excitation generator."""
    cap = {"fontSize": theme.FS_SM, "color": theme.TEXT_MUTED, "marginBottom": theme.SP_2}
    sp_targets = [{"label": f, "value": f} for f in setpoint_fields()]
    return html.Div(
        [
            html.H4("System identification — excitation", style={"marginTop": 0}),
            html.Div(
                "Generate a designed plant test (PRBS, GBN, APRBS, multisine, chirp) for model identification — the data you'd collect to "
                "commission an APC/MPC. Closed loop excites the controller setpoints (safe); open loop excites the valves directly — keep those short.",
                style=cap,
            ),
            html.Div(
                [
                    html.Div(
                        [
                            _field("Loop", dcc.RadioItems(id="exc-loop", options=[{"label": " Closed (setpoints)", "value": "closed"}, {"label": " Open (MVs)", "value": "open"}], value="closed", inline=True)),
                            _field("Signal", dcc.Dropdown(id="exc-signal", options=[{"label": s, "value": s} for s in SIGNAL_TYPES], value="prbs", clearable=False)),
                            _field("Targets", dcc.Dropdown(id="exc-targets", options=sp_targets, value=["reactor_pressure", "production_rate"], multi=True)),
                            _field("Amplitude (fraction of safe range)", dcc.Input(id="exc-amp", type="number", value=0.3, min=0, max=1, step="any", className="tep-input", style=theme.INPUT)),
                        ],
                        className="tep-col-left",
                        style={**theme.CARD, **theme.COL_LEFT},
                    ),
                    html.Div(
                        [
                            _field("Clock / hold (h) — step·PRBS·GBN·APRBS", dcc.Input(id="exc-clock", type="number", value=0.5, min=0.01, step="any", className="tep-input", style=theme.INPUT)),
                            _field("Frequency band (1/h) — multisine·chirp", html.Div([
                                dcc.Input(id="exc-flow", type="number", value=0.1, step="any", className="tep-input", style={**theme.INPUT, "width": "96px", "marginRight": theme.SP_2}),
                                dcc.Input(id="exc-fhigh", type="number", value=2.0, step="any", className="tep-input", style={**theme.INPUT, "width": "96px"}),
                            ])),
                            _field("Horizon (h)", dcc.Input(id="exc-horizon", type="number", value=16.0, min=0.5, step="any", className="tep-input", style=theme.INPUT)),
                            _field("Seed", dcc.Input(id="exc-seed", type="number", value=1, step=1, className="tep-input", style=theme.INPUT)),
                            _button("Run excitation", "exc-run-btn"),
                            html.Div(id="exc-status", style=theme.status_style("muted")),
                            html.Div(id="exc-banner", style=theme.HIDDEN),
                        ],
                        style={**theme.CARD, **theme.COL_RIGHT},
                    ),
                ],
                className="tep-row",
                style=theme.ROW,
            ),
            html.Div(id="exc-quality", style={"marginTop": theme.SP_2}),
        ],
        style=theme.CARD,
    )


def _dataset_tab() -> html.Div:
    sweep_options = (
        [{"label": f"setpoints.{f}", "value": f"setpoints.{f}"} for f in setpoint_fields()]
        + [{"label": "horizon", "value": "horizon"}, {"label": "control_interval", "value": "control_interval"}, {"label": "fixed_step", "value": "fixed_step"}]
    )
    return html.Div(
        [
            _excitation_card(),
            html.Div(
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
            ),
        ],
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


_ABOUT_H3 = {"color": theme.TITLE, "fontSize": theme.FS_LG, "fontWeight": "600", "marginTop": theme.SP_4, "marginBottom": theme.SP_1}
_ABOUT_PARA = {"color": theme.TEXT, "fontSize": theme.FS_MD, "lineHeight": "1.65", "marginBottom": theme.SP_2}
_ABOUT_NOTE = {"color": theme.TEXT_MUTED, "fontSize": theme.FS_SM, "lineHeight": "1.55", "marginBottom": theme.SP_2}
_ABOUT_UL = {"color": theme.TEXT, "fontSize": theme.FS_MD, "lineHeight": "1.65", "marginTop": 0, "marginBottom": theme.SP_2, "paddingLeft": "20px"}
_ABOUT_MONO = {"fontFamily": theme.FONT_MONO, "fontSize": theme.FS_SM, "background": theme.SURFACE_ALT, "padding": "10px 12px", "borderRadius": theme.RADIUS_SM, "lineHeight": "1.8", "margin": "0 0 " + theme.SP_2 + " 0", "whiteSpace": "pre", "overflowX": "auto"}


def _render_blocks(blocks: list) -> list:
    """Render the verified About-page content blocks (see ui.about_content) to Dash nodes."""
    out: list = []
    for b in blocks:
        kind = b.get("type")
        if kind == "subheading":
            out.append(html.H3(b.get("text", ""), style=_ABOUT_H3))
        elif kind == "para":
            out.append(html.P(b.get("text", ""), style=_ABOUT_PARA))
        elif kind == "note":
            out.append(html.P(b.get("text", ""), style=_ABOUT_NOTE))
        elif kind == "reactions":
            out.append(html.Div(chr(10).join(b.get("lines", [])), style=_ABOUT_MONO))
        elif kind == "bullets":
            items = []
            for it in b.get("items", []):
                term = it.get("term") or ""
                if term:
                    items.append(html.Li([html.B(term + " \u2014 "), it.get("text", "")]))
                else:
                    items.append(html.Li(it.get("text", "")))
            out.append(html.Ul(items, style=_ABOUT_UL))
    return out


def _schema_table(category: str, table_id: str, *, page_size: int = 10) -> dash_table.DataTable:
    """A sortable, filterable reference table of one schema category (name / unit / description)."""
    rows = []
    for i, name in enumerate(TEP_SCHEMA.names(category), start=1):
        var = TEP_SCHEMA.variable(category, name)
        rows.append({"#": i, "variable": name, "unit": getattr(var, "unit", "") or "", "description": getattr(var, "description", "") or ""})
    return dash_table.DataTable(
        id=table_id,
        data=rows,
        columns=[{"name": "#", "id": "#"}, {"name": "variable", "id": "variable"}, {"name": "unit", "id": "unit"}, {"name": "description", "id": "description"}],
        page_size=page_size,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto", "marginBottom": theme.SP_3},
        style_header={"backgroundColor": theme.SURFACE_ALT, "fontWeight": "600", "border": "1px solid " + theme.BORDER},
        style_cell={"fontSize": theme.FS_SM, "padding": "6px 10px", "fontFamily": theme.FONT_FAMILY, "border": "1px solid " + theme.BORDER, "textAlign": "left", "whiteSpace": "normal", "height": "auto", "maxWidth": "440px"},
        style_cell_conditional=[
            {"if": {"column_id": "#"}, "width": "44px"},
            {"if": {"column_id": "variable"}, "fontFamily": theme.FONT_MONO},
            {"if": {"column_id": "unit"}, "width": "84px"},
        ],
    )


def _about_variables() -> html.Div:
    sub = {"color": theme.TITLE, "fontSize": theme.FS_LG, "fontWeight": "600", "marginTop": theme.SP_4, "marginBottom": theme.SP_1}
    return html.Div(
        [
            html.P("Every variable the simulator exposes, grouped by role. The tables are sortable and filterable \u2014 type in a column filter to search.", style=_ABOUT_NOTE),
            html.H3("Manipulated variables (12)", style=sub),
            html.P("The valve and agitator setpoints a controller can move.", style=_ABOUT_NOTE),
            _schema_table("manipulated_variables", "about-mv-table", page_size=12),
            html.H3("Measurements (41)", style=sub),
            html.P("22 continuous process measurements plus 19 sampled stream compositions.", style=_ABOUT_NOTE),
            _schema_table("measurements", "about-meas-table"),
            html.H3("States (50)", style=sub),
            html.P("The internal model state: component holdups and energies across the units, plus the 12 valve positions.", style=_ABOUT_NOTE),
            _schema_table("states", "about-state-table"),
            html.H3("Disturbances (28)", style=sub),
            html.P("Selectable fault modes (IDVs) for disturbance-rejection and fault-detection studies.", style=_ABOUT_NOTE),
            _schema_table("disturbances", "about-dist-table"),
        ],
        style={"paddingTop": theme.SP_3},
    )


def _about_back_link() -> dcc.Link:
    return dcc.Link("\u2190 Back to the studio", href="/", style={"color": theme.PRIMARY, "textDecoration": "none", "fontSize": theme.FS_MD, "fontWeight": "500"})


def _about_section(key: str) -> html.Div:
    return html.Div(_render_blocks(ABOUT_SECTIONS[key]["blocks"]), style={"paddingTop": theme.SP_3})


def _about_page() -> html.Div:
    """A standalone, multi-section information page on the TEP (routed at /about)."""
    tab = dict(style=theme.TAB, selected_style=theme.TAB_SELECTED)
    return html.Div(
        [
            _about_back_link(),
            html.H1("The Tennessee Eastman Process", style={"color": theme.TITLE, "fontSize": "26px", "fontWeight": "700", "marginTop": theme.SP_3, "marginBottom": theme.SP_2}),
            dcc.Tabs(
                id="about-tabs",
                value="overview",
                children=[
                    dcc.Tab(label="Overview", value="overview", children=_about_section("overview"), **tab),
                    dcc.Tab(label="Plant & chemistry", value="plant", children=_about_section("plant"), **tab),
                    dcc.Tab(label="Variables", value="variables", children=_about_variables(), **tab),
                    dcc.Tab(label="Control strategy", value="control", children=_about_section("control"), **tab),
                    dcc.Tab(label="Using the studio", value="usage", children=_about_section("usage"), **tab),
                ],
                style={"marginTop": theme.SP_3, "marginBottom": theme.SP_3},
            ),
            html.Hr(style={"border": "none", "borderTop": "1px solid " + theme.BORDER, "margin": theme.SP_4 + " 0 " + theme.SP_3}),
            html.P("Reference: J. J. Downs and E. F. Vogel, \u201cA plant-wide industrial process control problem,\u201d Computers & Chemical Engineering 17(3), 1993.", style={**_ABOUT_NOTE, "fontStyle": "italic"}),
            _about_back_link(),
        ],
        style={**theme.CARD, "maxWidth": "920px", "margin": "0 auto", "padding": "24px 32px 32px"},
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
