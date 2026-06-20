from __future__ import annotations

import pytest

pytest.importorskip("dash")


def _string_ids(component) -> set[str]:
    found: set[str] = set()
    cid = getattr(component, "id", None)
    if isinstance(cid, str):
        found.add(cid)
    children = getattr(component, "children", None)
    if children is not None:
        if not isinstance(children, (list, tuple)):
            children = [children]
        for child in children:
            found |= _string_ids(child)
    return found


def test_create_app_builds_layout_and_callbacks() -> None:
    from tep_studio.ui import create_app

    app = create_app(background=False)
    ids = _string_ids(app.layout)

    # stores + tab container + one representative control per tab
    expected = {
        "session-runs",
        "active-run",
        "batch-store",
        "tabs",
        "run-btn",
        "trajectory-graph",
        "run-step-btn",
        "step-graph",
        "build-dataset-btn",
        "run-batch-btn",
        "compare-graph",
        "record-json",
    }
    missing = expected - ids
    assert not missing, f"missing component ids: {missing}"
    assert len(app.callback_map) > 8  # all the wired callbacks


def _find(component, target_id):
    if getattr(component, "id", None) == target_id:
        return component
    children = getattr(component, "children", None)
    if children is not None:
        if not isinstance(children, (list, tuple)):
            children = [children]
        for child in children:
            found = _find(child, target_id)
            if found is not None:
                return found
    return None


def test_number_inputs_commit_on_keystroke() -> None:
    # Number inputs must commit on every keystroke (debounce not True) so the form
    # State is current the moment the user clicks Run, never a stale default.
    from tep_studio.ui import create_app

    app = create_app()
    for input_id in ("horizon", "step-horizon", "step-value", "step-time", "dist-start", "seed"):
        node = _find(app.layout, input_id)
        assert node is not None, f"missing input {input_id}"
        assert getattr(node, "debounce", None) is not True, f"{input_id} must commit on keystroke (debounce must not be True)"


def test_backend_symbols_importable_from_package() -> None:
    import tep_studio.ui as ui

    assert hasattr(ui, "run_scenario")
    assert hasattr(ui, "ScenarioConfig")
    assert hasattr(ui, "build_dataset")


def test_scenario_glue_builds_valid_config() -> None:
    # The config glue that unpacks the simulate-form State into a ScenarioConfig.
    from tep_studio.ui.callbacks import _scenario

    sp_ids = [{"type": "sp-input", "name": "reactor_level"}, {"type": "sp-input", "name": "reactor_pressure"}]
    sp_vals = [72.0, 2700.0]
    cfg = _scenario("closed", 8.0, 0.01, None, ["composition", "overrides"], sp_vals, sp_ids, [], [], ["idv_01"], 1.5)
    cfg.validate()
    assert cfg.loop_type == "closed"
    assert cfg.horizon == 8.0
    assert cfg.setpoints["reactor_level"] == 72.0
    assert cfg.enable_overrides is True
    assert cfg.disturbances[0].idv == "idv_01"
    assert cfg.disturbances[0].start_time == 1.5

    mv_ids = [{"type": "mv-slider", "name": "d_feed_valve"}]
    open_cfg = _scenario("open", 4.0, 0.01, 7.0, ["composition"], [], [], [70.0], mv_ids, [], 0.0)
    open_cfg.validate()
    assert open_cfg.loop_type == "open"
    assert open_cfg.manual_mvs["d_feed_valve"] == 70.0
    assert open_cfg.setpoints is None  # open loop drops setpoints
