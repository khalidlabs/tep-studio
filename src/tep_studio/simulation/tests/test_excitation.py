from __future__ import annotations

import numpy as np
import pytest

from tep_studio.simulation.excitation import (
    SIGNAL_TYPES,
    ExcitationSignal,
    ExcitationSpec,
    excitation_quality,
    signal_series,
)
from tep_studio.ui.config import ScenarioConfig
from tep_studio.ui.service import run_scenario


def test_all_signals_generate_and_are_bounded() -> None:
    times = np.arange(0, 12, 0.01)
    for kind in SIGNAL_TYPES:
        sig = ExcitationSignal(target="reactor_pressure", signal=kind, amplitude=20.0, clock=0.5, f_low=0.1, f_high=2.0)
        y = signal_series(sig, times, master_seed=0)
        assert len(y) == len(times)
        assert np.all(np.abs(y) <= 20.0 + 1e-9)  # never exceeds the requested amplitude


def test_signal_is_deterministic_and_channels_decorrelate() -> None:
    times = np.arange(0, 12, 0.01)
    a = signal_series(ExcitationSignal("reactor_pressure", "prbs", 10.0, clock=0.5), times, 7)
    b = signal_series(ExcitationSignal("reactor_pressure", "prbs", 10.0, clock=0.5), times, 7)
    assert np.array_equal(a, b)  # deterministic given the seed
    c = signal_series(ExcitationSignal("reactor_level", "prbs", 10.0, clock=0.5), times, 7)
    assert abs(float(np.corrcoef(np.sign(a), np.sign(c))[0, 1])) < 0.5  # different target -> decorrelated


def test_pe_order_separates_step_from_prbs() -> None:
    step = ExcitationSpec(signals=(ExcitationSignal("reactor_pressure", "step", 20.0),), seed=1)
    prbs = ExcitationSpec(signals=(ExcitationSignal("reactor_pressure", "prbs", 20.0, clock=0.4), ExcitationSignal("production_rate", "prbs", 1.0, clock=0.6)), seed=1)
    q_step = excitation_quality(step, horizon=12.0, dt=0.01)
    q_prbs = excitation_quality(prbs, horizon=12.0, dt=0.01)
    assert q_step["pe_order"] == 0  # a single step is not persistently exciting
    assert q_prbs["pe_order"] > 5  # broadband multi-channel excitation is rich


def test_closed_loop_excitation_runs_and_labels_the_dataset() -> None:
    spec = ExcitationSpec(
        kind="setpoint", seed=2,
        signals=(ExcitationSignal("reactor_pressure", "prbs", 30.0, clock=0.4), ExcitationSignal("production_rate", "prbs", 1.2, clock=0.6)),
    )
    cfg = ScenarioConfig(mode="mode1", loop_type="closed", horizon=12.0, control_interval=0.01, excitation=spec)
    cfg.validate()
    run = run_scenario(cfg)
    assert not run.terminated, "bounded closed-loop excitation must not trip"
    frame = run.to_frame()
    assert "excitation.kind" in frame.columns and frame["excitation.kind"].iloc[0] == "setpoint"
    assert frame["measurement.reactor_pressure"].std() > 1.0  # the plant actually responded


def test_excitation_round_trips_and_validates() -> None:
    spec = ExcitationSpec(kind="setpoint", seed=5, signals=(ExcitationSignal("reactor_level", "gbn", 5.0),))
    cfg = ScenarioConfig(mode="mode1", excitation=spec)
    assert ScenarioConfig.from_json(cfg.to_json()).excitation == spec
    with pytest.raises(ValueError):
        ScenarioConfig(excitation=ExcitationSpec(kind="setpoint", signals=(ExcitationSignal("not_a_target", "prbs", 1.0),))).validate()
