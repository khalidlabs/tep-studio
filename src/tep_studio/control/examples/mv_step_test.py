"""Open-loop step test: step a manipulated variable and read the response.

Demonstrates the Dash-free analysis API (:mod:`tep_studio.analysis`). Steps the
D-feed valve and reports the measured change in the D-feed flow — a simple process
read-out. The plant is open-loop unstable, so the horizon is short and the step is
early; this visualises the response, it does not fit a model.

Usage:
    PYTHONPATH=src python3 src/tep_studio/control/examples/mv_step_test.py
"""

from __future__ import annotations

from tep_studio.analysis import ScenarioConfig, StepTestSpec, run_mv_step_test


def main() -> None:
    cfg = ScenarioConfig(loop_type="open", horizon=1.0, control_interval=0.01)
    spec = StepTestSpec(kind="mv", target="d_feed_valve", baseline=63.0, step_value=70.0, step_time=0.25)
    run = run_mv_step_test(cfg, spec)

    frame = run.to_frame()
    pv = "measurement.feed_D_flow"
    before = float(frame.loc[frame["time"] < spec.step_time, pv].iloc[-1])
    after = float(frame[pv].iloc[-1])
    print(f"step d_feed_valve {spec.baseline:g} -> {spec.step_value:g} % at t={spec.step_time} h "
          f"({run.n_steps} steps, terminated={run.terminated})")
    print(f"  feed_D_flow: {before:.2f} -> {after:.2f}  (delta {after - before:+.2f})")


if __name__ == "__main__":
    main()
