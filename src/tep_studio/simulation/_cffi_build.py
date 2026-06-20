from __future__ import annotations

from pathlib import Path

from cffi import FFI


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "temexd_mod" / "temexd_mod.c"


def _slice_between(text: str, start: str, end: str) -> str:
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[start_index:end_index]


def _kernel_source() -> str:
    source = SOURCE.read_text(encoding="latin-1")
    structs = _slice_between(
        source,
        "struct ProcessValues",
        "/**************************************************************************\n"
        "*                                                                         *\n"
        "*                  S - F U N C T I O N - M E T H O D S",
    )
    functions = _slice_between(
        source,
        "static int teinit",
        "/*=============================*",
    )

    return (
        r"""
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

typedef long int integer;
typedef unsigned long uinteger;
typedef short int shortint;
typedef float real;
typedef double doublereal;

#ifndef TRUE_
#define TRUE_ (1)
#define FALSE_ (0)
#endif

#ifdef abs
#undef abs
#endif
#define abs(x) ((x) >= 0 ? (x) : -(x))

static int teinit(void *ModelData, const integer *nn, doublereal *time,
                  doublereal *yy, doublereal *yp, doublereal *rseed,
                  doublereal *MSFlag);
static int tefunc(void *ModelData, const integer *nn, doublereal *time,
                  doublereal *yy, doublereal *yp, shortint Callflag);
static int tesub1_(void *ModelData, doublereal *z__, doublereal *t,
                   doublereal *h__, const integer *ity);
static int tesub2_(void *ModelData, doublereal *z__, doublereal *t,
                   doublereal *h__, const integer *ity);
static int tesub3_(void *ModelData, doublereal *z__, doublereal *t,
                   doublereal *dh, const integer *ity);
static int tesub4_(void *ModelData, doublereal *x, doublereal *t,
                   doublereal *r__);
static int tesub5_(void *ModelData, doublereal *s, doublereal *sp,
                   doublereal *adist, doublereal *bdist, doublereal *cdist,
                   doublereal *ddist, doublereal *tlast, doublereal *tnext,
                   doublereal *hspan, doublereal *hzero, doublereal *sspan,
                   doublereal *szero, doublereal *spspan,
                   doublereal *idvflag);
static int tesub6_(void *ModelData, doublereal *std, doublereal *x);
static doublereal tesub7_(void *ModelData, integer *i__);
static doublereal tesub8_(void *ModelData, const integer *i__, doublereal *t);
double d_mod(doublereal *x, doublereal *y);
double pow_dd(doublereal *ap, const doublereal *bp);
"""
        + structs
        + functions
        + r"""
typedef struct {
  struct stModelData model;
  doublereal state[50];
  doublereal deriv[50];
  doublereal time;
} TEPHandle;

TEPHandle *tep_create(void) {
  return (TEPHandle *)calloc(1, sizeof(TEPHandle));
}

void tep_destroy(TEPHandle *handle) {
  if (handle != NULL) {
    free(handle);
  }
}

int tep_reset(TEPHandle *handle, const double *initial_state, int has_initial,
              double seed, int has_seed, double ms_flag) {
  if (handle == NULL) {
    return -1;
  }

  memset(handle, 0, sizeof(TEPHandle));
  integer nx = NX;
  doublereal time = 0.0;
  doublereal *seed_ptr = has_seed ? &seed : NULL;
  doublereal *flag_ptr = &ms_flag;
  int status = teinit(&handle->model, &nx, &time, handle->state,
                      handle->deriv, seed_ptr, flag_ptr);
  handle->time = time;

  if (has_initial) {
    for (int i = 0; i < NX; ++i) {
      handle->state[i] = initial_state[i];
    }
    for (int i = 0; i < NU; ++i) {
      handle->model.pv_.xmv[i] = handle->state[i + 38];
      handle->model.teproc_.vcv[i] = handle->state[i + 38];
    }
  }

  handle->model.dvec_.idv[28] = 0.0;
  handle->model.code_sd = 0.0;
  return status;
}

void tep_set_inputs(TEPHandle *handle, const double *xmv, const double *idv) {
  if (handle == NULL) {
    return;
  }
  for (int i = 0; i < NU; ++i) {
    handle->model.pv_.xmv[i] = xmv[i];
  }
  for (int i = 0; i < NIDV; ++i) {
    if ((handle->model.MSFlag & 0x80) > 1) {
      handle->model.dvec_.idv[i] = idv[i];
    } else {
      handle->model.dvec_.idv[i] = (idv[i] >= 0.5);
    }
  }
}

int tep_derivatives(TEPHandle *handle, double time, const double *state,
                    double *deriv) {
  if (handle == NULL) {
    return -1;
  }
  doublereal t = time;
  integer nx = NX;
  int status = tefunc(&handle->model, &nx, &t, (doublereal *)state,
                      deriv, 2);
  return status;
}

int tep_outputs(TEPHandle *handle, double time, const double *state,
                double *measurements, double *additional, double *disturbance,
                double *monitor, double *concentration) {
  if (handle == NULL) {
    return -1;
  }
  doublereal t = time;
  integer nx = NX;
  doublereal scratch[50];
  int status = tefunc(&handle->model, &nx, &t, (doublereal *)state,
                      scratch, 1);

  for (int i = 0; i < NY; ++i) {
    measurements[i] = handle->model.pv_.xmeas[i];
  }
  for (int i = 0; i < NYADD; ++i) {
    additional[i] = handle->model.pv_.xmeasadd[i];
  }
  for (int i = 0; i < NYDIST; ++i) {
    disturbance[i] = handle->model.pv_.xmeasdist[i];
  }
  for (int i = 0; i < NYMONITOR; ++i) {
    monitor[i] = handle->model.pv_.xmeasmonitor[i];
  }
  for (int i = 0; i < NYCOMP; ++i) {
    concentration[i] = handle->model.pv_.xmeascomp[i];
  }

  if (handle->model.dvec_.idv[28] != 0.0 && time > 0.1) {
    handle->model.code_sd = handle->model.dvec_.idv[28];
  }
  return status;
}

double tep_shutdown_code(TEPHandle *handle) {
  if (handle == NULL) {
    return -1.0;
  }
  return handle->model.code_sd != 0.0 ? handle->model.code_sd
                                      : handle->model.dvec_.idv[28];
}

void tep_shutdown_message(TEPHandle *handle, char *buffer, size_t size) {
  if (handle == NULL || buffer == NULL || size == 0) {
    return;
  }
  if (handle->model.msg[0] == '\0') {
    buffer[0] = '\0';
    return;
  }
  snprintf(buffer, size, "%s", handle->model.msg);
}

size_t tep_model_size(void) {
  return sizeof(struct stModelData);
}

void tep_get_model_bytes(TEPHandle *handle, char *buffer) {
  memcpy(buffer, &handle->model, sizeof(struct stModelData));
}

void tep_set_model_bytes(TEPHandle *handle, const char *buffer) {
  memcpy(&handle->model, buffer, sizeof(struct stModelData));
}
"""
    )


ffibuilder = FFI()
ffibuilder.cdef(
    """
typedef struct TEPHandle TEPHandle;
TEPHandle *tep_create(void);
void tep_destroy(TEPHandle *handle);
int tep_reset(TEPHandle *handle, const double *initial_state, int has_initial,
              double seed, int has_seed, double ms_flag);
void tep_set_inputs(TEPHandle *handle, const double *xmv, const double *idv);
int tep_derivatives(TEPHandle *handle, double time, const double *state,
                    double *deriv);
int tep_outputs(TEPHandle *handle, double time, const double *state,
                double *measurements, double *additional, double *disturbance,
                double *monitor, double *concentration);
double tep_shutdown_code(TEPHandle *handle);
void tep_shutdown_message(TEPHandle *handle, char *buffer, size_t size);
size_t tep_model_size(void);
void tep_get_model_bytes(TEPHandle *handle, char *buffer);
void tep_set_model_bytes(TEPHandle *handle, const char *buffer);
"""
)
ffibuilder.set_source("tep_studio.simulation._tep_native", _kernel_source(), libraries=["m"])


if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
