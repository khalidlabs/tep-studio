from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from tep_studio.simulation import TEP_SCHEMA, TennesseeEastmanProcess


SOURCE = "Ricker, N. L. (1995). Optimal steady-state operation of the Tennessee Eastman challenge process."


@dataclass(frozen=True)
class ReportedSteadyState:
    key: str
    label: str
    product_mix: str
    production_kg_h: float | None
    measurements: tuple[float, ...]
    manipulated_variables: tuple[float, ...]


MEASUREMENT_NAMES = tuple(variable.name for variable in TEP_SCHEMA.measurements)
MV_NAMES = tuple(variable.name for variable in TEP_SCHEMA.manipulated_variables)


REPORTED_STEADY_STATES: tuple[ReportedSteadyState, ...] = (
    ReportedSteadyState(
        key="base_case",
        label="Downs and Vogel base case",
        product_mix="base",
        production_kg_h=None,
        measurements=(
            0.251,
            3664.0,
            4509.0,
            9.35,
            26.90,
            42.34,
            2705.0,
            75.0,
            120.4,
            0.337,
            80.1,
            50.0,
            2634.0,
            25.16,
            50.0,
            3102.0,
            22.95,
            65.73,
            230.0,
            341.0,
            94.6,
            77.3,
            32.19,
            8.89,
            26.38,
            6.88,
            18.78,
            1.66,
            32.96,
            13.82,
            23.98,
            1.26,
            18.58,
            2.26,
            4.84,
            2.30,
            0.02,
            0.84,
            0.10,
            53.72,
            43.83,
        ),
        manipulated_variables=(
            63.053,
            53.980,
            24.644,
            61.302,
            22.210,
            40.064,
            38.100,
            46.534,
            47.446,
            41.106,
            18.113,
            50.000,
        ),
    ),
    ReportedSteadyState(
        key="mode_1_50_50",
        label="Mode 1",
        product_mix="50/50",
        production_kg_h=14076.0,
        measurements=(
            0.267,
            3657.0,
            4440.0,
            9.24,
            32.18,
            47.36,
            2800.0,
            65.0,
            122.9,
            0.211,
            91.7,
            50.0,
            2706.0,
            25.28,
            50.0,
            3326.0,
            22.89,
            66.5,
            4.74,
            278.9,
            102.4,
            92.0,
            32.21,
            14.93,
            18.75,
            6.03,
            16.71,
            4.04,
            32.73,
            21.83,
            13.11,
            0.90,
            16.19,
            5.39,
            6.62,
            3.23,
            0.01,
            0.58,
            0.19,
            53.83,
            43.91,
        ),
        manipulated_variables=(
            62.935,
            53.147,
            26.248,
            60.566,
            1.000,
            25.770,
            37.266,
            46.444,
            1.000,
            35.992,
            12.431,
            100.000,
        ),
    ),
    ReportedSteadyState(
        key="mode_2_10_90",
        label="Mode 2",
        product_mix="10/90",
        production_kg_h=14077.0,
        measurements=(
            0.309,
            734.0,
            8038.0,
            8.55,
            31.69,
            46.08,
            2800.0,
            65.0,
            124.2,
            0.361,
            90.3,
            50.0,
            2705.0,
            26.31,
            50.0,
            3327.0,
            22.73,
            65.4,
            4.90,
            274.7,
            108.6,
            91.6,
            34.82,
            8.18,
            19.43,
            1.10,
            25.47,
            5.60,
            36.63,
            11.77,
            14.63,
            0.13,
            22.37,
            7.37,
            1.32,
            5.79,
            0.00,
            0.92,
            0.29,
            11.66,
            85.64,
        ),
        manipulated_variables=(
            12.637,
            96.216,
            30.412,
            56.092,
            1.000,
            44.347,
            35.799,
            42.065,
            1.000,
            25.257,
            np.nan,
            100.000,
        ),
    ),
    ReportedSteadyState(
        key="mode_3_90_10",
        label="Mode 3",
        product_mix="90/10",
        production_kg_h=11111.0,
        measurements=(
            0.194,
            5179.0,
            700.0,
            7.83,
            19.67,
            32.09,
            2800.0,
            65.0,
            121.9,
            0.087,
            83.4,
            50.0,
            2765.0,
            17.55,
            50.0,
            2996.0,
            18.04,
            62.3,
            5.34,
            272.6,
            101.9,
            45.0,
            29.46,
            27.74,
            17.97,
            12.68,
            3.86,
            1.29,
            27.86,
            45.07,
            9.22,
            2.18,
            3.94,
            1.82,
            9.40,
            0.50,
            0.03,
            0.16,
            0.07,
            90.09,
            8.17,
        ),
        manipulated_variables=(
            89.130,
            8.381,
            19.114,
            51.368,
            77.621,
            9.501,
            29.146,
            39.425,
            1.000,
            35.550,
            99.000,
            100.000,
        ),
    ),
    ReportedSteadyState(
        key="mode_4_50_50_max",
        label="Mode 4",
        product_mix="50/50 maximum",
        production_kg_h=None,
        measurements=(
            0.503,
            5811.0,
            7244.0,
            14.73,
            29.22,
            53.76,
            2800.0,
            65.0,
            128.2,
            0.462,
            74.1,
            50.0,
            2699.0,
            40.06,
            50.0,
            3365.0,
            36.04,
            51.5,
            6.87,
            263.2,
            96.6,
            73.5,
            36.40,
            8.78,
            22.36,
            7.95,
            17.01,
            3.88,
            40.94,
            15.90,
            15.68,
            0.68,
            15.41,
            5.72,
            3.85,
            1.82,
            0.02,
            1.21,
            0.04,
            53.35,
            43.52,
        ),
        manipulated_variables=(
            100.000,
            86.715,
            49.477,
            96.595,
            1.000,
            48.742,
            60.960,
            74.522,
            1.000,
            60.794,
            35.534,
            100.000,
        ),
    ),
    ReportedSteadyState(
        key="mode_5_10_90_max",
        label="Mode 5",
        product_mix="10/90 maximum",
        production_kg_h=None,
        measurements=(
            0.325,
            761.0,
            8354.0,
            8.87,
            31.27,
            46.24,
            2800.0,
            65.0,
            124.6,
            0.384,
            88.9,
            50.0,
            2705.0,
            27.45,
            50.0,
            3330.0,
            23.55,
            63.9,
            5.11,
            271.7,
            108.5,
            89.8,
            34.78,
            7.85,
            19.54,
            1.24,
            26.03,
            5.60,
            36.71,
            11.47,
            14.57,
            0.13,
            22.92,
            7.44,
            1.26,
            5.51,
            0.00,
            1.01,
            0.32,
            11.65,
            85.53,
        ),
        manipulated_variables=(
            13.090,
            100.000,
            32.009,
            58.155,
            1.000,
            47.095,
            37.422,
            44.491,
            1.000,
            26.070,
            14.115,
            100.000,
        ),
    ),
    ReportedSteadyState(
        key="mode_6_90_10_max",
        label="Mode 6",
        product_mix="90/10 maximum",
        production_kg_h=None,
        measurements=(
            0.219,
            5811.0,
            788.0,
            8.79,
            20.08,
            34.02,
            2800.0,
            65.0,
            123.0,
            0.099,
            80.9,
            50.0,
            2761.0,
            19.60,
            50.0,
            3015.0,
            20.20,
            60.5,
            5.59,
            293.2,
            100.6,
            45.7,
            29.99,
            26.34,
            18.80,
            13.23,
            3.91,
            1.33,
            28.61,
            44.41,
            9.76,
            2.09,
            4.00,
            1.91,
            8.76,
            0.46,
            0.03,
            0.18,
            0.08,
            90.07,
            8.16,
        ),
        manipulated_variables=(
            100.000,
            9.438,
            21.543,
            57.640,
            71.166,
            10.654,
            32.685,
            44.251,
            1.000,
            40.538,
            99.000,
            100.000,
        ),
    ),
)


def reported_steady_state_frame(group: str) -> pd.DataFrame:
    if group not in {"measurement", "manipulated_variable"}:
        raise ValueError("group must be 'measurement' or 'manipulated_variable'.")
    names = MEASUREMENT_NAMES if group == "measurement" else MV_NAMES
    rows = []
    for reference in REPORTED_STEADY_STATES:
        values = reference.measurements if group == "measurement" else reference.manipulated_variables
        for index, (name, value) in enumerate(zip(names, values), start=1):
            rows.append(
                {
                    "mode": reference.key,
                    "label": reference.label,
                    "product_mix": reference.product_mix,
                    "production_kg_h": reference.production_kg_h,
                    "group": group,
                    "index": index,
                    "variable": name,
                    "reported": value,
                    "source": SOURCE,
                }
            )
    return pd.DataFrame(rows)


def evaluate_reported_steady_states(
    *,
    state_vectors: Mapping[str, np.ndarray] | None = None,
    seed: float = 1431655765.0,
) -> pd.DataFrame:
    state_vectors = {} if state_vectors is None else state_vectors
    rows: list[dict[str, object]] = []
    for reference in REPORTED_STEADY_STATES:
        simulated_measurements: np.ndarray | None = None
        simulated_mvs: np.ndarray | None = None
        derivative_max_abs: float | None = None
        status = "state_vector_not_supplied"
        if reference.key == "base_case" or reference.key in state_vectors:
            sim = TennesseeEastmanProcess(ms_flag=0x0F)
            initial_state = state_vectors.get(reference.key)
            measurements, info = sim.reset(seed=seed, initial_state=initial_state)
            simulated_measurements = measurements
            simulated_mvs = np.asarray(info["implemented_action"], dtype=float)
            derivative_max_abs = float(np.max(np.abs(sim.kernel.derivatives(0.0, sim.state)[:38])))
            status = "evaluated"

        rows.extend(
            _comparison_rows(
                reference=reference,
                group="measurement",
                names=MEASUREMENT_NAMES,
                reported=reference.measurements,
                simulated=simulated_measurements,
                status=status,
                derivative_max_abs=derivative_max_abs,
            )
        )
        rows.extend(
            _comparison_rows(
                reference=reference,
                group="manipulated_variable",
                names=MV_NAMES,
                reported=reference.manipulated_variables,
                simulated=simulated_mvs,
                status=status,
                derivative_max_abs=derivative_max_abs,
            )
        )
    return pd.DataFrame(rows)


def write_reported_steady_state_validation(output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison = evaluate_reported_steady_states()
    comparison_path = output_dir / "steady_state_summary.csv"
    comparison.to_csv(comparison_path, index=False)

    measurement_path = output_dir / "ricker_1995_table2_measurements.csv"
    mv_path = output_dir / "ricker_1995_table3_manipulated_variables.csv"
    reported_steady_state_frame("measurement").to_csv(measurement_path, index=False)
    reported_steady_state_frame("manipulated_variable").to_csv(mv_path, index=False)
    return {
        "steady_state_summary_path": str(comparison_path),
        "reported_measurements_path": str(measurement_path),
        "reported_manipulated_variables_path": str(mv_path),
    }


def steady_state_metric_rows(comparison: pd.DataFrame) -> list[dict[str, object]]:
    evaluated = comparison[comparison["status"] == "evaluated"].copy()
    rows: list[dict[str, object]] = []
    if evaluated.empty:
        return rows
    for (mode, group), frame in evaluated.groupby(["mode", "group"], sort=False):
        finite = frame[np.isfinite(frame["reported"]) & np.isfinite(frame["simulated"])]
        rows.append(
            {
                "scenario": f"steady_state_{mode}_{group}",
                "solver": "algebraic_reference",
                "elapsed_s": 0.0,
                "trajectory_path": "",
                "samples": len(finite),
                "final_time_h": 0.0,
                "max_abs_error": float(finite["abs_error"].max()) if not finite.empty else np.nan,
                "mean_abs_error": float(finite["abs_error"].mean()) if not finite.empty else np.nan,
                "max_relative_error_pct": float(finite["relative_error_pct"].max()) if not finite.empty else np.nan,
                "terminated": False,
                "shutdown_time_h": np.nan,
                "shutdown_code": 0.0,
                "shutdown_message": "",
                "steady_state_derivative_max_abs": float(finite["derivative_max_abs"].dropna().max())
                if not finite["derivative_max_abs"].dropna().empty
                else np.nan,
            }
        )
    missing_modes = sorted(set(comparison.loc[comparison["status"] != "evaluated", "mode"]))
    if missing_modes:
        rows.append(
            {
                "scenario": "steady_state_ricker_modes_reference_only",
                "solver": "reported_tables",
                "elapsed_s": 0.0,
                "trajectory_path": "",
                "samples": int((comparison["status"] != "evaluated").sum()),
                "final_time_h": 0.0,
                "max_abs_error": np.nan,
                "mean_abs_error": np.nan,
                "max_relative_error_pct": np.nan,
                "terminated": False,
                "shutdown_time_h": np.nan,
                "shutdown_code": 0.0,
                "shutdown_message": "Mode state vectors are not in the Ricker PDF; reported tables were exported as references.",
                "steady_state_derivative_max_abs": np.nan,
                "reference_only_modes": ",".join(missing_modes),
            }
        )
    return rows


def _comparison_rows(
    *,
    reference: ReportedSteadyState,
    group: str,
    names: tuple[str, ...],
    reported: tuple[float, ...],
    simulated: np.ndarray | None,
    status: str,
    derivative_max_abs: float | None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, (name, reported_value) in enumerate(zip(names, reported), start=1):
        simulated_value = np.nan if simulated is None else float(simulated[index - 1])
        abs_error = np.nan
        rel_error = np.nan
        if np.isfinite(reported_value) and np.isfinite(simulated_value):
            abs_error = abs(simulated_value - reported_value)
            rel_error = 100.0 * abs_error / max(abs(reported_value), 1e-12)
        row_status = "reported_value_uncertain" if not np.isfinite(reported_value) else status
        rows.append(
            {
                "mode": reference.key,
                "label": reference.label,
                "product_mix": reference.product_mix,
                "production_kg_h": reference.production_kg_h,
                "group": group,
                "index": index,
                "variable": name,
                "reported": reported_value,
                "simulated": simulated_value,
                "abs_error": abs_error,
                "relative_error_pct": rel_error,
                "status": row_status,
                "derivative_max_abs": derivative_max_abs,
                "source": SOURCE,
            }
        )
    return rows
