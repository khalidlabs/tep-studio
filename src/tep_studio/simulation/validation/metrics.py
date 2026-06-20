from __future__ import annotations

import numpy as np
import pandas as pd


def shutdown_metrics(trajectory: pd.DataFrame) -> dict[str, float | str | bool]:
    terminated_rows = trajectory[trajectory["terminated"].astype(bool)]
    if terminated_rows.empty:
        return {"terminated": False, "shutdown_time_h": np.nan, "shutdown_code": 0.0, "shutdown_message": ""}
    row = terminated_rows.iloc[0]
    return {
        "terminated": True,
        "shutdown_time_h": float(row["time"]),
        "shutdown_code": float(row["shutdown_code"]),
        "shutdown_message": str(row["shutdown_message"]),
    }


def basic_trajectory_metrics(trajectory: pd.DataFrame) -> dict[str, float]:
    time = trajectory["time"].to_numpy(dtype=float)
    pressure = trajectory["measurement.reactor_pressure"].to_numpy(dtype=float)
    reactor_temp = trajectory["measurement.reactor_temperature"].to_numpy(dtype=float)
    pressure_limit = 3000.0
    pressure_violation = np.maximum(pressure - pressure_limit, 0.0)
    return {
        "samples": float(len(trajectory)),
        "final_time_h": float(time[-1]) if len(time) else 0.0,
        "max_reactor_pressure_kpa_gauge": float(np.max(pressure)) if len(pressure) else np.nan,
        "max_reactor_pressure_violation_kpa": float(np.max(pressure_violation)) if len(pressure_violation) else 0.0,
        "max_reactor_temperature_deg_c": float(np.max(reactor_temp)) if len(reactor_temp) else np.nan,
    }


def trajectory_error(reference: pd.Series, candidate: pd.Series) -> dict[str, float]:
    aligned = pd.concat([reference.rename("reference"), candidate.rename("candidate")], axis=1).dropna()
    if aligned.empty:
        return {"rmse": np.nan, "mae": np.nan, "max_abs_error": np.nan}
    error = aligned["candidate"].to_numpy(dtype=float) - aligned["reference"].to_numpy(dtype=float)
    return {
        "rmse": float(np.sqrt(np.mean(error**2))),
        "mae": float(np.mean(np.abs(error))),
        "max_abs_error": float(np.max(np.abs(error))),
    }


def solver_disagreement(trajectories: dict[str, pd.DataFrame], column: str) -> pd.DataFrame:
    if len(trajectories) < 2:
        return pd.DataFrame()
    base_name = next(iter(trajectories))
    base = trajectories[base_name].set_index("time")[column]
    rows = []
    for name, trajectory in trajectories.items():
        if name == base_name:
            continue
        candidate = trajectory.set_index("time")[column]
        row = {"reference_solver": base_name, "candidate_solver": name, "column": column}
        row.update(trajectory_error(base, candidate))
        rows.append(row)
    return pd.DataFrame(rows)

