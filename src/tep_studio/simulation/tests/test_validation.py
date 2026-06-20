from __future__ import annotations

import numpy as np
import pandas as pd

from tep_studio.simulation.validation.base_case import (
    evaluate_base_case_states,
    evaluate_high_precision_base_case,
    load_example_doc_y0,
    load_temexd_default_state,
)
from tep_studio.simulation.validation.figures import generate_figures
from tep_studio.simulation.validation.mat_states import (
    MAT_STATE_REFERENCES,
    evaluate_mat_state_references,
)
from tep_studio.simulation.validation.metrics import shutdown_metrics, trajectory_error
from tep_studio.simulation.validation.report import generate_report
from tep_studio.simulation.validation.runner import ValidationConfig, run_suite
from tep_studio.simulation.validation.steady_state import (
    REPORTED_STEADY_STATES,
    evaluate_reported_steady_states,
)


def test_metric_helpers() -> None:
    frame = pd.DataFrame(
        {
            "time": [0.0, 1.0],
            "terminated": [False, True],
            "shutdown_code": [0.0, 1.0],
            "shutdown_message": ["", "High Reactor Pressure!!  Shutting down."],
        }
    )
    metrics = shutdown_metrics(frame)
    assert metrics["terminated"] is True
    assert metrics["shutdown_time_h"] == 1.0

    error = trajectory_error(pd.Series([1.0, 2.0]), pd.Series([1.0, 4.0]))
    assert np.isclose(error["rmse"], np.sqrt(2.0))


def test_local_validation_suite_and_figures(tmp_path) -> None:
    result = run_suite(ValidationConfig(suite="local", output_dir=tmp_path))
    assert not result.metrics.empty
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "metrics" / "validation_summary.csv").exists()
    assert any(name.startswith("r12_open_loop_shutdown") for name in result.trajectories)
    r12 = next(frame for name, frame in result.trajectories.items() if name.startswith("r12_open_loop_shutdown"))
    assert {"time_start", "time_end", "control_interval", "terminated_at_end", "is_initial"} <= set(r12.columns)
    assert bool(r12.iloc[0]["is_initial"]) is True
    assert float(r12.iloc[1]["time_start"]) == float(r12.iloc[0]["time_end"])
    assert "reproducibility" in result.manifest
    assert result.manifest["reproducibility"]["build_command"] == "python3 setup.py build_ext --inplace"

    figures = generate_figures(tmp_path)
    assert any(path.name == "fig_r12_shutdown.png" for path in figures)
    assert (tmp_path / "figures" / "fig_r12_shutdown_source.csv").exists()

    report = generate_report(tmp_path)
    assert report.exists()
    assert "TEP Simulation Validation Report" in report.read_text(encoding="utf-8")


def test_reported_steady_state_references_are_evaluated_for_base_case() -> None:
    assert len(REPORTED_STEADY_STATES) == 7
    comparison = evaluate_reported_steady_states()
    base_measurements = comparison[
        (comparison["mode"] == "base_case") & (comparison["group"] == "measurement")
    ]
    assert len(base_measurements) == 41
    assert base_measurements["simulated"].notna().all()
    assert base_measurements["abs_error"].max() < 1.0

    optimal_modes = comparison[comparison["mode"] != "base_case"]
    assert set(optimal_modes["status"]) >= {"state_vector_not_supplied", "reported_value_uncertain"}


def test_example_doc_high_precision_base_case_reference() -> None:
    y0 = load_example_doc_y0()
    assert len(y0) == 51
    comparison = evaluate_high_precision_base_case()
    assert len(comparison) == 41
    assert comparison["abs_error"].max() < 1e-3


def test_temexd_default_state_reference_table() -> None:
    state = load_temexd_default_state()
    assert state.shape == (50,)
    comparison = evaluate_base_case_states()
    assert len(comparison) == 50
    assert comparison["relative_error_pct"].max() == 0.0


def test_steady_state_validation_suite_outputs_references(tmp_path) -> None:
    result = run_suite(ValidationConfig(suite="steady_state", output_dir=tmp_path))
    assert not result.metrics.empty
    assert (tmp_path / "metrics" / "steady_state_summary.csv").exists()
    assert (tmp_path / "metrics" / "base_case_high_precision_summary.csv").exists()
    assert (tmp_path / "metrics" / "base_case_state_validation_table.csv").exists()
    assert (tmp_path / "metrics" / "ricker_1995_table2_measurements.csv").exists()
    assert any(result.metrics["scenario"].str.contains("steady_state_base_case_measurement"))


def test_mat_state_references_reproduce_reported_modes() -> None:
    assert len(MAT_STATE_REFERENCES) == 3
    comparison = evaluate_mat_state_references()
    assert {"mode1_multiloop", "mode3_multiloop", "mode1_skogestad"} == set(comparison["reference"])

    mode3 = comparison[
        (comparison["reference"] == "mode3_multiloop")
        & (comparison["group"] == "measurement")
        & (
            comparison["variable"].isin(
                ["reactor_temperature", "stripper_underflow_G_concentration", "stripper_underflow_H_concentration"]
            )
        )
    ]
    assert mode3["abs_error"].max() < 0.25


def test_mat_state_validation_suite_outputs_paper_artifacts(tmp_path) -> None:
    result = run_suite(ValidationConfig(suite="mat_states", output_dir=tmp_path))
    assert not result.metrics.empty
    assert (tmp_path / "metrics" / "mat_state_validation_summary.csv").exists()
    assert (tmp_path / "metrics" / "mat_state_validation_paper_table.csv").exists()

    figures = generate_figures(tmp_path)
    assert any(path.name == "fig_mat_state_output_parity.png" for path in figures)
    assert any(path.name == "fig_validation_performance_summary.png" for path in figures)

    report = generate_report(tmp_path)
    assert report.exists()
    assert (tmp_path / "report" / "paper_validation_section.md").exists()
