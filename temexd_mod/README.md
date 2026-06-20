# temexd_mod

Numerical source-of-truth files for the modified Tennessee Eastman Process,
trimmed to what the Python package actually consumes:

- `temexd_mod.c`, `teprob_mod.h` — the modified TEP C kernel (Bathelt, Ricker &
  Jelali, 2015). Compiled into the native extension by
  `src/tep_studio/simulation/_cffi_build.py`, and used as the base-case state
  reference by the validation suite (`validation/base_case.py`).
- `Mode1xInitial.mat`, `Mode3xInitial.mat`, `Mode1SkogeInit.mat` — Simulink
  `CSTATE` operating-point vectors loaded by the MAT-state validation suite
  (`validation/mat_states.py`).

The original MATLAB/Simulink reference bundle (`.mdl` models, `*_Init.m` scripts,
Windows `.mexw64`, and the ADCHEM reference paper) was removed; it is not read by
the Python package. The control strategy was transcribed from the upstream
archive into `src/tep_studio/control/registry.py`.
