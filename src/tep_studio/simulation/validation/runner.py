from __future__ import annotations

from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
import platform
import sys
import time
from typing import Iterable

import numpy as np
import pandas as pd

from tep_studio.simulation import TEP_SCHEMA, TennesseeEastmanProcess
from tep_studio.simulation.validation.artifacts import DEFAULT_OUTPUT_DIR, ensure_output_tree, utc_now, write_json
from tep_studio.simulation.validation.base_case import (
    evaluate_high_precision_base_case,
    high_precision_base_case_metric_rows,
    write_high_precision_base_case_validation,
)
from tep_studio.simulation.validation.mat_states import (
    evaluate_mat_state_references,
    mat_state_metric_rows,
    write_mat_state_validation,
)
from tep_studio.simulation.validation.metrics import basic_trajectory_metrics, shutdown_metrics, solver_disagreement
from tep_studio.simulation.validation.references import download_references
from tep_studio.simulation.validation.scenarios import SCENARIOS, Scenario
from tep_studio.simulation.validation.steady_state import (
    evaluate_reported_steady_states,
    steady_state_metric_rows,
    write_reported_steady_state_validation,
)


@dataclass(frozen=True)
class ValidationConfig:
    suite: str = "local"
    output_dir: Path = DEFAULT_OUTPUT_DIR
    solvers: tuple[str, ...] = ("RK23", "RK45")
    download_external: bool = False
    reference_names: tuple[str, ...] = ("ricker_archive", "mv_per_dataset", "adchem_2015_pdf")


@dataclass(frozen=True)
class ValidationResult:
    manifest: dict[str, object]
    metrics: pd.DataFrame
    trajectories: dict[str, pd.DataFrame] = field(repr=False)


def run_suite(config: ValidationConfig) -> ValidationResult:
    paths = ensure_output_tree(config.output_dir)
    manifest: dict[str, object] = {
        "created_utc": utc_now(),
        "suite": config.suite,
        "output_dir": str(config.output_dir),
        "schema": TEP_SCHEMA.name,
        "reproducibility": _reproducibility_metadata(),
        "references": [],
        "scenarios": [],
    }
    if config.download_external:
        manifest["references"] = download_references(list(config.reference_names), paths["reference_cache"])

    scenario_names = _scenario_names(config.suite)
    include_steady_state = config.suite in {"steady_state", "all"}
    include_mat_states = config.suite in {"mat_states", "all"}
    trajectories: dict[str, pd.DataFrame] = {}
    metric_rows: list[dict[str, object]] = []

    for scenario_name in scenario_names:
        scenario = SCENARIOS[scenario_name]()
        manifest["scenarios"].append(
            {
                "name": scenario.name,
                "description": scenario.description,
                "horizon_h": scenario.horizon_h,
                "sample_period_h": scenario.sample_period_h,
                "ms_flag": scenario.ms_flag,
                "expected": scenario.expected,
            }
        )
        solver_names = config.solvers if scenario_name == "adchem_solver" else ("RK45",)
        per_solver: dict[str, pd.DataFrame] = {}
        for solver in solver_names:
            key = f"{scenario.name}.{solver}"
            trajectory, elapsed_s = run_scenario(scenario, solver_method=solver)
            trajectories[key] = trajectory
            per_solver[solver] = trajectory
            trajectory_path = paths["trajectories"] / f"{key}.csv"
            trajectory.to_csv(trajectory_path, index=False)

            row = {
                "scenario": scenario.name,
                "solver": solver,
                "elapsed_s": elapsed_s,
                "trajectory_path": str(trajectory_path),
            }
            row.update(basic_trajectory_metrics(trajectory))
            row.update(shutdown_metrics(trajectory))
            metric_rows.append(row)

        if len(per_solver) > 1:
            disagreement = solver_disagreement(per_solver, "measurement.reactor_pressure")
            if not disagreement.empty:
                disagreement["scenario"] = scenario.name
                disagreement.to_csv(paths["metrics"] / f"{scenario.name}_solver_disagreement.csv", index=False)

    if include_steady_state:
        steady_state_paths = write_reported_steady_state_validation(paths["metrics"])
        base_case_paths = write_high_precision_base_case_validation(paths["metrics"])
        base_case_comparison = evaluate_high_precision_base_case()
        metric_rows.extend(high_precision_base_case_metric_rows(base_case_comparison))
        steady_state_comparison = evaluate_reported_steady_states()
        metric_rows.extend(steady_state_metric_rows(steady_state_comparison))
        manifest["steady_state_references"] = {
            "source": "Ricker, N. L. (1995). Optimal steady-state operation of the Tennessee Eastman challenge process.",
            "note": (
                "The PDF reports measurement and manipulated-variable steady-state values for the base case "
                "and six optimized modes. It does not include the electronic 50-state vectors needed to "
                "evaluate modes 1-6 directly in the simulator; those rows are exported as reference-only "
                "until state vectors are supplied."
            ),
            **steady_state_paths,
            **base_case_paths,
        }

    if include_mat_states:
        mat_state_paths = write_mat_state_validation(paths["metrics"])
        mat_state_comparison = evaluate_mat_state_references()
        metric_rows.extend(mat_state_metric_rows(mat_state_comparison))
        manifest["mat_state_references"] = {
            "source": "Bundled temexd_mod Simulink initialization files.",
            "note": (
                "The MAT files contain saved Simulink plant CSTATE vectors. They are used as local "
                "operating-point validation references by evaluating the Python native kernel at the "
                "stored states and comparing selected outputs against the corresponding Ricker 1995 "
                "reported steady-state tables."
            ),
            **mat_state_paths,
        }

    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(paths["metrics"] / "validation_summary.csv", index=False)
    manifest["metrics_path"] = str(paths["metrics"] / "validation_summary.csv")
    manifest["trajectory_count"] = len(trajectories)
    write_json(paths["root"] / "manifest.json", manifest)
    return ValidationResult(manifest=manifest, metrics=metrics, trajectories=trajectories)


def run_scenario(scenario: Scenario, *, solver_method: str = "RK45") -> tuple[pd.DataFrame, float]:
    sim = TennesseeEastmanProcess(ms_flag=scenario.ms_flag, solver_method="RK45" if solver_method == "Euler" else solver_method)
    obs, info = sim.reset(seed=scenario.seed, disturbances=scenario.disturbances, ms_flag=scenario.ms_flag)
    rows = [
        _row(
            time_start_h=0.0,
            time_end_h=0.0,
            control_interval_h=0.0,
            measurements=obs,
            action=scenario.action,
            disturbances=scenario.disturbances,
            shutdown_status=info["shutdown_status"],
            objective_terms=info["objective_terms"],
            is_initial=True,
        )
    ]
    start_wall = time.perf_counter()
    while sim.time < scenario.horizon_h:
        base_action = scenario.action
        action = scenario.action_policy(sim.time, base_action) if scenario.action_policy else base_action
        disturbances = (
            scenario.disturbance_policy(sim.time, scenario.disturbances)
            if scenario.disturbance_policy
            else scenario.disturbances
        )
        dt = min(scenario.sample_period_h, scenario.horizon_h - sim.time)
        if solver_method == "Euler":
            result = _advance_euler(sim, action, dt, disturbances)
        else:
            result = sim.advance(action, control_interval=dt, disturbances=disturbances)
        rows.append(
            _row(
                time_start_h=result.time_start,
                time_end_h=result.time_end,
                control_interval_h=result.control_interval,
                measurements=result.measurements,
                action=result.implemented_action,
                disturbances=result.disturbances,
                shutdown_status=result.shutdown_status,
                objective_terms=result.objective_terms,
                is_initial=False,
            )
        )
        if result.shutdown_status["terminated"]:
            break
    elapsed_s = time.perf_counter() - start_wall
    return pd.DataFrame(rows), elapsed_s


def _advance_euler(sim: TennesseeEastmanProcess, action: np.ndarray, dt: float, disturbances: np.ndarray):
    sim.kernel.set_inputs(np.clip(action, 0.0, 100.0), disturbances)
    deriv = sim.kernel.derivatives(sim.time, sim.state)
    sim.state = np.ascontiguousarray(sim.state + dt * deriv, dtype=np.float64)
    sim.time = float(sim.time + dt)
    sim.kernel.state = sim.state.copy()
    sim.kernel.time = sim.time
    outputs = sim.kernel.outputs(sim.time, sim.state)
    code, message = sim.kernel.shutdown_status()
    from tep_studio.simulation.core import AdvanceResult

    return AdvanceResult(
        time=sim.time,
        time_start=sim.time - dt,
        time_end=sim.time,
        control_interval=dt,
        state=sim.state.copy(),
        measurements=outputs["measurements"].copy(),
        additional_measurements=outputs["additional_measurements"].copy(),
        disturbance_monitors=outputs["disturbance_monitors"].copy(),
        process_monitors=outputs["process_monitors"].copy(),
        concentration_monitors=outputs["concentration_monitors"].copy(),
        requested_action=np.asarray(action, dtype=np.float64).copy(),
        implemented_action=np.clip(action, 0.0, 100.0).copy(),
        disturbances=disturbances.copy(),
        constraint_margins=sim._constraint_margins(outputs["measurements"]),
        events=sim._events(code, message),
        shutdown_status={"code": code, "message": message, "terminated": code != 0.0},
        solver_stats={"method": "Euler", "success": True, "message": "fixed-step explicit Euler"},
        objective_terms=sim._objective_terms(outputs),
    )


def _row(
    *,
    time_start_h: float,
    time_end_h: float,
    control_interval_h: float,
    measurements: np.ndarray,
    action: np.ndarray,
    disturbances: np.ndarray,
    shutdown_status: dict[str, object],
    objective_terms: dict[str, float],
    is_initial: bool,
) -> dict[str, object]:
    row: dict[str, object] = {
        "time": float(time_end_h),
        "time_start": float(time_start_h),
        "time_end": float(time_end_h),
        "control_interval": float(control_interval_h),
        "is_initial": bool(is_initial),
        "terminated": bool(shutdown_status["terminated"]),
        "terminated_at_end": bool(shutdown_status["terminated"]),
        "shutdown_code": float(shutdown_status["code"]),
        "shutdown_message": str(shutdown_status["message"]),
    }
    row.update(
        {
            f"measurement.{variable.name}": float(value)
            for variable, value in zip(TEP_SCHEMA.measurements, measurements)
        }
    )
    row.update(
        {
            f"implemented_action.{variable.name}": float(value)
            for variable, value in zip(TEP_SCHEMA.manipulated_variables, action)
        }
    )
    row.update(
        {
            f"disturbance.{variable.name}": float(value)
            for variable, value in zip(TEP_SCHEMA.disturbances, disturbances)
        }
    )
    row.update({f"objective.{name}": float(value) for name, value in objective_terms.items()})
    return row


def _reproducibility_metadata() -> dict[str, object]:
    packages = {}
    for package_name in ("tep-studio", "cffi", "numpy", "scipy", "pandas", "gymnasium", "matplotlib"):
        try:
            packages[package_name] = metadata.version(package_name)
        except metadata.PackageNotFoundError:
            packages[package_name] = "not_installed_or_not_declared"
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": packages,
        "solver_defaults": {
            "package_default": "RK4 (fixed-step, h=0.0005 h)",
            "validation_pinned": "RK45 (adchem scenario also runs RK23)",
            "scipy_rtol": 1e-6,
            "scipy_atol": 1e-8,
        },
        "random_seed_convention": "Seed is passed to the native TEP reset routine when supplied.",
        "build_command": "python3 setup.py build_ext --inplace",
        "test_command": "PYTHONPATH=src python3 -m pytest -q",
        "repository_url": "not_declared_in_repository",
        "commit_hash": "not_declared_in_repository",
        "license": "not_declared_in_repository",
        "archived_release": "not_declared_in_repository",
    }


def _scenario_names(suite: str) -> tuple[str, ...]:
    if suite == "steady_state":
        return ()
    if suite == "mat_states":
        return ()
    if suite == "local":
        return ("r12", "mode1_short")
    if suite == "adchem":
        return ("adchem_solver",)
    if suite == "all":
        return ("r12", "mode1_short", "adchem_solver")
    if suite in SCENARIOS:
        return (suite,)
    raise ValueError(
        f"Unknown validation suite {suite!r}. Expected local, adchem, steady_state, mat_states, all, or one scenario key."
    )
