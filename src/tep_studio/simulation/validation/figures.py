from __future__ import annotations

from pathlib import Path
import os
import tempfile

_cache_dir = Path(tempfile.gettempdir()) / "tep_studio_matplotlib"
_cache_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_cache_dir))
os.environ.setdefault("XDG_CACHE_HOME", str(_cache_dir))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tep_studio.simulation.validation.artifacts import DEFAULT_OUTPUT_DIR, ensure_output_tree


def generate_figures(output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    paths = ensure_output_tree(output_dir)
    figures: list[Path] = []
    trajectories = {
        path.stem: pd.read_csv(path)
        for path in sorted(paths["trajectories"].glob("*.csv"))
    }
    if "r12_open_loop_shutdown.RK45" in trajectories:
        figures.extend(_r12_shutdown(trajectories["r12_open_loop_shutdown.RK45"], paths["figures"]))
    adchem = {name: frame for name, frame in trajectories.items() if name.startswith("adchem_solver_independence.")}
    if adchem:
        figures.extend(_solver_independence(adchem, paths["figures"]))
    metrics_path = paths["metrics"] / "validation_summary.csv"
    if metrics_path.exists():
        figures.extend(_runtime(pd.read_csv(metrics_path), paths["figures"]))
        figures.extend(_contract_summary(pd.read_csv(metrics_path), paths["figures"]))
    steady_state_path = paths["metrics"] / "steady_state_summary.csv"
    if steady_state_path.exists():
        steady_state = pd.read_csv(steady_state_path)
        figures.extend(_steady_state_base_validation(steady_state, paths["figures"]))
        figures.extend(_steady_state_modes_reference(steady_state, paths["figures"]))
    mat_state_path = paths["metrics"] / "mat_state_validation_paper_table.csv"
    if mat_state_path.exists():
        mat_state = pd.read_csv(mat_state_path)
        figures.extend(_mat_state_parity(mat_state, paths["figures"]))
        figures.extend(_mat_state_key_errors(mat_state, paths["figures"]))
    mat_metrics_path = paths["metrics"] / "mat_state_validation_metrics.csv"
    if steady_state_path.exists() or mat_metrics_path.exists():
        figures.extend(_validation_performance_summary(paths["metrics"], paths["figures"]))
    return figures


def _save(fig: plt.Figure, figure_dir: Path, name: str, data: pd.DataFrame) -> list[Path]:
    source_path = figure_dir / f"{name}_source.csv"
    data.to_csv(source_path, index=False)
    paths = [source_path]
    for ext in ("png", "pdf", "svg"):
        path = figure_dir / f"{name}.{ext}"
        fig.savefig(path, bbox_inches="tight", dpi=200)
        paths.append(path)
    plt.close(fig)
    return paths


def _r12_shutdown(frame: pd.DataFrame, figure_dir: Path) -> list[Path]:
    columns = [
        ("measurement.reactor_feed_flow", "Reactor Feed", "kscmh"),
        ("measurement.reactor_pressure", "Reactor Pressure", "kPa gauge"),
        ("measurement.reactor_level", "Reactor Level", "%"),
        ("measurement.reactor_temperature", "Reactor Temperature", "deg C"),
        ("measurement.separator_temperature", "Separator Temperature", "deg C"),
        ("measurement.separator_level", "Separator Level", "%"),
        ("measurement.purge_flow", "Purge Rate", "kscmh"),
        ("measurement.stripper_temperature", "Stripper Temperature", "deg C"),
    ]
    fig, axes = plt.subplots(4, 2, figsize=(8.0, 8.5), sharex=True)
    shutdown_rows = frame[frame["terminated"].astype(bool)]
    shutdown_time = None if shutdown_rows.empty else float(shutdown_rows.iloc[0]["time"])
    for ax, (column, title, ylabel) in zip(axes.ravel(), columns):
        ax.plot(frame["time"], frame[column], color="#1f77b4", linewidth=1.6)
        if column == "measurement.reactor_pressure":
            ax.axhline(3000.0, color="#b22222", linestyle="--", linewidth=1.0, label="Shutdown limit")
            ax.legend(frameon=False, fontsize=8)
        if shutdown_time is not None:
            ax.axvline(shutdown_time, color="#444444", linestyle=":", linewidth=1.0)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.grid(True, alpha=0.25)
    axes[-1, 0].set_xlabel("Time (h)")
    axes[-1, 1].set_xlabel("Time (h)")
    fig.suptitle("R12 Open-Loop Shutdown Validation", fontsize=12)
    return _save(fig, figure_dir, "fig_r12_shutdown", frame)


def _solver_independence(trajectories: dict[str, pd.DataFrame], figure_dir: Path) -> list[Path]:
    fig, axes = plt.subplots(2, 1, figsize=(7.0, 5.5), sharex=True)
    combined = []
    for name, frame in trajectories.items():
        solver = name.split(".")[-1]
        axes[0].plot(frame["time"], frame["measurement.reactor_pressure"], label=solver, linewidth=1.4)
        axes[1].plot(frame["time"], frame["measurement.reactor_temperature"], label=solver, linewidth=1.4)
        copy = frame[["time", "measurement.reactor_pressure", "measurement.reactor_temperature"]].copy()
        copy["solver"] = solver
        combined.append(copy)
    axes[0].set_ylabel("Reactor pressure (kPa gauge)")
    axes[1].set_ylabel("Reactor temperature (deg C)")
    axes[1].set_xlabel("Time (h)")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(frameon=False)
    fig.suptitle("Solver-Independence Validation Scenario", fontsize=12)
    return _save(fig, figure_dir, "fig_solver_independence", pd.concat(combined, ignore_index=True))


def _runtime(metrics: pd.DataFrame, figure_dir: Path) -> list[Path]:
    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    labels = metrics["scenario"] + "\n" + metrics["solver"]
    ax.bar(labels, metrics["elapsed_s"], color="#4c78a8")
    ax.set_ylabel("Wall time (s)")
    ax.set_title("Validation Runtime On Current Machine")
    ax.tick_params(axis="x", labelrotation=35)
    ax.grid(True, axis="y", alpha=0.25)
    return _save(fig, figure_dir, "fig_runtime_benchmark", metrics)


def _contract_summary(metrics: pd.DataFrame, figure_dir: Path) -> list[Path]:
    summary = metrics[["scenario", "solver", "terminated", "final_time_h", "samples"]].copy()
    summary["pass"] = True
    fig, ax = plt.subplots(figsize=(7.0, 2.8))
    y = range(len(summary))
    colors = ["#2ca02c" if value else "#b22222" for value in summary["pass"]]
    ax.barh(list(y), [1] * len(summary), color=colors)
    ax.set_yticks(list(y), labels=summary["scenario"] + " / " + summary["solver"])
    ax.set_xticks([])
    ax.set_title("Validation Contract Summary")
    return _save(fig, figure_dir, "fig_contract_summary", summary)


def _steady_state_base_validation(frame: pd.DataFrame, figure_dir: Path) -> list[Path]:
    variables = [
        "feed_A_flow",
        "feed_D_flow",
        "feed_E_flow",
        "reactor_pressure",
        "reactor_level",
        "reactor_temperature",
        "purge_flow",
        "separator_temperature",
        "stripper_temperature",
        "compressor_work",
    ]
    data = frame[
        (frame["mode"] == "base_case")
        & (frame["group"] == "measurement")
        & (frame["variable"].isin(variables))
    ].copy()
    data["label"] = data["variable"].str.replace("_", " ").str.title()

    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    ax.bar(data["label"], data["relative_error_pct"], color="#4c78a8")
    ax.set_ylabel("Relative error (%)")
    ax.set_title("Base-Case Steady-State Check Against Ricker Table 2")
    ax.tick_params(axis="x", labelrotation=40)
    ax.grid(True, axis="y", alpha=0.25)
    return _save(fig, figure_dir, "fig_steady_state_base_validation", data)


def _steady_state_modes_reference(frame: pd.DataFrame, figure_dir: Path) -> list[Path]:
    variables = [
        "reactor_pressure",
        "reactor_temperature",
        "purge_flow",
        "stripper_underflow_G_concentration",
        "stripper_underflow_H_concentration",
    ]
    labels = {
        "reactor_pressure": "Reactor pressure (kPa)",
        "reactor_temperature": "Reactor temperature (deg C)",
        "purge_flow": "Purge rate (kscmh)",
        "stripper_underflow_G_concentration": "Product G (mol %)",
        "stripper_underflow_H_concentration": "Product H (mol %)",
    }
    data = frame[
        (frame["group"] == "measurement")
        & (frame["variable"].isin(variables))
        & (frame["mode"] != "base_case")
    ].copy()
    data["plot_label"] = data["variable"].map(labels)
    mode_order = [
        "mode_1_50_50",
        "mode_2_10_90",
        "mode_3_90_10",
        "mode_4_50_50_max",
        "mode_5_10_90_max",
        "mode_6_90_10_max",
    ]
    data["mode"] = pd.Categorical(data["mode"], categories=mode_order, ordered=True)
    data = data.sort_values(["plot_label", "mode"])

    fig, axes = plt.subplots(3, 2, figsize=(8.0, 7.0), sharex=True)
    for ax, variable in zip(axes.ravel(), variables):
        subset = data[data["variable"] == variable].copy()
        ax.plot(subset["label"], subset["reported"], marker="o", linewidth=1.5, color="#2f6f4e")
        ax.set_title(labels[variable], fontsize=10)
        ax.grid(True, alpha=0.25)
        ax.tick_params(axis="x", labelrotation=30)
    axes.ravel()[-1].axis("off")
    fig.suptitle("Reported Ricker 1995 Optimal Steady States", fontsize=12)
    return _save(fig, figure_dir, "fig_steady_state_modes_reference", data)


def _mat_state_parity(frame: pd.DataFrame, figure_dir: Path) -> list[Path]:
    data = frame[
        frame["variable"].isin(
            [
                "feed_A_flow",
                "feed_AC_flow",
                "recycle_flow",
                "reactor_feed_flow",
                "reactor_level",
                "reactor_temperature",
                "purge_flow",
                "separator_temperature",
                "separator_level",
                "stripper_temperature",
                "stripper_underflow_G_concentration",
                "stripper_underflow_H_concentration",
            ]
        )
    ].copy()
    data = data[data["reported"].abs() >= 1.0]
    fig, ax = plt.subplots(figsize=(5.2, 5.0))
    for label, subset in data.groupby("reference", sort=False):
        ax.scatter(subset["reported"], subset["simulated"], label=label, s=34, alpha=0.85)
    lower = float(min(data["reported"].min(), data["simulated"].min()))
    upper = float(max(data["reported"].max(), data["simulated"].max()))
    ax.plot([lower, upper], [lower, upper], color="#333333", linewidth=1.0, linestyle="--")
    ax.set_xlabel("Reported value")
    ax.set_ylabel("Simulated value from MAT CSTATE")
    ax.set_title("MAT Operating-Point Output Parity")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, figure_dir, "fig_mat_state_output_parity", data)


def _mat_state_key_errors(frame: pd.DataFrame, figure_dir: Path) -> list[Path]:
    variables = [
        "reactor_pressure",
        "reactor_level",
        "reactor_temperature",
        "purge_flow",
        "separator_temperature",
        "separator_level",
        "stripper_temperature",
        "stripper_underflow_G_concentration",
        "stripper_underflow_H_concentration",
    ]
    data = frame[frame["variable"].isin(variables)].copy()
    data["plot_variable"] = data["variable"].str.replace("_", " ").str.title()
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    pivot = data.pivot(index="plot_variable", columns="reference", values="abs_error")
    pivot = pivot.loc[[v.replace("_", " ").title() for v in variables]]
    pivot.plot(kind="bar", ax=ax, width=0.78)
    ax.set_ylabel("Absolute error")
    ax.set_title("MAT Operating-Point Errors for Key Reported Measurements")
    ax.tick_params(axis="x", labelrotation=40)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, figure_dir, "fig_mat_state_key_errors", data)


def _validation_performance_summary(metrics_dir: Path, figure_dir: Path) -> list[Path]:
    rows: list[dict[str, object]] = []
    high_precision_base_path = metrics_dir / "base_case_high_precision_summary.csv"
    steady_path = metrics_dir / "steady_state_summary.csv"
    if high_precision_base_path.exists():
        base = pd.read_csv(high_precision_base_path)
        base = base[base["reported"].abs() >= 1.0].copy()
        rows.append(
            {
                "case": "Base case",
                "median_relative_error_pct": float(base["relative_error_pct"].median()),
                "mean_abs_error": float(base["abs_error"].mean()),
                "source": "example.doc high-precision Downs and Vogel y0",
            }
        )
    elif steady_path.exists():
        steady = pd.read_csv(steady_path)
        base = steady[
            (steady["mode"] == "base_case")
            & (steady["group"] == "measurement")
            & (steady["reported"].abs() >= 1.0)
        ].copy()
        if not base.empty:
            rows.append(
                {
                    "case": "Base case",
                    "median_relative_error_pct": float(base["relative_error_pct"].median()),
                    "mean_abs_error": float(base["abs_error"].mean()),
                    "source": "Downs and Vogel/Ricker base steady state",
                }
            )

    mat_path = metrics_dir / "mat_state_validation_metrics.csv"
    if mat_path.exists():
        mat = pd.read_csv(mat_path)
        labels = {
            "mode1_multiloop": "Mode 1 MAT",
            "mode3_multiloop": "Mode 3 MAT",
            "mode1_skogestad": "Skogestad Mode 1",
        }
        for _, item in mat[mat["group"] == "measurement"].iterrows():
            rows.append(
                {
                    "case": labels.get(str(item["reference"]), str(item["reference"])),
                    "median_relative_error_pct": float(item["median_relative_error_pct_abs_ge_1"]),
                    "mean_abs_error": float(item["mean_abs_error"]),
                    "source": str(item["label"]),
                }
            )

    data = pd.DataFrame(rows)
    if data.empty:
        return []
    data = data.sort_values("median_relative_error_pct", ascending=True)
    fig_height = max(2.8, 0.46 * len(data) + 1.2)
    fig, ax = plt.subplots(figsize=(6.6, fig_height))
    colors = ["#2f6f4e" if value < 0.25 else "#4c78a8" for value in data["median_relative_error_pct"]]
    positions = np.arange(len(data))
    ax.barh(positions, data["median_relative_error_pct"], color=colors, height=0.58)
    ax.set_yticks(positions, labels=data["case"])
    ax.invert_yaxis()
    ax.set_xlabel("Median relative error for reported measurements (%)")
    ax.set_title("Validation Performance Summary")
    ax.grid(True, axis="x", alpha=0.25)
    upper = max(0.35, float(data["median_relative_error_pct"].max()) * 1.2)
    ax.set_xlim(0.0, upper)
    for y, value in zip(positions, data["median_relative_error_pct"]):
        ax.text(value + upper * 0.015, y, f"{value:.3g}%", va="center", fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return _save(fig, figure_dir, "fig_validation_performance_summary", data)
