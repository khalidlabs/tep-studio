"""Excitation-signal design for system identification (APC-commissioning datasets).

A small, dependency-light (numpy only) library of the standard input-design signals
used to identify dynamic models of a plant — steps, PRBS, GBN, APRBS, multisine, and
chirp — plus helpers that turn an :class:`ExcitationSpec` into the time-varying input
the runner already accepts (a setpoint schedule for closed-loop tests, or a 12-MV
action function for short open-loop tests), and an excitation-quality report
(persistency-of-excitation order, regressor condition number, per-channel power).

Because the TEP is open-loop unstable, closed-loop *setpoint* excitation is the safe,
primary mode; open-loop MV excitation is only sound for short, small bumps. Signals are
deterministic given a seed, and each channel gets an independent stream so a multi-input
campaign is decorrelated by construction.
"""

from __future__ import annotations

import dataclasses as dc
import hashlib
import math
from dataclasses import dataclass

import numpy as np

from tep_studio.control.controller import ControllerSetpoints

# Shared per-setpoint (low, high) operating bounds — also used by the gym env. Excitation
# on a setpoint is clipped to these so a test never drives a target out of its safe range.
SETPOINT_ACTION_BOUNDS: dict[str, tuple[float, float]] = {
    "production_rate": (10.0, 40.0),
    "pct_g": (5.0, 95.0),
    "reactor_pressure": (2700.0, 2900.0),
    "reactor_level": (30.0, 90.0),
    "reactor_temperature": (115.0, 135.0),
    "separator_level": (30.0, 90.0),
    "stripper_level": (30.0, 90.0),
    "ya": (50.0, 70.0),
    "yac": (40.0, 65.0),
}

SIGNAL_TYPES = ("step", "prbs", "gbn", "aprbs", "multisine", "chirp")


@dataclass(frozen=True)
class ExcitationSignal:
    """One excitation applied to a single target (an MV name or a setpoint field)."""

    target: str
    signal: str = "prbs"  # one of SIGNAL_TYPES
    amplitude: float = 0.0  # peak deviation from the baseline (half-range for two-level signals)
    start_time: float = 0.0  # h
    end_time: float | None = None  # h; None -> run to the end
    clock: float = 0.5  # h; hold/switch period for step/prbs/gbn/aprbs
    switch_prob: float = 0.5  # GBN per-clock switch probability (< 0.5 emphasises low frequencies)
    f_low: float = 0.05  # 1/h; multisine/chirp band
    f_high: float = 2.0  # 1/h
    n_tones: int = 8  # multisine
    seed: int | None = None  # per-signal seed; None -> derived from the spec master seed


@dataclass(frozen=True)
class ExcitationSpec:
    """A system-identification excitation: a set of per-target signals applied either to
    the manipulated variables (``kind="mv"``, open loop) or the controller setpoints
    (``kind="setpoint"``, closed loop)."""

    kind: str = "setpoint"  # "mv" | "setpoint"
    signals: tuple[ExcitationSignal, ...] = ()
    seed: int = 0  # master seed; per-signal stream = seed unless a signal sets its own

    def to_dict(self) -> dict:
        return {"kind": self.kind, "seed": self.seed, "signals": [dc.asdict(s) for s in self.signals]}

    @classmethod
    def from_dict(cls, d: dict) -> "ExcitationSpec":
        return cls(
            kind=d.get("kind", "setpoint"),
            seed=int(d.get("seed", 0)),
            signals=tuple(ExcitationSignal(**s) for s in d.get("signals", [])),
        )


# -- deterministic signal generation ---------------------------------------
def _stream_seed(master: int, sig: ExcitationSignal) -> int:
    if sig.seed is not None:
        return int(sig.seed)
    digest = hashlib.sha256(f"{master}:{sig.target}:{sig.signal}".encode()).hexdigest()
    return int(digest[:8], 16)


def _prbs_levels(n: int, rng: np.random.Generator) -> np.ndarray:
    """A maximal-length LFSR sequence (period 1023) mapped to +/-1, length n."""
    taps = (10, 7)  # maximal taps for a 10-bit register
    state = int(rng.integers(1, 1 << 10))  # nonzero seed
    out = np.empty(n, dtype=float)
    for i in range(n):
        bit = state & 1
        out[i] = 1.0 if bit else -1.0
        feedback = 0
        for t in taps:
            feedback ^= (state >> (t - 1)) & 1
        state = (state >> 1) | (feedback << 9)
    return out


def _clocked(times: np.ndarray, start: float, clock: float, levels_fn) -> np.ndarray:
    """Sample a per-clock level sequence (from ``levels_fn(n_clocks)``) onto ``times``."""
    span = max(times[-1] - start, 0.0)
    n_clocks = int(math.floor(span / clock)) + 2
    levels = levels_fn(n_clocks)
    idx = np.floor((times - start) / clock).astype(int)
    idx = np.clip(idx, 0, len(levels) - 1)
    return levels[idx]


def signal_series(sig: ExcitationSignal, times: np.ndarray, master_seed: int) -> np.ndarray:
    """The deviation-from-baseline series for ``sig`` over absolute ``times`` (hours)."""
    times = np.asarray(times, dtype=float)
    rng = np.random.default_rng(_stream_seed(master_seed, sig))
    a = float(sig.amplitude)
    dev = np.zeros_like(times)
    active = times >= sig.start_time
    if sig.end_time is not None:
        active &= times < sig.end_time
    if not active.any() or a == 0.0:
        return dev

    kind = sig.signal
    if kind == "step":
        dev[active] = a
    elif kind == "prbs":
        dev = a * _clocked(times, sig.start_time, sig.clock, lambda n: _prbs_levels(n, rng))
    elif kind == "gbn":
        def gbn(n: int) -> np.ndarray:
            lvl = np.empty(n); cur = 1.0
            for i in range(n):
                if rng.random() < sig.switch_prob:
                    cur = -cur
                lvl[i] = cur
            return lvl
        dev = a * _clocked(times, sig.start_time, sig.clock, gbn)
    elif kind == "aprbs":  # amplitude-modulated: a fresh random level each hold (nonlinear ID)
        dev = a * _clocked(times, sig.start_time, sig.clock, lambda n: rng.uniform(-1.0, 1.0, size=n))
    elif kind == "multisine":
        freqs = np.linspace(sig.f_low, sig.f_high, max(1, sig.n_tones))
        k = np.arange(1, len(freqs) + 1)
        phases = -math.pi * k * (k - 1) / len(freqs)  # Schroeder phasing -> low crest factor
        tau = times - sig.start_time
        s = np.sum([np.sin(2 * math.pi * f * tau + p) for f, p in zip(freqs, phases)], axis=0)
        peak = np.max(np.abs(s)) or 1.0
        dev = a * (s / peak)
    elif kind == "chirp":
        end = sig.end_time if sig.end_time is not None else times[-1]
        dur = max(end - sig.start_time, 1e-9)
        tau = np.clip(times - sig.start_time, 0.0, dur)
        inst = sig.f_low + (sig.f_high - sig.f_low) * tau / (2 * dur)  # linear sweep
        dev = a * np.sin(2 * math.pi * inst * tau)
    else:
        raise ValueError(f"unknown excitation signal {kind!r}; expected one of {SIGNAL_TYPES}")

    dev = np.where(active, dev, 0.0)
    return dev


# -- schedules the runner consumes -----------------------------------------
def _grid(horizon: float, dt: float) -> np.ndarray:
    n = int(round(horizon / dt)) + 1
    return np.arange(n) * dt


def build_setpoint_schedule(spec: ExcitationSpec, base: ControllerSetpoints, *, horizon: float, dt: float):
    """A ``time -> ControllerSetpoints`` schedule: each signal perturbs its setpoint field,
    clipped to its safe operating bound."""
    times = _grid(horizon, dt)
    series = {s.target: signal_series(s, times, spec.seed) for s in spec.signals}

    def schedule(t: float) -> ControllerSetpoints:
        i = min(len(times) - 1, max(0, int(round(t / dt))))
        updates = {}
        for target, dev in series.items():
            lo, hi = SETPOINT_ACTION_BOUNDS.get(target, (-math.inf, math.inf))
            updates[target] = float(np.clip(getattr(base, target) + dev[i], lo, hi))
        return dc.replace(base, **updates)

    return schedule


def build_mv_action_fn(spec: ExcitationSpec, base_mv: np.ndarray, *, horizon: float, dt: float, schema):
    """A ``time -> 12-MV vector`` action function (open loop), each MV clipped to [0, 100]."""
    times = _grid(horizon, dt)
    base_mv = np.asarray(base_mv, dtype=float)
    idx_series = [(schema.index("manipulated_variables", s.target), signal_series(s, times, spec.seed)) for s in spec.signals]

    def action(t: float) -> np.ndarray:
        i = min(len(times) - 1, max(0, int(round(t / dt))))
        vec = base_mv.copy()
        for j, dev in idx_series:
            vec[j] = vec[j] + dev[i]
        return np.clip(vec, 0.0, 100.0)

    return action


# -- excitation quality (no model fitting) ---------------------------------
def excitation_input_matrix(spec: ExcitationSpec, *, horizon: float, dt: float) -> tuple[list[str], np.ndarray]:
    """The (n_samples x n_channels) matrix of excitation deviations, for diagnostics."""
    times = _grid(horizon, dt)
    cols = [s.target for s in spec.signals]
    mat = np.stack([signal_series(s, times, spec.seed) for s in spec.signals], axis=1) if spec.signals else np.zeros((len(times), 0))
    return cols, mat


def excitation_quality(spec: ExcitationSpec, *, horizon: float, dt: float, max_lag: int = 20) -> dict:
    """An excitation-quality report: persistency-of-excitation order, regressor condition
    number, and per-channel RMS / dominant frequency. Diagnostics only — no model fitting."""
    cols, u = excitation_input_matrix(spec, horizon=horizon, dt=dt)
    n, m = u.shape
    report: dict = {"n_samples": int(n), "n_channels": int(m), "channels": []}
    if m == 0 or n < 4:
        report.update(pe_order=0, condition_number=float("inf"))
        return report

    uc = u - u.mean(axis=0, keepdims=True)
    lag = int(min(max_lag, (n - 1) // (m + 1)))
    lag = max(lag, 1)
    # Block-Hankel regressor over `lag` lags; PE order = # singular values above tolerance.
    blocks = [uc[i: n - lag + i] for i in range(lag)]
    phi = np.concatenate(blocks, axis=1)  # (n-lag) x (lag*m)
    sv = np.linalg.svd(phi, compute_uv=False)
    tol = sv[0] * 1e-6 if sv.size else 0.0
    rank = int(np.sum(sv > tol))
    report["pe_order"] = int(rank // m) if m else 0
    report["condition_number"] = float(sv[0] / sv[-1]) if sv.size and sv[-1] > 0 else float("inf")
    report["regressor_rank"] = rank
    freqs = np.fft.rfftfreq(n, d=dt)
    for j, name in enumerate(cols):
        spec_j = np.abs(np.fft.rfft(uc[:, j]))
        dom = float(freqs[int(np.argmax(spec_j))]) if spec_j.size else 0.0
        report["channels"].append({"target": name, "rms": float(np.sqrt(np.mean(uc[:, j] ** 2))), "dominant_freq_per_h": dom})
    return report
