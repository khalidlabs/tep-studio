"""Dash callbacks wiring the widgets to the backend service and Plotly figures.

All heavy work is delegated to ``tep_studio.ui.service`` (Dash-free). Runs are
stored in a server-side ``RunStore``; the browser session keeps only small run
summaries. Service calls are wrapped so a failed run surfaces a red banner instead
of a silent server-log traceback. Imports Dash (used only by the app).
"""

from __future__ import annotations

import base64
import json

import numpy as np
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, dcc, html, no_update
from dash.exceptions import PreventUpdate

from tep_studio.simulation.schema import TEP_SCHEMA
from tep_studio.ui import figures, service, theme
from tep_studio.ui.config import BatchSpec, DisturbanceActivation, ScenarioConfig
from tep_studio.ui.service import default_manual_mvs, default_setpoints
from tep_studio.ui.widgets import DEFAULT_PLOT_VARS

_SHOW = {**theme.CARD, "display": "block"}
_HIDE = theme.HIDDEN


def _empty(message: str = "Run a simulation to see results") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(size=14, color=theme.TEXT_FAINT))
    fig.update_layout(template="tep", xaxis_visible=False, yaxis_visible=False, margin=dict(l=20, r=20, t=20, b=20))
    return fig


def _floats(text) -> list[float]:
    if not text:
        return []
    return [float(x) for x in str(text).replace(";", ",").split(",") if x.strip()]


def _parse_state(text) -> tuple[float, ...] | None:
    """Parse a free-form 50-vector: a JSON array, or comma/space/newline-separated numbers."""
    if not text or not str(text).strip():
        return None
    raw = str(text).strip()
    try:
        values = json.loads(raw)
    except (ValueError, TypeError):
        values = [tok for tok in raw.replace(",", " ").replace(";", " ").split() if tok]
    return tuple(float(x) for x in values)


def _tuning_overrides(rows) -> dict[str, float] | None:
    """The table rows that differ from the registry defaults (None if all are default)."""
    from tep_studio.control.tuning import tuning_defaults

    defaults = tuning_defaults()
    changed: dict[str, float] = {}
    for row in rows or []:
        key, value = row.get("parameter"), row.get("value")
        if key not in defaults or value is None or value == "":
            continue
        new = float(value)
        ref = defaults[key]
        if ref is None or abs(new - ref) > 1e-12 * max(1.0, abs(ref)):
            changed[key] = new
    return changed or None


def _parse_seed(seed):
    return None if seed in (None, "") else float(seed)


def _num(value, default):
    return default if value in (None, "") else float(value)


def _fmt(value, ndigits: int = 3):
    if value is None:
        return "—"
    try:
        return round(float(value), ndigits)
    except (TypeError, ValueError):
        return value


def _level_margin(peak: dict, name: str):
    lo, hi = peak.get(f"{name}_min"), peak.get(f"{name}_max")
    if lo is None or hi is None:
        return None
    return round(min(float(lo), 100.0 - float(hi)), 1)


def _metric_card(label: str, value) -> html.Div:
    return html.Div(
        [
            html.Div(label, style={"fontSize": theme.FS_XS, "color": theme.TEXT_MUTED}),
            html.Div(str(value), style={"fontSize": theme.FS_LG, "fontWeight": "700", "color": theme.TITLE}),
        ],
        style={"border": f"1px solid {theme.BORDER}", "borderRadius": theme.RADIUS_SM, "padding": "8px 10px", "minWidth": "118px", "backgroundColor": theme.SURFACE_ALT},
    )


def _exc_quality_view(q: dict, run) -> html.Div:
    """Render the excitation-quality report (PE order, condition number, per-channel power)."""
    cond = q.get("condition_number", float("inf"))
    cards = [
        _metric_card("PE order", q.get("pe_order", 0)),
        _metric_card("regressor rank", q.get("regressor_rank", 0)),
        _metric_card("condition number", "∞" if cond == float("inf") else f"{cond:.0f}"),
        _metric_card("channels", q.get("n_channels", 0)),
        _metric_card("samples", q.get("n_samples", 0)),
    ]
    th = {"textAlign": "left", "padding": "4px 10px", "borderBottom": f"1px solid {theme.BORDER}", "color": theme.TEXT_MUTED}
    td = {"padding": "4px 10px", "borderBottom": f"1px solid {theme.BORDER}", "fontFamily": theme.FONT_MONO}
    head = html.Tr([html.Th(h, style=th) for h in ("channel", "rms", "dominant freq (1/h)")])
    body = [html.Tr([html.Td(c["target"], style=td), html.Td(f"{c['rms']:.2f}", style=td), html.Td(f"{c['dominant_freq_per_h']:.2f}", style=td)]) for c in q.get("channels", [])]
    note = "Higher PE order = richer excitation (a single step gives PE≈0). " + (
        "⚠ run tripped — reduce amplitude or horizon." if getattr(run, "terminated", False) else "Tick this run under 'Runs to include' to export the dataset (excitation metadata is included)."
    )
    return html.Div(
        [
            html.H5("Excitation quality", style={"margin": f"{theme.SP_2} 0"}),
            html.Div(cards, style={"display": "flex", "flexWrap": "wrap", "gap": theme.SP_2}),
            html.Table([html.Thead(head), html.Tbody(body)], style={"borderCollapse": "collapse", "marginTop": theme.SP_2, "fontSize": theme.FS_SM}),
            html.Div(note, style={"fontSize": theme.FS_SM, "color": theme.TEXT_MUTED, "marginTop": theme.SP_2}),
        ]
    )


def _scenario(
    loop, horizon, ci, seed, flags, sp_values, sp_ids, mv_values, mv_ids, dist_select, dist_start, name="scenario",
    dist_mags=None, dist_mag_ids=None, solver_method="RK4", rtol=1e-6, atol=1e-8, fixed_step=0.0005, record_every=0, mode="mode1",
    initial_state_source="mode", initial_state_text="", tuning_rows_data=None,
) -> ScenarioConfig:
    flags = flags or []
    initial_state = _parse_state(initial_state_text) if initial_state_source == "custom" else None
    controller_tuning = _tuning_overrides(tuning_rows_data)
    setpoints = {i["name"]: float(v) for i, v in zip(sp_ids, sp_values) if v is not None} or None
    manual_mvs = {i["name"]: float(v) for i, v in zip(mv_ids, mv_values) if v is not None} or None
    mag_by_name = {i["name"]: float(v) for i, v in zip(dist_mag_ids or [], dist_mags or []) if v is not None}
    disturbances = tuple(
        DisturbanceActivation(idv=name_, magnitude=mag_by_name.get(name_, 1.0), start_time=float(dist_start or 0.0))
        for name_ in (dist_select or [])
    )
    return ScenarioConfig(
        name=name,
        loop_type=loop,
        mode=mode or "mode1",
        horizon=float(horizon or 12.0),
        control_interval=float(ci),
        seed=_parse_seed(seed),
        disturbances=disturbances,
        setpoints=setpoints if loop == "closed" else None,
        manual_mvs=manual_mvs if loop == "open" else None,
        initial_state=initial_state,
        controller_tuning=controller_tuning if loop == "closed" else None,
        enable_composition="composition" in flags,
        enable_overrides="overrides" in flags,
        enable_pct_g_feedback="pct_g_feedback" in flags,
        solver_method=solver_method or "RK4",
        rtol=_num(rtol, 1e-6),
        atol=_num(atol, 1e-8),
        fixed_step=_num(fixed_step, 0.0005),
        record_every=int(_num(record_every, 0)),
    )


# Shared State lists for the simulate-tab configuration form. The trailing block
# (idv-mag pattern + solver/record fields) is read by run_simulation and
# save_scenario; _scenario receives them by keyword so the positional contract
# (pinned by test_app_smoke) is unchanged.
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
    State({"type": "idv-mag", "name": ALL}, "value"),
    State({"type": "idv-mag", "name": ALL}, "id"),
    State("solver-method", "value"),
    State("rtol", "value"),
    State("atol", "value"),
    State("fixed-step", "value"),
    State("record-every", "value"),
    State("mode-select", "value"),
    State("initial-state-source", "value"),
    State("initial-state-text", "value"),
    State("tuning-table", "data"),
]


def register_callbacks(app, store) -> None:
    # -- route between the studio, the About page, and the MCP page --------
    @app.callback(
        Output("main-view", "style"), Output("about-view", "style"), Output("mcp-view", "style"),
        Input("url", "pathname"),
    )
    def _route(pathname):
        path = (pathname or "/").rstrip("/")
        show = {"display": "block"}
        if path.endswith("/about"):
            return _HIDE, show, _HIDE
        if path.endswith("/mcp"):
            return _HIDE, _HIDE, show
        return show, _HIDE, _HIDE

    # -- toggle open/closed control panels --------------------------------
    @app.callback(Output("closed-controls", "style"), Output("open-controls", "style"), Input("loop-type", "value"))
    def _toggle(loop):
        return (_HIDE, _SHOW) if loop == "open" else (_SHOW, _HIDE)

    # -- render a magnitude input per selected disturbance ----------------
    @app.callback(Output("dist-mag-container", "children"), Input("dist-select", "value"))
    def _render_idv_mags(selected):
        selected = selected or []
        if not selected:
            return []
        rows = [html.Div("Disturbance magnitude (0–1)", style={"fontSize": theme.FS_SM, "fontWeight": "600", "marginBottom": theme.SP_1})]
        for name_ in selected:
            rows.append(
                html.Div(
                    [
                        html.Label(name_, style={"fontSize": theme.FS_SM, "width": "90px", "display": "inline-block"}),
                        dcc.Input(type="number", min=0, max=1, step=0.05, value=1.0, id={"type": "idv-mag", "name": name_}, className="tep-input", style={"width": "90px"}),
                    ],
                    style={"marginBottom": theme.SP_1},
                )
            )
        return rows

    # -- initial-state & controller-tuning helpers ------------------------
    @app.callback(
        Output("initial-state-text", "value", allow_duplicate=True),
        Output("initial-state-source", "value", allow_duplicate=True),
        Input("load-mode-state-btn", "n_clicks"),
        State("mode-select", "value"),
        prevent_initial_call=True,
    )
    def _load_mode_state(n, mode):
        from tep_studio.simulation.core import TennesseeEastmanProcess

        sim = TennesseeEastmanProcess()
        sim.reset(mode=mode or "mode1")
        return json.dumps([round(float(x), 6) for x in np.asarray(sim.state)[:50]]), "custom"

    @app.callback(
        Output("tuning-table", "data", allow_duplicate=True),
        Input("reset-tuning-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def _reset_tuning(n):
        from tep_studio.control.tuning import tuning_rows

        return tuning_rows()

    # -- system-identification excitation ---------------------------------
    @app.callback(
        Output("exc-targets", "options"),
        Output("exc-targets", "value"),
        Input("exc-loop", "value"),
        prevent_initial_call=True,
    )
    def _exc_targets(loop):
        from tep_studio.ui.config import setpoint_fields

        if loop == "open":
            opts = [{"label": n, "value": n} for n in TEP_SCHEMA.names("manipulated_variables")]
            return opts, ["a_feed_valve", "purge_valve"]
        return [{"label": f, "value": f} for f in setpoint_fields()], ["reactor_pressure", "production_rate"]

    @app.callback(
        Output("active-run", "data", allow_duplicate=True),
        Output("session-runs", "data", allow_duplicate=True),
        Output("exc-status", "children"),
        Output("exc-banner", "style"),
        Output("exc-banner", "children"),
        Output("exc-quality", "children"),
        Output("exc-graph", "figure"),
        Output("exc-run-btn", "disabled", allow_duplicate=True),
        Input("exc-run-btn", "n_clicks"),
        State("exc-loop", "value"), State("exc-signal", "value"), State("exc-targets", "value"),
        State("exc-amp", "value"), State("exc-clock", "value"), State("exc-flow", "value"), State("exc-fhigh", "value"),
        State("exc-horizon", "value"), State("exc-seed", "value"), State("session-runs", "data"),
        prevent_initial_call=True,
    )
    def run_excitation(n, loop, signal, targets, amp, clock, flow, fhigh, horizon, seed, session):
        try:
            from tep_studio.simulation.excitation import SETPOINT_ACTION_BOUNDS, ExcitationSignal, ExcitationSpec, excitation_input_matrix, excitation_quality

            target_meas = {
                "production_rate": "measurement.stripper_underflow", "pct_g": "measurement.stripper_underflow_G_concentration",
                "reactor_pressure": "measurement.reactor_pressure", "reactor_level": "measurement.reactor_level",
                "reactor_temperature": "measurement.reactor_temperature", "separator_level": "measurement.separator_level",
                "stripper_level": "measurement.stripper_level", "ya": "measurement.reactor_feed_A_concentration", "yac": "measurement.reactor_feed_C_concentration",
            }
            targets = targets or []
            if not targets:
                raise ValueError("select at least one target to excite")
            kind = "setpoint" if loop == "closed" else "mv"
            frac, hz = float(amp or 0.0), float(horizon or 16.0)
            signals = []
            for tgt in targets:
                if kind == "setpoint":
                    lo, hi = SETPOINT_ACTION_BOUNDS.get(tgt, (0.0, 1.0))
                    a = frac * (hi - lo) / 2.0
                else:
                    a = frac * 50.0  # MV range [0, 100] -> half-range 50
                signals.append(ExcitationSignal(target=tgt, signal=signal, amplitude=a, clock=float(clock or 0.5), f_low=float(flow or 0.1), f_high=float(fhigh or 2.0)))
            spec = ExcitationSpec(kind=kind, signals=tuple(signals), seed=int(seed or 0))
            cfg = ScenarioConfig(name=f"sysid_{signal}", mode="mode1", loop_type=loop, horizon=hz, control_interval=0.01, excitation=spec)
            cfg.validate()
            run = service.run_scenario(cfg)
            store.put(run)
            session = (session or []) + [run.summary()]
            q = excitation_quality(spec, horizon=hz, dt=0.01)
            cols, mat = excitation_input_matrix(spec, horizon=hz, dt=0.01)
            times = np.arange(mat.shape[0]) * 0.01
            response = [target_meas[t] for t in targets if t in target_meas] if kind == "setpoint" else ["measurement.reactor_pressure", "measurement.reactor_level"]
            fig = figures.excitation_diagnostics(times, cols, mat, run.to_frame(), response, dt=0.01, uirevision=run.run_id)
            outcome = f"shutdown at {run.final_time:.2f} h" if run.terminated else f"ran {run.final_time:.1f} h"
            status = f"{outcome} · peak reactor P = {run.peak.get('reactor_pressure_max', 0):.0f} kPa · run {run.run_id}"
            return run.run_id, session, status, theme.HIDDEN, "", _exc_quality_view(q, run), fig, False
        except Exception as exc:
            return no_update, no_update, "", theme.banner_style("danger"), f"Excitation failed — {exc}", no_update, no_update, False

    # -- run a simulation -------------------------------------------------
    @app.callback(
        Output("active-run", "data", allow_duplicate=True),
        Output("session-runs", "data", allow_duplicate=True),
        Output("run-status", "children"),
        Output("run-banner", "style"),
        Output("run-banner", "children"),
        Output("run-btn", "disabled", allow_duplicate=True),
        Input("run-btn", "n_clicks"),
        *_SIM_STATE,
        State("session-runs", "data"),
        prevent_initial_call=True,
    )
    def run_simulation(n, loop, horizon, ci, seed, flags, sp_v, sp_id, mv_v, mv_id, dist, dist_start, mag_v, mag_id, solver, rtol, atol, fixed_step, record_every, mode, init_src, init_text, tuning_data, session):
        try:
            cfg = _scenario(
                loop, horizon, ci, seed, flags, sp_v, sp_id, mv_v, mv_id, dist, dist_start, name=f"{loop}_run",
                dist_mags=mag_v, dist_mag_ids=mag_id, solver_method=solver, rtol=rtol, atol=atol, fixed_step=fixed_step, record_every=record_every, mode=mode,
                initial_state_source=init_src, initial_state_text=init_text, tuning_rows_data=tuning_data,
            )
            cfg.validate()
            run = service.run_scenario(cfg)
            store.put(run)
            session = (session or []) + [run.summary()]
            outcome = f"shutdown at {run.final_time:.2f} h" if run.terminated else f"ran {run.final_time:.1f} h"
            status = f"{outcome} · peak reactor P = {run.peak.get('reactor_pressure_max', 0):.0f} kPa · run {run.run_id}"
            return run.run_id, session, status, theme.HIDDEN, "", False
        except Exception as exc:  # surface the failure instead of a silent server-log traceback
            return no_update, no_update, "", theme.banner_style("danger"), f"Run failed — {exc}", False

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
            return _empty("Run a simulation to see trajectories"), _empty("Manipulated variables appear after a run")
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

    # -- keep run-derived lists in sync with the session ------------------
    # Also refire on tab / dataset-sub-tab switches: the dataset-runs / compare /
    # record components mount lazily with their tab, so a session change while their
    # tab is hidden would otherwise be lost until the next session change.
    @app.callback(
        Output("dataset-runs", "options"),
        Output("compare-table", "data"),
        Output("compare-table", "columns"),
        Output("record-run", "options"),
        Input("session-runs", "data"),
        Input("tabs", "value"),
        Input("dataset-tabs", "value"),
    )
    def _update_run_lists(session, _main_tab=None, _dataset_tab=None):
        session = session or []
        options = [{"label": f"{s['name']} ({s['run_id']})", "value": s["run_id"]} for s in session]
        keys = ("run_id", "name", "loop_type", "terminated", "final_time", "peak_reactor_pressure", "iae_reactor_pressure", "ise_reactor_pressure", "time_to_shutdown")
        columns = [{"name": k, "id": k} for k in keys]
        return options, session, columns, options

    # -- apply per-mode setpoints when the operating mode changes ---------
    @app.callback(
        Output({"type": "sp-input", "name": ALL}, "value", allow_duplicate=True),
        Input("mode-select", "value"),
        State({"type": "sp-input", "name": ALL}, "id"),
        prevent_initial_call=True,
    )
    def _apply_mode_setpoints(mode, sp_ids):
        from tep_studio.ui.service import mode_default_setpoints

        sp = mode_default_setpoints(mode or "mode1")
        return [round(float(sp[i["name"]]), 3) for i in sp_ids]

    # -- reset the Advanced overrides when the mode changes, so each mode runs from
    # its own clean config (a custom initial state / edited tuning left over from a
    # previous mode must not leak into the new mode's run).
    @app.callback(
        Output("initial-state-source", "value", allow_duplicate=True),
        Output("initial-state-text", "value", allow_duplicate=True),
        Output("tuning-table", "data", allow_duplicate=True),
        Input("mode-select", "value"),
        prevent_initial_call=True,
    )
    def _reset_overrides_on_mode_change(mode):
        from tep_studio.control.tuning import tuning_rows

        return "mode", "", tuning_rows()

    # -- RunStore capacity / eviction indicator ---------------------------
    @app.callback(Output("store-capacity", "children"), Output("store-capacity", "style"), Input("session-runs", "data"))
    def _capacity(session):
        used, cap = len(store.ids()), store.capacity
        msg, kind = f"RunStore: {used}/{cap} runs cached", "muted"
        if used >= cap:
            msg, kind = msg + " — oldest runs are being evicted (LRU)", "danger"
        elif used >= 0.8 * cap:
            kind = "warning"
        return msg, theme.status_style(kind)

    # -- copy all run ids -------------------------------------------------
    @app.callback(Output("copy-runids", "content"), Input("session-runs", "data"))
    def _copy_runids(session):
        return "\n".join(s["run_id"] for s in (session or []))

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

    # -- export preview: overlay the selected-for-export runs -------------
    @app.callback(
        Output("dataset-preview-graph", "figure"),
        Input("dataset-runs", "value"),
        Input("dataset-preview-var", "value"),
    )
    def _dataset_preview(run_ids, column):
        runs = [store.get(r) for r in (run_ids or [])]
        runs = [r for r in runs if r is not None]
        if not runs or not column:
            return _empty("Tick runs under 'Runs to include' to preview them here")
        return figures.compare_overlay(runs, column, uirevision="dataset-preview")

    # -- batch generation -------------------------------------------------
    @app.callback(
        Output("batch-table", "data"),
        Output("batch-table", "columns"),
        Output("batch-status", "children"),
        Output("batch-store", "data"),
        Output("session-runs", "data", allow_duplicate=True),
        Output("batch-banner", "style"),
        Output("batch-banner", "children"),
        Output("run-batch-btn", "disabled", allow_duplicate=True),
        Output("batch-coverage-graph", "figure"),
        Input("run-batch-btn", "n_clicks"),
        State("loop-type", "value"),
        State("horizon", "value"),
        State("ci-preset", "value"),
        State("ctrl-flags", "value"),
        State({"type": "sp-input", "name": ALL}, "value"),
        State({"type": "sp-input", "name": ALL}, "id"),
        State("dist-select", "value"),
        State("dist-start", "value"),
        State({"type": "idv-mag", "name": ALL}, "value"),
        State({"type": "idv-mag", "name": ALL}, "id"),
        State("solver-method", "value"),
        State("rtol", "value"),
        State("atol", "value"),
        State("fixed-step", "value"),
        State("record-every", "value"),
        State("mode-select", "value"),
        State("batch-seeds", "value"),
        State("batch-field", "value"),
        State("batch-values", "value"),
        State("session-runs", "data"),
        prevent_initial_call=True,
    )
    def run_batch(n, loop, horizon, ci, flags, sp_v, sp_id, dist, dist_start, mag_v, mag_id, solver, rtol, atol, fixed_step, record_every, mode, seeds_text, field, values_text, session):
        try:
            base = _scenario(
                loop, horizon, ci, None, flags, sp_v, sp_id, [], [], dist, dist_start, name="batch",
                dist_mags=mag_v, dist_mag_ids=mag_id, solver_method=solver, rtol=rtol, atol=atol, fixed_step=fixed_step, record_every=record_every, mode=mode,
            )
            param_grid = {field: tuple(_floats(values_text))} if field and values_text else {}
            spec = BatchSpec(base=base, seeds=tuple(_floats(seeds_text)), param_grid=param_grid, label="batch")
            batch, runs = service.run_batch(spec)
            for run in runs:
                store.put(run)
            session = (session or []) + [run.summary() for run in runs]
            rows = batch.per_run_metrics
            columns = [{"name": k, "id": k} for k in rows[0]] if rows else []
            fig = figures.batch_coverage(rows, uirevision=batch.batch_id)
            return rows, columns, f"ran {len(runs)} scenarios", {"run_ids": list(batch.run_ids)}, session, theme.HIDDEN, "", False, fig
        except Exception as exc:
            return no_update, no_update, "", no_update, no_update, theme.banner_style("danger"), f"Batch failed — {exc}", False, no_update

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
    def render_compare(variables, session):
        session = session or []
        runs = [store.get(s["run_id"]) for s in session]
        runs = [r for r in runs if r is not None]
        if not runs:
            return _empty("Run simulations, then compare them here")
        vars_ = variables if isinstance(variables, list) else [variables]
        vars_ = [v for v in vars_ if v] or ["measurement.reactor_pressure"]
        if len(vars_) == 1:
            return figures.compare_overlay(runs, vars_[0])
        return figures.compare_overlay_multi(runs, vars_)

    # -- metrics & experiment record --------------------------------------
    @app.callback(
        Output("metrics-panel", "children"),
        Output("record-json", "children"),
        Output("copy-active-id", "content"),
        Input("record-run", "value"),
        Input("active-run", "data"),
    )
    def render_record(picked, active):
        run = store.get(picked or active) if (picked or active) else None
        if run is None:
            return "No run selected.", "", ""
        metrics = run.metrics if isinstance(run.metrics, dict) else {}
        peak_p = run.peak.get("reactor_pressure_max", float("nan"))
        cards = [
            _metric_card("terminated", run.terminated),
            _metric_card("final time (h)", round(run.final_time, 3)),
            _metric_card("time to shutdown (h)", _fmt(metrics.get("time_to_shutdown"))),
            _metric_card("peak reactor P (kPa)", round(peak_p, 1)),
            _metric_card("pressure margin (kPa)", round(3000.0 - peak_p, 1)),
            _metric_card("violation steps", metrics.get("constraint_violation_steps")),
            _metric_card("operating cost", round(metrics.get("operating_cost_total", 0.0), 2)),
            _metric_card("production mean", round(metrics.get("production_rate_mean", 0.0), 2)),
        ]
        for level in ("reactor_level", "separator_level", "stripper_level"):
            margin = _level_margin(run.peak, level)
            if margin is not None:
                cards.append(_metric_card(f"{level} margin", margin))
        # Per-CV IAE / ISE comparison table.
        iae, ise = metrics.get("iae") or {}, metrics.get("ise") or {}
        cvs = sorted(set(iae) | set(ise))
        err_table = html.Table(
            [html.Tr([html.Th("controlled variable"), html.Th("IAE"), html.Th("ISE")], style={"textAlign": "left"})]
            + [html.Tr([html.Td(cv, style={"paddingRight": "16px"}), html.Td(_fmt(iae.get(cv))), html.Td(_fmt(ise.get(cv)))]) for cv in cvs],
            style={"fontSize": theme.FS_MD, "marginTop": theme.SP_3, "borderCollapse": "collapse"},
        ) if cvs else None
        panel = html.Div([
            html.Div(cards, style={"display": "flex", "flexWrap": "wrap", "gap": theme.SP_2}),
            err_table or html.Div(),
        ])
        record_json = json.dumps(run.record, indent=2) if run.record else "(open-loop run — no experiment record)"
        return panel, record_json, run.run_id

    @app.callback(Output("record-download", "data"), Input("download-record-btn", "n_clicks"), State("record-run", "value"), State("active-run", "data"), prevent_initial_call=True)
    def download_record(n, picked, active):
        run = store.get(picked or active) if (picked or active) else None
        if run is None or not run.record:
            raise PreventUpdate
        return dcc.send_string(json.dumps(run.record, indent=2), f"{run.run_id}_record.json")

    # -- scenario save / load --------------------------------------------
    @app.callback(Output("scenario-download", "data"), Input("save-scenario-btn", "n_clicks"), *_SIM_STATE, prevent_initial_call=True)
    def save_scenario(n, loop, horizon, ci, seed, flags, sp_v, sp_id, mv_v, mv_id, dist, dist_start, mag_v, mag_id, solver, rtol, atol, fixed_step, record_every, mode, init_src, init_text, tuning_data):
        cfg = _scenario(
            loop, horizon, ci, seed, flags, sp_v, sp_id, mv_v, mv_id, dist, dist_start, name="scenario",
            dist_mags=mag_v, dist_mag_ids=mag_id, solver_method=solver, rtol=rtol, atol=atol, fixed_step=fixed_step, record_every=record_every, mode=mode,
            initial_state_source=init_src, initial_state_text=init_text, tuning_rows_data=tuning_data,
        )
        return dcc.send_string(cfg.to_json(), f"{cfg.name}.json")

    @app.callback(
        Output("loop-type", "value"),
        Output("horizon", "value"),
        Output("ci-preset", "value"),
        Output("seed", "value"),
        Output("ctrl-flags", "value"),
        Output("dist-select", "value"),
        Output("dist-start", "value"),
        Output("solver-method", "value"),
        Output("rtol", "value"),
        Output("atol", "value"),
        Output("fixed-step", "value"),
        Output("record-every", "value"),
        Output({"type": "sp-input", "name": ALL}, "value"),
        Output({"type": "mv-slider", "name": ALL}, "value"),
        Output("initial-state-source", "value", allow_duplicate=True),
        Output("initial-state-text", "value", allow_duplicate=True),
        Output("tuning-table", "data", allow_duplicate=True),
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
        # initial state + controller tuning round-trip
        from tep_studio.control.tuning import tuning_rows

        init_src = "custom" if cfg.initial_state is not None else "mode"
        init_text = json.dumps([round(float(x), 6) for x in cfg.initial_state]) if cfg.initial_state is not None else ""
        tuning_data = tuning_rows()
        for row in tuning_data:
            if cfg.controller_tuning and row["parameter"] in cfg.controller_tuning:
                row["value"] = cfg.controller_tuning[row["parameter"]]
        # Note: per-disturbance magnitudes reset to 1.0 on load (the idv-mag inputs
        # are created only after dist-select updates); full round-trip is a follow-up.
        return (
            cfg.loop_type, cfg.horizon, ci, cfg.seed, flags, dist_names, dist_start,
            cfg.solver_method, cfg.rtol, cfg.atol, cfg.fixed_step, cfg.record_every,
            sp_values, mv_values, init_src, init_text, tuning_data,
        )

    # -- disable the Run buttons while a synchronous run is in flight -----
    for _btn in ("run-btn", "run-batch-btn", "exc-run-btn"):
        app.clientside_callback(
            "function(n){ return !!n; }",
            Output(_btn, "disabled", allow_duplicate=True),
            Input(_btn, "n_clicks"),
            prevent_initial_call=True,
        )
