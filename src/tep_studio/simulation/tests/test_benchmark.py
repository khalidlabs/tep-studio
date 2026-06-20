from __future__ import annotations

import numpy as np

from tep_studio.simulation.benchmark import FAULT_FREE, feature_columns, make_fdd_benchmark


def _small_benchmark():
    return make_fdd_benchmark(
        faults=("idv_01", "idv_04"),
        n_runs_per_fault=2,
        onset_h=2.0,
        horizon_h=4.0,
        sampling_min=3.0,
        splits=("train", "test"),
        split_fractions=(0.5, 0.5),
    )


def test_benchmark_has_label_onset_split_columns() -> None:
    frame = _small_benchmark().to_frame()
    for column in ("fault_label", "fault_onset", "split"):
        assert column in frame.columns
    labels = set(frame["fault_label"].unique())
    assert labels == {FAULT_FREE, "idv_01", "idv_04"}


def test_benchmark_splits_partition_runs_disjointly() -> None:
    bench = _small_benchmark()
    by_run = {item.run.run_id: item.split for item in bench.runs}
    assert set(by_run.values()) == {"train", "test"}
    # fault-free has 2 runs -> one train, one test
    ff = [s for item, s in zip(bench.runs, by_run.values()) if item.fault_label == FAULT_FREE]
    assert sorted(ff) == ["test", "train"]


def test_benchmark_sampling_period_is_three_minutes() -> None:
    frame = _small_benchmark().to_frame()
    run0 = frame[frame["run_id"] == frame["run_id"].iloc[0]]
    dt_min = float(np.median(np.diff(run0["time"].to_numpy())) * 60.0)
    assert abs(dt_min - 3.0) < 0.1


def test_benchmark_is_deterministic() -> None:
    a = _small_benchmark().to_frame()
    b = _small_benchmark().to_frame()
    assert a.shape == b.shape
    np.testing.assert_allclose(
        a["measurement.reactor_pressure"].to_numpy(), b["measurement.reactor_pressure"].to_numpy()
    )


def test_feature_column_sets() -> None:
    assert len(feature_columns("canonical41")) == 41
    assert len(feature_columns("classic52")) == 52
    assert len(feature_columns("all")) == 53
