"""Stabilize the modified TEP with the Ricker (1996) decentralized controller.

The base-case plant is open-loop unstable: held at constant inputs it trips on high
reactor pressure within a few hours. Closing the decentralized multiloop strategy
keeps it on its operating point for the full horizon. This script runs the closed
loop, prints the stability outcome and regulatory metrics, and emits a reproducible
experiment record (principle P6).

Usage:
    PYTHONPATH=src python3 src/tep_studio/control/examples/ricker_mode1_closed_loop.py
"""

from __future__ import annotations

from tep_studio import TennesseeEastmanProcess
from tep_studio.control import (
    ClosedLoopSimulation,
    RickerMultiLoopController,
    build_experiment_record,
)


def main() -> None:
    simulator = TennesseeEastmanProcess()
    controller = RickerMultiLoopController(enable_overrides=True)
    runner = ClosedLoopSimulation(
        simulator=simulator,
        controller=controller,
        control_interval=0.0005,
        horizon=24.0,
    )
    result = runner.run()

    print(f"stabilized      : {result.stabilized}")
    print(f"terminated      : {result.terminated} (endogenous shutdown)")
    print(f"truncated       : {result.truncated} (reached horizon)")
    print(f"final time      : {result.final_time:.2f} h over {result.n_steps} steps")
    print(f"peak reactor P  : {result.peak['reactor_pressure_max']:.1f} kPa (trip 3000)")

    metrics = result.metrics
    print(f"IAE reactor P   : {metrics['iae']['reactor_pressure']:.4g}")
    print(f"IAE reactor lvl : {metrics['iae']['reactor_level']:.4g}")
    print(f"violations      : {metrics['constraint_violation_steps']} steps")
    print(f"mean production : {metrics['production_rate_mean']:.2f}")

    record = build_experiment_record(result, controller, simulator=simulator)
    print("\nexperiment record (P6):")
    print(record.to_json())


if __name__ == "__main__":
    main()
