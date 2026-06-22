# History and Lineage of the Tennessee Eastman Process

The Tennessee Eastman Process (TEP) is among the most widely used benchmarks in process
control and process fault detection. Every implementation in use today descends
from a single Fortran 77 model published by Downs and Vogel in 1993. This page
traces that lineage, explains the numerical core all variants share, surveys the
Python ecosystem, and locates TEP Studio within it.

## The original model (Downs & Vogel, 1993)

J. J. Downs and E. F. Vogel of Eastman Chemical released the foundational model in
*A plant-wide industrial process control problem* (Computers & Chemical
Engineering 17(3):245–255, 1993). It describes a plant (reactor, condenser,
vapor–liquid separator, recycle compressor, and product stripper) that produces
liquid products G and H from gaseous reactants A, C, D and E, with inert B and
byproduct F, through four irreversible exothermic reactions.

In code the model exposes:

| Quantity | Count | Symbol |
| --- | --- | --- |
| Internal ODE states | 50 | `YY` |
| Measurements | 41 | `XMEAS(1..41)` — 22 continuous + 19 sampled compositions |
| Manipulated variables | 12 | `XMV(1..12)` — valve positions; the 12th is agitator speed |
| Programmable disturbances | 20 | `IDV(1..20)` |

The original model is **open-loop and plant-unstable**: without control it trips on
high reactor pressure within a few hours. Every later layer adds control, datasets,
or numerical and structural revisions on top of this core.

## The lineage of implementations

| # | Implementation | Authors | Language | Role |
| --- | --- | --- | --- | --- |
| 1 | Original open-loop model | Downs & Vogel (Eastman) | Fortran 77 | The 50-state core (`teprob.f`, `temain.f`) |
| 2 | Closed-loop modified model | Russell, Chiang & Braatz (Illinois/MIT) | Fortran 77 | Adds decentralized PI control; produced the canonical FDD `.dat` files |
| 3 | MATLAB/Simulink + C-mex | Ricker (U. Washington) | C / MATLAB | `temex.c`/`temexd.c` S-functions; decentralized & MPC control models |
| 4 | **Revised model (2015)** | Bathelt, Ricker & Jelali | C / MATLAB | `temexd_mod.c`; solver-safe, extra faults/measurements — **TEP Studio's basis** |
| 5 | `tesim` | Candell & Zimmerman (NIST) | C++ | Cyber-physical / networking research port |
| 6 | Modelica libraries | Martín-Villalba, Urquía & Shao | Modelica | Object-oriented, acausal, equation-based |
| 7 | COSTEP (2025) | Various | MATLAB/Simulink | A fully open Simulink rebuild of the process |

### 1. Original Fortran 77 (open-loop)

`teprob.f` contains the function evaluator `TEFUNC(NN,TIME,YY,YP)`, the initializer
`TEINIT`, and utility subroutines `TESUB1`–`TESUB8`; `temain.f` is the open-loop
driver. Historically distributed by Eastman, the original standalone download is no
longer publicly hosted.

### 2. Russell–Chiang–Braatz closed-loop model

Evan Russell, Leo Chiang and Richard Braatz (University of Illinois, later MIT)
added `temain_mod.f`, a plant-wide decentralized PI control scheme that stabilizes
the plant. This version generated the canonical training/testing `.dat` files
(480-row training, 960-row testing; 52 columns = `XMEAS(1..41)` + `XMV(1..11)`) that
underpin most of the classical fault-detection literature (PCA, PLS, FDA, CVA). It
carries a permissive, MIT-style University of Illinois grant.

### 3. Ricker MATLAB/Simulink and C-mex

N. Lawrence Ricker (University of Washington) translated the Fortran to C and wrote
MEX S-functions (`temex.c`, `temexd.c`) connecting the process to Simulink, together
with the decentralized control model `MultiLoop_mode1.mdl` (Ricker, 1996), the
self-optimizing `MultiLoop_Skoge_mode1.mdl` (Larsson et al., 2001), and MPC code.
The `temexd` variant accepts disturbances as live input signals rather than
parameters. TEP Studio's built-in controller reproduces the loop pairings and gains
of Ricker's `MultiLoop_mode1` model.

### 4. Bathelt–Ricker–Jelali revised model (2015) — TEP Studio's basis

Andreas Bathelt, N. Lawrence Ricker and Mohieddine Jelali published *Revision of the
Tennessee Eastman Process Model* (IFAC-PapersOnLine 48(8):309–314, 2015; ADCHEM,
DOI 10.1016/j.ifacol.2015.08.199). The revised kernel `temexd_mod.c` introduced:

- **Solver-safe random numbers.** The original regenerated measurement noise and
  random-variation disturbances on *every* model-function call, so a variable-step
  solver produced solver-dependent, non-repeatable results. The revision decouples
  random-number generation from solver function-evaluations, making results
  reproducible under arbitrary solvers.
- **Separate generators** for process disturbances and measurement noise.
- **Eight new disturbances** (`IDV 21–28`) and the option to scale disturbance
  magnitude.
- **Extended measurements** and the option to log previously hidden internal
  variables.
- **All six production operating modes**, and roughly 45% lower runtime than the
  original.

This is the modern reference simulator. The Reinartz et al. (2021) extended dataset
is generated from it, and TEP Studio compiles this same kernel as its numerical
source of truth.

### 5–7. C++, Modelica, and COSTEP

NIST's `tesim` is a C++ port built for cyber-physical and wireless-networking
research, using Ricker's decentralized control as a baseline. Martín-Villalba,
Urquía and Shao published object-oriented, acausal **Modelica** implementations
(IFAC-PapersOnLine 51(2):619–624, 2018) usable in Dymola and OpenModelica. **COSTEP**
(SoftwareX, 2025) is a from-scratch open Simulink rebuild that exposes every
parameter and variable, in contrast to the opaque compiled C-mex.

## The shared numerical core

All live implementations integrate the same 50-state ODE system. Given the current
state `YY` and the active disturbance vector `IDV`, `TEFUNC` computes the derivatives
`YP`: material balances for the eight components A–H across reactor, separator and
stripper liquid/vapor holdups, energy balances, and compressor, valve and
analyzer-delay states. The states map roughly to reactor component moles (1–9),
separator and stripper holdups (10–17), pressures/levels/temperatures (18–30),
compressor states (31–36), and analyzer dead-time states (37–50). From the states,
`XMEAS(1..41)` are computed (continuous measurements with Gaussian noise; sampled
compositions with 0.1–0.25 h dead time), and `XMV(1..12)` are the manipulated valve
positions.

### Integration mechanics

The classical Fortran cores integrate with a **fixed-step explicit (forward) Euler**
method at a one-second step:

```fortran
SUBROUTINE INTGTR(NN,TIME,DELTAT,YY,YP)
C  Euler Integration Algorithm
   CALL TEFUNC(NN,TIME,YY,YP)
   TIME = TIME + DELTAT
   DO 100 I = 1, NN
       YY(I) = YY(I) + YP(I) * DELTAT
100 CONTINUE
```

with `DELTAT = 1./3600.` (one second, expressed in hours). The main loop runs one
Euler step per iteration; in the closed-loop version controllers are evaluated every
third iteration (3 s), and outputs are recorded every 180th iteration (180 s). This
is the origin of the familiar "one point per second, one sample per three minutes"
cadence.

At a one-second step, forward Euler sits near its stability limit; larger steps can
destabilize the integration. That fragility, combined with the original code's
per-function-call random-number regeneration, is what the 2015 revision
addressed.

!!! tip "Why TEP Studio can use a higher-order integrator"
    Because the revised kernel decouples random-number generation from `TEFUNC`
    calls, a solver may evaluate the derivative many times per step and still
    produce reproducible results. TEP Studio exploits this: its default integrator
    is **fixed-step RK4** (4th order), with Euler and adaptive SciPy solvers
    (RK45/RK23) also available — a departure from the canonical Euler-at-one-second
    that is both faster and more accurate. See [Core Concepts](concepts.md) and
    [Comparison](comparison.md).

## The Python ecosystem

Python access to the TEP has, until recently, followed three strategies. TEP Studio
adds a fourth.

| Strategy | Representative projects | Model | Integrator |
| --- | --- | --- | --- |
| **Wrap the Fortran (f2py)** | `tep2py`, `TEP-meets-LSTM`, the Fortran backend of `jkitchin/...` | Classic Braatz | Fortran Euler, 1 s |
| **Bridge to MATLAB** | `pyTEP` | Revised (2015) | MATLAB/Simulink solver |
| **Reimplement in NumPy/JAX** | `jkitchin/...` pure-Python backend | Classic Braatz | Hand-written Euler, 1 s |
| **Compile the C kernel (CFFI)** | **TEP Studio** | **Revised (2015)** | **RK4 default; Euler / RK45 / RK23 optional** |

- **f2py wrappers** (e.g. `camaramm/tep2py`) marshal inputs to the unchanged Fortran
  and read back a measurement matrix; integration runs entirely in compiled Fortran.
  They are fast but expose no closed-loop intervention from Python, and faults can be
  toggled only on the sampling grid.
- **`pyTEP`** drives the revised Simulink model through the MATLAB Engine for Python
  (Reinartz & Enevoldsen, SoftwareX, 2022). It exposes the extended variable and
  disturbance set and all six modes, but requires a licensed MATLAB installation.
- **NumPy/JAX reimplementations** re-derive the ODEs in pure Python. They run
  anywhere with no compiler, at the cost of being a second implementation that can
  drift from the reference.
- **TEP Studio** compiles the revised `temexd_mod.c` into a single native CFFI
  extension (one numerical source of truth, no MATLAB dependency) and wraps it in a
  schema-driven domain model with online (Gymnasium), offline (dataset), and
  optimization contracts.

## Datasets: the dominant research artifact

For machine-learning fault detection, the most-used artifacts are not live
simulators but static datasets:

- **Rieth, Amsel, Tran & Cook (2017)** — *Additional Tennessee Eastman Process
  Simulation Data for Anomaly Detection Evaluation* (Harvard Dataverse,
  doi:10.7910/DVN/6C3JR1). Generated from the Braatz closed-loop Fortran; 500
  simulation runs per condition; fault-free plus faults 1–20; faults introduced 1 h
  into faulty training runs and 8 h into faulty test runs. The most-used ML benchmark.
- **Reinartz, Kulahci & Ravn (2021)** — *An extended Tennessee Eastman simulation
  dataset* (Computers & Chemical Engineering 149:107281; DTU/figshare
  doi:10.11583/DTU.13385936). Generated from the Bathelt revised simulator: 28 faults
  across 6 operating modes, 500 seeded simulations each, plus setpoint changes and
  mode transitions.

Downstream toolkits (FDD benchmarks, anomaly-detection libraries, and the MATLAB
Deep Learning Toolbox example) typically load these datasets rather than
re-implement the ODEs.

## References

- J. J. Downs and E. F. Vogel. *A plant-wide industrial process control problem.*
  Computers & Chemical Engineering, 17(3):245–255, 1993.
- N. L. Ricker. *Decentralized control of the Tennessee Eastman challenge process.*
  Journal of Process Control, 6(4):205–221, 1996.
- A. Bathelt, N. L. Ricker, and M. Jelali. *Revision of the Tennessee Eastman Process
  Model.* IFAC-PapersOnLine, 48(8):309–314, 2015.
- C. Reinartz, M. Kulahci, and O. Ravn. *An extended Tennessee Eastman simulation
  dataset for fault-detection and decision-support systems.* Computers & Chemical
  Engineering, 149:107281, 2021.
- C. A. Rieth, B. D. Amsel, R. Tran, and M. B. Cook. *Additional Tennessee Eastman
  Process Simulation Data for Anomaly Detection Evaluation.* Harvard Dataverse, 2017.
- C. Reinartz and T. Enevoldsen. *pyTEP: A Python package for interactive simulations
  of the Tennessee Eastman process.* SoftwareX, 18:101053, 2022.
- C. Martín-Villalba, A. Urquía, and G. Shao. *Implementations of the Tennessee
  Eastman Process in Modelica.* IFAC-PapersOnLine, 51(2):619–624, 2018.
