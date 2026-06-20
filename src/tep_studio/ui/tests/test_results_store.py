from __future__ import annotations

import tempfile

import pytest

from tep_studio.ui.config import ScenarioConfig
from tep_studio.ui.results import RunResult
from tep_studio.ui.store import RunStore


def _dummy(run_id: str) -> RunResult:
    return RunResult(
        run_id=run_id,
        scenario=ScenarioConfig(name=run_id),
        frame_records=[{"time": 0.0, "measurement.reactor_pressure": 2700.0}],
        columns=["time", "measurement.reactor_pressure"],
        metrics={"iae": {"reactor_pressure": 1.25}},
        peak={"reactor_pressure_max": 2708.6},
        terminated=False,
        truncated=True,
        final_time=12.0,
        n_steps=1200,
        shutdown=None,
        record=None,
        created_at="2026-06-19T00:00:00Z",
    )


def test_put_get_has_evict_in_memory() -> None:
    store = RunStore(capacity=10)
    store.put(_dummy("a"))
    assert store.has("a")
    assert store.get("a").scenario.name == "a"
    assert store.get("missing") is None
    store.evict("a")
    assert not store.has("a")


def test_capacity_eviction_in_memory() -> None:
    store = RunStore(capacity=3)
    for rid in ("a", "b", "c", "d"):
        store.put(_dummy(rid))
    assert store.ids() == ["b", "c", "d"]  # oldest "a" evicted
    assert store.get("a") is None
    assert store.get("d") is not None


def test_summary_and_frame() -> None:
    run = _dummy("x")
    summary = run.summary()
    assert summary["run_id"] == "x"
    assert summary["peak_reactor_pressure"] == 2708.6
    assert summary["iae_reactor_pressure"] == 1.25
    frame = run.to_frame()
    assert list(frame.columns) == ["time", "measurement.reactor_pressure"]
    assert len(frame) == 1


def test_diskcache_backend_roundtrip() -> None:
    diskcache = pytest.importorskip("diskcache")
    with tempfile.TemporaryDirectory() as tmp:
        cache = diskcache.Cache(tmp)
        store = RunStore(cache=cache, capacity=2)
        store.put(_dummy("a"))
        store.put(_dummy("b"))
        store.put(_dummy("c"))  # evicts "a"
        assert store.get("a") is None
        assert store.get("c").scenario.name == "c"  # survives pickle round-trip
        assert store.ids() == ["b", "c"]
        cache.close()
