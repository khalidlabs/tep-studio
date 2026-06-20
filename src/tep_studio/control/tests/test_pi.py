from __future__ import annotations

import pytest

from tep_studio.control.pi import DiscretePI, VelocityPI


def test_discrete_pi_exact_recursion() -> None:
    # de = kc*(e - e_prev + (dt/ti)*e); dt == ts == 0.1 each fired step.
    pi = DiscretePI(kc=2.0, ti_hours=0.5, ts_hours=0.1)
    state = pi.initial_state(10.0, time=0.0)
    outputs = []
    for t, (sp, pv) in zip([0.0, 0.1, 0.2], [(5.0, 3.0), (5.0, 4.0), (5.0, 5.0)]):
        out, state = pi.update(state, sp, pv, t)
        outputs.append(out)
    assert outputs == pytest.approx([14.8, 13.2, 11.2], abs=1e-12)


def test_velocity_pi_exact_recursion() -> None:
    pi = VelocityPI(kc=2.0, ti_hours=0.5, ts_hours=0.1)
    state = pi.initial_state(time=0.0)
    deltas = []
    for t, (sp, pv) in zip([0.0, 0.1], [(5.0, 3.0), (5.0, 4.0)]):
        delta, state = pi.update(state, sp, pv, t)
        deltas.append(delta)
    assert deltas == pytest.approx([4.8, -1.6], abs=1e-12)


def test_discrete_pi_anti_windup_releases_immediately() -> None:
    # Saturated-state memory means the loop cannot wind up past its limit and
    # leaves the limit on the very next sample once the error reverses.
    pi = DiscretePI(kc=1.0, ti_hours=1.0, ts_hours=1.0, hi=10.0, lo=0.0)
    state = pi.initial_state(9.0, time=0.0)
    out, state = pi.update(state, 100.0, 0.0, 0.0)
    assert out == 10.0  # clamped high
    out, state = pi.update(state, 100.0, 0.0, 1.0)
    assert out == 10.0  # still saturated, no accumulation beyond the limit
    out, state = pi.update(state, 0.0, 0.0, 2.0)
    assert out == 0.0  # error reversed -> releases at once (no wind-up lag)


def test_discrete_pi_bumpless_zero_error() -> None:
    pi = DiscretePI(kc=5.0, ti_hours=0.25, ts_hours=0.1)
    state = pi.initial_state(50.0, time=0.0)
    out, _ = pi.update(state, 20.0, 20.0, 0.0)  # setpoint == measurement
    assert out == 50.0  # first action equals the seeded output: no startup bump


def test_sample_hold_between_periods() -> None:
    pi = DiscretePI(kc=1.0, ti_hours=1.0, ts_hours=0.1)
    state = pi.initial_state(0.0, time=0.0)
    fired0, state = pi.update(state, 1.0, 0.0, 0.0)  # fires at t=0
    held, held_state = pi.update(state, 1.0, 0.0, 0.05)  # between samples -> hold
    assert held == fired0
    assert held_state is state  # state untouched between samples
    fired1, state = pi.update(state, 1.0, 0.0, 0.1)  # fires at t=0.1
    assert fired1 != fired0
