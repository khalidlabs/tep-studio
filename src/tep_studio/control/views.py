"""Causal views over the process variables (principles P3/P4).

The ``online_control_view`` is the only information a controller or RL policy may
read at time k: published measurements, never the internal 50-state vector. The
``diagnostic_view`` exposes full state and events for OFFLINE analysis only and is
explicitly non-causal -- it must never be fed back into a control law.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike

from tep_studio.control.registry import RICKER_MODE1, RickerRegistry
from tep_studio.simulation.core import AdvanceResult
from tep_studio.simulation.schema import TEP_SCHEMA, ProcessSchema

# Reactant-composition analyzers the controller reads in addition to the loop PVs.
_EXTRA_ONLINE = {"reactor_feed_A_concentration", "reactor_feed_C_concentration"}


def online_control_view(
    measurements: ArrayLike,
    *,
    schema: ProcessSchema = TEP_SCHEMA,
    registry: RickerRegistry = RICKER_MODE1,
) -> dict[str, float]:
    """The measurements available to the controller at time k (causal, leak-free)."""
    meas = np.asarray(measurements, dtype=np.float64)
    names = sorted(registry.measurement_pvs() | _EXTRA_ONLINE)
    return {name: float(meas[schema.index("measurements", name)]) for name in names}


def diagnostic_view(result: AdvanceResult, *, schema: ProcessSchema = TEP_SCHEMA) -> dict[str, object]:
    """Full internal state + events for OFFLINE analysis only (non-causal)."""
    return {
        "time": result.time,
        "state": {name: float(v) for name, v in zip(schema.names("states"), result.state)},
        "measurements": {name: float(v) for name, v in zip(schema.names("measurements"), result.measurements)},
        "constraint_margins": dict(result.constraint_margins),
        "shutdown_status": dict(result.shutdown_status),
    }
