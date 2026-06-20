"""Serializable controller configuration + content hashes (principle P6).

The process description has no controller block, so the controller config is a
separate artifact that *references* the process description by hash and reuses its
vocabulary (``model_leakage_policy``, ``action_authority``). Hashing a canonical
JSON of the loop table makes any change to a gain, setpoint, or pairing traceable
in an experiment record.
"""

from __future__ import annotations

import hashlib
import json

from tep_studio.simulation.schema import TEP_SCHEMA, ProcessSchema

# The controller reads only published measurements and never the true plant model
# or parameters (no train/test or controller==plant leakage).
MODEL_LEAKAGE_POLICY = {
    "controller_may_use_true_model": False,
    "controller_may_use_true_parameters": False,
}


def process_description_hash(schema: ProcessSchema = TEP_SCHEMA) -> str:
    payload = {
        "name": schema.name,
        "states": schema.names("states"),
        "manipulated_variables": schema.names("manipulated_variables"),
        "measurements": schema.names("measurements"),
    }
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def controller_config(controller: object) -> dict:
    """Build a serializable description of the controller's loop table and policy."""
    reg = controller.registry  # type: ignore[attr-defined]

    def _pi(spec) -> dict:
        return {
            "pv": spec.pv,
            "kc": spec.kc,
            "ti_hours": spec.ti_hours,
            "ts_hours": spec.ts_hours,
            "x0": spec.x0,
            "hi": _finite(spec.hi),
            "lo": _finite(spec.lo),
            "form": spec.form,
            "drives": spec.drives,
            "source": spec.source,
        }

    def _ratio(spec) -> dict:
        return {
            "pv": spec.pv,
            "mv": spec.mv,
            "ratio_key": spec.ratio_key,
            "kc": spec.kc,
            "ti_hours": spec.ti_hours,
            "ts_hours": spec.ts_hours,
            "x0": spec.x0,
            "source": spec.source,
        }

    return {
        "strategy": "ricker_1996_decentralized_mode1",
        "process_description_hash": process_description_hash(controller.schema),  # type: ignore[attr-defined]
        "action_authority": "direct_mv",
        "model_leakage_policy": MODEL_LEAKAGE_POLICY,
        "enable": {
            "composition": controller.enable_composition,  # type: ignore[attr-defined]
            "pct_g_feedback": controller.enable_pct_g_feedback,  # type: ignore[attr-defined]
            "overrides": controller.enable_overrides,  # type: ignore[attr-defined]
        },
        "feed_loops": {spec.name: _ratio(spec) for spec in reg.feed_loops},
        "loops": {spec.name: _pi(spec) for spec in reg.pi_loops()},
        "overrides": [
            {
                "name": ov.name,
                "trigger_pv": ov.trigger_pv,
                "target": ov.target,
                "threshold": ov.threshold,
                "gain": ov.gain,
                "enabled": ov.enabled,
                "source": ov.confirmed_source,
            }
            for ov in reg.overrides
        ],
    }


def config_hash(config: dict) -> str:
    blob = json.dumps(config, sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def _finite(value: float) -> float | None:
    """Map +/-inf to None so the config serializes as strict JSON."""
    return None if value in (float("inf"), float("-inf")) else value
