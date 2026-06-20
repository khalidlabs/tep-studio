"""Bring your own controller: drive the plant with a custom control law.

``ClosedLoopSimulation`` accepts anything that satisfies the
:class:`~tep_studio.control.Controller` protocol (a mutable ``setpoints`` plus
``reset`` and ``compute_action``) — no subclassing required. This example keeps the
decentralized Ricker strategy for stability but swaps in a user-tuned
:class:`~tep_studio.control.DiscretePI` loop on the reactor-temperature →
cooling-water valve pairing, showing how to plug your own loop into the boundary.

Usage:
    PYTHONPATH=src python3 src/tep_studio/control/examples/custom_controller.py
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike

from tep_studio import TEP_SCHEMA, ClosedLoopSimulation
from tep_studio.control import Controller, DiscretePI, RickerMultiLoopController

_MV = TEP_SCHEMA.index("manipulated_variables", "reactor_cooling_water_valve")
_TEMP = TEP_SCHEMA.index("measurements", "reactor_temperature")


class MyController:
    """Ricker base + a bring-your-own PI on the reactor-temperature loop."""

    def __init__(self, *, kc: float = -8.0, ti_hours: float = 0.125) -> None:
        self._base = RickerMultiLoopController()
        self._pi = DiscretePI(kc, ti_hours, 0.0005, 100.0, 0.0)  # (kc, Ti, Ts, hi, lo)
        self._pi_state = None
        self.setpoints = None  # read by the runner for metric references

    def reset(self, measurements: ArrayLike, *, time: float = 0.0) -> None:
        self._base.reset(measurements, time=time)
        self.setpoints = self._base.setpoints
        self._pi_state = self._pi.initial_state(41.106, time=time)  # nominal valve position

    def compute_action(self, measurements: ArrayLike, *, time: float):
        action, diagnostics = self._base.compute_action(measurements, time=time)
        temperature = float(np.asarray(measurements)[_TEMP])
        valve, self._pi_state = self._pi.update(self._pi_state, self.setpoints.reactor_temperature, temperature, time)
        action[_MV] = float(np.clip(valve, 0.0, 100.0))
        return action, diagnostics


def main() -> None:
    controller = MyController()
    assert isinstance(controller, Controller)  # structural check (runtime_checkable)
    result = ClosedLoopSimulation(controller=controller, control_interval=0.01, horizon=12.0).run()
    print(f"custom controller stabilized : {result.stabilized}")
    print(f"peak reactor pressure        : {result.peak['reactor_pressure_max']:.1f} kPa (trip 3000)")
    print(f"IAE reactor temperature      : {result.metrics['iae']['reactor_temperature']:.4g}")


if __name__ == "__main__":
    main()
