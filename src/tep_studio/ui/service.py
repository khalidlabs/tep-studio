"""UI-agnostic backend: turn a ``ScenarioConfig`` into a ``RunResult``.

Pure functions (no Dash, no globals beyond a memoised default-setpoints cache) so
the run / step-test / batch / export logic is testable without a browser. Reuses
``ClosedLoopSimulation`` for closed-loop runs and a small explicit ``advance`` loop
for open-loop runs. This module is Dash-free.
"""

from __future__ import annotations

import dataclasses as dc
import io
import json
import math
import os
from datetime import datetime, timezone
from typing import Callable, Sequence
from uuid import uuid4

import numpy as np

from tep_studio import TEP_SCHEMA, TennesseeEastmanProcess, TrajectoryDataset
from tep_studio.control import (
    ClosedLoopSimulation,
    ControllerSetpoints,
    RickerMultiLoopController,
    build_experiment_record,
)
from tep_studio.control.metrics import MetricsAccumulator
from tep_studio.control.registry import RICKER_MODE1
from tep_studio.ui.config import BatchSpec, ScenarioConfig, StepTestSpec
from tep_studio.ui.results import BatchResult, RunResult

Progress = Callable[[float, str], None]

_DEFAULT_SETPOINTS: dict[str, float] | None = None


# -- defaults / builders ---------------------------------------------------
def default_setpoints() -> dict[str, float]:
    """The Mode-1 nominal setpoints (seeded once from a clean reset)."""
    global _DEFAULT_SETPOINTS
    if _DEFAULT_SETPOINTS is None:
        sim = TennesseeEastmanProcess()
        meas0, _ = sim.reset(mode="mode1")
        ctl = RickerMultiLoopController()
        ctl.reset(meas0)
        _DEFAULT_SETPOINTS = dc.asdict(ctl.setpoints)
    return dict(_DEFAULT_SETPOINTS)


def default_manual_mvs() -> dict[str, float]:
    return dict(zip(TEP_SCHEMA.names("manipulated_variables"), RICKER_MODE1.nominal.u0))


def build_simulator(cfg: ScenarioConfig) -> TennesseeEastmanProcess:
    return TennesseeEastmanProcess(solver_method=cfg.solver_method, rtol=cfg.rtol, atol=cfg.atol, fixed_step=cfg.fixed_step)


def build_setpoints(cfg: ScenarioConfig) -> ControllerSetpoints:
    return ControllerSetpoints(**{**default_setpoints(), **(cfg.setpoints or {})})


def build_controller(cfg: ScenarioConfig) -> RickerMultiLoopController:
    return RickerMultiLoopController(
        setpoints=build_setpoints(cfg),
        enable_composition=cfg.enable_composition,
        enable_overrides=cfg.enable_overrides,
        enable_pct_g_feedback=cfg.enable_pct_g_feedback,
    )


# -- schedules -------------------------------------------------------------
def disturbance_schedule_from(cfg: ScenarioConfig) -> Callable[[float], np.ndarray] | None:
    if not cfg.disturbances:
        return None
    acts = [(a, TEP_SCHEMA.index("disturbances", a.idv)) for a in cfg.disturbances]

    def schedule(t: float) -> np.ndarray:
        vec = np.zeros(28, dtype=np.float64)
        for activation, idx in acts:
            if t >= activation.start_time:
                vec[idx] = activation.magnitude
        return vec

    return schedule


def setpoint_schedule_from(cfg: ScenarioConfig, base: ControllerSetpoints):
    st = cfg.step_test
    if st is None or st.kind != "setpoint":
        return None
    pre = dc.replace(base, **{st.target: st.baseline})
    post = dc.replace(base, **{st.target: st.step_value})
    return lambda t: post if t >= st.step_time else pre


def _open_loop_action_fn(cfg: ScenarioConfig) -> Callable[[float], np.ndarray]:
    base = TEP_SCHEMA.vector("manipulated_variables", cfg.manual_mvs or {}, base=np.array(RICKER_MODE1.nominal.u0))
    st = cfg.step_test
    if st is not None and st.kind == "mv":
        idx = TEP_SCHEMA.index("manipulated_variables", st.target)

        def action(t: float) -> np.ndarray:
            vec = base.copy()
            vec[idx] = st.step_value if t >= st.step_time else st.baseline
            return vec

        return action
    return lambda t: base.copy()


# -- run entry points ------------------------------------------------------
def run_scenario(cfg: ScenarioConfig, *, run_id: str | None = None, progress: Progress | None = None) -> RunResult:
    cfg.validate()
    run_id = run_id or f"{cfg.loop_type}_{uuid4().hex[:8]}"
    if cfg.loop_type == "closed":
        return _run_closed(cfg, run_id, progress)
    return _run_open(cfg, run_id, progress)


def run_mv_step_test(cfg: ScenarioConfig, spec: StepTestSpec, *, run_id: str | None = None, progress: Progress | None = None) -> RunResult:
    return run_scenario(dc.replace(cfg, loop_type="open", step_test=spec), run_id=run_id, progress=progress)


def run_setpoint_step_test(cfg: ScenarioConfig, spec: StepTestSpec, *, run_id: str | None = None, progress: Progress | None = None) -> RunResult:
    return run_scenario(dc.replace(cfg, loop_type="closed", step_test=spec), run_id=run_id, progress=progress)


def _run_closed(cfg: ScenarioConfig, run_id: str, progress: Progress | None) -> RunResult:
    sim = build_simulator(cfg)
    controller = build_controller(cfg)
    base_sp = controller.setpoints
    runner = ClosedLoopSimulation(simulator=sim, controller=controller, control_interval=cfg.control_interval, horizon=cfg.horizon)
    if progress:
        progress(0.05, "running closed-loop simulation")
    result = runner.run(
        seed=cfg.seed,
        disturbance_schedule=disturbance_schedule_from(cfg),
        setpoint_schedule=setpoint_schedule_from(cfg, base_sp),
        record_every=cfg.resolved_record_every(),
    )
    if progress:
        progress(0.9, "building outputs")
    frame = TrajectoryDataset.from_results(result.results, run_id=run_id, scenario_id=cfg.name).to_pandas()
    record = json.loads(build_experiment_record(result, controller, simulator=sim, seed=cfg.seed).to_json())
    run = RunResult(
        run_id=run_id,
        scenario=cfg,
        frame_records=frame.to_dict("records"),
        columns=list(frame.columns),
        metrics=result.metrics,
        peak=result.peak,
        terminated=result.terminated,
        truncated=result.truncated,
        final_time=result.final_time,
        n_steps=result.n_steps,
        shutdown=dict(result.results[-1].shutdown_status) if result.terminated and result.results else None,
        record=record,
        created_at=_now(),
    )
    if progress:
        progress(1.0, "done")
    return run


def _run_open(cfg: ScenarioConfig, run_id: str, progress: Progress | None) -> RunResult:
    sim = build_simulator(cfg)
    meas, _ = sim.reset(mode="mode1", seed=cfg.seed)
    action_fn = _open_loop_action_fn(cfg)
    disturbance_schedule = disturbance_schedule_from(cfg)
    metrics = MetricsAccumulator(setpoints=ControllerSetpoints(**default_setpoints()))
    record_every = cfg.resolved_record_every()
    peak = _init_peak(meas)

    results = []
    terminated = False
    last = None
    step = 0
    eps = cfg.control_interval * 1e-6
    total = max(1, int(cfg.horizon / cfg.control_interval))
    while sim.time < cfg.horizon - eps:
        t = sim.time
        idv = disturbance_schedule(t) if disturbance_schedule is not None else None
        result = sim.advance(action_fn(t), control_interval=cfg.control_interval, disturbances=idv)
        meas = result.measurements
        metrics.update(result)
        ClosedLoopSimulation._track_peak(peak, meas)
        last = result
        is_terminated = result.shutdown_status["terminated"]
        if step % record_every == 0 or is_terminated:
            results.append(result)
        step += 1
        if progress and step % 50 == 0:
            progress(min(0.99, step / total), f"open-loop step {step}")
        if is_terminated:
            terminated = True
            break

    frame = TrajectoryDataset.from_results(results, run_id=run_id, scenario_id=cfg.name).to_pandas()
    run = RunResult(
        run_id=run_id,
        scenario=cfg,
        frame_records=frame.to_dict("records"),
        columns=list(frame.columns),
        metrics=metrics.finalize(),
        peak=peak,
        terminated=terminated,
        truncated=not terminated,
        final_time=sim.time,
        n_steps=step,
        shutdown=dict(last.shutdown_status) if terminated and last is not None else None,
        record=None,
        created_at=_now(),
    )
    if progress:
        progress(1.0, "done")
    return run


# -- dataset / batch -------------------------------------------------------
def build_dataset(runs: Sequence[RunResult], *, fmt: str = "csv") -> tuple[bytes, str]:
    import pandas as pd

    frames = [r.to_frame() for r in runs]
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if fmt == "parquet":
        buffer = io.BytesIO()
        combined.to_parquet(buffer, index=False)
        return buffer.getvalue(), "tep_dataset.parquet"
    return combined.to_csv(index=False).encode("utf-8"), "tep_dataset.csv"


def run_batch(
    spec: BatchSpec,
    *,
    progress: Progress | None = None,
    run_id_prefix: str = "batch",
    max_workers: int | None = 1,
) -> tuple[BatchResult, list[RunResult]]:
    """Run every scenario in ``spec`` and return the batch metrics + per-run results.

    Batch runs are independent, so set ``max_workers`` > 1 to generate large datasets
    in parallel across processes (``None`` or <= 0 means "all CPU cores"). The default
    of 1 is sequential: it keeps the call safe inside an already-forked worker (e.g. the
    Studio's background callback), where spawning a pool would fail. The terminal
    ``tep dataset`` command parallelises by default.
    """
    configs = spec.expand()
    total = len(configs)
    run_ids = [f"{run_id_prefix}_{i:03d}_{uuid4().hex[:4]}" for i in range(total)]
    workers = _resolve_workers(max_workers, total)
    if workers <= 1:
        runs = _run_batch_sequential(configs, run_ids, progress)
    else:
        runs = _run_batch_parallel(configs, run_ids, workers, progress)
    batch = BatchResult(
        batch_id=f"{run_id_prefix}_{uuid4().hex[:6]}",
        label=spec.label,
        run_ids=tuple(r.run_id for r in runs),
        per_run_metrics=[_metrics_row(r) for r in runs],
    )
    return batch, runs


def _resolve_workers(max_workers: int | None, total: int) -> int:
    if max_workers is None or max_workers <= 0:  # auto: one worker per core, capped by job count
        return max(1, min(total, os.cpu_count() or 1))
    return min(max_workers, total)


def _run_batch_sequential(configs, run_ids, progress: Progress | None) -> list[RunResult]:
    runs: list[RunResult] = []
    total = len(configs)
    for i, cfg in enumerate(configs):
        runs.append(run_scenario(cfg, run_id=run_ids[i]))
        if progress:
            progress((i + 1) / total, f"batch run {i + 1}/{total}")
    return runs


def _run_batch_parallel(configs, run_ids, workers: int, progress: Progress | None) -> list[RunResult]:
    from concurrent.futures import ProcessPoolExecutor, as_completed

    total = len(configs)
    results: list[RunResult | None] = [None] * total
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_scenario, cfg, run_id=run_ids[i]): i for i, cfg in enumerate(configs)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()  # re-raises a worker error here
            done += 1
            if progress:
                progress(done / total, f"batch run {done}/{total}")
    return [run for run in results if run is not None]  # original config order


# -- helpers ---------------------------------------------------------------
def _init_peak(meas: np.ndarray) -> dict[str, float]:
    return {
        "reactor_pressure_max": float(meas[6]),
        "reactor_level_min": float(meas[7]),
        "reactor_level_max": float(meas[7]),
        "separator_level_min": float(meas[11]),
        "separator_level_max": float(meas[11]),
        "stripper_level_min": float(meas[14]),
        "stripper_level_max": float(meas[14]),
    }


def _metrics_row(run: RunResult) -> dict:
    metrics = run.metrics
    iae = metrics.get("iae", {}) if isinstance(metrics, dict) else {}
    return {
        "run_id": run.run_id,
        "name": run.scenario.name,
        "seed": run.scenario.seed,
        "terminated": run.terminated,
        "final_time": round(run.final_time, 3),
        "peak_reactor_pressure": _r(run.peak.get("reactor_pressure_max")),
        "iae_reactor_pressure": _r(iae.get("reactor_pressure"), 3),
        "iae_reactor_level": _r(iae.get("reactor_level"), 3),
        "operating_cost": _r(metrics.get("operating_cost_total"), 2),
        "production_mean": _r(metrics.get("production_rate_mean"), 2),
    }


def _r(value, ndigits: int = 1):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), ndigits)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
