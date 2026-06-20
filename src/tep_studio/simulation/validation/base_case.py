from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd

from tep_studio.simulation import TEP_SCHEMA, TennesseeEastmanProcess


REPO_ROOT = Path(__file__).resolve().parents[4]
EXAMPLE_DOC = REPO_ROOT / "example.doc"
TEMEXD_MOD_C = REPO_ROOT / "temexd_mod" / "temexd_mod.c"
SOURCE = "example.doc high-precision Downs and Vogel base-case y0 vector"
STATE_SOURCE = "temexd_mod.c default Mode 1 yy[1:50] initialization"


def load_example_doc_y0(path: Path = EXAMPLE_DOC) -> np.ndarray:
    text = path.read_text(encoding="ascii", errors="ignore")
    match = re.search(r"y0=\[(.*?)\];", text, flags=re.DOTALL)
    if match is None:
        raise ValueError(f"Could not find y0 vector in {path}.")
    values = [float(item) for item in re.findall(r"[-+]?\d+(?:\.\d*)?(?:[eEdD][-+]?\d+)?", match.group(1))]
    if len(values) < len(TEP_SCHEMA.measurements):
        raise ValueError(f"Expected at least {len(TEP_SCHEMA.measurements)} y0 values in {path}, found {len(values)}.")
    return np.asarray(values, dtype=np.float64)


def evaluate_high_precision_base_case(path: Path = EXAMPLE_DOC) -> pd.DataFrame:
    reported = load_example_doc_y0(path)[: len(TEP_SCHEMA.measurements)]
    sim = TennesseeEastmanProcess(ms_flag=0x0F)
    measurements, _ = sim.reset(seed=1431655765.0)
    derivative = sim.kernel.derivatives(0.0, sim.state)
    rows = []
    for index, (variable, reported_value, simulated_value) in enumerate(
        zip(TEP_SCHEMA.measurements, reported, measurements),
        start=1,
    ):
        abs_error = abs(float(simulated_value) - float(reported_value))
        rows.append(
            {
                "mode": "base_case_high_precision",
                "group": "measurement",
                "index": index,
                "variable": variable.name,
                "reported": float(reported_value),
                "simulated": float(simulated_value),
                "abs_error": abs_error,
                "relative_error_pct": 100.0 * abs_error / max(abs(float(reported_value)), 1e-12),
                "derivative_max_abs": float(np.max(np.abs(derivative[:38]))),
                "source": SOURCE,
            }
        )
    return pd.DataFrame(rows)


def load_temexd_default_state(path: Path = TEMEXD_MOD_C) -> np.ndarray:
    text = path.read_text(encoding="latin-1")
    pattern = re.compile(
        r"yy\[(?P<index>\d+)\]\s*=\s*(?:\(float\))?\s*(?P<value>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eEdD][-+]?\d+)?)\s*;",
    )
    values: dict[int, float] = {}
    for match in pattern.finditer(text):
        index = int(match.group("index"))
        if 1 <= index <= 50:
            values[index] = float(match.group("value").replace("D", "E").replace("d", "e"))
    missing = [index for index in range(1, 51) if index not in values]
    if missing:
        raise ValueError(f"Could not parse default state entries {missing} from {path}.")
    return np.asarray([values[index] for index in range(1, 51)], dtype=np.float64)


def evaluate_base_case_states(path: Path = TEMEXD_MOD_C) -> pd.DataFrame:
    reference_state = load_temexd_default_state(path)
    sim = TennesseeEastmanProcess(ms_flag=0x0F)
    sim.reset(seed=1431655765.0)
    rows = []
    for index, (variable, reference_value, simulated_value) in enumerate(
        zip(TEP_SCHEMA.states, reference_state, sim.state),
        start=1,
    ):
        abs_error = abs(float(simulated_value) - float(reference_value))
        rows.append(
            {
                "mode": "base_case",
                "group": "state",
                "index": index,
                "state": variable.name,
                "unit": variable.unit,
                "reference": float(reference_value),
                "simulator": float(simulated_value),
                "abs_error": abs_error,
                "relative_error_pct": 100.0 * abs_error / max(abs(float(reference_value)), 1e-12),
                "source": STATE_SOURCE,
            }
        )
    return pd.DataFrame(rows)


def write_high_precision_base_case_validation(output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison = evaluate_high_precision_base_case()
    comparison_path = output_dir / "base_case_high_precision_summary.csv"
    comparison.to_csv(comparison_path, index=False)

    state_comparison = evaluate_base_case_states()
    state_comparison_path = output_dir / "base_case_state_validation_table.csv"
    state_comparison.to_csv(state_comparison_path, index=False)
    return {
        "base_case_high_precision_path": str(comparison_path),
        "base_case_state_validation_path": str(state_comparison_path),
    }


def high_precision_base_case_metric_rows(comparison: pd.DataFrame) -> list[dict[str, object]]:
    finite = comparison[np.isfinite(comparison["reported"]) & np.isfinite(comparison["simulated"])]
    return [
        {
            "scenario": "base_case_high_precision_measurement",
            "solver": "example_doc_reference",
            "elapsed_s": 0.0,
            "trajectory_path": "",
            "samples": len(finite),
            "final_time_h": 0.0,
            "max_abs_error": float(finite["abs_error"].max()),
            "mean_abs_error": float(finite["abs_error"].mean()),
            "rmse": float(np.sqrt(np.mean(np.square(finite["abs_error"])))),
            "max_relative_error_pct": float(finite["relative_error_pct"].max()),
            "terminated": False,
            "shutdown_time_h": np.nan,
            "shutdown_code": 0.0,
            "shutdown_message": "",
            "steady_state_derivative_max_abs": float(finite["derivative_max_abs"].iloc[0]),
        }
    ]
