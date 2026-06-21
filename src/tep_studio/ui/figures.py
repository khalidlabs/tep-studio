"""Interactive Plotly figure builders for the TEP interface.

Schema-aware (titles/units from ``TEP_SCHEMA``), with constraint-limit and setpoint
overlays mirroring ``core._constraint_margins``. Dash-free -- only depends on
plotly + pandas, so the builders are unit-testable on their own.
"""

from __future__ import annotations

from math import ceil
from typing import Sequence

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from tep_studio.simulation.schema import TEP_SCHEMA
from tep_studio.ui import theme

# Constraint limits per measurement column (mirrors core._constraint_margins).
LIMIT_LINES: dict[str, list[tuple[float, str]]] = {
    "measurement.reactor_pressure": [(3000.0, "Shutdown 3000 kPa")],
    "measurement.reactor_temperature": [(175.0, "High-temp limit")],
    "measurement.reactor_level": [(0.0, "Low"), (100.0, "High")],
    "measurement.separator_level": [(0.0, "Low"), (100.0, "High")],
    "measurement.stripper_level": [(0.0, "Low"), (100.0, "High")],
}
# Measurement column -> ControllerSetpoints field, for setpoint overlays.
SETPOINT_FIELD: dict[str, str] = {
    "measurement.reactor_level": "reactor_level",
    "measurement.reactor_pressure": "reactor_pressure",
    "measurement.reactor_temperature": "reactor_temperature",
    "measurement.separator_level": "separator_level",
    "measurement.stripper_level": "stripper_level",
    "measurement.stripper_underflow": "production_rate",
}
# Sourced from the central theme so app chrome and plots share one palette.
_BLUE = theme.BLUE
_RED = theme.RED
_PALETTE = theme.PALETTE


def _label(column: str) -> tuple[str, str]:
    if column.startswith("measurement."):
        name = column.split(".", 1)[1]
        try:
            var = TEP_SCHEMA.variable("measurements", name)
            return var.description, var.unit
        except KeyError:
            return name, ""
    return column.split(".", 1)[-1], ""


def _thin(frame, max_points: int):
    n = len(frame)
    if n <= max_points:
        return frame
    return frame.iloc[:: int(ceil(n / max_points))]


def _style(fig: go.Figure, uirevision=None) -> go.Figure:
    # uirevision keyed on the RUN (not a constant): a new run rescales the axes to
    # the new data, while re-plotting the same run preserves the user's zoom/pan.
    fig.update_layout(
        template="tep",
        margin=dict(l=60, r=20, t=50, b=50),
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        uirevision=uirevision,
    )
    return fig


def trajectory_grid(
    frame,
    variables: Sequence[str],
    *,
    setpoints: dict | None = None,
    show_limits: bool = True,
    shutdown_time: float | None = None,
    max_points: int = 3000,
    uirevision: str | None = None,
) -> go.Figure:
    """One panel per variable; overlays setpoints (dotted), limits (dashed), shutdown (vline)."""
    columns = [c if c.startswith(("measurement.", "state.", "implemented_action.")) else f"measurement.{c}" for c in variables]
    frame = _thin(frame, max_points)
    n = max(1, len(columns))
    rows = ceil(n / 2)
    titles = [f"{_label(c)[0]} ({_label(c)[1]})" if _label(c)[1] else _label(c)[0] for c in columns]
    fig = make_subplots(rows=rows, cols=2, shared_xaxes=True, subplot_titles=titles, vertical_spacing=0.08)
    for i, column in enumerate(columns):
        r, c = i // 2 + 1, i % 2 + 1
        fig.add_trace(go.Scatter(x=frame["time"], y=frame[column], mode="lines", line=dict(color=_BLUE, width=1.5), name=_label(column)[0], showlegend=False), row=r, col=c)
        if setpoints and column in SETPOINT_FIELD and SETPOINT_FIELD[column] in setpoints:
            fig.add_hline(y=setpoints[SETPOINT_FIELD[column]], line_dash="dot", line_color="#888888", line_width=1, row=r, col=c)
        if show_limits:
            for value, _name in LIMIT_LINES.get(column, []):
                fig.add_hline(y=value, line_dash="dash", line_color=_RED, line_width=1, row=r, col=c)
        if shutdown_time is not None:
            fig.add_vline(x=shutdown_time, line_dash="dot", line_color="#444444", line_width=1, row=r, col=c)
    fig.update_xaxes(title_text="Time (h)", row=rows, col=1)
    fig.update_xaxes(title_text="Time (h)", row=rows, col=2)
    return _style(fig, uirevision)


def mv_panel(frame, mvs: Sequence[str], *, which: str = "implemented_action", max_points: int = 3000, uirevision: str | None = None) -> go.Figure:
    frame = _thin(frame, max_points)
    fig = go.Figure()
    for mv in mvs:
        column = f"{which}.{mv}"
        if column in frame.columns:
            fig.add_trace(go.Scatter(x=frame["time"], y=frame[column], mode="lines", line=dict(width=1.3), name=mv))
    fig.update_layout(title="Manipulated variables (%)", xaxis_title="Time (h)", yaxis_title="Valve / speed (%)", yaxis_range=[-2, 102])
    fig = _style(fig, uirevision)
    # 12 traces: put the legend below the plot so it doesn't crowd the title.
    fig.update_layout(legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="left", x=0), margin=dict(b=110))
    return fig


def compare_overlay(runs: Sequence, column: str, *, max_points: int = 3000, uirevision: str | None = None) -> go.Figure:
    """Overlay one variable across several RunResults."""
    column = column if column.startswith(("measurement.", "state.", "implemented_action.")) else f"measurement.{column}"
    title, unit = _label(column)
    fig = go.Figure()
    setpoints = None
    for i, run in enumerate(runs):
        frame = _thin(run.to_frame(), max_points)
        if column not in frame.columns:
            continue
        label = run.scenario.name or run.run_id
        fig.add_trace(go.Scatter(x=frame["time"], y=frame[column], mode="lines", line=dict(width=1.5, color=_PALETTE[i % len(_PALETTE)]), name=label))
        setpoints = setpoints or (run.record or {}).get("setpoints")
    for value, name in LIMIT_LINES.get(column, []):
        fig.add_hline(y=value, line_dash="dash", line_color=_RED, annotation_text=name)
    fig.update_layout(title=f"Compare: {title}", xaxis_title="Time (h)", yaxis_title=unit)
    return _style(fig, uirevision)


def compare_overlay_multi(runs: Sequence, columns: Sequence[str], *, max_points: int = 3000, uirevision: str | None = None) -> go.Figure:
    """Overlay several variables (one stacked panel each) across several RunResults.

    Color encodes the run (consistent across panels); each variable gets its own row.
    The single-variable :func:`compare_overlay` is kept for the 1-variable case.
    """
    cols = [c if c.startswith(("measurement.", "state.", "implemented_action.")) else f"measurement.{c}" for c in columns]
    titles = [f"{_label(c)[0]} ({_label(c)[1]})" if _label(c)[1] else _label(c)[0] for c in cols]
    fig = make_subplots(rows=max(1, len(cols)), cols=1, shared_xaxes=True, subplot_titles=titles, vertical_spacing=0.08)
    frames = [_thin(run.to_frame(), max_points) for run in runs]
    for r, column in enumerate(cols, start=1):
        for i, (run, frame) in enumerate(zip(runs, frames)):
            if column not in frame.columns:
                continue
            label = run.scenario.name or run.run_id
            # One legend entry per run (on the first panel only) to avoid duplicates.
            fig.add_trace(
                go.Scatter(x=frame["time"], y=frame[column], mode="lines", line=dict(width=1.5, color=_PALETTE[i % len(_PALETTE)]), name=label, legendgroup=label, showlegend=(r == 1)),
                row=r,
                col=1,
            )
        for value, _name in LIMIT_LINES.get(column, []):
            fig.add_hline(y=value, line_dash="dash", line_color=_RED, line_width=1, row=r, col=1)
    fig.update_xaxes(title_text="Time (h)", row=len(cols), col=1)
    return _style(fig, uirevision)


def step_response(frame, response_column: str, drive_column: str, step_time: float, *, max_points: int = 5000, uirevision: str | None = None) -> go.Figure:
    """Two stacked panels: the driven signal and the measured response (visualization only)."""
    frame = _thin(frame, max_points)
    drive_title = _label(drive_column)[0]
    resp_title, resp_unit = _label(response_column)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, subplot_titles=[f"Drive: {drive_title}", f"Response: {resp_title} ({resp_unit})" if resp_unit else f"Response: {resp_title}"])
    fig.add_trace(go.Scatter(x=frame["time"], y=frame[drive_column], mode="lines", line=dict(color="#888888", width=1.5), name=drive_title), row=1, col=1)
    fig.add_trace(go.Scatter(x=frame["time"], y=frame[response_column], mode="lines", line=dict(color=_BLUE, width=1.6), name=resp_title), row=2, col=1)
    fig.add_vline(x=step_time, line_dash="dot", line_color=_RED, line_width=1)
    fig.update_xaxes(title_text="Time (h)", row=2, col=1)
    return _style(fig, uirevision)


def excitation_diagnostics(times, input_cols, input_mat, frame, response_columns, *, dt: float, uirevision: str | None = None) -> go.Figure:
    """Three stacked panels for a system-identification run: the designed excitation input(s)
    over time, their power spectrum (band coverage), and the measured plant response."""
    fig = make_subplots(
        rows=3, cols=1, vertical_spacing=0.1,
        subplot_titles=["Excitation input (deviation from baseline)", "Input power spectrum", "Plant response"],
    )
    for j, name in enumerate(input_cols):
        color = _PALETTE[j % len(_PALETTE)]
        y = np.asarray(input_mat)[:, j]
        fig.add_trace(go.Scatter(x=times, y=y, mode="lines", line=dict(color=color, width=1.3), name=name), row=1, col=1)
        sig = y - y.mean()
        freqs = np.fft.rfftfreq(len(sig), d=dt)
        amp = np.abs(np.fft.rfft(sig))
        fig.add_trace(go.Scatter(x=freqs[1:], y=amp[1:], mode="lines", line=dict(color=color, width=1.2), name=name, showlegend=False), row=2, col=1)
    frame = _thin(frame, 5000)
    for k, col in enumerate(response_columns):
        if col in frame:
            fig.add_trace(go.Scatter(x=frame["time"], y=frame[col], mode="lines", line=dict(color=_PALETTE[k % len(_PALETTE)], width=1.4), name=_label(col)[0]), row=3, col=1)
    fig.update_xaxes(title_text="Time (h)", row=1, col=1)
    fig.update_xaxes(title_text="Frequency (1/h)", row=2, col=1)
    fig.update_xaxes(title_text="Time (h)", row=3, col=1)
    return _style(fig, uirevision)


def batch_coverage(rows, *, x_key: str = "production_mean", y_key: str = "peak_reactor_pressure", uirevision: str | None = None) -> go.Figure:
    """Scatter of what a batch dataset spans: an outcome (y) vs a knob/outcome (x), split by
    whether each run tripped — so the operating envelope and the safe region are visible."""
    def pts(predicate):
        xs, ys, txt = [], [], []
        for r in rows:
            if predicate(bool(r.get("terminated"))) and r.get(x_key) is not None and r.get(y_key) is not None:
                xs.append(r[x_key]); ys.append(r[y_key]); txt.append(r.get("name", ""))
        return xs, ys, txt

    fig = go.Figure()
    ok_x, ok_y, ok_t = pts(lambda t: not t)
    tr_x, tr_y, tr_t = pts(lambda t: t)
    fig.add_trace(go.Scatter(x=ok_x, y=ok_y, mode="markers", marker=dict(color=_BLUE, size=9), name="ran", text=ok_t, hovertemplate="%{text}<br>%{x}, %{y}<extra></extra>"))
    if tr_x:
        fig.add_trace(go.Scatter(x=tr_x, y=tr_y, mode="markers", marker=dict(color=_RED, size=11, symbol="x"), name="tripped", text=tr_t, hovertemplate="%{text}<br>%{x}, %{y}<extra></extra>"))
    if y_key == "peak_reactor_pressure":
        fig.add_hline(y=3000.0, line_dash="dash", line_color=_RED, line_width=1, annotation_text="shutdown 3000 kPa")
    fig.update_xaxes(title_text=x_key.replace("_", " "))
    fig.update_yaxes(title_text=y_key.replace("_", " "))
    return _style(fig, uirevision)
