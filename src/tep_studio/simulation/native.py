from __future__ import annotations

import glob
import os
import platform
from dataclasses import dataclass
from importlib import import_module

import numpy as np
from numpy.typing import ArrayLike

try:
    _tep_native = import_module("tep_studio.simulation._tep_native")
except ImportError as exc:  # pragma: no cover - exercised before extension build.
    _pkg_dir = os.path.dirname(__file__)
    _built = sorted(
        glob.glob(os.path.join(_pkg_dir, "_tep_native*.so"))
        + glob.glob(os.path.join(_pkg_dir, "_tep_native*.pyd"))
    )
    if _built:
        # The extension is present but won't load — almost always an OS/architecture
        # mismatch (e.g. a macOS arm64 build checked out on Linux, or vice versa).
        raise ImportError(
            "The TEP native extension is present but failed to load on this platform "
            f"({platform.system()} {platform.machine()}, Python {platform.python_version()}): "
            f"{os.path.basename(_built[0])}. It was most likely built for a different "
            "operating system or CPU architecture. Reinstall the matching wheel "
            "(`pip install --force-reinstall tep-studio`) or rebuild from source "
            "(`pip install -e .`, or `python3 setup.py build_ext --inplace`)."
        ) from exc
    raise ImportError(
        "The TEP native extension is not built. Install the package with "
        "`python3 -m pip install -e .` or run `python3 setup.py build_ext --inplace`."
    ) from exc


ffi = _tep_native.ffi
lib = _tep_native.lib


@dataclass(frozen=True)
class NativeSnapshot:
    model_bytes: bytes
    state: np.ndarray
    time: float
    xmv: np.ndarray
    idv: np.ndarray


class NativeTEPKernel:
    nx = 50
    nu = 12
    nidv = 28
    ny = 41
    nyadd = 32
    nydist = 21
    nymonitor = 62
    nycomp = 96

    def __init__(self) -> None:
        self._handle = lib.tep_create()
        if self._handle == ffi.NULL:
            raise MemoryError("Could not allocate TEP native model state.")
        self.state = np.zeros(self.nx, dtype=np.float64)
        self.time = 0.0
        self.xmv = np.zeros(self.nu, dtype=np.float64)
        self.idv = np.zeros(self.nidv, dtype=np.float64)

    def close(self) -> None:
        if getattr(self, "_handle", ffi.NULL) != ffi.NULL:
            lib.tep_destroy(self._handle)
            self._handle = ffi.NULL

    def __del__(self) -> None:  # pragma: no cover - destructor best effort.
        self.close()

    def reset(
        self,
        *,
        initial_state: ArrayLike | None = None,
        seed: float | None = None,
        ms_flag: int = 0,
    ) -> np.ndarray:
        init = None if initial_state is None else self._as_array(initial_state, self.nx)
        init_ptr = ffi.NULL if init is None else ffi.cast("double *", init.ctypes.data)
        status = lib.tep_reset(
            self._handle,
            init_ptr,
            int(init is not None),
            float(0.0 if seed is None else seed),
            int(seed is not None),
            float(ms_flag),
        )
        if status != 0:
            raise RuntimeError(f"Native TEP reset failed with status {status}.")
        if init is not None:
            self.state = init.copy()
        else:
            self.state = self._read_reset_state()
        self.time = 0.0
        self.xmv = self.state[38:50].copy()
        self.idv = np.zeros(self.nidv, dtype=np.float64)
        self.set_inputs(self.xmv, self.idv)
        return self.state.copy()

    def _read_reset_state(self) -> np.ndarray:
        # The C reset stores the initialized state in the handle but intentionally
        # exposes it through an output evaluation path, so we keep a Python copy by
        # asking for the documented default from the schema-bearing implementation.
        return np.array(
            [
                10.40491389,
                4.363996017,
                7.570059737,
                0.4230042431,
                24.15513437,
                2.942597645,
                154.3770655,
                159.186596,
                2.808522723,
                63.75581199,
                26.74026066,
                46.38532432,
                0.2464521543,
                15.20484404,
                1.852266172,
                52.44639459,
                41.20394008,
                0.569931776,
                0.4306056376,
                0.0079906200783,
                0.9056036089,
                0.016054258216,
                0.7509759687,
                0.088582855955,
                48.27726193,
                39.38459028,
                0.3755297257,
                107.7562698,
                29.77250546,
                88.32481135,
                23.03929507,
                62.85848794,
                5.546318688,
                11.92244772,
                5.555448243,
                0.9218489762,
                94.59927549,
                77.29698353,
                63.05263039,
                53.97970677,
                24.64355755,
                61.30192144,
                22.21,
                40.06374673,
                38.1003437,
                46.53415582,
                47.44573456,
                41.10581288,
                18.11349055,
                50.0,
            ],
            dtype=np.float64,
        )

    def set_inputs(self, xmv: ArrayLike, idv: ArrayLike | None = None) -> None:
        self.xmv = self._as_array(xmv, self.nu)
        if idv is not None:
            self.idv = self._as_array(idv, self.nidv)
        lib.tep_set_inputs(
            self._handle,
            ffi.cast("double *", self.xmv.ctypes.data),
            ffi.cast("double *", self.idv.ctypes.data),
        )

    def derivatives(self, time: float, state: ArrayLike) -> np.ndarray:
        # Hot path: called ~6x per solver step, millions of times per dataset. Pass the
        # NumPy buffers straight to C with ffi.from_buffer (avoids building a ctypes
        # array-interface object per call); the C result is identical.
        state_array = self._as_array(state, self.nx)
        out = np.zeros(self.nx, dtype=np.float64)
        status = lib.tep_derivatives(
            self._handle,
            float(time),
            ffi.from_buffer("double[]", state_array),
            ffi.from_buffer("double[]", out),
        )
        if status != 0:
            raise RuntimeError(f"Native TEP derivative call failed with status {status}.")
        return out

    def outputs(self, time: float, state: ArrayLike) -> dict[str, np.ndarray]:
        state_array = self._as_array(state, self.nx)
        arrays = {
            "measurements": np.zeros(self.ny, dtype=np.float64),
            "additional_measurements": np.zeros(self.nyadd, dtype=np.float64),
            "disturbance_monitors": np.zeros(self.nydist, dtype=np.float64),
            "process_monitors": np.zeros(self.nymonitor, dtype=np.float64),
            "concentration_monitors": np.zeros(self.nycomp, dtype=np.float64),
        }
        status = lib.tep_outputs(
            self._handle,
            float(time),
            ffi.cast("double *", state_array.ctypes.data),
            ffi.cast("double *", arrays["measurements"].ctypes.data),
            ffi.cast("double *", arrays["additional_measurements"].ctypes.data),
            ffi.cast("double *", arrays["disturbance_monitors"].ctypes.data),
            ffi.cast("double *", arrays["process_monitors"].ctypes.data),
            ffi.cast("double *", arrays["concentration_monitors"].ctypes.data),
        )
        if status != 0:
            raise RuntimeError(f"Native TEP output call failed with status {status}.")
        return arrays

    def shutdown_status(self) -> tuple[float, str]:
        code = float(lib.tep_shutdown_code(self._handle))
        buffer = ffi.new("char[]", 256)
        lib.tep_shutdown_message(self._handle, buffer, 256)
        return code, ffi.string(buffer).decode("utf-8", errors="replace")

    def snapshot(self) -> NativeSnapshot:
        size = int(lib.tep_model_size())
        buffer = ffi.new(f"char[{size}]")
        lib.tep_get_model_bytes(self._handle, buffer)
        return NativeSnapshot(
            model_bytes=bytes(ffi.buffer(buffer, size)),
            state=self.state.copy(),
            time=float(self.time),
            xmv=self.xmv.copy(),
            idv=self.idv.copy(),
        )

    def restore(self, snapshot: NativeSnapshot) -> None:
        buffer = ffi.from_buffer(snapshot.model_bytes)
        lib.tep_set_model_bytes(self._handle, buffer)
        self.state = snapshot.state.copy()
        self.time = float(snapshot.time)
        self.xmv = snapshot.xmv.copy()
        self.idv = snapshot.idv.copy()

    @staticmethod
    def _as_array(values: ArrayLike, length: int) -> np.ndarray:
        array = np.asarray(values, dtype=np.float64)
        if array.shape != (length,):
            raise ValueError(f"Expected shape ({length},), got {array.shape}.")
        return np.ascontiguousarray(array, dtype=np.float64)
