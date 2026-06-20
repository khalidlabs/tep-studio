"""Decentralized multiloop PI controller for the modified TEP (Ricker 1996).

The controller is a thin, explicit interpreter of :data:`RICKER_MODE1`. It consumes
ONLY published measurements -- never the simulator's internal 50-state vector -- so
the controller/plant boundary is a property of the type signature (principle P5,
no model leakage). :meth:`compute_action` returns the 12 manipulated variables ready
for ``TennesseeEastmanProcess.advance(action, action_level="direct_mv")``.

Bring-up is incremental: ``enable_composition`` and ``enable_overrides`` gate the
slow composition trims and the constraint overrides so the core regulatory loops
(inventory, pressure, temperature) can be validated on their own first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import ArrayLike

from tep_studio.control.loops import OverrideSpec, PILoopSpec, RatioLoopSpec
from tep_studio.control.pi import DiscretePI, PIState, VelocityPI
from tep_studio.control.registry import RICKER_MODE1, RickerRegistry
from tep_studio.simulation.schema import TEP_SCHEMA, ProcessSchema


@dataclass(frozen=True)
class ControllerSetpoints:
    """Operator targets for the regulatory loops (defaults seeded from the Mode-1 state)."""

    reactor_level: float
    reactor_pressure: float
    reactor_temperature: float
    separator_level: float
    stripper_level: float
    pct_g: float
    production_rate: float
    ya: float
    yac: float


@dataclass(frozen=True)
class ControlStepDiagnostics:
    """Auditable per-step record (feeds principles P3/P6)."""

    fp: float
    ratios: dict[str, float]
    setpoints: dict[str, float]
    loop_outputs: dict[str, float]
    overrides_active: dict[str, bool] = field(default_factory=dict)


def _yA(measurements: np.ndarray, a_idx: int, c_idx: int) -> float:
    a = float(measurements[a_idx])
    c = float(measurements[c_idx])
    total = a + c
    return 100.0 * a / total if total != 0.0 else 0.0


@runtime_checkable
class Controller(Protocol):
    """Structural interface a controller must satisfy to drive ``ClosedLoopSimulation``.

    Bring your own control law (LQR, MPC, a learned policy) without subclassing: any
    object exposing a mutable ``setpoints`` plus ``reset`` and ``compute_action`` works.
    ``compute_action`` must read only the 41 measurements (never the plant state),
    preserving the controller/plant boundary, and return ``(action[12], diagnostics)``.
    See ``control/examples/custom_controller.py`` for a worked example.
    """

    setpoints: ControllerSetpoints | None

    def reset(self, measurements: ArrayLike, *, time: float = 0.0) -> None: ...

    def compute_action(self, measurements: ArrayLike, *, time: float) -> tuple[np.ndarray, ControlStepDiagnostics]: ...


class RickerMultiLoopController:
    """Decentralized PI controller producing the 12 TEP manipulated variables."""

    def __init__(
        self,
        *,
        schema: ProcessSchema = TEP_SCHEMA,
        registry: RickerRegistry = RICKER_MODE1,
        setpoints: ControllerSetpoints | None = None,
        enable_composition: bool = True,
        enable_pct_g_feedback: bool = False,
        enable_overrides: bool = False,
    ) -> None:
        self.schema = schema
        self.registry = registry
        self.setpoints = setpoints
        self.enable_composition = enable_composition
        # The %G->Eadj feedback (and its x32/x46xFp feedforward) was tuned for the
        # ORIGINAL TEP (temex.c). This port wraps the MODIFIED TEP (temexd_mod.c),
        # whose composition dynamics differ, so the loop needs retuning before use;
        # it is off by default. The stable yA/yAC reactant trims stay on.
        self.enable_pct_g_feedback = enable_pct_g_feedback
        self.enable_overrides = enable_overrides

        # Build immutable PI primitives once.
        self._feed_pi: dict[str, DiscretePI] = {
            loop.name: DiscretePI(loop.kc, loop.ti_hours, loop.ts_hours, loop.hi, loop.lo)
            for loop in registry.feed_loops
        }
        self._pi: dict[str, DiscretePI] = {
            loop.name: DiscretePI(loop.kc, loop.ti_hours, loop.ts_hours, loop.hi, loop.lo)
            for loop in self._positional_pi_loops()
        }
        self._ya = VelocityPI(registry.ya.kc, registry.ya.ti_hours, registry.ya.ts_hours)
        self._yac = VelocityPI(registry.yac.kc, registry.yac.ti_hours, registry.yac.ts_hours)

        # Index maps (name -> array position), resolved once.
        self._mi = {name: schema.index("measurements", name) for name in self._measurement_names()}
        self._vi = {name: schema.index("manipulated_variables", name) for name in schema.names("manipulated_variables")}
        self._a_idx = schema.index("measurements", "reactor_feed_A_concentration")
        self._c_idx = schema.index("measurements", "reactor_feed_C_concentration")

        # Mutable state (populated by reset()).
        self._state: dict[str, PIState] = {}
        self._r1 = registry.nominal.ratios["r1"]
        self._r4 = registry.nominal.ratios["r4"]
        self._fp = registry.nominal.fp_base
        self._time = 0.0
        self._initialized = False

    # -- public API --------------------------------------------------------
    def reset(self, measurements: ArrayLike, *, time: float = 0.0) -> None:
        """Seed every loop for a bumpless start from the current measurements."""
        meas = np.asarray(measurements, dtype=np.float64)
        nominal = self.registry.nominal
        if self.setpoints is None:
            self.setpoints = self._default_setpoints(meas)

        for loop in self.registry.feed_loops:
            self._state[loop.name] = self._feed_pi[loop.name].initial_state(loop.x0, time=time)
        for loop in self._positional_pi_loops():
            self._state[loop.name] = self._pi[loop.name].initial_state(loop.x0, time=time)
        self._state[self.registry.ya.name] = self._ya.initial_state(time=time)
        self._state[self.registry.yac.name] = self._yac.initial_state(time=time)

        self._r1 = nominal.ratios["r1"]
        self._r4 = nominal.ratios["r4"]
        self._fp = nominal.fp_base
        # Ramped (rate-limited) production and %G setpoints, seeded bumplessly from the
        # current measurements. The decentralized strategy moves these slow, feed-driven
        # targets gradually (not in steps); ramping them avoids the large transients that
        # otherwise trip the plant on an operating-point change.
        self._ramped_production = float(meas[self._mi["stripper_underflow"]])
        self._ramped_pct_g = float(meas[self._mi["stripper_underflow_G_concentration"]])
        self._ramp_time = float(time)
        self._initialized = True

    @staticmethod
    def _ramp(current: float, target: float, rate: float, dt: float) -> float:
        """Move ``current`` toward ``target`` by at most ``rate * dt`` (units per hour)."""
        step = abs(rate) * dt
        if target >= current:
            return min(target, current + step)
        return max(target, current - step)

    def compute_action(self, measurements: ArrayLike, *, time: float) -> tuple[np.ndarray, ControlStepDiagnostics]:
        """Map the current measurements to the 12 manipulated variables.

        Args:
            measurements: the 41 published measurements. The controller reads ONLY these
                — never the plant state — so the controller/plant boundary holds (P5).
            time: current simulation time in **hours** (drives the discrete-PI sampling).

        Returns:
            ``(action, diagnostics)``: ``action`` is the 12-element MV vector clamped to
            ``[0, 100]`` for ``advance(action_level="direct_mv")``; ``diagnostics`` is a
            :class:`ControlStepDiagnostics` snapshot (Fp, ratios, setpoints, loop outputs,
            active overrides) for auditing.
        """
        if not self._initialized:
            raise RuntimeError("Call reset(measurements) before compute_action().")
        meas = np.asarray(measurements, dtype=np.float64)
        self._time = float(time)
        sp = self.setpoints
        nominal = self.registry.nominal
        reg = self.registry
        outputs: dict[str, float] = {}
        overrides_active: dict[str, bool] = {}

        # 0. Rate-limit the slow production and %G setpoints toward their targets so an
        # operating-point change is a gradual transition rather than a step.
        dt = max(0.0, self._time - self._ramp_time)
        self._ramp_time = self._time
        self._ramped_production = self._ramp(self._ramped_production, sp.production_rate, nominal.production_sp_rate_limit, dt)
        self._ramped_pct_g = self._ramp(self._ramped_pct_g, sp.pct_g, nominal.pct_g_sp_rate_limit, dt)

        # 1. Production index Fp = base + feedback adjustment (slow outer trim).
        fp_adj = self._update(reg.production, self._ramped_production, meas)
        fp = nominal.fp_base + fp_adj
        if self.enable_overrides:
            fp, overrides_active = self._apply_pressure_override(fp, meas, overrides_active)
        self._fp = fp

        # 2. Composition feedforward + feedback (-> feed ratios r1..r4).
        if self.enable_composition:
            eadj = self._update(reg.pct_g, self._ramped_pct_g, meas) if self.enable_pct_g_feedback else nominal.eadj0
            r2 = float(np.polyval(nominal.p2_coeffs, self._ramped_pct_g)) - nominal.ff_gain_d * eadj * fp
            r3 = float(np.polyval(nominal.p3_coeffs, self._ramped_pct_g)) + nominal.ff_gain_e * eadj * fp
            ya = _yA(meas, self._a_idx, self._c_idx)
            yac = float(meas[self._a_idx]) + float(meas[self._c_idx])
            d_ya = self._update_velocity(reg.ya, sp.ya, ya)
            d_yac = self._update_velocity(reg.yac, sp.yac, yac)
            self._r1 += d_ya
            self._r4 += d_yac - d_ya
            outputs["Eadj"] = eadj
        else:
            r2 = nominal.ratios["r2"]
            r3 = nominal.ratios["r3"]
        r1, r4 = self._r1, self._r4

        # 3. Inventory outer cascade + level->ratio loops.
        sep_temp_sp = self._update(reg.reactor_level, sp.reactor_level, meas)
        r6 = self._update(reg.separator_level, sp.separator_level, meas)
        r7 = self._update(reg.stripper_level, sp.stripper_level, meas)

        # 4. Reactor pressure -> purge ratio.
        r5 = self._update(reg.reactor_pressure, sp.reactor_pressure, meas)

        # 5. Inventory inner (separator temperature, setpoint from reactor-level loop) + reactor temperature.
        xmv_condenser = self._update(reg.separator_temperature, sep_temp_sp, meas)
        xmv_reactor_cool = self._update(reg.reactor_temperature, sp.reactor_temperature, meas)

        # 6. Fast feed/flow ratio loops: setpoint = ratio * Fp.
        ratios = {"r1": r1, "r2": r2, "r3": r3, "r4": r4, "r5": r5, "r6": r6, "r7": r7}
        action = np.zeros(12, dtype=np.float64)
        for loop in reg.feed_loops:
            setpoint = ratios[loop.ratio_key] * fp
            value = self._update_ratio(loop, setpoint, meas)
            action[self._vi[loop.mv]] = value
            outputs[loop.mv] = value

        action[self._vi[reg.reactor_temperature.drives]] = xmv_reactor_cool
        action[self._vi[reg.separator_temperature.drives]] = xmv_condenser
        outputs[reg.reactor_temperature.drives] = xmv_reactor_cool
        outputs[reg.separator_temperature.drives] = xmv_condenser

        # 7. Static MVs (held at nominal in Mode 1), then the high-level override.
        for name, value in nominal.static_mv.items():
            action[self._vi[name]] = value
        if self.enable_overrides:
            action, overrides_active = self._apply_level_override(action, meas, overrides_active)

        np.clip(action, 0.0, 100.0, out=action)

        diagnostics = ControlStepDiagnostics(
            fp=fp,
            ratios=ratios,
            setpoints=self._setpoint_dict(sep_temp_sp),
            loop_outputs=outputs,
            overrides_active=overrides_active,
        )
        return action, diagnostics

    # -- internals ---------------------------------------------------------
    def _positional_pi_loops(self) -> tuple[PILoopSpec, ...]:
        reg = self.registry
        return (
            reg.production,
            reg.reactor_level,
            reg.reactor_pressure,
            reg.reactor_temperature,
            reg.separator_level,
            reg.separator_temperature,
            reg.stripper_level,
            reg.pct_g,
        )

    def _measurement_names(self) -> set[str]:
        names = set(self.registry.measurement_pvs())
        names |= {"reactor_feed_A_concentration", "reactor_feed_C_concentration"}
        return names

    def _update(self, loop: PILoopSpec, setpoint: float, meas: np.ndarray) -> float:
        pi = self._pi[loop.name]
        value, self._state[loop.name] = pi.update(self._state[loop.name], setpoint, float(meas[self._mi[loop.pv]]), self._time)
        return value

    def _update_ratio(self, loop: RatioLoopSpec, setpoint: float, meas: np.ndarray) -> float:
        pi = self._feed_pi[loop.name]
        value, self._state[loop.name] = pi.update(self._state[loop.name], setpoint, float(meas[self._mi[loop.pv]]), self._time)
        return value

    def _update_velocity(self, loop: PILoopSpec, setpoint: float, measurement: float) -> float:
        pi = self._ya if loop.name == self.registry.ya.name else self._yac
        delta, self._state[loop.name] = pi.update(self._state[loop.name], setpoint, measurement, self._time)
        return delta

    def _apply_pressure_override(self, fp: float, meas: np.ndarray, active: dict[str, bool]) -> tuple[float, dict[str, bool]]:
        ov = self._override("high_pressure_to_production")
        if ov is None or not ov.enabled or ov.threshold is None or ov.gain is None:
            return fp, active
        excess = float(meas[self._mi[ov.trigger_pv]]) - ov.threshold
        correction = min(0.0, -ov.gain * max(0.0, excess))
        active[ov.name] = excess > 0.0
        return fp + correction, active

    def _apply_level_override(self, action: np.ndarray, meas: np.ndarray, active: dict[str, bool]) -> tuple[np.ndarray, dict[str, bool]]:
        ov = self._override("high_level_to_recycle")
        if ov is None or not ov.enabled or ov.threshold is None or ov.gain is None:
            return action, active
        excess = float(meas[self._mi[ov.trigger_pv]]) - ov.threshold
        correction = ov.gain * max(0.0, excess)
        idx = self._vi[ov.target]
        action[idx] = action[idx] - correction
        active[ov.name] = excess > 0.0
        return action, active

    def _override(self, name: str) -> OverrideSpec | None:
        for ov in self.registry.overrides:
            if ov.name == name:
                return ov
        return None

    def _default_setpoints(self, meas: np.ndarray) -> ControllerSetpoints:
        m = self._mi
        return ControllerSetpoints(
            reactor_level=float(meas[m["reactor_level"]]),
            reactor_pressure=float(meas[m["reactor_pressure"]]),
            reactor_temperature=float(meas[m["reactor_temperature"]]),
            separator_level=float(meas[m["separator_level"]]),
            stripper_level=float(meas[m["stripper_level"]]),
            pct_g=float(meas[m["stripper_underflow_G_concentration"]]),
            production_rate=float(meas[m["stripper_underflow"]]),
            ya=_yA(meas, self._a_idx, self._c_idx),
            yac=float(meas[self._a_idx]) + float(meas[self._c_idx]),
        )

    def _setpoint_dict(self, sep_temp_sp: float) -> dict[str, float]:
        sp = self.setpoints
        return {
            "reactor_level": sp.reactor_level,
            "reactor_pressure": sp.reactor_pressure,
            "reactor_temperature": sp.reactor_temperature,
            "separator_level": sp.separator_level,
            "separator_temperature": sep_temp_sp,  # cascade setpoint from the reactor-level loop
            "stripper_level": sp.stripper_level,
            "pct_g": sp.pct_g,
            "production_rate": sp.production_rate,
        }

