"""Dash callbacks wiring the widgets to the backend service and Plotly figures.

All heavy work is delegated to ``tep_studio.ui.service`` (Dash-free). Runs are
stored in a server-side ``RunStore``; the browser session keeps only small run
summaries. Imports Dash (used only by the app).
"""

from __future__ import annotations

import base64
import json

import plotly.graph_objects as go
from dash import ALL, Input, Output, State, dcc, html, no_update
from dash.exceptions import PreventUpdate

from tep_studio.simulation.schema import TEP_SCHEMA
from tep_studio.ui import figures, service
from tep_studio.ui.config import BatchSpec, DisturbanceActivation, ScenarioConfig, StepTestSpec
from tep_studio.ui.service import default_manual_mvs, default_setpoints
from tep_studio.ui.widgets import DEFAULT_PLOT_VARS, mv_target_options, setpoint_target_options

_SHOW = {"border": "1px solid #ddd", "borderRadius": "6px", "padding": "12px", "marginBottom": "12px", "display": "block"}
_HIDE = {"display": "none"}

SETPOINT_TO_MEAS = {
    "reactor_level": "measurement.reactor_level",
    "reactor_pressure": "measurement.reactor_pressure",
    "reactor_temperature": "measurement.reactor_temperature",
    "separator_level": "measurement.separator_level",
    "stripper_level": "measurement.stripper_level",
    "production_rate": "measurement.stripper_underflow",
    "pct_g": "measurement.stripper_underflow_G_concentration",
    "ya": "measurement.reactor_feed_A_concentration",
    "yac": "measurement.reactor_feed_C_concentration",
}
MV_TO_MEAS = {
    "d_feed_valve": "measurement.feed_D_flow",
    "e_feed_valve": "measurement.feed_E_flow",
    "a_feed_valve": "measurement.feed_A_flow",
    "ac_feed_valve": "measurement.feed_AC_flow",
    "purge_valve": "measurement.purge_flow",
    "reactor_cooling_water_valve": "measurement.reactor_temperature",
    "separator_cooling_water_valve": "measurement.separator_temperature",
}


def _empty(message: str = "Run a simulation to see results") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(size=14, color="#999"))
    fig.update_layout(template="plotly_white", xaxis_visible=False, yaxis_visible=False, margin=dict(l=20, r=20, t=20, b=20))
    return fig


def _floats(text) -> list[float]:
    if not text:
        return []
    return [float(x) for x in str(text).replace(";", ",").split(",") if x.strip()]


def _parse_seed(seed):
    return None if seed in (None, "") else float(seed)


def _scenario(loop, horizon, ci, seed, flags, sp_values, sp_ids, mv_values, mv_ids, dist_select, dist_start, name="scenario") -> ScenarioConfig:
    flags = flags or []
    setpoints = {i["name"]: float(v) for i, v in zip(sp_ids, sp_values) if v is not None} or None
    manual_mvs = {i["name"]: float(v) for i, v in zip(mv_ids, mv_values) if v is not None} or None
    disturbances = tuple(
        DisturbanceActivation(idv=name_, magnitude=1.0, start_time=float(dist_start or 0.0)) for name_ in (dist_select or [])
    )
    return ScenarioConfig(
        name=name,
        loop_type=loop,
        horizon=float(horizon or 12.0),
        control_interval=float(ci),
        seed=_parse_seed(seed),
        disturbances=disturbances,
        setpoints=setpoints if loop == "closed" else None,
        manual_mvs=manual_mvs if loop == "open" else None,
        enable_composition="composition" in flags,
        enable_overrides="overrides" in flags,
        enable_pct_g_feedback="pct_g_feedback" in flags,
    )


# Shared State lists for the simulate-tab configuration form.
_SIM_STATE = [
    State("loop-type", "value"),
    State("horizon", "value"),
    State("ci-preset", "value"),
    State("seed", "value"),
    State("ctrl-flags", "value"),
    State({"type": "sp-input", "name": ALL}, "value"),
    State({"type": "sp-input", "name": ALL}, "id"),
    State({"type": "mv-slider", "name": ALL}, "value"),
    State({"type": "mv-slider", "name": ALL}, "id"),
    State("dist-select", "value"),
    State("dist-start", "value"),
]


def register_callbacks(app, store) -> None:
    # -- toggle open/closed control panels --------------------------------
    @app.callback(Output("closed-controls", "style"), Output("open-controls", "style"), Input("loop-type", "value"))
    def _toggle(loop):
        return (_HIDE, _SHOW) if loop == "open" else (_SHOW, _HIDE)

    # -- run a simulation -------------------------------------------------
    @app.callback(
        Output("active-run", "data", allow_duplicate=True),
        Output("session-runs", "data", allow_duplicate=True),
        Output("run-status", "children"),
        Input("run-btn", "n_clicks"),
        *_SIM_STATE,
        State("session-runs", "data"),
        prevent_initial_call=True,
    )
    def run_simulation(n, loop, horizon, ci, seed, flags, sp_v, sp_id, mv_v, mv_id, dist, dist_start, session):
        cfg = _scenario(loop, horizon, ci, seed, flags, sp_v, sp_id, mv_v, mv_id, dist, dist_start, name=f"{loop}_run")
        run = service.run_scenario(cfg)
        store.put(run)
        session = (session or []) + [run.summary()]
        outcome = f"shutdown at {run.final_time:.2f} h" if run.terminated else f"ran {run.final_time:.1f} h"
        status = f"{outcome} · peak reactor P = {run.peak.get('reactor_pressure_max', 0):.0f} kPa · run {run.run_id}"
        return run.run_id, session, status

    # -- render the simulate plots from the stored run --------------------
    @app.callback(
        Output("trajectory-graph", "figure"),
        Output("mv-graph", "figure"),
        Input("active-run", "data"),
        Input("plot-vars", "value"),
        Input("plot-toggles", "value"),
    )
    def render_simulate(run_id, plot_vars, toggles):
        run = store.get(run_id) if run_id else None
        if run is None:
            return _empty(), _empty()
        frame = run.to_frame()
        toggles = toggles or []
        setpoints = (run.record or {}).get("setpoints")
        # No uirevision: every run re-autoranges the axes to fit its own data.
        traj = figures.trajectory_grid(
            frame,
            plot_vars or DEFAULT_PLOT_VARS,
            setpoints=setpoints if "setpoints" in toggles else None,
            show_limits="limits" in toggles,
            shutdown_time=run.final_time if run.terminated else None,
        )
        mv = figures.mv_panel(frame, TEP_SCHEMA.names("manipulated_variables"))
        return traj, mv

    # -- step-test target options depend on the kind ----------------------
    @app.callback(Output("step-target", "options"), Output("step-target", "value"), Input("step-kind", "value"))
    def _step_targets(kind):
        if kind == "mv":
            options = mv_target_options()
            return options, options[0]["value"]
        return setpoint_target_options(), "reactor_level"

    # -- run a step test --------------------------------------------------
    @app.callback(
        Output("active-run", "data", allow_duplicate=True),
        Output("session-runs", "data", allow_duplicate=True),
        Output("step-graph", "figure"),
        Output("step-status", "children"),
        Input("run-step-btn", "n_clicks"),
        State("step-kind", "value"),
        State("step-target", "value"),
        State("step-baseline", "value"),
        State("step-value", "value"),
        State("step-time", "value"),
        State("step-horizon", "value"),
        State("step-ci", "value"),
        State("session-runs", "data"),
        prevent_initial_call=True,
    )
    def run_step(n, kind, target, baseline, step_value, step_time, horizon, ci, session):
        spec = StepTestSpec(kind=kind, target=target, baseline=float(baseline), step_value=float(step_value), step_time=float(step_time))
        cfg = ScenarioConfig(
            name=f"step_{target}",
            loop_type="open" if kind == "mv" else "closed",
            horizon=float(horizon or 6.0),
            control_interval=float(ci),
            step_test=spec,
        )
        run = service.run_scenario(cfg)
        store.put(run)
        session = (session or []) + [run.summary()]
        frame = run.to_frame()
        if kind == "mv":
            drive_col = f"implemented_action.{target}"
            response = MV_TO_MEAS.get(target, "measurement.reactor_pressure")
        else:
            frame = frame.copy()
            frame["drive.setpoint"] = [float(step_value) if t >= float(step_time) else float(baseline) for t in frame["time"]]
            drive_col = "drive.setpoint"
            response = SETPOINT_TO_MEAS.get(target, "measurement.reactor_pressure")
        fig = figures.step_response(frame, response, drive_col, float(step_time))
        status = f"{'shutdown at %.2f h' % run.final_time if run.terminated else 'ran %.1f h' % run.final_time} · run {run.run_id}"
        return run.run_id, session, fig, status

    # -- keep run-derived lists in sync with the session ------------------
    @app.callback(
        Output("dataset-runs", "options"),
        Output("compare-table", "data"),
        Output("compare-table", "columns"),
        Output("record-run", "options"),
        Input("session-runs", "data"),
    )
    def _update_run_lists(session):
        session = session or []
        options = [{"label": f"{s['name']} ({s['run_id']})", "value": s["run_id"]} for s in session]
        columns = [{"name": k, "id": k} for k in ("run_id", "name", "loop_type", "terminated", "final_time", "peak_reactor_pressure", "iae_reactor_pressure")]
        return options, session, columns, options

    @app.callback(Output("session-runs", "data", allow_duplicate=True), Input("clear-runs-btn", "n_clicks"), prevent_initial_call=True)
    def _clear_runs(n):
        return []

    # -- dataset export ---------------------------------------------------
    @app.callback(
        Output("dataset-download", "data"),
        Input("build-dataset-btn", "n_clicks"),
        State("dataset-runs", "value"),
        State("dataset-format", "value"),
        prevent_initial_call=True,
    )
    def build_dataset(n, run_ids, fmt):
        runs = [store.get(r) for r in (run_ids or [])]
        runs = [r for r in runs if r is not None]
        if not runs:
            raise PreventUpdate
        payload, filename = service.build_dataset(runs, fmt=fmt or "csv")
        return dcc.send_bytes(lambda buffer: buffer.write(payload), filename)

    # -- batch generation -------------------------------------------------
    @app.callback(
        Output("batch-table", "data"),
        Output("batch-table", "columns"),
        Output("batch-status", "children"),
        Output("batch-store", "data"),
        Output("session-runs", "data", allow_duplicate=True),
        Input("run-batch-btn", "n_clicks"),
        State("loop-type", "value"),
        State("horizon", "value"),
        State("ci-preset", "value"),
        State("ctrl-flags", "value"),
        State({"type": "sp-input", "name": ALL}, "value"),
        State({"type": "sp-input", "name": ALL}, "id"),
        State("dist-select", "value"),
        State("dist-start", "value"),
        State("batch-seeds", "value"),
        State("batch-field", "value"),
        State("batch-values", "value"),
        State("session-runs", "data"),
        prevent_initial_call=True,
    )
    def run_batch(n, loop, horizon, ci, flags, sp_v, sp_id, dist, dist_start, seeds_text, field, values_text, session):
        base = _scenario(loop, horizon, ci, None, flags, sp_v, sp_id, [], [], dist, dist_start, name="batch")
        param_grid = {field: tuple(_floats(values_text))} if field and values_text else {}
        spec = BatchSpec(base=base, seeds=tuple(_floats(seeds_text)), param_grid=param_grid, label="batch")
        batch, runs = service.run_batch(spec)
        for run in runs:
            store.put(run)
        session = (session or []) + [run.summary() for run in runs]
        rows = batch.per_run_metrics
        columns = [{"name": k, "id": k} for k in rows[0]] if rows else []
        return rows, columns, f"ran {len(runs)} scenarios", {"run_ids": list(batch.run_ids)}, session

    @app.callback(
        Output("batch-dataset-download", "data"),
        Input("batch-dataset-btn", "n_clicks"),
        State("batch-store", "data"),
        State("dataset-format", "value"),
        prevent_initial_call=True,
    )
    def batch_dataset(n, batch_store, fmt):
        if not batch_store:
            raise PreventUpdate
        runs = [store.get(r) for r in batch_store["run_ids"]]
        runs = [r for r in runs if r is not None]
        payload, filename = service.build_dataset(runs, fmt=fmt or "csv")
        return dcc.send_bytes(lambda buffer: buffer.write(payload), f"batch_{filename}")

    @app.callback(Output("batch-metrics-download", "data"), Input("batch-metrics-btn", "n_clicks"), State("batch-table", "data"), prevent_initial_call=True)
    def batch_metrics(n, rows):
        if not rows:
            raise PreventUpdate
        import pandas as pd

        return dcc.send_string(pd.DataFrame(rows).to_csv(index=False), "batch_metrics.csv")

    # -- compare overlay --------------------------------------------------
    @app.callback(Output("compare-graph", "figure"), Input("compare-var", "value"), Input("session-runs", "data"))
    def render_compare(variable, session):
        session = session or []
        runs = [store.get(s["run_id"]) for s in session]
        runs = [r for r in runs if r is not None]
        if not runs:
            return _empty("Run simulations, then compare them here")
        return figures.compare_overlay(runs, variable or "measurement.reactor_pressure")

    # -- metrics & experiment record --------------------------------------
    @app.callback(Output("metrics-panel", "children"), Output("record-json", "children"), Input("record-run", "value"), Input("active-run", "data"))
    def render_record(picked, active):
        run = store.get(picked or active) if (picked or active) else None
        if run is None:
            return "No run selected.", ""
        metrics = run.metrics
        rows = [
            ("terminated", run.terminated),
            ("final_time_h", round(run.final_time, 3)),
            ("peak_reactor_pressure_kPa", round(run.peak.get("reactor_pressure_max", float("nan")), 1)),
            ("constraint_violation_steps", metrics.get("constraint_violation_steps")),
            ("operating_cost_total", round(metrics.get("operating_cost_total", 0.0), 2)),
            ("production_rate_mean", round(metrics.get("production_rate_mean", 0.0), 2)),
        ]
        for cv, value in (metrics.get("iae") or {}).items():
            rows.append((f"IAE.{cv}", round(value, 3)))
        table = html.Table(
            [html.Tr([html.Td(k, style={"fontWeight": "600", "paddingRight": "16px"}), html.Td(str(v))]) for k, v in rows],
            style={"fontSize": "13px"},
        )
        record_json = json.dumps(run.record, indent=2) if run.record else "(open-loop run — no experiment record)"
        return table, record_json

    @app.callback(Output("record-download", "data"), Input("download-record-btn", "n_clicks"), State("record-run", "value"), State("active-run", "data"), prevent_initial_call=True)
    def download_record(n, picked, active):
        run = store.get(picked or active) if (picked or active) else None
        if run is None or not run.record:
            raise PreventUpdate
        return dcc.send_string(json.dumps(run.record, indent=2), f"{run.run_id}_record.json")

    # -- scenario save / load --------------------------------------------
    @app.callback(Output("scenario-download", "data"), Input("save-scenario-btn", "n_clicks"), *_SIM_STATE, prevent_initial_call=True)
    def save_scenario(n, loop, horizon, ci, seed, flags, sp_v, sp_id, mv_v, mv_id, dist, dist_start):
        cfg = _scenario(loop, horizon, ci, seed, flags, sp_v, sp_id, mv_v, mv_id, dist, dist_start, name="scenario")
        return dcc.send_string(cfg.to_json(), f"{cfg.name}.json")

    @app.callback(
        Output("loop-type", "value"),
        Output("horizon", "value"),
        Output("ci-preset", "value"),
        Output("seed", "value"),
        Output("ctrl-flags", "value"),
        Output("dist-select", "value"),
        Output("dist-start", "value"),
        Output({"type": "sp-input", "name": ALL}, "value"),
        Output({"type": "mv-slider", "name": ALL}, "value"),
        Input("scenario-upload", "contents"),
        State({"type": "sp-input", "name": ALL}, "id"),
        State({"type": "mv-slider", "name": ALL}, "id"),
        prevent_initial_call=True,
    )
    def load_scenario(contents, sp_ids, mv_ids):
        if not contents:
            raise PreventUpdate
        text = base64.b64decode(contents.split(",", 1)[1]).decode("utf-8")
        cfg = ScenarioConfig.from_json(text)
        flags = [f for f, on in (("composition", cfg.enable_composition), ("overrides", cfg.enable_overrides), ("pct_g_feedback", cfg.enable_pct_g_feedback)) if on]
        ci = cfg.control_interval if cfg.control_interval in (0.01, 0.0005) else 0.01
        dist_names = [d.idv for d in cfg.disturbances]
        dist_start = cfg.disturbances[0].start_time if cfg.disturbances else 1.0
        merged_sp = {**default_setpoints(), **(cfg.setpoints or {})}
        merged_mv = {**default_manual_mvs(), **(cfg.manual_mvs or {})}
        sp_values = [round(float(merged_sp[i["name"]]), 3) for i in sp_ids]
        mv_values = [round(float(merged_mv[i["name"]]), 1) for i in mv_ids]
        return cfg.loop_type, cfg.horizon, ci, cfg.seed, flags, dist_names, dist_start, sp_values, mv_values
