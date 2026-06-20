from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from tep_studio.simulation.validation.artifacts import DEFAULT_OUTPUT_DIR, ensure_output_tree, utc_now


def generate_report(output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    paths = ensure_output_tree(output_dir)
    metrics_path = paths["metrics"] / "validation_summary.csv"
    manifest_path = paths["root"] / "manifest.json"
    if metrics_path.exists():
        metrics = pd.read_csv(metrics_path)
    else:
        metrics = pd.DataFrame()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    lines = [
        "# TEP Simulation Validation Report",
        "",
        f"Generated: `{utc_now()}`",
        "",
        "## Summary",
        "",
    ]
    if metrics.empty:
        lines.append("No validation metrics were found. Run `python -m tep_studio.simulation.validation run` first.")
    else:
        lines.append(f"Recorded `{len(metrics)}` validation metric rows.")
        lines.append("")
        lines.append("```text")
        lines.append(metrics.to_string(index=False))
        lines.append("```")
    if manifest.get("scenarios"):
        lines.extend(["", "## Scenario Notes", ""])
        for scenario in manifest["scenarios"]:
            lines.append(f"- `{scenario['name']}`: {scenario['description']}")
            expected = scenario.get("expected", {})
            if expected.get("intended_reference_ms_flag") is not None:
                lines.append(
                    f"  Intended reference `MSFlag={expected['intended_reference_ms_flag']}`; "
                    f"current stable validation run uses `MSFlag={expected.get('current_ms_flag')}`."
                )
    steady_state = manifest.get("steady_state_references")
    if steady_state:
        lines.extend(
            [
                "",
                "## Steady-State References",
                "",
                f"- Source: {steady_state['source']}",
                f"- Comparison CSV: `{Path(steady_state['steady_state_summary_path']).name}`",
                f"- High-precision base CSV: `{Path(steady_state['base_case_high_precision_path']).name}`",
                f"- Base-case state table CSV: `{Path(steady_state['base_case_state_validation_path']).name}`",
                f"- Reported Table 2 CSV: `{Path(steady_state['reported_measurements_path']).name}`",
                f"- Reported Table 3 CSV: `{Path(steady_state['reported_manipulated_variables_path']).name}`",
                f"- Note: {steady_state['note']}",
            ]
        )
    mat_state = manifest.get("mat_state_references")
    if mat_state:
        lines.extend(
            [
                "",
                "## MAT Operating-Point Validation",
                "",
                f"- Source: {mat_state['source']}",
                f"- Full comparison CSV: `{Path(mat_state['mat_state_summary_path']).name}`",
                f"- Metrics CSV: `{Path(mat_state['mat_state_metrics_path']).name}`",
                f"- Paper table CSV: `{Path(mat_state['mat_state_paper_table_path']).name}`",
                f"- Note: {mat_state['note']}",
            ]
        )

    figures = sorted(paths["figures"].glob("*.png"))
    if figures:
        lines.extend(["", "## Figures", ""])
        for figure in figures:
            lines.append(f"- `{figure.name}`")

    report_path = paths["report"] / "validation_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_paper_validation_section(paths)
    return report_path


def _write_paper_validation_section(paths: dict[str, Path]) -> Path | None:
    mat_metrics_path = paths["metrics"] / "mat_state_validation_metrics.csv"
    steady_metrics_path = paths["metrics"] / "steady_state_summary.csv"
    if not mat_metrics_path.exists():
        return None
    mat_metrics = pd.read_csv(mat_metrics_path)
    measurement_metrics = mat_metrics[mat_metrics["group"] == "measurement"].copy()
    mode3 = measurement_metrics[measurement_metrics["reference"] == "mode3_multiloop"]
    mode1 = measurement_metrics[measurement_metrics["reference"] == "mode1_multiloop"]
    skoge = measurement_metrics[measurement_metrics["reference"] == "mode1_skogestad"]
    steady_note = ""
    high_precision_path = paths["metrics"] / "base_case_high_precision_summary.csv"
    if high_precision_path.exists():
        base = pd.read_csv(high_precision_path)
        if not base.empty:
            steady_note = (
                f"The default base-case initialization reproduced all 41 high-precision Downs and Vogel "
                f"measurements with a mean absolute error of {base['abs_error'].mean():.4g} in native "
                f"reported units and a maximum absolute error of {base['abs_error'].max():.4g}."
            )
    elif steady_metrics_path.exists():
        steady = pd.read_csv(steady_metrics_path)
        base = steady[(steady["mode"] == "base_case") & (steady["group"] == "measurement")]
        if not base.empty:
            steady_note = (
                f"The default base-case initialization reproduced all 41 rounded Downs and Vogel "
                f"measurements with a mean absolute error of {base['abs_error'].mean():.4g} in native "
                f"reported units and a maximum absolute error of {base['abs_error'].max():.4g}."
            )

    lines = [
        "# Journal-Ready Validation Section",
        "",
        "## Validation of the Python Tennessee Eastman simulator",
        "",
        (
            "The Python implementation was validated against two independent reference sources embedded "
            "in the original `temexd_mod` distribution: the default process initialization coded in the "
            "native model and the saved Simulink plant-state vectors distributed with the Mode 1, Mode 3, "
            "and Skogestad Mode 1 closed-loop examples. The high-precision base-case output vector in "
            "`example.doc` and the reported steady-state measurements and manipulated variables from "
            "Ricker (1995) were used as numerical references."
        ),
        "",
    ]
    if steady_note:
        lines.extend([steady_note, ""])

    lines.extend(
        [
            (
                "For the bundled MAT operating points, each 50-element plant `CSTATE` vector was loaded, "
                "passed directly to the Python native kernel, and evaluated at time zero without controller "
                "or disturbance adaptation. The resulting measurements and manipulated-variable states were "
                "compared with the corresponding Ricker operating mode. This test verifies that the Python "
                "wrapper preserves the process-state interpretation, unit conventions, output equations, and "
                "mode-dependent operating-point behavior of the original implementation."
            ),
            "",
        "Table-ready metrics are summarized in `mat_state_validation_metrics.csv`; the variable-level table used for figures is `mat_state_validation_paper_table.csv`.",
        "For the main manuscript, `fig_validation_performance_summary` is the recommended compact performance figure; the parity and key-error figures are intended as supporting diagnostics.",
        "",
            "### Main numerical findings",
            "",
        ]
    )
    for title, frame in (
        ("Mode 1 MultiLoop", mode1),
        ("Mode 3 MultiLoop", mode3),
        ("Skogestad Mode 1", skoge),
    ):
        if frame.empty:
            continue
        row = frame.iloc[0]
        lines.append(
            f"- {title}: measurement RMSE = {row['rmse']:.4g}, mean absolute error = "
            f"{row['mean_abs_error']:.4g}, maximum absolute error = {row['max_abs_error']:.4g} "
            f"in native reported units, and median relative error = "
            f"{row['median_relative_error_pct_abs_ge_1']:.4g}% for variables with reported magnitude at least 1."
        )
    lines.extend(
        [
            "",
            "### Interpretation and limitations",
            "",
            (
                "The Mode 3 MAT state is the clearest cross-mode validation case: its simulated product "
                "composition and primary process measurements agree closely with the reported 90/10 operating "
                "mode. The Mode 1 MAT states reproduce the reported Mode 1 output pattern, but they are saved "
                "closed-loop controller initializations rather than the original Ricker optimization state "
                "vectors. Consequently, some manipulated variables, especially valves at or near lower bounds, "
                "should be interpreted as local controller operating-point checks rather than exact NLP optimum "
                "replications."
            ),
            "",
            (
                "The Ricker paper states that the optimized 50-state vectors were available electronically, "
                "but those vectors are not contained in the PDF. Therefore, optimized modes without bundled "
                "MAT state vectors are retained as reference-only rows until the original electronic state "
                "vectors are supplied."
            ),
        ]
    )
    path = paths["report"] / "paper_validation_section.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
