from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

from tep_studio import TEP_SCHEMA, TennesseeEastmanProcess
from tep_studio.control.config import process_description_hash


def _normalized_reference_text(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        value.lower().replace("&", " and ").replace("sperator", "separator"),
    )


def _legacy_c_source() -> str:
    source_path = Path(__file__).resolve().parents[4] / "temexd_mod" / "temexd_mod.c"
    return source_path.read_text(encoding="latin-1")


def _legacy_measurement_rows() -> dict[int, tuple[str, str]]:
    source = _legacy_c_source()
    table = source.split("Output 1 - Measured Values", 1)[1].split(
        "Output 2 - Monitoring", 1
    )[0]
    rows: dict[int, list[str]] = {}
    current: int | None = None
    for line in table.splitlines():
        match = re.match(r"\s*(\d+)\s*\|([^|]*)\|([^|]*)", line)
        if match:
            index = int(match.group(1))
            current = index if 1 <= index <= 41 else None
            if current is not None:
                rows[current] = [match.group(2).strip(), match.group(3).strip()]
            continue
        continuation = re.match(r"\s*\|([^|]*)\|([^|]*)", line)
        if current is not None and continuation:
            rows[current][0] += " " + continuation.group(1).strip()
    return {index: (values[0], values[1]) for index, values in rows.items()}


def test_schema_conformance_validation_passes() -> None:
    validation = TEP_SCHEMA.validate()

    assert validation["ok"] is True
    assert validation["errors"] == []
    assert validation["checks"]["measurements.count"] is True
    assert validation["checks"]["manipulated_variables.count"] is True
    assert validation["checks"]["disturbances.count"] is True


def test_standard_measurements_match_legacy_c_interface_table() -> None:
    """Cross-check the schema against the independently embedded C source table."""
    reference = _legacy_measurement_rows()

    assert list(reference) == list(range(1, 42))
    for index, variable in enumerate(TEP_SCHEMA.measurements, start=1):
        description, unit = reference[index]
        assert _normalized_reference_text(variable.description) == _normalized_reference_text(description)
        assert _normalized_reference_text(variable.unit) == _normalized_reference_text(
            unit.replace("°C", "degC").replace("m³/h", "m3/h")
        )


def test_availability_timing_and_bounds_match_legacy_c_source() -> None:
    source = _legacy_c_source()

    assert "Output 1 with outputs 1 through 41 is the default" in source
    assert all(variable.available_online for variable in TEP_SCHEMA.measurements)
    assert "teproc_.tgas = (float).1" in source
    assert "teproc_.tprod = (float).25" in source
    assert "teproc_.tgas += (float).1" in source
    assert "teproc_.tprod += (float).25" in source
    assert "Constraints of Manipulated Variable" in source
    assert "teproc_.vcv[i__ - 1] < (float)0." in source
    assert "teproc_.vcv[i__ - 1] > (float)100." in source
    assert "dvec_.idv[i__ - 1] < (float)0." in source
    assert "dvec_.idv[i__ - 1] > (float)1." in source
    assert "*uPtrs[i + NU] >= 0.5" in source


def test_measurement_availability_and_analyzer_timing() -> None:
    continuous = TEP_SCHEMA.measurements[:22]
    gas_analyzers = TEP_SCHEMA.measurements[22:36]
    product_analyzers = TEP_SCHEMA.measurements[36:41]

    assert all(variable.available_online for variable in TEP_SCHEMA.measurements)
    assert all(
        variable.update_mode == "continuous" and variable.sample_period_hours is None and variable.delay_samples == 0
        for variable in continuous
    )
    assert all(
        variable.update_mode == "sample_and_hold"
        and variable.sample_period_hours == 0.1
        and variable.delay_samples == 1
        for variable in gas_analyzers
    )
    assert all(
        variable.update_mode == "sample_and_hold"
        and variable.sample_period_hours == 0.25
        and variable.delay_samples == 1
        for variable in product_analyzers
    )


def test_legacy_aliases_disambiguate_idv15_and_xmeas22() -> None:
    idv15 = TEP_SCHEMA.variable("disturbances", "IDV15")
    xmeas22 = TEP_SCHEMA.variable("measurements", "XMEAS22")

    assert idv15.legacy_symbol == "IDV(15)"
    assert idv15.description == "Separator cooling water valve stiction"
    assert xmeas22.legacy_symbol == "XMEAS(22)"
    assert xmeas22.name == "condenser_cooling_water_outlet_temperature"


def test_action_and_native_rng_semantics_are_explicit() -> None:
    assert "external request" in TEP_SCHEMA.requested_action_semantics
    assert "saturation" in TEP_SCHEMA.implemented_action_semantics
    assert TEP_SCHEMA.wrapper_rate_limit is False
    assert "inside the legacy kernel" in TEP_SCHEMA.actuator_semantics
    assert "measurement noise" in TEP_SCHEMA.native_rng_semantics
    assert "stochastic disturbances" in TEP_SCHEMA.native_rng_semantics
    assert "binary latched activations" in TEP_SCHEMA.disturbance_input_semantics
    assert {
        variable.legacy_symbol for variable in TEP_SCHEMA.disturbances if variable.root_cause_status == "unknown"
    } == {"IDV(16)", "IDV(17)", "IDV(18)", "IDV(20)"}


def test_safety_constraints_are_published_and_compute_margins() -> None:
    assert len(TEP_SCHEMA.constraints) == 8
    measurements = [0.0] * len(TEP_SCHEMA.measurements)
    measurements[TEP_SCHEMA.index("measurements", "reactor_pressure")] = 2900.0
    measurements[TEP_SCHEMA.index("measurements", "reactor_level")] = 50.0
    measurements[TEP_SCHEMA.index("measurements", "reactor_temperature")] = 170.0
    measurements[TEP_SCHEMA.index("measurements", "separator_level")] = 50.0
    measurements[TEP_SCHEMA.index("measurements", "stripper_level")] = 50.0
    margins = TEP_SCHEMA.constraint_margins(measurements)
    assert margins["reactor_pressure_high"] == 100.0
    assert margins["reactor_temperature_high"] == 5.0


def test_conformance_report_is_generated_and_json_serializable() -> None:
    report = TEP_SCHEMA.conformance_report()

    assert report["validation"]["ok"] is True
    assert report["role_counts"]["measurements"] == 41
    assert report["role_counts"]["manipulated_variables"] == 12
    assert report["role_counts"]["disturbances"] == 28
    assert len(report["variables"]) == sum(report["role_counts"].values())
    assert json.loads(json.dumps(report, allow_nan=False))["schema"] == TEP_SCHEMA.name


def test_process_description_hash_covers_full_canonical_description() -> None:
    changed_unit_policy = replace(TEP_SCHEMA, external_unit_policy="different policy")
    changed_measurement = replace(
        TEP_SCHEMA,
        measurements=(
            replace(TEP_SCHEMA.measurements[0], unit="different unit"),
            *TEP_SCHEMA.measurements[1:],
        ),
    )

    assert process_description_hash() == process_description_hash(TEP_SCHEMA)
    assert process_description_hash(changed_unit_policy) != process_description_hash(TEP_SCHEMA)
    assert process_description_hash(changed_measurement) != process_description_hash(TEP_SCHEMA)


def test_simulator_validation_includes_schema_audit() -> None:
    validation = TennesseeEastmanProcess().validate()

    assert validation["ok"] is True
    assert validation["checks"]["schema.measurements.gas_analyzer_timing"] is True
    assert validation["checks"]["schema.action.no_wrapper_rate_limit"] is True
