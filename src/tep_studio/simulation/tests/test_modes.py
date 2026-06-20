from __future__ import annotations

import numpy as np
import pytest

from tep_studio.simulation.core import TennesseeEastmanProcess
from tep_studio.simulation.modes import MODE_KEYS, MODES, available_modes, mode_info, mode_setpoints
from tep_studio.ui.config import ScenarioConfig
from tep_studio.ui.service import run_scenario

_PCT_G = 39  # measurement index for product G concentration (mol%)


def test_mode_registry() -> None:
    assert set(available_modes()) == set(MODE_KEYS) == {"mode1", "mode2", "mode3", "mode4", "mode5", "mode6"}
    assert len(MODES) == 6
    assert mode_info("mode4").production == "max"
    with pytest.raises(KeyError):
        mode_info("mode7")


def test_mode_setpoints_presets() -> None:
    # The G:H ratio is the defining knob: low %G for 10/90 modes, high for 90/10.
    assert mode_setpoints("mode2").pct_g < 30.0
    assert mode_setpoints("mode3").pct_g > 80.0
    assert mode_setpoints("mode5").pct_g < 30.0
    assert mode_setpoints("mode6").pct_g > 80.0
    # Max-production modes request a higher production rate than the base modes.
    assert mode_setpoints("mode4").production_rate > mode_setpoints("mode1").production_rate


def test_reset_accepts_all_modes_from_base_state() -> None:
    sim = TennesseeEastmanProcess()
    for mode in MODE_KEYS:
        meas, _ = sim.reset(mode=mode)
        assert np.all(np.isfinite(meas))
    with pytest.raises(NotImplementedError):
        sim.reset(mode="mode7")


def test_modes_steer_product_composition() -> None:
    """Outcome check: a closed-loop run in a 90/10 mode drives product G up, a 10/90 mode
    drives it down — well separated after enough run time."""
    horizon = 24.0
    g_high = run_scenario(ScenarioConfig(mode="mode3", loop_type="closed", horizon=horizon, control_interval=0.01)).to_frame()
    g_low = run_scenario(ScenarioConfig(mode="mode2", loop_type="closed", horizon=horizon, control_interval=0.01)).to_frame()
    pct_g_high = g_high["measurement.stripper_underflow_G_concentration"].iloc[-1]
    pct_g_low = g_low["measurement.stripper_underflow_G_concentration"].iloc[-1]
    assert pct_g_high > pct_g_low + 20.0
    assert pct_g_high > 65.0 and pct_g_low < 40.0
