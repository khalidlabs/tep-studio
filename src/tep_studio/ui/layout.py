"""Dash layout factories for the TEP interface (one builder per tab)."""

from __future__ import annotations

from dash import dash_table, dcc, html

from tep_studio.ui.config import setpoint_fields
from tep_studio.ui.widgets import (
    DEFAULT_PLOT_VARS,
    disturbance_options,
    measurement_options,
    mv_sliders,
    mv_target_options,
    setpoint_inputs,
    setpoint_target_options,
)

_CARD = {"border": "1px solid #e2e6ec", "borderRadius": "8px", "padding": "14px", "marginBottom": "12px", "backgroundColor": "#ffffff", "boxShadow": "0 1px 2px rgba(16,32,46,0.04)"}
_COL_LEFT = {"flex": "0 0 360px", "maxWidth": "360px"}
_COL_RIGHT = {"flex": "1 1 auto", "minWidth": "0"}
_TAB = {"padding": "9px 16px", "fontWeight": "500", "border": "none", "borderBottom": "3px solid transparent", "backgroundColor": "transparent", "color": "#5a6573"}
_TAB_SELECTED = {"padding": "9px 16px", "fontWeight": "700", "border": "none", "borderBottom": "3px solid #6c4cf0", "backgroundColor": "#ffffff", "color": "#6c4cf0"}


def _field(label: str, control) -> html.Div:
    return html.Div([html.Label(label, style={"fontSize": "12px", "fontWeight": "600"}), control], style={"marginBottom": "8px"})


def _config_card() -> html.Div:
    return html.Div(
        [
            html.H4("Run configuration", style={"marginTop": 0}),
            _field("Loop", dcc.RadioItems(id="loop-type", options=[{"label": " Closed loop", "value": "closed"}, {"label": " Open loop", "value": "open"}], value="closed", inline=True)),
            _field("Horizon (h)", dcc.Input(id="horizon", type="number", value=12.0, min=0.1, step="any", style={"width": "120px"})),
            _field("Fidelity", dcc.RadioItems(id="ci-preset", options=[{"label": " Explore (Δt=0.01 h)", "value": 0.01}, {"label": " Fidelity (Δt=0.0005 h)", "value": 0.0005}], value=0.01)),
            _field("Seed (optional)", dcc.Input(id="seed", type="number", step="any", placeholder="none", style={"width": "120px"})),
            _field("Controller", dcc.Checklist(id="ctrl-flags", options=[{"label": " composition", "value": "composition"}, {"label": " overrides", "value": "overrides"}, {"label": " %G feedback", "value": "pct_g_feedback"}], value=["composition"])),
            html.Div(setpoint_inputs(), id="closed-controls", style={**_CARD, "display": "block"}),
            html.Div(mv_sliders(), id="open-controls", style={**_CARD, "display": "none"}),
            html.H4("Disturbances"),
            _field("Active IDVs", dcc.Dropdown(id="dist-select", options=disturbance_options(), multi=True, placeholder="none")),
            _field("Activation time (h)", dcc.Input(id="dist-start", type="number", value=1.0, min=0, step="any", style={"width": "120px"})),
            html.Button("Run simulation", id="run-btn", n_clicks=0, style={"width": "100%", "padding": "8px", "fontWeight": "600"}),
            html.Div(id="run-status", style={"fontSize": "12px", "marginTop": "8px", "color": "#555"}),
            html.Hr(),
            html.Div([
                html.Button("Save scenario", id="save-scenario-btn", n_clicks=0, style={"marginRight": "8px"}),
                dcc.Upload(html.Button("Load scenario"), id="scenario-upload", accept=".json"),
            ]),
            dcc.Download(id="scenario-download"),
        ],
        style={**_CARD, **_COL_LEFT},
    )


def _simulate_tab() -> html.Div:
    return html.Div(
        [
            _config_card(),
            html.Div(
                [
                    _field("Variables to plot", dcc.Dropdown(id="plot-vars", options=measurement_options(), value=DEFAULT_PLOT_VARS, multi=True)),
                    dcc.Checklist(id="plot-toggles", options=[{"label": " setpoints", "value": "setpoints"}, {"label": " limits", "value": "limits"}], value=["setpoints", "limits"], inline=True),
                    dcc.Loading(dcc.Graph(id="trajectory-graph", style={"height": "560px"})),
                    dcc.Loading(dcc.Graph(id="mv-graph", style={"height": "320px"})),
                ],
                style={**_CARD, **_COL_RIGHT},
            ),
        ],
        style={"display": "flex", "gap": "12px", "alignItems": "flex-start"},
    )


def _step_test_tab() -> html.Div:
    return html.Div(
        [
            html.Div(
                [
                    html.H4("Step test", style={"marginTop": 0}),
                    _field("Kind", dcc.RadioItems(id="step-kind", options=[{"label": " Setpoint (closed loop)", "value": "setpoint"}, {"label": " MV (open loop)", "value": "mv"}], value="setpoint")),
                    _field("Target", dcc.Dropdown(id="step-target", options=setpoint_target_options(), value="reactor_level")),
                    _field("Baseline value", dcc.Input(id="step-baseline", type="number", value=75.0, step="any", style={"width": "120px"})),
                    _field("Step value", dcc.Input(id="step-value", type="number", value=70.0, step="any", style={"width": "120px"})),
                    _field("Step time (h)", dcc.Input(id="step-time", type="number", value=1.0, min=0, step="any", style={"width": "120px"})),
                    _field("Horizon (h)", dcc.Input(id="step-horizon", type="number", value=6.0, min=0.1, step="any", style={"width": "120px"})),
                    _field("Fidelity", dcc.RadioItems(id="step-ci", options=[{"label": " Explore", "value": 0.01}, {"label": " Fidelity", "value": 0.0005}], value=0.01)),
                    html.Button("Run step test", id="run-step-btn", n_clicks=0, style={"width": "100%", "padding": "8px", "fontWeight": "600"}),
                    html.Div(id="step-status", style={"fontSize": "12px", "marginTop": "8px", "color": "#555"}),
                ],
                style={**_CARD, **_COL_LEFT},
            ),
            html.Div(dcc.Loading(dcc.Graph(id="step-graph", style={"height": "640px"})), style={**_CARD, **_COL_RIGHT}),
        ],
        style={"display": "flex", "gap": "12px", "alignItems": "flex-start"},
    )


def _dataset_tab() -> html.Div:
    sweep_options = [{"label": f"setpoints.{f}", "value": f"setpoints.{f}"} for f in setpoint_fields()]
    return html.Div(
        [
            html.Div(
                [
                    html.H4("Export dataset", style={"marginTop": 0}),
                    _field("Runs to include", dcc.Checklist(id="dataset-runs", options=[], value=[])),
                    _field("Format", dcc.RadioItems(id="dataset-format", options=[{"label": " CSV", "value": "csv"}, {"label": " Parquet", "value": "parquet"}], value="csv", inline=True)),
                    html.Button("Build & download", id="build-dataset-btn", n_clicks=0, style={"width": "100%", "padding": "8px"}),
                    dcc.Download(id="dataset-download"),
                ],
                style={**_CARD, **_COL_LEFT},
            ),
            html.Div(
                [
                    html.H4("Batch generation", style={"marginTop": 0}),
                    _field("Seeds (comma-separated)", dcc.Input(id="batch-seeds", type="text", value="1, 2, 3", style={"width": "100%"})),
                    _field("Sweep parameter (optional)", dcc.Dropdown(id="batch-field", options=sweep_options, placeholder="none")),
                    _field("Sweep values (comma-separated)", dcc.Input(id="batch-values", type="text", placeholder="e.g. 22, 28, 32", style={"width": "100%"})),
                    html.Button("Run batch", id="run-batch-btn", n_clicks=0, style={"width": "100%", "padding": "8px", "fontWeight": "600"}),
                    html.Div(id="batch-status", style={"fontSize": "12px", "margin": "8px 0", "color": "#555"}),
                    dcc.Loading(dash_table.DataTable(id="batch-table", page_size=8, style_table={"overflowX": "auto"})),
                    html.Div([
                        html.Button("Download combined dataset", id="batch-dataset-btn", n_clicks=0, style={"marginRight": "8px"}),
                        html.Button("Download metrics CSV", id="batch-metrics-btn", n_clicks=0),
                    ], style={"marginTop": "8px"}),
                    dcc.Download(id="batch-dataset-download"),
                    dcc.Download(id="batch-metrics-download"),
                ],
                style={**_CARD, **_COL_RIGHT},
            ),
        ],
        style={"display": "flex", "gap": "12px", "alignItems": "flex-start"},
    )


def _compare_tab() -> html.Div:
    return html.Div(
        [
            html.Div([
                html.H4("Compare runs", style={"marginTop": 0, "display": "inline-block"}),
                html.Button("Clear all runs", id="clear-runs-btn", n_clicks=0, style={"marginLeft": "16px"}),
            ]),
            dash_table.DataTable(id="compare-table", page_size=8, style_table={"overflowX": "auto"}),
            _field("Overlay variable", dcc.Dropdown(id="compare-var", options=measurement_options(), value="measurement.reactor_pressure")),
            dcc.Loading(dcc.Graph(id="compare-graph", style={"height": "520px"})),
        ],
        style=_CARD,
    )


def _record_tab() -> html.Div:
    return html.Div(
        [
            html.H4("Metrics & experiment record", style={"marginTop": 0}),
            _field("Run", dcc.Dropdown(id="record-run", options=[], placeholder="run a simulation first")),
            html.Div(id="metrics-panel"),
            html.H4("Experiment record (P6)"),
            html.Button("Download record JSON", id="download-record-btn", n_clicks=0),
            dcc.Download(id="record-download"),
            html.Pre(id="record-json", style={"background": "#f6f8fa", "padding": "10px", "borderRadius": "6px", "overflowX": "auto", "fontSize": "11px", "maxHeight": "420px"}),
        ],
        style=_CARD,
    )


def build_layout() -> html.Div:
    return html.Div(
        [
            dcc.Store(id="session-runs", storage_type="session", data=[]),
            dcc.Store(id="active-run", storage_type="memory"),
            dcc.Store(id="batch-store", storage_type="memory"),
            html.H2("Tennessee Eastman Process — Simulation Studio", style={"marginBottom": "4px", "color": "#16202e"}),
            html.Div("Open / closed-loop runs · disturbances · step tests · dataset generation", style={"color": "#5a6573", "marginBottom": "12px"}),
            dcc.Tabs(
                id="tabs",
                value="simulate",
                children=[
                    dcc.Tab(label="Simulate", value="simulate", children=_simulate_tab(), style=_TAB, selected_style=_TAB_SELECTED),
                    dcc.Tab(label="Step Test", value="steptest", children=_step_test_tab(), style=_TAB, selected_style=_TAB_SELECTED),
                    dcc.Tab(label="Dataset", value="dataset", children=_dataset_tab(), style=_TAB, selected_style=_TAB_SELECTED),
                    dcc.Tab(label="Compare", value="compare", children=_compare_tab(), style=_TAB, selected_style=_TAB_SELECTED),
                    dcc.Tab(label="Metrics / Record", value="record", children=_record_tab(), style=_TAB, selected_style=_TAB_SELECTED),
                ],
                style={"marginBottom": "12px"},
            ),
        ],
        style={"maxWidth": "1280px", "margin": "0 auto", "padding": "16px 20px 40px", "fontFamily": "system-ui, sans-serif"},
    )
