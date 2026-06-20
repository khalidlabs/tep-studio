"""Paper-style figures for the closed-loop decentralized control results.

These mirror the validation framework's figure conventions (Agg backend, png/pdf/svg
plus a source CSV per figure) so the closed-loop demonstration is reproducible the
same way the base-case validation figures are. Run as::

    PYTHONPATH=src python3 -m tep_studio.control.figures
"""

from __future__ import annotations

import dataclasses as dc
import os
import tempfile
from pathlib import Path

_cache_dir = Path(tempfile.gettempdir()) / "tep_studio_matplotlib"
_cache_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_cache_dir))
os.environ.setdefault("XDG_CACHE_HOME", str(_cache_dir))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tep_studio import TennesseeEastmanProcess, TrajectoryDataset
from tep_studio.control import ClosedLoopSimulation, RickerMultiLoopController
from tep_studio.control.registry import RICKER_MODE1
from tep_studio.simulation.validation.artifacts import DEFAULT_OUTPUT_DIR, ensure_output_tree

U0 = np.array(RICKER_MODE1.nominal.u0, dtype=np.float64)
_PRESSURE = "measurement.reactor_pressure"


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


def _frame(result) -> pd.DataFrame:
    return TrajectoryDataset.from_results(result.results).to_pandas()


def _default_setpoints():
    sim = TennesseeEastmanProcess()
    meas0, _ = sim.reset(mode="mode1")
    ctl = RickerMultiLoopController()
    ctl.reset(meas0)
    return ctl.setpoints


def _open_loop_frame(horizon: float = 4.0, control_interval: float = 0.01) -> pd.DataFrame:
    sim = TennesseeEastmanProcess()
    sim.reset(mode="mode1")
    results = []
    while sim.time < horizon:
        result = sim.advance(U0, control_interval=control_interval)
        results.append(result)
        if result.shutdown_status["terminated"]:
            break
    return TrajectoryDataset.from_results(results).to_pandas()


def _closed_loop(horizon: float, *, overrides: bool = True, setpoints=None, disturbances=None,
                 disturbance_schedule=None, record_every: int = 100):
    controller = RickerMultiLoopController(enable_overrides=overrides, setpoints=setpoints)
    runner = ClosedLoopSimulation(controller=controller, control_interval=0.0005, horizon=horizon)
    return runner.run(disturbances=disturbances, disturbance_schedule=disturbance_schedule, record_every=record_every)


def fig_closed_loop_stabilization(figure_dir: Path, *, horizon: float = 48.0) -> list[Path]:
    """Multi-panel closed-loop trajectory: the plant held at its operating point."""
    result = _closed_loop(horizon, record_every=100)
    frame = _frame(result)
    sp = _default_setpoints()
    panels = [
        (_PRESSURE, "Reactor Pressure", "kPa gauge", sp.reactor_pressure),
        ("measurement.reactor_level", "Reactor Level", "%", sp.reactor_level),
        ("measurement.reactor_temperature", "Reactor Temperature", "deg C", sp.reactor_temperature),
        ("measurement.separator_level", "Separator Level", "%", sp.separator_level),
        ("measurement.stripper_level", "Stripper Level", "%", sp.stripper_level),
        ("measurement.separator_temperature", "Separator Temperature", "deg C", None),
        ("measurement.stripper_underflow", "Production Rate", "m3/h", sp.production_rate),
        ("measurement.purge_flow", "Purge Rate", "kscmh", None),
    ]
    fig, axes = plt.subplots(4, 2, figsize=(8.0, 8.5), sharex=True)
    for ax, (column, title, ylabel, setpoint) in zip(axes.ravel(), panels):
        ax.plot(frame["time"], frame[column], color="#1f77b4", linewidth=1.5)
        if setpoint is not None:
            ax.axhline(setpoint, color="#888888", linestyle=":", linewidth=1.0)
        if column == _PRESSURE:
            ax.axhline(3000.0, color="#b22222", linestyle="--", linewidth=1.0, label="Shutdown limit")
            ax.legend(frameon=False, fontsize=8)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.grid(True, alpha=0.25)
    axes[-1, 0].set_xlabel("Time (h)")
    axes[-1, 1].set_xlabel("Time (h)")
    fig.suptitle("Closed-Loop Stabilization (Decentralized Multiloop Control)", fontsize=12)
    return _save(fig, figure_dir, "fig_closed_loop_stabilization", frame)


def fig_open_vs_closed_pressure(figure_dir: Path) -> list[Path]:
    """The headline contrast: open-loop trips on high pressure; closed-loop holds it."""
    open_frame = _open_loop_frame(horizon=4.0)
    closed_frame = _frame(_closed_loop(4.0, record_every=20))
    shutdown_rows = open_frame[open_frame["terminated"].astype(bool)]
    shutdown_time = None if shutdown_rows.empty else float(shutdown_rows.iloc[0]["time"])

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(open_frame["time"], open_frame[_PRESSURE], color="#b22222", linewidth=1.8, label="Open loop (constant inputs)")
    ax.plot(closed_frame["time"], closed_frame[_PRESSURE], color="#1f77b4", linewidth=1.8, label="Closed loop (decentralized control)")
    ax.axhline(3000.0, color="#444444", linestyle="--", linewidth=1.0, label="Shutdown limit (3000 kPa)")
    if shutdown_time is not None:
        ax.axvline(shutdown_time, color="#b22222", linestyle=":", linewidth=1.0)
        ax.annotate(f"open-loop shutdown\n{shutdown_time:.2f} h", xy=(shutdown_time, 3000.0),
                    xytext=(shutdown_time - 1.4, 2880.0), fontsize=8, color="#b22222")
    ax.set_xlabel("Time (h)")
    ax.set_ylabel("Reactor pressure (kPa gauge)")
    ax.set_title("Open-Loop Instability vs Closed-Loop Stabilization")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    merged = pd.concat(
        [
            open_frame[["time", _PRESSURE]].assign(case="open_loop"),
            closed_frame[["time", _PRESSURE]].assign(case="closed_loop"),
        ],
        ignore_index=True,
    )
    return _save(fig, figure_dir, "fig_open_vs_closed_pressure", merged)


def fig_disturbance_rejection(figure_dir: Path, *, horizon: float = 20.0) -> list[Path]:
    """Reactor pressure and level under step disturbances applied at t = 1 h."""
    cases = [(1, "IDV(1) A/C ratio"), (8, "IDV(8) random A/B/C"), (13, "IDV(13) kinetics drift")]
    colors = ["#1f77b4", "#2f6f4e", "#d2691e"]
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 6.0), sharex=True)
    collected = []
    for (idv, label), color in zip(cases, colors):
        vec = np.zeros(28)
        vec[idv - 1] = 1.0
        schedule = (lambda t, v=vec: v if t >= 1.0 else np.zeros(28))
        frame = _frame(_closed_loop(horizon, disturbance_schedule=schedule, record_every=50))
        axes[0].plot(frame["time"], frame[_PRESSURE], color=color, linewidth=1.4, label=label)
        axes[1].plot(frame["time"], frame["measurement.reactor_level"], color=color, linewidth=1.4, label=label)
        collected.append(frame[["time", _PRESSURE, "measurement.reactor_level"]].assign(disturbance=label))
    axes[0].axhline(3000.0, color="#b22222", linestyle="--", linewidth=1.0)
    for ax in axes:
        ax.axvline(1.0, color="#888888", linestyle=":", linewidth=1.0)
        ax.grid(True, alpha=0.25)
    axes[0].set_ylabel("Reactor pressure (kPa)")
    axes[1].set_ylabel("Reactor level (%)")
    axes[1].set_xlabel("Time (h)")
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")
    fig.suptitle("Disturbance Rejection (Step Applied at t = 1 h)", fontsize=12)
    return _save(fig, figure_dir, "fig_disturbance_rejection", pd.concat(collected, ignore_index=True))


def fig_pressure_override(figure_dir: Path, *, horizon: float = 8.0) -> list[Path]:
    """High-pressure override caps the reactor under a high-throughput kinetics upset."""
    sp = dc.replace(_default_setpoints(), production_rate=32.0)
    idv13 = np.zeros(28)
    idv13[12] = 1.0
    without = _frame(_closed_loop(horizon, overrides=False, setpoints=sp, disturbances=idv13, record_every=40))
    with_ovr = _frame(_closed_loop(horizon, overrides=True, setpoints=sp, disturbances=idv13, record_every=40))

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.plot(without["time"], without[_PRESSURE], color="#b22222", linewidth=1.6, label="Overrides off")
    ax.plot(with_ovr["time"], with_ovr[_PRESSURE], color="#1f77b4", linewidth=1.6, label="Overrides on")
    ax.axhline(3000.0, color="#444444", linestyle="--", linewidth=1.0, label="Shutdown limit")
    ax.axhline(2900.0, color="#888888", linestyle=":", linewidth=1.0, label="Override threshold")
    ax.set_xlabel("Time (h)")
    ax.set_ylabel("Reactor pressure (kPa gauge)")
    ax.set_title("High-Pressure Override Under a Kinetics Upset at High Throughput")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    merged = pd.concat(
        [without[["time", _PRESSURE]].assign(case="overrides_off"), with_ovr[["time", _PRESSURE]].assign(case="overrides_on")],
        ignore_index=True,
    )
    return _save(fig, figure_dir, "fig_pressure_override", merged)


def generate_control_figures(output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    figure_dir = ensure_output_tree(output_dir)["figures"]
    figures: list[Path] = []
    figures.extend(fig_closed_loop_stabilization(figure_dir))
    figures.extend(fig_open_vs_closed_pressure(figure_dir))
    figures.extend(fig_disturbance_rejection(figure_dir))
    figures.extend(fig_pressure_override(figure_dir))
    return figures


if __name__ == "__main__":
    produced = generate_control_figures()
    images = [p for p in produced if p.suffix == ".png"]
    print(f"Wrote {len(produced)} files to the figures directory:")
    for path in images:
        print(f"  {path}")
