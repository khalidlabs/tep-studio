from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np


R12_ACTION = np.array(
    [63.53, 53.98, 24.644, 61.302, 22.21, 40.064, 38.1, 46.534, 47.446, 38.0, 18.114, 50.0],
    dtype=np.float64,
)

MODE1_ACTION = np.array(
    [63.053, 53.98, 24.644, 61.302, 22.21, 40.064, 38.10, 46.534, 47.446, 41.106, 18.114, 50.0],
    dtype=np.float64,
)


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    horizon_h: float
    sample_period_h: float
    action: np.ndarray = field(repr=False)
    ms_flag: int = 0x0F
    seed: float = 1431655765.0
    disturbances: np.ndarray = field(default_factory=lambda: np.zeros(28, dtype=np.float64), repr=False)
    action_policy: Callable[[float, np.ndarray], np.ndarray] | None = field(default=None, repr=False)
    disturbance_policy: Callable[[float, np.ndarray], np.ndarray] | None = field(default=None, repr=False)
    expected: dict[str, float | str | bool] = field(default_factory=dict)


def r12_open_loop() -> Scenario:
    return Scenario(
        name="r12_open_loop_shutdown",
        description="Open-loop R12 example with XMV(10)=38 and high reactor pressure shutdown.",
        horizon_h=5.0,
        sample_period_h=0.01,
        action=R12_ACTION.copy(),
        ms_flag=0x0F,
        expected={"terminated": True, "shutdown_code": 1.0, "shutdown_time_min_h": 0.9, "shutdown_time_max_h": 1.3},
    )


def adchem_solver_independence() -> Scenario:
    disturbances = np.zeros(28, dtype=np.float64)
    disturbances[7] = 1.0
    disturbances[10] = 1.0

    def coolant_slope(time_h: float, base_action: np.ndarray) -> np.ndarray:
        action = base_action.copy()
        action[9] = np.clip(base_action[9] - 8.0 * time_h, 0.0, 100.0)
        return action

    return Scenario(
        name="adchem_solver_independence",
        description=(
            "Mode 1 open-loop disturbance case inspired by ADCHEM 2015: stream 4 composition "
            "and reactor cooling-water inlet disturbance flags (IDV 8 and 11) with a reactor "
            "coolant valve ramp. Under both RK23 and RK45 the run reaches a high separator "
            "liquid level shutdown near 1.9 h, and the two solvers are compared for "
            "reactor-pressure agreement. The original ADCHEM disturbance-recalculation flag "
            "(ms_flag=96) is tracked as an intended reference but not enabled in the current "
            "native Python kernel validation run."
        ),
        horizon_h=2.0,
        sample_period_h=0.01,
        action=MODE1_ACTION.copy(),
        ms_flag=0x0F,
        disturbances=disturbances,
        action_policy=coolant_slope,
        expected={
            "terminated": True,
            "shutdown_message_contains": "Separator Liquid Level",
            "shutdown_time_min_h": 1.7,
            "shutdown_time_max_h": 2.0,
            "solver_reactor_pressure_rmse_max": 1.0e-2,
            "intended_reference_ms_flag": 96,
            "current_ms_flag": 0x0F,
        },
    )


def normal_mode1_short() -> Scenario:
    return Scenario(
        name="mode1_normal_short",
        description="Short normal Mode 1 open-loop baseline for schema, runtime, and dataset checks.",
        horizon_h=0.25,
        sample_period_h=0.01,
        action=MODE1_ACTION.copy(),
        ms_flag=0x0F,
        expected={"terminated": False},
    )


SCENARIOS = {
    "r12": r12_open_loop,
    "adchem_solver": adchem_solver_independence,
    "mode1_short": normal_mode1_short,
}
