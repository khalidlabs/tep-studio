"""Closed-loop disturbance rejection: inject IDV(1) and export the trajectory.

Runs the stabilized closed loop, steps in disturbance ``idv_01`` (the A/C feed-ratio
change) at t = 1 h, prints the rejection metrics, and writes a tidy CSV dataset for
downstream analysis or plotting.

Usage:
    PYTHONPATH=src python3 src/tep_studio/control/examples/disturbance_scenario.py
"""

from __future__ import annotations

from tep_studio.analysis import (
    DisturbanceActivation,
    ScenarioConfig,
    build_dataset,
    run_scenario,
)


def main() -> None:
    cfg = ScenarioConfig(
        name="idv01_rejection",
        loop_type="closed",
        horizon=12.0,
        control_interval=0.01,
        disturbances=(DisturbanceActivation(idv="idv_01", start_time=1.0),),
    )
    run = run_scenario(cfg)

    stabilized = run.truncated and not run.terminated
    iae = run.metrics.get("iae", {}) if isinstance(run.metrics, dict) else {}
    print(f"idv_01 @ 1 h : stabilized={stabilized} peak_P={run.peak['reactor_pressure_max']:.1f} kPa")
    print(f"  IAE reactor_pressure={iae.get('reactor_pressure', float('nan')):.3f} "
          f"reactor_level={iae.get('reactor_level', float('nan')):.3f}")

    payload, filename = build_dataset([run], fmt="csv")
    with open(filename, "wb") as handle:
        handle.write(payload)
    print(f"  wrote {len(run.frame_records)} rows -> {filename}")


if __name__ == "__main__":
    main()
