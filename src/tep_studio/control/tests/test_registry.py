from __future__ import annotations

from tep_studio import TEP_SCHEMA
from tep_studio.control.registry import RICKER_MODE1


def test_every_pv_resolves_to_a_measurement() -> None:
    measurement_names = set(TEP_SCHEMA.names("measurements"))
    for pv in RICKER_MODE1.measurement_pvs():
        assert pv in measurement_names, pv


def test_every_mv_resolves_to_a_manipulated_variable() -> None:
    mv_names = set(TEP_SCHEMA.names("manipulated_variables"))
    for mv in RICKER_MODE1.manipulated_variables():
        assert mv in mv_names, mv


def test_loops_cover_all_twelve_mvs_disjointly() -> None:
    feed = [loop.mv for loop in RICKER_MODE1.feed_loops]
    temps = [RICKER_MODE1.reactor_temperature.drives, RICKER_MODE1.separator_temperature.drives]
    static = list(RICKER_MODE1.nominal.static_mv)
    covered = feed + temps + static
    assert len(covered) == 12
    assert len(set(covered)) == 12  # disjoint
    assert set(covered) == set(TEP_SCHEMA.names("manipulated_variables"))


def test_sample_and_reset_times_positive() -> None:
    for loop in RICKER_MODE1.pi_loops():
        assert loop.ti_hours > 0, loop.name
        assert loop.ts_hours > 0, loop.name
    for loop in RICKER_MODE1.feed_loops:
        assert loop.ti_hours > 0 and loop.ts_hours > 0, loop.name
        assert loop.ratio_key in RICKER_MODE1.nominal.ratios, loop.ratio_key


def test_pressure_is_controlled_through_the_purge_ratio() -> None:
    # The single most important point the secondhand extractions disagreed on.
    assert RICKER_MODE1.reactor_pressure.drives == "r5"
    assert RICKER_MODE1.reactor_temperature.drives == "reactor_cooling_water_valve"


def test_pct_g_pv_is_xmeas40() -> None:
    pv = RICKER_MODE1.pct_g.pv
    assert pv == "stripper_underflow_G_concentration"
    assert TEP_SCHEMA.index("measurements", pv) == 39  # 0-based == XMEAS(40)


def test_feed_gain_assignment_matches_flow_units() -> None:
    # A feed (kscmh, ~0.25) gets the large Kc; D feed (kg/h, ~3664) the tiny one.
    by_mv = {loop.mv: loop for loop in RICKER_MODE1.feed_loops}
    assert by_mv["a_feed_valve"].kc == 0.01
    assert by_mv["d_feed_valve"].kc == 1.6e-6


def test_overrides_require_params_before_enabling() -> None:
    for ov in RICKER_MODE1.overrides:
        if ov.enabled:
            assert ov.threshold is not None and ov.gain is not None, ov.name
