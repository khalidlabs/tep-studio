"""Fault-detection (FDD) benchmark generator.

Produces the standard fault-detection dataset shape: a fault-free set plus one set per
IDV, faults introduced at a fixed time, fixed sampling (~3 min), with named
train/val/test splits and explicit ``fault_label`` / ``fault_onset`` columns.

This builds on the existing batch/dataset machinery — it only adds the labeling,
protocol presets, and split assignment on top of :func:`run_scenario`. Dash-free.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tep_studio.simulation.schema import TEP_SCHEMA
from tep_studio.ui.config import DisturbanceActivation, ScenarioConfig
from tep_studio.ui.results import RunResult
from tep_studio.ui.service import Progress, run_scenario

ALL_IDVS: tuple[str, ...] = tuple(TEP_SCHEMA.names("disturbances"))
FAULT_FREE = "fault_free"


@dataclass(frozen=True)
class FDDRun:
    run: RunResult
    fault_label: str  # "fault_free" or an IDV name, e.g. "idv_06"
    fault_onset: float  # hours (NaN for fault-free)
    split: str  # "train" | "val" | "test"


@dataclass(frozen=True)
class FDDBenchmark:
    runs: tuple[FDDRun, ...]
    sampling_min: float
    onset_h: float
    horizon_h: float
    mode: str

    def to_frame(self):
        import pandas as pd

        frames = []
        for item in self.runs:
            frame = item.run.to_frame()
            frame = frame.copy()
            frame.insert(0, "fault_label", item.fault_label)
            frame.insert(1, "fault_onset", item.fault_onset)
            frame.insert(2, "split", item.split)
            frames.append(frame)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def summary(self):
        """One row per run: label, split, seed, terminated, n_samples."""
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "run_id": r.run.run_id,
                    "fault_label": r.fault_label,
                    "split": r.split,
                    "seed": r.run.scenario.seed,
                    "terminated": r.run.terminated,
                    "n_samples": len(r.run.frame_records),
                }
                for r in self.runs
            ]
        )

    def write(self, path: str, *, fmt: str = "parquet") -> str:
        frame = self.to_frame()
        if fmt == "csv":
            frame.to_csv(path, index=False)
        elif fmt == "json":
            frame.to_json(path, orient="records")
        else:
            frame.to_parquet(path, index=False)
        return path


def sampling_to_record_every(sampling_min: float, control_interval: float) -> int:
    """``record_every`` that yields ``sampling_min``-minute samples at ``control_interval`` (h)."""
    return max(1, int(round((sampling_min / 60.0) / control_interval)))


def _assign_splits(n: int, splits: tuple[str, ...], fractions: tuple[float, ...]) -> list[str]:
    """Deterministically assign ``n`` seed-runs to ``splits`` by ``fractions`` (per fault)."""
    if len(splits) != len(fractions):
        raise ValueError("splits and split_fractions must have equal length.")
    counts = [int(round(f * n)) for f in fractions]
    # Fix rounding so the counts sum to n (adjust the largest bucket).
    counts[int(np.argmax(fractions))] += n - sum(counts)
    out: list[str] = []
    for split, count in zip(splits, counts):
        out.extend([split] * max(0, count))
    return out[:n] + [splits[-1]] * max(0, n - len(out))


def make_fdd_benchmark(
    faults: tuple[str, ...] = ALL_IDVS,
    *,
    n_runs_per_fault: int = 1,
    include_fault_free: bool = True,
    onset_h: float = 8.0,
    horizon_h: float = 48.0,
    sampling_min: float = 3.0,
    seeds: tuple[float, ...] | None = None,
    splits: tuple[str, ...] = ("train", "test"),
    split_fractions: tuple[float, ...] = (0.5, 0.5),
    loop_type: str = "closed",
    mode: str = "mode1",
    control_interval: float = 0.01,
    magnitude: float = 1.0,
    progress: Progress | None = None,
) -> FDDBenchmark:
    """Generate a labeled FDD benchmark: fault-free + one set per IDV, faults at ``onset_h``.

    Each fault is run ``n_runs_per_fault`` times (one per seed); runs are partitioned
    into ``splits`` by ``split_fractions``. Faults are injected on the closed-loop plant
    by default (the FDD norm). Returns an :class:`FDDBenchmark`.
    """
    seeds = seeds or tuple(float(i) for i in range(1, n_runs_per_fault + 1))
    record_every = sampling_to_record_every(sampling_min, control_interval)
    split_of = _assign_splits(len(seeds), splits, split_fractions)

    labels: list[tuple[str, tuple[DisturbanceActivation, ...]]] = []
    if include_fault_free:
        labels.append((FAULT_FREE, ()))
    for idv in faults:
        labels.append((idv, (DisturbanceActivation(idv=idv, magnitude=magnitude, start_time=onset_h),)))

    total = len(labels) * len(seeds)
    done = 0
    runs: list[FDDRun] = []
    for fault_label, disturbances in labels:
        for seed_index, seed in enumerate(seeds):
            cfg = ScenarioConfig(
                name=f"{fault_label}_seed{int(seed)}",
                loop_type=loop_type,
                mode=mode,
                horizon=horizon_h,
                control_interval=control_interval,
                record_every=record_every,
                seed=seed,
                disturbances=disturbances,
            )
            run = run_scenario(cfg)
            runs.append(
                FDDRun(
                    run=run,
                    fault_label=fault_label,
                    fault_onset=float("nan") if not disturbances else float(onset_h),
                    split=split_of[seed_index],
                )
            )
            done += 1
            if progress:
                progress(done / total, f"{fault_label} ({done}/{total})")
    return FDDBenchmark(runs=tuple(runs), sampling_min=sampling_min, onset_h=onset_h, horizon_h=horizon_h, mode=mode)


# -- feature-column helpers (reproduce common benchmark feature sets) -------
_MEAS = tuple(f"measurement.{n}" for n in TEP_SCHEMA.names("measurements"))  # 41
_MV = tuple(f"implemented_action.{n}" for n in TEP_SCHEMA.names("manipulated_variables"))  # 12


def feature_columns(kind: str = "canonical41") -> list[str]:
    """Column subsets matching common FDD conventions.

    - ``canonical41``: the 41 published measurements.
    - ``classic52``: 22 continuous + 19 composition measurements + 11 MVs.
    - ``all``: every measurement + manipulated-variable column.
    """
    if kind == "canonical41":
        return list(_MEAS)
    if kind == "classic52":
        return list(_MEAS[:22]) + list(_MEAS[22:41]) + list(_MV[:11])
    if kind == "all":
        return list(_MEAS) + list(_MV)
    raise ValueError(f"Unknown feature set {kind!r}; expected canonical41|classic52|all.")
