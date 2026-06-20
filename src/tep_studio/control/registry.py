"""Ricker (1996) Mode-1 decentralized control strategy, encoded as data.

Every gain / reset time / limit / x0 below was read directly from the runnable
reference ``MultiLoop_mode1.mdl`` (line numbers cited in ``source=``) and the
nominal conditions from ``Mode_1_Init.m``. Note in particular that the A-feed and
D-feed proportional gains differ by four orders of magnitude because the A feed is
measured in kscmh (~0.25) while the D feed is in kg/h (~3664): small flow -> larger
Kc, large flow -> tiny Kc.
"""

from __future__ import annotations

import math

from tep_studio.control.loops import (
    NominalConditions,
    OverrideSpec,
    PILoopSpec,
    RatioLoopSpec,
    RickerRegistry,
)

# --- Mode-1 base case (Mode_1_Init.m) -------------------------------------
_U0 = (63.053, 53.98, 24.644, 61.302, 22.21, 40.064, 38.10, 46.534, 47.446, 41.106, 18.114, 50.0)
_TS_BASE = 0.0005

_NOMINAL = NominalConditions(
    u0=_U0,
    fp_base=100.0,
    ratios={
        "r1": 0.251 / 100.0,  # A feed  (kscmh)
        "r2": 3664.0 / 100.0,  # D feed  (kg/h)
        "r3": 4509.0 / 100.0,  # E feed  (kg/h)
        "r4": 9.35 / 100.0,  # A+C feed (kscmh)
        "r5": 0.337 / 100.0,  # purge   (kscmh)
        "r6": 25.16 / 100.0,  # separator underflow (m3/h)
        "r7": 22.95 / 100.0,  # stripper underflow  (m3/h)
    },
    eadj0=0.0,
    sep_temp_sp0=80.1,  # SP17_0
    ts_base=_TS_BASE,
    static_mv={
        "compressor_recycle_valve": _U0[4],  # 22.21
        "stripper_steam_valve": _U0[8],  # 47.446
        "reactor_agitator_speed": _U0[11],  # 50.0
    },
    p2_coeffs=(1.5192e-3, 5.9446e-1, 2.7690e-1),  # r2 = polyval(p2, %Gsp) - ff_gain_d*Eadj*Fp
    p3_coeffs=(-1.1377e-3, -8.0893e-1, 9.1060e1),  # r3 = polyval(p3, %Gsp) + ff_gain_e*Eadj*Fp
    ff_gain_d=32.0,
    ff_gain_e=46.0,
    production_sp_rate_limit=0.3 * 22.95 / 24.0,  # units/h
    pct_g_sp_rate_limit=50.0 / 24.0,  # %/h
)

# --- Group A: feed/flow ratio loops (SP = ratio * Fp), Ti=0.001/60 h -------
_FEED_TI = 0.001 / 60.0
_FEED_LOOPS = (
    RatioLoopSpec("A feed", "feed_A_flow", "a_feed_valve", "r1", 0.01, _FEED_TI, _TS_BASE, _U0[2], source="mode1.mdl:1431"),
    RatioLoopSpec("C feed", "feed_AC_flow", "ac_feed_valve", "r4", 0.003, _FEED_TI, _TS_BASE, _U0[3], source="mode1.mdl:1537"),
    RatioLoopSpec("D feed", "feed_D_flow", "d_feed_valve", "r2", 1.6e-6, _FEED_TI, _TS_BASE, _U0[0], source="mode1.mdl:1643"),
    RatioLoopSpec("E feed", "feed_E_flow", "e_feed_valve", "r3", 1.8e-6, _FEED_TI, _TS_BASE, _U0[1], source="mode1.mdl:1758"),
    RatioLoopSpec("Purge", "purge_flow", "purge_valve", "r5", 0.01, _FEED_TI, _TS_BASE, _U0[5], source="mode1.mdl:2795"),
    RatioLoopSpec("Sep flow", "separator_underflow", "separator_underflow_valve", "r6", 4e-4, _FEED_TI, _TS_BASE, _U0[6], source="mode1.mdl:3117"),
    RatioLoopSpec("Strip flow", "stripper_underflow", "stripper_underflow_valve", "r7", 4e-4, _FEED_TI, _TS_BASE, _U0[7], source="mode1.mdl:3253"),
)

RICKER_MODE1 = RickerRegistry(
    nominal=_NOMINAL,
    feed_loops=_FEED_LOOPS,
    # Group B: production index. PV = production rate (stripper underflow); out -> Fp adjustment in [-30, 30]; Fp = fp_base + out.
    production=PILoopSpec("Production rate", "stripper_underflow", 3.2, 120 / 60, _TS_BASE, 0.0, hi=30.0, lo=-30.0, drives="production_index", source="mode1.mdl:2744"),
    # Group C: inventory cascades.
    reactor_level=PILoopSpec("Reactor level", "reactor_level", 0.8, 60 / 60, _TS_BASE, _NOMINAL.sep_temp_sp0, hi=120.0, lo=0.0, drives="separator_temperature_setpoint", source="mode1.mdl:3028"),
    separator_level=PILoopSpec("Separator level", "separator_level", -1e-3, 200 / 60, _TS_BASE, _NOMINAL.ratios["r6"], hi=100.0, lo=0.0, drives="r6", source="mode1.mdl:3187"),
    separator_temperature=PILoopSpec("Separator temperature", "separator_temperature", -4.0, 15 / 60, _TS_BASE, _U0[10], hi=100.0, lo=0.0, drives="separator_cooling_water_valve", source="mode1.mdl:3202"),
    stripper_level=PILoopSpec("Stripper level", "stripper_level", -2e-4, 200 / 60, _TS_BASE, _NOMINAL.ratios["r7"], hi=100.0, lo=0.0, drives="r7", source="mode1.mdl:3323"),
    # Group D: reactor temperature -> reactor cooling water valve.
    reactor_temperature=PILoopSpec("Reactor temperature", "reactor_temperature", -8.0, 7.5 / 60, _TS_BASE, _U0[9], hi=100.0, lo=0.0, drives="reactor_cooling_water_valve", source="mode1.mdl:3058"),
    # Group E: reactor pressure -> purge ratio r5 (NOT the recycle valve).
    reactor_pressure=PILoopSpec("Reactor pressure", "reactor_pressure", -1e-4, 20 / 60, _TS_BASE, _NOMINAL.ratios["r5"], hi=100.0, lo=0.0, drives="r5", source="mode1.mdl:3043"),
    # Group F: %G composition feedback (-> Eadj) and the two velocity-form reactant loops.
    pct_g=PILoopSpec("%G in product", "stripper_underflow_G_concentration", -0.4, 100 / 60, _TS_BASE, _NOMINAL.eadj0, hi=math.inf, lo=-math.inf, drives="Eadj", source="mode1.mdl:1257"),
    ya=PILoopSpec("yA control", "", 2e-4, 1.0, 0.1, 0.0, form="velocity", drives="r1_trim", source="mode1.mdl:3376"),
    yac=PILoopSpec("yAC control", "", 3e-4, 2.0, 0.1, 0.0, form="velocity", drives="r4_trim", source="mode1.mdl:3388"),
    # Group G: overrides. Mode-1 thresholds/gains are NOT in the .mdl files (only Mode 3's
    # coolant->recycle override is). Ricker 1996 sec. 4 describes a high-reactor-pressure
    # override that cuts the production index and a high-reactor-level override on the recycle
    # valve. The values below follow that description and are tuned to hold the 3000 kPa trip;
    # they are explicit config so a different plant/operating point can retune them.
    overrides=(
        OverrideSpec("high_pressure_to_production", "reactor_pressure", "production_index", threshold=2900.0, gain=1.5, confirmed_source="ricker_1996_sec4 (tuned to hold 3000 kPa)", enabled=True),
        OverrideSpec("high_level_to_recycle", "reactor_level", "compressor_recycle_valve", threshold=90.0, gain=2.0, confirmed_source="ricker_1996_sec4 / mode3 recycle override", enabled=True),
    ),
)
