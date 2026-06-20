# Comparison with Other TEP Implementations

TEP Studio is one of several open Python interfaces to the Tennessee Eastman
Process. The most directly comparable project is
[`jkitchin/tennessee-eastman-profbraatz`](https://github.com/jkitchin/tennessee-eastman-profbraatz),
which — like TEP Studio — is a Claude-assisted Python wrapper around the
original simulation code. This page records how the two differ in model
variant, backend design, integration method, and measured performance, so users
can choose the right tool and so the design decisions behind TEP Studio are on
the record.

The two projects solve adjacent problems on **different model variants**, and
the comparison is meant to be factual rather than promotional. Where the
reference implementation is the better fit, this page says so.

## 1. Model variant and provenance

| | **TEP Studio** | **jkitchin/tennessee-eastman-profbraatz** |
| --- | --- | --- |
| Numerical source of truth | Modified TEP C kernel `temexd_mod.c` (Bathelt, Ricker & Jelali, 2015 revision) | Original Fortran 77 `teprob.f` (Downs & Vogel, 1993; closed-loop additions by Russell, Chiang & Braatz) |
| Disturbances (IDV) | 28 | 20 |
| Manipulated variables | 12 | 12 |
| Published measurements | 41 | 41 |
| Focus | Schema-driven domain model for control, RL, data, and optimization workflows | Fault detection (PCA/PLS/FDA/CVA) and benchmark dataset reproduction |

The two implement **different revisions of the model**. Numerical trajectories
are not expected to match between them, and direct numeric cross-validation is
not meaningful. TEP Studio targets the revised (Ricker/Jelali) process; the
reference targets the classic 1993 process as distributed by the Braatz group.

## 2. Backend architecture

**TEP Studio — single source of truth.** The modified C kernel is compiled into
a single `abi3` native extension via CFFI. There is exactly one numerical
implementation. Prebuilt wheels deliver the compiled kernel without requiring a
C compiler on the user's machine.

**Reference — dual backend.** The project ships two backends:

- a **Fortran** backend (`teprob.f` via f2py), numerically exact to the 1993
  model but requiring a Fortran toolchain to build; and
- a **pure-Python** reimplementation of `teprob.f`, which runs anywhere with no
  compiler.

The dual-backend design trades a second implementation for zero-dependency
portability. The reference project's own validation notes that the pure-Python
backend is *statistically similar but not identical* to the Fortran reference —
in particular the long-run variance differs (the Python fork damps the
limit-cycle dynamics). TEP Studio avoids that drift by keeping a single kernel.

!!! note "Out-of-the-box backend"
    A default `pip install -e .` of the reference repository builds only the
    pure-Python backend; the Fortran extension requires a separate, toolchain-
    dependent build step. Most users therefore run the slower Python path unless
    they explicitly build the Fortran module.

## 3. Integration method

| | Integrator | Order | Step | Adaptive |
| --- | --- | --- | --- | --- |
| **TEP Studio** (default) | RK4, in-process fixed step | 4th | `fixed_step = 0.0005 h` | No |
| **TEP Studio** (option) | Euler, in-process fixed step | 1st | configurable | No |
| **TEP Studio** (option) | RK45 / RK23 via SciPy `solve_ivp` | 4th–5th / 2nd–3rd | adaptive | Yes |
| **Reference** (both backends) | Forward Euler | 1st | fixed 1 s (`1/3600 h`) | No |

The reference implementation integrates with forward Euler in Python in **both**
backends; the Fortran/Python kernel only supplies the derivative (`TEFUNC`/
`tefunc`). TEP Studio defaults to a 4th-order RK4 fixed-step loop and
additionally exposes adaptive SciPy solvers for stiff regions. RK4's higher
order lets it take larger steps than Euler at a given accuracy, which is why the
default path is both faster and more accurate than a first-order Euler loop.

## 4. Performance

Benchmark: wall-clock time to simulate **one process-hour** from the Mode-1
steady state, fixed manipulated variables, IDV = 0. Measured on Apple Silicon,
Python 3.10, single process. The reference Fortran backend was hand-built with
f2py for this comparison.

| Path | Time / sim-hour | Throughput |
| --- | --- | --- |
| TEP Studio — Euler (fixed-step) | **8 ms** | ~125 sim-h/s |
| TEP Studio — RK4 (default) | **21 ms** | ~47 sim-h/s |
| TEP Studio — RK23 | 26 ms | ~38 sim-h/s |
| Reference — Fortran (f2py, Euler 1 s) | 44 ms | ~23 sim-h/s |
| TEP Studio — RK45 (adaptive) | 185 ms | ~5 sim-h/s |
| Reference — pure-Python (default, Euler 1 s) | 1434 ms | ~0.7 sim-h/s |

The compiled kernels are comparable at the level of a single derivative
evaluation (~0.5–0.9 µs/call). The end-to-end differences come from binding
overhead and integrator choice: the CFFI path writes into preallocated buffers,
whereas f2py marshals arrays on every call. TEP Studio's RK4 default simulates a
process-hour in roughly **half the time** of the reference Fortran backend and
about **65× faster** than the reference's default pure-Python path, while using
a higher-order integrator.

!!! warning "Benchmark caveats"
    The two projects integrate **different model variants**, so this measures
    realized simulation speed for each tool as shipped, not identical numerical
    work. Absolute numbers are machine-dependent; the ranking
    (pure-Python ≪ Fortran-f2py < CFFI/C kernel, with adaptive RK45 trading
    speed for robustness) is stable across runs.

## 5. Capability summary

| Capability | TEP Studio | Reference |
| --- | --- | --- |
| Machine-readable process schema | Yes | No |
| Gymnasium RL environment | Yes | No |
| Optimization adapter (rollout, finite-difference, linearization) | Yes | No |
| Full-state snapshot / restore (for MHE, MPC, RL resets) | Yes | No |
| Decentralized PI closed-loop control | Yes | Yes |
| Fault-detection framework (PCA/EWMA/CUSUM/voting) | No | Yes |
| Dual Fortran/pure-Python backend | No | Yes |
| Zero-compiler pure-Python fallback | No | Yes |
| Interactive Dash/Plotly interface | Yes | Yes |

## 6. When to use which

**Use TEP Studio when** the work is control, reinforcement learning, system
identification, data generation, or optimization, and you want a schema-driven
domain model, higher-order integration, full-state branching, and the modified
(revised) process variant.

**Use the reference implementation when** you specifically need the classic 1993
process for fault-detection research or for reproducing the Braatz-group
benchmark datasets, or when you require a fully dependency-free pure-Python
simulation in an environment where no compiled extension can be installed.
