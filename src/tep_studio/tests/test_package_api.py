"""Top-level ergonomics: version, discoverability helpers, quickstart, gym registration."""

from __future__ import annotations

import subprocess
import sys


def test_version_present() -> None:
    import tep_studio

    assert isinstance(tep_studio.__version__, str) and tep_studio.__version__


def test_importing_package_does_not_pull_dash() -> None:
    # Hermetic check (fresh interpreter): the core import and the analysis façade must
    # stay Dash-free so non-UI users never need the `ui` extra.
    code = (
        "import sys, tep_studio, tep_studio.analysis; "
        "assert 'dash' not in sys.modules, sorted(m for m in sys.modules if 'dash' in m)"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_list_helpers_match_schema() -> None:
    import tep_studio as tep

    assert len(tep.list_measurements()) == 41
    assert len(tep.list_manipulated_variables()) == 12
    assert len(tep.list_disturbances()) == 28
    assert ("idv_01", "A/C ratio of stream 4, B composition constant") in tep.list_disturbances()
    assert "production_rate" in tep.list_setpoints()
    # tuples have the documented (name, unit, description) / (name, description) shapes
    assert tep.list_measurements()[6][0] == "reactor_pressure"
    assert len(tep.list_disturbances()[0]) == 2


def test_gym_make_roundtrip() -> None:
    import gymnasium as gym

    import tep_studio  # noqa: F401 -- importing registers the env

    assert "TennesseeEastman-v0" in gym.registry
    env = gym.make("TennesseeEastman-v0", horizon=1.0, control_interval=0.1)
    obs, _ = env.reset(seed=0)
    assert obs.shape == (41,)
    step = env.step(env.action_space.sample())
    assert len(step) == 5  # Gymnasium 5-tuple


def test_quickstart_stabilizes() -> None:
    import tep_studio

    summary = tep_studio.quickstart(horizon=6.0, control_interval=0.01)
    assert summary["stabilized"] is True
    assert summary["peak_reactor_pressure_kpa"] < 3000.0
