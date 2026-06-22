# Performance Comparison

This page benchmarks TEP Studio's simulation speed against a closely comparable
contemporary Python wrapper, `jkitchin/tennessee-eastman-profbraatz`. It is about
speed only; for how the two projects differ in model variant, backend design, and
the broader Python ecosystem, see [History & Lineage](history.md).

## Benchmark

Wall-clock time to simulate one process-hour from the Mode-1 steady state, with
fixed manipulated variables and IDV = 0. Measured on Apple Silicon, Python 3.10,
single process. The reference Fortran backend was hand-built with f2py for this
comparison.

| Path | Time / sim-hour | Throughput |
| --- | --- | --- |
| TEP Studio — Euler (fixed-step) | **8 ms** | ~125 sim-h/s |
| TEP Studio — RK4 (default) | **21 ms** | ~47 sim-h/s |
| TEP Studio — RK23 | 26 ms | ~38 sim-h/s |
| Reference — Fortran (f2py, Euler 1 s) | 44 ms | ~23 sim-h/s |
| TEP Studio — RK45 (adaptive) | 185 ms | ~5 sim-h/s |
| Reference — pure-Python (default, Euler 1 s) | 1434 ms | ~0.7 sim-h/s |

The compiled kernels are comparable at the level of a single derivative evaluation
(~0.5–0.9 µs/call). The end-to-end differences come from binding overhead and
integrator choice: the CFFI path writes into preallocated buffers, whereas f2py
marshals arrays on every call. TEP Studio's RK4 default simulates a process-hour in
roughly half the time of the reference Fortran backend and about 65× faster
than the reference's default pure-Python path, while using a higher-order integrator.

!!! warning "Benchmark caveats"
    The two projects integrate different model variants, so this measures the
    realized simulation speed of each tool as shipped, not identical numerical work.
    Absolute numbers are machine-dependent; the ranking (pure-Python ≪ Fortran-f2py
    < CFFI/C kernel, with adaptive RK45 trading speed for robustness) is stable
    across runs.
