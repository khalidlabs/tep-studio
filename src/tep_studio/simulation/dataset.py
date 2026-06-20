from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from tep_studio.simulation.core import AdvanceResult
from tep_studio.simulation.schema import TEP_SCHEMA, ProcessSchema


@dataclass(frozen=True)
class TrajectoryDataset:
    rows: tuple[dict[str, object], ...]
    schema: ProcessSchema = TEP_SCHEMA

    @classmethod
    def from_results(
        cls,
        results: Iterable[AdvanceResult],
        *,
        run_id: str = "run_000",
        scenario_id: str = "scenario_000",
        schema: ProcessSchema = TEP_SCHEMA,
    ) -> "TrajectoryDataset":
        rows: list[dict[str, object]] = []
        measurement_names = schema.names("measurements")
        state_names = schema.names("states")
        mv_names = schema.names("manipulated_variables")
        disturbance_names = schema.names("disturbances")
        for sample_index, result in enumerate(results):
            row: dict[str, object] = {
                "run_id": run_id,
                "scenario_id": scenario_id,
                "sample_index": sample_index,
                "time": result.time_end,
                "time_start": result.time_start,
                "time_end": result.time_end,
                "control_interval": result.control_interval,
                "is_initial": False,
                "terminated": result.shutdown_status["terminated"],
                "terminated_at_end": result.shutdown_status["terminated"],
                "shutdown_code": result.shutdown_status["code"],
            }
            row.update({f"measurement.{name}": float(value) for name, value in zip(measurement_names, result.measurements)})
            row.update({f"state.{name}": float(value) for name, value in zip(state_names, result.state)})
            row.update({f"requested_action.{name}": float(value) for name, value in zip(mv_names, result.requested_action)})
            row.update({f"implemented_action.{name}": float(value) for name, value in zip(mv_names, result.implemented_action)})
            row.update({f"disturbance.{name}": float(value) for name, value in zip(disturbance_names, result.disturbances)})
            row.update({f"objective.{name}": float(value) for name, value in result.objective_terms.items()})
            rows.append(row)
        return cls(tuple(rows), schema=schema)

    def to_pandas(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)

    def to_numpy(self, view: str = "measurement") -> tuple[np.ndarray, list[str]]:
        frame = self.to_pandas()
        aliases = {
            "measurements": "measurement",
            "states": "state",
            "requested_actions": "requested_action",
            "implemented_actions": "implemented_action",
            "disturbances": "disturbance",
        }
        view = aliases.get(view, view)
        prefix = f"{view}."
        columns = [column for column in frame.columns if column.startswith(prefix)]
        return frame[columns].to_numpy(dtype=np.float64), columns

    def to_csv(self, path: str | Path) -> None:
        self.to_pandas().to_csv(path, index=False)

    def to_parquet(self, path: str | Path) -> None:
        self.to_pandas().to_parquet(path, index=False)
