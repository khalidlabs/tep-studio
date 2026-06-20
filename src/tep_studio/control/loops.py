"""Declarative specifications for the decentralized control loops.

Each loop is data (controlled variable, manipulated/target signal, PI parameters)
so the strategy is auditable and the controller orchestration stays a thin
interpreter of this table. Every ``pv``/``mv`` is a schema *name* (resolved
against ``TEP_SCHEMA``), never a raw array index -- this is what prevents the
1-based XMEAS/XMV <-> 0-based Python drift.

All numeric values are transcribed directly from Ricker's runnable reference
``MultiLoop_mode1.mdl`` (gains/reset times/limits) and ``Mode_1_Init.m`` (nominal
conditions). ``ti_hours``/``ts_hours`` are in HOURS (the .mdl writes reset times
as ``minutes/60``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PILoopSpec:
    """A single PI loop whose output is an MV or an internal setpoint/ratio."""

    name: str
    pv: str  # schema measurement name; "" when the PV is computed (e.g. yA/yAC)
    kc: float
    ti_hours: float
    ts_hours: float
    x0: float  # initial output, for bumpless start
    hi: float = math.inf
    lo: float = -math.inf
    form: str = "positional"  # "positional" | "velocity"
    drives: str = ""  # human label of the driven signal (MV name or internal tag)
    source: str = ""  # citation into the reference model


@dataclass(frozen=True)
class RatioLoopSpec:
    """A fast feed/flow loop: setpoint = ratio * Fp, output = a valve %."""

    name: str
    pv: str  # measured flow (schema measurement name)
    mv: str  # output manipulated variable (schema name)
    ratio_key: str  # which production ratio scales the setpoint: "r1".."r7"
    kc: float
    ti_hours: float
    ts_hours: float
    x0: float  # initial valve %, for bumpless start
    hi: float = 100.0
    lo: float = 0.0
    source: str = ""


@dataclass(frozen=True)
class OverrideSpec:
    """A constraint override that clamps a signal when a measurement crosses a limit.

    ``target`` is either ``"production_index"`` (reduce Fp) or a manipulated-variable
    name. ``threshold``/``gain`` for the Mode-1 high-pressure and high-level overrides
    are NOT present in the reference .mdl files (only Mode 3's coolant->recycle override
    is); they are transcribed from Ricker 1996 Table 2 / tuned to hold the constraint,
    so they are required (non-None) before an enabled override may run.
    """

    name: str
    trigger_pv: str  # schema measurement name
    target: str  # "production_index" | manipulated-variable name
    threshold: float | None
    gain: float | None
    confirmed_source: str
    enabled: bool = False


@dataclass(frozen=True)
class NominalConditions:
    """Mode-1 base-case constants from ``Mode_1_Init.m`` (and Downs & Vogel base case)."""

    u0: tuple[float, ...]  # 12 base manipulated-variable values (%)
    fp_base: float  # nominal production index (100)
    ratios: dict[str, float]  # nominal r1..r7 (steady flow / Fp)
    eadj0: float  # initial composition trim
    sep_temp_sp0: float  # SP17_0: initial separator-temperature setpoint
    ts_base: float  # base sample / integration period (h)
    static_mv: dict[str, float]  # MVs held constant in Mode 1: name -> %
    p2_coeffs: tuple[float, float, float]  # D-feed-ratio feedforward polynomial vs %G sp
    p3_coeffs: tuple[float, float, float]  # E-feed-ratio feedforward polynomial vs %G sp
    ff_gain_d: float  # Eadj feedforward gain into r2
    ff_gain_e: float  # Eadj feedforward gain into r3
    production_sp_rate_limit: float  # max |d(production sp)/dt| (units/h)
    pct_g_sp_rate_limit: float  # max |d(%G sp)/dt| (%/h)


@dataclass(frozen=True)
class RickerRegistry:
    """The complete Mode-1 decentralized strategy as data."""

    nominal: NominalConditions
    feed_loops: tuple[RatioLoopSpec, ...]
    production: PILoopSpec
    reactor_level: PILoopSpec
    reactor_pressure: PILoopSpec
    reactor_temperature: PILoopSpec
    separator_level: PILoopSpec
    separator_temperature: PILoopSpec
    stripper_level: PILoopSpec
    pct_g: PILoopSpec
    ya: PILoopSpec
    yac: PILoopSpec
    overrides: tuple[OverrideSpec, ...]

    def pi_loops(self) -> tuple[PILoopSpec, ...]:
        return (
            self.production,
            self.reactor_level,
            self.reactor_pressure,
            self.reactor_temperature,
            self.separator_level,
            self.separator_temperature,
            self.stripper_level,
            self.pct_g,
            self.ya,
            self.yac,
        )

    def measurement_pvs(self) -> set[str]:
        names = {loop.pv for loop in self.feed_loops}
        names |= {loop.pv for loop in self.pi_loops() if loop.pv}
        names |= {ov.trigger_pv for ov in self.overrides}
        return names

    def manipulated_variables(self) -> set[str]:
        names = {loop.mv for loop in self.feed_loops}
        names |= {self.reactor_temperature.drives, self.separator_temperature.drives}
        names |= set(self.nominal.static_mv)
        names |= {ov.target for ov in self.overrides if ov.target != "production_index"}
        return names
