"""Schema-driven Dash widget factories.

These pull labels, units, descriptions, and bounds straight from ``TEP_SCHEMA`` so
the controls stay in sync with the process definition. Imports Dash (only used by
the app, never by the dash-free backend).
"""

from __future__ import annotations

from dash import dcc, html

from tep_studio.simulation.schema import TEP_SCHEMA
from tep_studio.ui import theme
from tep_studio.ui.config import setpoint_fields
from tep_studio.ui.service import default_manual_mvs, default_setpoints

DEFAULT_PLOT_VARS = [
    "measurement.reactor_pressure",
    "measurement.reactor_level",
    "measurement.reactor_temperature",
    "measurement.separator_level",
    "measurement.stripper_level",
    "measurement.stripper_underflow",
]


def mode_options() -> list[dict]:
    from tep_studio.simulation.modes import MODES

    options = []
    for info in MODES:
        options.append({"label": f"{info.label} — {info.product_mix} G:H, {info.production} rate", "value": info.key})
    return options


def disturbance_options() -> list[dict]:
    return [
        {"label": f"{name} — {TEP_SCHEMA.variable('disturbances', name).description}", "value": name}
        for name in TEP_SCHEMA.names("disturbances")
    ]


def measurement_options() -> list[dict]:
    options = []
    for name in TEP_SCHEMA.names("measurements"):
        var = TEP_SCHEMA.variable("measurements", name)
        options.append({"label": f"{var.description} ({var.unit})", "value": f"measurement.{name}"})
    return options


def mv_target_options() -> list[dict]:
    return [
        {"label": f"{name} — {TEP_SCHEMA.variable('manipulated_variables', name).description}", "value": name}
        for name in TEP_SCHEMA.names("manipulated_variables")
    ]


def setpoint_target_options() -> list[dict]:
    return [{"label": field, "value": field} for field in setpoint_fields()]


def mv_sliders() -> list:
    values = default_manual_mvs()
    rows = []
    for name in TEP_SCHEMA.names("manipulated_variables"):
        var = TEP_SCHEMA.variable("manipulated_variables", name)
        rows.append(
            html.Div(
                [
                    html.Label(name, title=var.description, style={"fontSize": theme.FS_SM, "display": "block"}),
                    dcc.Slider(
                        min=0, max=100, value=round(float(values[name]), 1),
                        id={"type": "mv-slider", "name": name},
                        marks=None, tooltip={"placement": "bottom", "always_visible": False},
                    ),
                ],
                style={"marginBottom": theme.SP_1},
            )
        )
    return rows


def setpoint_inputs() -> list:
    values = default_setpoints()
    rows = []
    for field in setpoint_fields():
        rows.append(
            html.Div(
                [
                    html.Label(field, style={"fontSize": theme.FS_SM, "width": "150px", "display": "inline-block"}),
                    dcc.Input(
                        type="number", value=round(float(values[field]), 3),
                        id={"type": "sp-input", "name": field},
                        debounce=True, className="tep-input", style={"width": "120px"},
                    ),
                ],
                style={"marginBottom": theme.SP_1},
            )
        )
    return rows
