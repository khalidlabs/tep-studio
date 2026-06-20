"""Decentralized multiloop PI control for the modified Tennessee Eastman Process.

Reference implementation of N. L. Ricker, "Decentralized control of the Tennessee
Eastman Challenge Process", J. Proc. Cont. 6(4), 205-221, 1996. The control layer
is deliberately separate from the simulator core (principle P2): it consumes only
published measurements (principle P5, no plant-state leakage) and drives the
documented direct manipulated-variable interface of
:class:`tep_studio.TennesseeEastmanProcess`.

Typical use::

    from tep_studio.control import ClosedLoopSimulation
    result = ClosedLoopSimulation(control_interval=0.0005, horizon=48.0).run()
    assert result.stabilized  # the open-loop-unstable plant now runs the horizon
"""

from tep_studio.control.config import (
    MODEL_LEAKAGE_POLICY,
    controller_config,
    process_description_hash,
)
from tep_studio.control.controller import (
    Controller,
    ControllerSetpoints,
    ControlStepDiagnostics,
    RickerMultiLoopController,
)
from tep_studio.control.experiment import ExperimentRecord, build_experiment_record
from tep_studio.control.loops import (
    NominalConditions,
    OverrideSpec,
    PILoopSpec,
    RatioLoopSpec,
    RickerRegistry,
)
from tep_studio.control.metrics import MetricsAccumulator
from tep_studio.control.pi import DiscretePI, PIState, VelocityPI
from tep_studio.control.registry import RICKER_MODE1
from tep_studio.control.runner import ClosedLoopResult, ClosedLoopSimulation
from tep_studio.control.views import diagnostic_view, online_control_view

__all__ = [
    "DiscretePI",
    "VelocityPI",
    "PIState",
    "PILoopSpec",
    "RatioLoopSpec",
    "OverrideSpec",
    "NominalConditions",
    "RickerRegistry",
    "RICKER_MODE1",
    "RickerMultiLoopController",
    "Controller",
    "ControllerSetpoints",
    "ControlStepDiagnostics",
    "ClosedLoopSimulation",
    "ClosedLoopResult",
    "MetricsAccumulator",
    "online_control_view",
    "diagnostic_view",
    "ExperimentRecord",
    "build_experiment_record",
    "controller_config",
    "process_description_hash",
    "MODEL_LEAKAGE_POLICY",
]
