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
    setpoint_target_options,
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


def _simulate_tab() -> html.Div:
    return html.Div(
        [
            _config_card(),
            html.Div(
                [
                    _field("Variables to plot", dcc.Dropdown(id="plot-vars", options=measurement_options(), value=DEFAULT_PLOT_VARS, multi=True)),
                    dcc.Checklist(id="plot-toggles", options=[{"label": " setpoints", "value": "setpoints"}, {"label": " limits", "value": "limits"}], value=["setpoints", "limits"], inline=True),
                    dcc.Loading(dcc.Graph(id="trajectory-graph", config=theme.GRAPH_CONFIG, style={"height": "560px"})),
                    dcc.Loading(dcc.Graph(id="mv-graph", config=theme.GRAPH_CONFIG, style={"height": "320px"})),
                ],
                style={**theme.CARD, **theme.COL_RIGHT},
            ),
        ],
        className="tep-row",
        style=theme.ROW,
    )


def _step_test_tab() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H4("Step test", style={"marginTop": 0}),
                    _field("Kind", dcc.RadioItems(id="step-kind", options=[{"label": " Setpoint (closed loop)", "value": "setpoint"}, {"label": " MV (open loop)", "value": "mv"}], value="setpoint")),
                    _field("Target", dcc.Dropdown(id="step-target", options=setpoint_target_options(), value="reactor_level")),
                    _field("Baseline value", dcc.Input(id="step-baseline", type="number", value=75.0, step="any", className="tep-input", style=theme.INPUT)),
                    _field("Step value", dcc.Input(id="step-value", type="number", value=70.0, step="any", className="tep-input", style=theme.INPUT)),
                    _field("Step time (h)", dcc.Input(id="step-time", type="number", value=1.0, min=0, step="any", className="tep-input", style=theme.INPUT)),
                    _field("Horizon (h)", dcc.Input(id="step-horizon", type="number", value=6.0, min=0.1, step="any", className="tep-input", style=theme.INPUT)),
                    _field("Fidelity", dcc.RadioItems(id="step-ci", options=[{"label": " Explore", "value": 0.01}, {"label": " Fidelity", "value": 0.0005}], value=0.01)),
                    _button("Run step test", "run-step-btn"),
                    html.Div(id="step-status", style=theme.status_style("muted")),
                    html.Div(id="step-banner", style=theme.HIDDEN),
                ],
                className="tep-col-left",
                style={**theme.CARD, **theme.COL_LEFT},
            ),
            html.Div(dcc.Loading(dcc.Graph(id="step-graph", config=theme.GRAPH_CONFIG, style={"height": "640px"})), style={**theme.CARD, **theme.COL_RIGHT}),
        ],
        className="tep-row",
        style=theme.ROW,
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


def _benchmark_tab() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H4("FDD benchmark", style={"marginTop": 0}),
                    html.Div("Fault-free + per-IDV runs with labels, fixed onset, and train/test splits.", style={"fontSize": theme.FS_SM, "color": theme.TEXT_MUTED, "marginBottom": theme.SP_2}),
                    _field("Faults (IDVs)", dcc.Dropdown(id="bench-faults", options=disturbance_options(), value=["idv_01", "idv_04", "idv_06"], multi=True)),
                    _field("Operating mode", dcc.Dropdown(id="bench-mode", options=mode_options(), value="mode1", clearable=False)),
                    _field("Runs per fault", dcc.Input(id="bench-runs", type="number", value=2, min=1, step=1, className="tep-input", style=theme.INPUT)),
                    _field("Fault onset (h)", dcc.Input(id="bench-onset", type="number", value=8.0, min=0, step="any", className="tep-input", style=theme.INPUT)),
                    _field("Horizon (h)", dcc.Input(id="bench-horizon", type="number", value=24.0, min=0.5, step="any", className="tep-input", style=theme.INPUT)),
                    _field("Sampling (min)", dcc.Input(id="bench-sampling", type="number", value=3.0, min=0.1, step="any", className="tep-input", style=theme.INPUT)),
                    _field("Format", dcc.RadioItems(id="bench-format", options=[{"label": " CSV", "value": "csv"}, {"label": " Parquet", "value": "parquet"}, {"label": " JSON", "value": "json"}], value="csv", inline=True)),
                    _button("Generate & download", "bench-run-btn"),
                    html.Div(id="bench-status", style=theme.status_style("muted")),
                    html.Div(id="bench-banner", style=theme.HIDDEN),
                    dcc.Download(id="bench-download"),
                ],
                className="tep-col-left",
                style={**theme.CARD, **theme.COL_LEFT},
            ),
            html.Div([html.H4("Per-fault run summary", style={"marginTop": 0}), dcc.Loading(_table("bench-summary-table"))], style={**theme.CARD, **theme.COL_RIGHT}),
        ],
        className="tep-row",
        style=theme.ROW,
    )


def build_layout() -> html.Div:
    return html.Div(
        [
            dcc.Store(id="session-runs", storage_type="session", data=[]),
            dcc.Store(id="active-run", storage_type="memory"),
            dcc.Store(id="batch-store", storage_type="memory"),
            html.Div(
                [
                    html.H1("Tennessee Eastman Process — Simulation Studio", className="tep-title"),
                    html.Div("Open / closed-loop runs · disturbances · step tests · dataset generation", className="tep-subtitle"),
                ],
                className="tep-header",
            ),
            dcc.Tabs(
                id="tabs",
                value="simulate",
                children=[
                    dcc.Tab(label="Simulate", value="simulate", children=_simulate_tab(), style=theme.TAB, selected_style=theme.TAB_SELECTED),
                    dcc.Tab(label="Step Test", value="steptest", children=_step_test_tab(), style=theme.TAB, selected_style=theme.TAB_SELECTED),
                    dcc.Tab(label="Dataset", value="dataset", children=_dataset_tab(), style=theme.TAB, selected_style=theme.TAB_SELECTED),
                    dcc.Tab(label="Compare", value="compare", children=_compare_tab(), style=theme.TAB, selected_style=theme.TAB_SELECTED),
                    dcc.Tab(label="Benchmark", value="benchmark", children=_benchmark_tab(), style=theme.TAB, selected_style=theme.TAB_SELECTED),
                    dcc.Tab(label="Metrics / Record", value="record", children=_record_tab(), style=theme.TAB, selected_style=theme.TAB_SELECTED),
                ],
                style={"marginBottom": theme.SP_3},
            ),
        ],
        style={"maxWidth": "1280px", "margin": "0 auto", "padding": "16px 20px 40px", "fontFamily": theme.FONT_FAMILY},
    )
