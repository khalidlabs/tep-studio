"""Tennessee Eastman Process simulator — a schema-driven Python implementation.

A reproducible, named-variable interface to the modified Tennessee Eastman Process
(Downs & Vogel; modified kernel by Bathelt, Ricker & Jelali), bundled with a
decentralized PI controller, a Gymnasium environment, dataset tooling, and an
interactive studio.

Quickstart by audience
----------------------
Process / control engineers — run the closed loop and inspect stability::

    import tep_studio as tep
    tep.quickstart()                                    # short closed-loop smoke run
    from tep_studio import ClosedLoopSimulation
    result = ClosedLoopSimulation(horizon=24.0).run()   # result.stabilized == True

ML / RL researchers — a standard Gymnasium environment (registered on import)::

    import gymnasium, tep_studio
    env = gymnasium.make("TennesseeEastman-v0", horizon=24.0)
    obs, info = env.reset(seed=0)
    obs, reward, terminated, truncated, info = env.step(env.action_space.sample())

Control theorists — a local linear state-space model around an operating point::

    from tep_studio import TennesseeEastmanProcess, OptimizationAdapter
    sim = TennesseeEastmanProcess(rtol=1e-10, atol=1e-12)
    sim.reset(); u0 = sim.state[38:50]
    A, B = OptimizationAdapter(sim).linearize(sim.state, u0, control_interval=0.001)

Discover what you can touch with :func:`list_measurements`,
:func:`list_manipulated_variables`, :func:`list_disturbances`, and
:func:`list_setpoints`. Step tests and dataset export live in
:mod:`tep_studio.analysis`; the web studio is ``python -m tep_studio.ui``
(install the ``ui`` extra). See the documentation "Cookbook" for recipes.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version

from tep_studio.simulation import (
    AdvanceResult,
    GymTEPEnv,
    OptimizationAdapter,
    ProcessSchema,
    TEP_SCHEMA,
    TennesseeEastmanProcess,
    TrajectoryDataset,
)
from tep_studio.control import (
    ClosedLoopSimulation,
    ControllerSetpoints,
    RickerMultiLoopController,
)

try:
    __version__ = _pkg_version("tep-studio")
except PackageNotFoundError:  # running from a source checkout without an install
    __version__ = "0.0.0+local"


# -- discoverability helpers (thin wrappers over TEP_SCHEMA / ControllerSetpoints) --
def list_measurements() -> list[tuple[str, str, str]]:
    """The 41 online measurements as ``(name, unit, description)`` — the observation/CV names."""
    return [(v.name, v.unit, v.description) for v in TEP_SCHEMA.measurements]


def list_manipulated_variables() -> list[tuple[str, str, str]]:
    """The 12 manipulated variables as ``(name, unit, description)`` — the action vector (each 0..100%)."""
    return [(v.name, v.unit, v.description) for v in TEP_SCHEMA.manipulated_variables]


def list_disturbances() -> list[tuple[str, str]]:
    """The 28 process disturbances as ``(name, description)`` — activate by name, e.g. ``"idv_01"``."""
    return [(v.name, v.description) for v in TEP_SCHEMA.disturbances]


def list_setpoints() -> list[str]:
    """The closed-loop setpoint field names (see :class:`~tep_studio.ControllerSetpoints`)."""
    import dataclasses

    return [f.name for f in dataclasses.fields(ControllerSetpoints)]


def quickstart(*, horizon: float = 8.0, control_interval: float = 0.01) -> dict:
    """Run a short closed-loop simulation and print/return a one-line health summary.

    A fast end-to-end check (native kernel + solver + decentralized controller) that
    the open-loop-unstable plant is stabilized by the built-in Ricker controller.
    Returns a dict with ``stabilized``, ``final_time_h`` and ``peak_reactor_pressure_kpa``.
    """
    result = ClosedLoopSimulation(control_interval=control_interval, horizon=horizon).run()
    summary = {
        "stabilized": bool(result.stabilized),
        "horizon_h": float(horizon),
        "final_time_h": round(result.final_time, 3),
        "peak_reactor_pressure_kpa": round(result.peak["reactor_pressure_max"], 1),
    }
    print(
        f"TEP quickstart: stabilized={summary['stabilized']} over {summary['horizon_h']} h; "
        f"peak reactor pressure {summary['peak_reactor_pressure_kpa']} kPa (shutdown trip at 3000)."
    )
    return summary


def _register_gym_env() -> None:
    """Register ``TennesseeEastman-v0`` so ``gymnasium.make`` works. Best-effort, idempotent."""
    try:
        import gymnasium as gym

        if "TennesseeEastman-v0" not in gym.registry:
            gym.register(
                id="TennesseeEastman-v0",
                entry_point="tep_studio.simulation.gym_env:GymTEPEnv",
            )
    except Exception:  # registration is a convenience; never break `import tep_studio`
        pass


_register_gym_env()


__all__ = [
    "AdvanceResult",
    "GymTEPEnv",
    "OptimizationAdapter",
    "ProcessSchema",
    "TEP_SCHEMA",
    "TennesseeEastmanProcess",
    "TrajectoryDataset",
    "ClosedLoopSimulation",
    "ControllerSetpoints",
    "RickerMultiLoopController",
    "list_measurements",
    "list_manipulated_variables",
    "list_disturbances",
    "list_setpoints",
    "quickstart",
    "__version__",
]
