from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat

from tep_studio.simulation import TEP_SCHEMA, TennesseeEastmanProcess
from tep_studio.simulation.validation.steady_state import (
    MV_NAMES,
    MEASUREMENT_NAMES,
    REPORTED_STEADY_STATES,
    SOURCE,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
MAT_ROOT = REPO_ROOT / "temexd_mod"


@dataclass(frozen=True)
class MatStateReference:
    key: str
    label: str
    mat_file: str
    reported_mode: str
    interpretation: str


MAT_STATE_REFERENCES: tuple[MatStateReference, ...] = (
    MatStateReference(
        key="mode1_multiloop",
        label="Bundled MultiLoop Mode 1 operating point",
        mat_file="Mode1xInitial.mat",
        reported_mode="mode_1_50_50",
        interpretation=(
            "Local Simulink closed-loop Mode 1 initialization. It is expected to reproduce the "
            "reported Mode 1 measured outputs closely, but its saved controller strategy permits "
            "some manipulated variables to sit below the 1% optimization lower bound used by Ricker."
        ),
    ),
    MatStateReference(
        key="mode3_multiloop",
        label="Bundled MultiLoop Mode 3 operating point",
        mat_file="Mode3xInitial.mat",
        reported_mode="mode_3_90_10",
        interpretation=(
            "Local Simulink closed-loop Mode 3 initialization. This is the strongest bundled "
            "cross-mode validation point because its measured outputs align with the reported "
            "90/10 steady-state operating mode."
        ),
    ),
    MatStateReference(
        key="mode1_skogestad",
        label="Bundled Skogestad Mode 1 operating point",
        mat_file="Mode1SkogeInit.mat",
        reported_mode="mode_1_50_50",
        interpretation=(
            "Local Skogestad-style Mode 1 controller initialization. It validates reproduction of "
            "a distinct Mode 1 operating point, but should not be treated as the Ricker optimum."
        ),
    ),
)


PAPER_VARIABLES = (
    "feed_A_flow",
    "feed_D_flow",
    "feed_E_flow",
    "feed_AC_flow",
    "recycle_flow",
    "reactor_feed_flow",
    "reactor_pressure",
    "reactor_level",
    "reactor_temperature",
    "purge_flow",
    "separator_temperature",
    "separator_level",
    "separator_pressure",
    "separator_underflow",
    "stripper_level",
    "stripper_pressure",
    "stripper_underflow",
    "stripper_temperature",
    "stripper_steam_flow",
    "compressor_work",
    "reactor_cooling_water_outlet_temperature_meas",
    "condenser_cooling_water_outlet_temperature",
    "stripper_underflow_G_concentration",
    "stripper_underflow_H_concentration",
)


def load_mat_cstate(path: Path) -> np.ndarray:
    mat = loadmat(path, squeeze_me=True, struct_as_record=False)
    x_initial = mat.get("xInitial")
    if x_initial is None:
        raise ValueError(f"{path} does not contain xInitial.")
    signals = np.atleast_1d(x_initial.signals)
    for signal in signals:
        label = str(getattr(signal, "label", ""))
        values = np.asarray(getattr(signal, "values", []), dtype=float).reshape(-1)
        if label == "CSTATE" and values.size == 50:
            values[np.abs(values) < 1e-300] = 0.0
            return np.ascontiguousarray(values, dtype=np.float64)
    raise ValueError(f"{path} does not contain a 50-element CSTATE signal.")


def evaluate_mat_state_references(mat_root: Path = MAT_ROOT) -> pd.DataFrame:
    reported_by_key = {reference.key: reference for reference in REPORTED_STEADY_STATES}
    rows: list[dict[str, object]] = []
    for reference in MAT_STATE_REFERENCES:
        state = load_mat_cstate(mat_root / reference.mat_file)
        reported = reported_by_key[reference.reported_mode]
        sim = TennesseeEastmanProcess(ms_flag=0x0F)
        measurements, info = sim.reset(seed=1431655765.0, initial_state=state)
        mvs = np.asarray(info["implemented_action"], dtype=float)
        derivative = sim.kernel.derivatives(0.0, sim.state)
        derivative_max_abs = float(np.max(np.abs(derivative[:38])))
        derivative_l2 = float(np.linalg.norm(derivative[:38]))

        rows.extend(
            _comparison_rows(
                reference=reference,
                group="measurement",
                names=MEASUREMENT_NAMES,
                reported=reported.measurements,
                simulated=measurements,
                derivative_max_abs=derivative_max_abs,
                derivative_l2=derivative_l2,
            )
        )
        rows.extend(
            _comparison_rows(
                reference=reference,
                group="manipulated_variable",
                names=MV_NAMES,
                reported=reported.manipulated_variables,
                simulated=mvs,
                derivative_max_abs=derivative_max_abs,
                derivative_l2=derivative_l2,
            )
        )
    return pd.DataFrame(rows)


def write_mat_state_validation(output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison = evaluate_mat_state_references()
    comparison_path = output_dir / "mat_state_validation_summary.csv"
    comparison.to_csv(comparison_path, index=False)

    summary = summarize_mat_state_validation(comparison)
    summary_path = output_dir / "mat_state_validation_metrics.csv"
    summary.to_csv(summary_path, index=False)

    paper_table = comparison[
        (comparison["group"] == "measurement")
        & (comparison["variable"].isin(PAPER_VARIABLES))
    ].copy()
    paper_table_path = output_dir / "mat_state_validation_paper_table.csv"
    paper_table.to_csv(paper_table_path, index=False)
    return {
        "mat_state_summary_path": str(comparison_path),
        "mat_state_metrics_path": str(summary_path),
        "mat_state_paper_table_path": str(paper_table_path),
    }


def summarize_mat_state_validation(comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (reference, group), frame in comparison.groupby(["reference", "group"], sort=False):
        finite = frame[np.isfinite(frame["reported"]) & np.isfinite(frame["simulated"])].copy()
        finite_rel = finite[finite["reported"].abs() >= 1.0]
        rows.append(
            {
                "reference": reference,
                "label": str(frame["label"].iloc[0]),
                "reported_mode": str(frame["reported_mode"].iloc[0]),
                "group": group,
                "n_variables": len(finite),
                "mean_abs_error": float(finite["abs_error"].mean()) if not finite.empty else np.nan,
                "rmse": float(np.sqrt(np.mean(np.square(finite["abs_error"])))) if not finite.empty else np.nan,
                "max_abs_error": float(finite["abs_error"].max()) if not finite.empty else np.nan,
                "median_relative_error_pct_abs_ge_1": float(finite_rel["relative_error_pct"].median())
                if not finite_rel.empty
                else np.nan,
                "max_relative_error_pct_abs_ge_1": float(finite_rel["relative_error_pct"].max())
                if not finite_rel.empty
                else np.nan,
                "derivative_max_abs_first_38": float(frame["derivative_max_abs"].iloc[0]),
                "derivative_l2_first_38": float(frame["derivative_l2"].iloc[0]),
                "interpretation": str(frame["interpretation"].iloc[0]),
            }
        )
    return pd.DataFrame(rows)


def mat_state_metric_rows(comparison: pd.DataFrame) -> list[dict[str, object]]:
    summary = summarize_mat_state_validation(comparison)
    rows = []
    for _, item in summary.iterrows():
        rows.append(
            {
                "scenario": f"mat_state_{item['reference']}_{item['group']}",
                "solver": "cstate_evaluation",
                "elapsed_s": 0.0,
                "trajectory_path": "",
                "samples": int(item["n_variables"]),
                "final_time_h": 0.0,
                "max_abs_error": float(item["max_abs_error"]),
                "mean_abs_error": float(item["mean_abs_error"]),
                "rmse": float(item["rmse"]),
                "max_relative_error_pct": float(item["max_relative_error_pct_abs_ge_1"]),
                "terminated": False,
                "shutdown_time_h": np.nan,
                "shutdown_code": 0.0,
                "shutdown_message": "",
                "steady_state_derivative_max_abs": float(item["derivative_max_abs_first_38"]),
            }
        )
    return rows


def _comparison_rows(
    *,
    reference: MatStateReference,
    group: str,
    names: tuple[str, ...],
    reported: tuple[float, ...],
    simulated: np.ndarray,
    derivative_max_abs: float,
    derivative_l2: float,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, (name, reported_value) in enumerate(zip(names, reported), start=1):
        simulated_value = float(simulated[index - 1])
        abs_error = np.nan
        rel_error = np.nan
        if np.isfinite(reported_value) and np.isfinite(simulated_value):
            abs_error = abs(simulated_value - reported_value)
            rel_error = 100.0 * abs_error / max(abs(reported_value), 1e-12)
        rows.append(
            {
                "reference": reference.key,
                "label": reference.label,
                "reported_mode": reference.reported_mode,
                "group": group,
                "index": index,
                "variable": name,
                "reported": reported_value,
                "simulated": simulated_value,
                "abs_error": abs_error,
                "relative_error_pct": rel_error,
                "derivative_max_abs": derivative_max_abs,
                "derivative_l2": derivative_l2,
                "source": SOURCE,
                "mat_file": reference.mat_file,
                "interpretation": reference.interpretation,
            }
        )
    return rows
