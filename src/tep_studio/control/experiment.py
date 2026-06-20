"""Reproducible experiment record for a closed-loop run (principle P6).

Captures everything needed to connect a reported trajectory/metric back to the
exact configuration that produced it: source revision, process-description hash,
controller-config hash, seed, solver settings, setpoints, gains, and metrics.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass

from tep_studio.control.config import (
    MODEL_LEAKAGE_POLICY,
    config_hash,
    controller_config,
)


def _git_revision() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


@dataclass(frozen=True)
class ExperimentRecord:
    strategy: str
    process_description_hash: str
    controller_config_hash: str
    git_revision: str
    action_authority: str
    model_leakage_policy: dict
    seed: float | None
    solver: dict
    control_interval: float
    horizon: float
    enable: dict
    setpoints: dict
    controller_config: dict
    terminated: bool
    truncated: bool
    metrics: dict

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent)


def build_experiment_record(
    result: object,
    controller: object,
    *,
    simulator: object,
    seed: float | None = None,
) -> ExperimentRecord:
    cfg = controller_config(controller)
    setpoints = asdict(controller.setpoints)  # type: ignore[attr-defined]
    return ExperimentRecord(
        strategy="ricker_1996_decentralized_mode1",
        process_description_hash=cfg["process_description_hash"],
        controller_config_hash=config_hash(cfg),
        git_revision=_git_revision(),
        action_authority="direct_mv",
        model_leakage_policy=MODEL_LEAKAGE_POLICY,
        seed=seed,
        solver={
            "method": simulator.solver_method,  # type: ignore[attr-defined]
            "rtol": simulator.rtol,  # type: ignore[attr-defined]
            "atol": simulator.atol,  # type: ignore[attr-defined]
        },
        control_interval=result.control_interval,  # type: ignore[attr-defined]
        horizon=result.horizon,  # type: ignore[attr-defined]
        enable=cfg["enable"],
        setpoints=setpoints,
        controller_config=cfg,
        terminated=result.terminated,  # type: ignore[attr-defined]
        truncated=result.truncated,  # type: ignore[attr-defined]
        metrics=result.metrics,  # type: ignore[attr-defined]
    )
