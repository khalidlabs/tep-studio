from __future__ import annotations

import numpy as np
import pytest

from tep_studio.simulation.core import TennesseeEastmanProcess
from tep_studio.simulation.modes import MODE_KEYS, MODES, available_modes, mode_info, mode_setpoints
from tep_studio.ui.config import ScenarioConfig
from tep_studio.ui.service import run_scenario

_PCT_G = 39  # measurement index for product G concentration (mol%)
_REACTOR_P = 6  # measurement index for reactor pressure (kPa)


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


def test_reset_initial_states_per_mode() -> None:
    """Base / 50-50 / 10-90 modes start from the base case; the 90/10 modes (3, 6) start
    from the bundled operating-point state, already at high %G near 2800 kPa."""
    sim = TennesseeEastmanProcess()
    for mode in MODE_KEYS:
        meas, _ = sim.reset(mode=mode)
        assert np.all(np.isfinite(meas))
    for mode in ("mode3", "mode6"):  # bundled 90/10 operating-point state
        meas, _ = sim.reset(mode=mode)
        assert meas[_PCT_G] > 80.0
        assert 2700.0 < meas[_REACTOR_P] < 2900.0
    meas1, _ = sim.reset(mode="mode1")  # base case ~50/50 composition
    assert 40.0 < meas1[_PCT_G] < 70.0
    with pytest.raises(NotImplementedError):
        sim.reset(mode="mode7")


def test_90_10_modes_hold_without_tripping() -> None:
    """The 90/10 modes (3, 6) hold their operating point on a long run: they start from the
    bundled state and the controller keeps %G high without a high-pressure trip."""
    for mode in ("mode3", "mode6"):
        run = run_scenario(ScenarioConfig(mode=mode, loop_type="closed", horizon=36.0, control_interval=0.01))
        assert not run.terminated, f"{mode} tripped at t={run.final_time:.1f} h"
        frame = run.to_frame()
        assert frame["measurement.stripper_underflow_G_concentration"].iloc[-1] > 80.0
        assert frame["measurement.reactor_pressure"].iloc[-1] < 2950.0


def test_modes_steer_product_composition() -> None:
    """Outcome check: the 90/10 mode holds product G high, the 10/90 mode steers it down —
    well separated after enough run time."""
    horizon = 24.0
    g_high = run_scenario(ScenarioConfig(mode="mode3", loop_type="closed", horizon=horizon, control_interval=0.01)).to_frame()
    g_low = run_scenario(ScenarioConfig(mode="mode2", loop_type="closed", horizon=horizon, control_interval=0.01)).to_frame()
    pct_g_high = g_high["measurement.stripper_underflow_G_concentration"].iloc[-1]
    pct_g_low = g_low["measurement.stripper_underflow_G_concentration"].iloc[-1]
    assert pct_g_high > pct_g_low + 20.0
    assert pct_g_high > 65.0 and pct_g_low < 40.0
