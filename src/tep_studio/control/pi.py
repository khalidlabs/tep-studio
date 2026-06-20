"""Discrete PI controller primitives for the decentralized TEP control strategy.

These reproduce the two controller blocks in Ricker's ``TElib.mdl``:

* :class:`DiscretePI` -- the positional "Discrete PI" block. Its integral memory
  is the *saturated* previous output, which gives clamp-type anti-windup for free:
  the accumulator can never travel past ``[lo, hi]``.
* :class:`VelocityPI` -- the inner "Vel PI" block. It returns only the per-sample
  *increment* (delta); the composition loops add that delta onto a ratio signal.

Both use the velocity form ``de = Kc * (e - e_prev + (dt / Ti) * e)`` with
``e = setpoint - measurement``. Ricker samples every loop at a fixed period and
uses that period in the integral term. Here we use the *actual* elapsed time
``dt`` since the loop last fired, so the controller degrades gracefully when the
closed-loop runner uses a control interval coarser than ``Ts_base`` (at
``control_interval == ts`` the two are identical). ``Ti``/``ts`` are in HOURS,
matching ``Mode_1_Init.m`` (every reset time is written ``minutes/60``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Tolerance (hours) when deciding whether a loop's sample period has elapsed.
_SAMPLE_EPS = 1e-9


def _clip(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


@dataclass(frozen=True)
class PIState:
    """Immutable controller memory.

    ``output`` is the last *saturated* absolute output (the integral memory for a
    positional loop; unused/zero for a pure velocity loop). ``prev_error`` is the
    error at the last fired sample. ``last_update_time`` is the time (hours) of the
    last fired sample; it is primed to ``time0 - ts`` so the first call fires with
    ``dt == ts``.
    """

    output: float
    prev_error: float
    last_update_time: float


@dataclass(frozen=True)
class DiscretePI:
    """Positional discrete PI with saturated-state anti-windup (TElib form)."""

    kc: float
    ti_hours: float
    ts_hours: float
    hi: float = math.inf
    lo: float = -math.inf

    def initial_state(self, x0: float, *, prev_error: float = 0.0, time: float = 0.0) -> PIState:
        """Seed the integral memory to ``x0`` (bumpless start at a known output)."""
        return PIState(
            output=_clip(float(x0), self.lo, self.hi),
            prev_error=float(prev_error),
            last_update_time=float(time) - self.ts_hours,
        )

    def due(self, state: PIState, time: float) -> bool:
        return time - state.last_update_time >= self.ts_hours - _SAMPLE_EPS

    def update(self, state: PIState, setpoint: float, measurement: float, time: float) -> tuple[float, PIState]:
        """Return ``(output, new_state)``; holds the previous output between samples."""
        if not self.due(state, time):
            return state.output, state
        dt = time - state.last_update_time
        error = float(setpoint) - float(measurement)
        delta = self.kc * (error - state.prev_error + (dt / self.ti_hours) * error)
        output = _clip(state.output + delta, self.lo, self.hi)
        return output, PIState(output=output, prev_error=error, last_update_time=float(time))


@dataclass(frozen=True)
class VelocityPI:
    """Pure velocity PI: returns the per-sample increment (no saturation, no bias)."""

    kc: float
    ti_hours: float
    ts_hours: float

    def initial_state(self, *, prev_error: float = 0.0, time: float = 0.0) -> PIState:
        return PIState(output=0.0, prev_error=float(prev_error), last_update_time=float(time) - self.ts_hours)

    def due(self, state: PIState, time: float) -> bool:
        return time - state.last_update_time >= self.ts_hours - _SAMPLE_EPS

    def update(self, state: PIState, setpoint: float, measurement: float, time: float) -> tuple[float, PIState]:
        """Return ``(delta, new_state)``; delta is 0.0 between samples."""
        if not self.due(state, time):
            return 0.0, state
        dt = time - state.last_update_time
        error = float(setpoint) - float(measurement)
        delta = self.kc * (error - state.prev_error + (dt / self.ti_hours) * error)
        return delta, PIState(output=0.0, prev_error=error, last_update_time=float(time))
