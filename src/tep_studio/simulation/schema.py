from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike


ROLE_ALIASES = {
    "state": "states",
    "states": "states",
    "measurement": "measurements",
    "measurements": "measurements",
    "manipulated_variable": "manipulated_variables",
    "manipulated_variables": "manipulated_variables",
    "mv": "manipulated_variables",
    "mvs": "manipulated_variables",
    "disturbance": "disturbances",
    "disturbances": "disturbances",
}

VARIABLE_ROLES = {
    "states",
    "manipulated_variables",
    "disturbances",
    "measurements",
    "additional_measurements",
    "disturbance_monitors",
    "process_monitors",
    "concentration_monitors",
}


@dataclass(frozen=True)
class Variable:
    name: str
    unit: str
    role: str
    index: int
    description: str
    lower: float | None = None
    upper: float | None = None
    nominal: float | None = None
    available_online: bool = True
    legacy_symbol: str | None = None
    legacy_index: int | None = None
    stream: str | None = None
    component: str | None = None
    physical_type: str | None = None
    measurement_noise: str | None = None
    sample_period: str | None = None


@dataclass(frozen=True)
class ProcessSchema:
    name: str
    states: tuple[Variable, ...]
    manipulated_variables: tuple[Variable, ...]
    disturbances: tuple[Variable, ...]
    measurements: tuple[Variable, ...]
    additional_measurements: tuple[Variable, ...]
    disturbance_monitors: tuple[Variable, ...]
    process_monitors: tuple[Variable, ...]
    concentration_monitors: tuple[Variable, ...]
    time_unit: str = "h"
    internal_unit_policy: str = "legacy_temexd_mod"
    external_unit_policy: str = "schema documents SI-facing names; kernel values remain legacy TEP values"

    def names(self, role: str) -> list[str]:
        variables = self._variables_for_role(role)
        return [variable.name for variable in variables]

    def variable(self, role: str, name: str) -> Variable:
        variables = self._variables_for_role(role)
        for variable in variables:
            if variable.name == name:
                return variable
        valid_names = ", ".join(variable.name for variable in variables)
        raise KeyError(f"Unknown {self._canonical_role(role)} variable {name!r}. Valid names: {valid_names}.")

    def index(self, role: str, name: str) -> int:
        return self.variable(role, name).index

    def vector(
        self,
        role: str,
        values: Mapping[str, float] | ArrayLike | None = None,
        *,
        base: ArrayLike | None = None,
    ) -> np.ndarray:
        variables = self._variables_for_role(role)
        length = len(variables)
        if values is not None and not isinstance(values, Mapping):
            array = np.asarray(values, dtype=np.float64)
            if array.shape != (length,):
                raise ValueError(f"Expected shape ({length},) for {self._canonical_role(role)}, got {array.shape}.")
            return np.ascontiguousarray(array, dtype=np.float64)

        if base is None:
            result = np.zeros(length, dtype=np.float64)
        else:
            result = np.asarray(base, dtype=np.float64).copy()
            if result.shape != (length,):
                raise ValueError(f"Expected base shape ({length},) for {self._canonical_role(role)}, got {result.shape}.")

        if values is not None:
            for name, value in values.items():
                result[self.index(role, name)] = float(value)
        return np.ascontiguousarray(result, dtype=np.float64)

    def update_vector(self, role: str, base: ArrayLike, values: Mapping[str, float]) -> np.ndarray:
        return self.vector(role, values, base=base)

    def to_dict(self, role: str, values: ArrayLike) -> dict[str, float]:
        variables = self._variables_for_role(role)
        array = np.asarray(values, dtype=np.float64)
        if array.shape != (len(variables),):
            raise ValueError(f"Expected shape ({len(variables)},) for {self._canonical_role(role)}, got {array.shape}.")
        return {variable.name: float(value) for variable, value in zip(variables, array)}

    def _variables_for_role(self, role: str) -> tuple[Variable, ...]:
        canonical = self._canonical_role(role)
        return getattr(self, canonical)

    def _canonical_role(self, role: str) -> str:
        canonical = ROLE_ALIASES.get(role, role)
        if canonical not in VARIABLE_ROLES:
            valid_roles = ", ".join(sorted(set(ROLE_ALIASES) | VARIABLE_ROLES))
            raise KeyError(f"Unknown schema role {role!r}. Valid roles: {valid_roles}.")
        return canonical


STATE_DESCRIPTIONS = [
    ("reactor_vapor_A_holdup", "lb-mol", "Holdup of component A in vapor phase of reactor"),
    ("reactor_vapor_B_holdup", "lb-mol", "Holdup of component B in vapor phase of reactor"),
    ("reactor_vapor_C_holdup", "lb-mol", "Holdup of component C in vapor phase of reactor"),
    ("reactor_liquid_D_holdup", "lb-mol", "Holdup of component D in liquid phase of reactor"),
    ("reactor_liquid_E_holdup", "lb-mol", "Holdup of component E in liquid phase of reactor"),
    ("reactor_liquid_F_holdup", "lb-mol", "Holdup of component F in liquid phase of reactor"),
    ("reactor_liquid_G_holdup", "lb-mol", "Holdup of component G in liquid phase of reactor"),
    ("reactor_liquid_H_holdup", "lb-mol", "Holdup of component H in liquid phase of reactor"),
    ("reactor_internal_energy", "MMBTU", "Internal energy of reactor"),
    ("separator_vapor_A_holdup", "lb-mol", "Holdup of component A in vapor phase of separator"),
    ("separator_vapor_B_holdup", "lb-mol", "Holdup of component B in vapor phase of separator"),
    ("separator_vapor_C_holdup", "lb-mol", "Holdup of component C in vapor phase of separator"),
    ("separator_liquid_D_holdup", "lb-mol", "Holdup of component D in liquid phase of separator"),
    ("separator_liquid_E_holdup", "lb-mol", "Holdup of component E in liquid phase of separator"),
    ("separator_liquid_F_holdup", "lb-mol", "Holdup of component F in liquid phase of separator"),
    ("separator_liquid_G_holdup", "lb-mol", "Holdup of component G in liquid phase of separator"),
    ("separator_liquid_H_holdup", "lb-mol", "Holdup of component H in liquid phase of separator"),
    ("separator_internal_energy", "MMBTU", "Internal energy of separator"),
    ("stripper_liquid_A_holdup", "lb-mol", "Holdup of component A in stripper sump"),
    ("stripper_liquid_B_holdup", "lb-mol", "Holdup of component B in stripper sump"),
    ("stripper_liquid_C_holdup", "lb-mol", "Holdup of component C in stripper sump"),
    ("stripper_liquid_D_holdup", "lb-mol", "Holdup of component D in stripper sump"),
    ("stripper_liquid_E_holdup", "lb-mol", "Holdup of component E in stripper sump"),
    ("stripper_liquid_F_holdup", "lb-mol", "Holdup of component F in stripper sump"),
    ("stripper_liquid_G_holdup", "lb-mol", "Holdup of component G in stripper sump"),
    ("stripper_liquid_H_holdup", "lb-mol", "Holdup of component H in stripper sump"),
    ("stripper_internal_energy", "MMBTU", "Internal energy of stripper sump"),
    ("header_vapor_A_holdup", "lb-mol", "Holdup of component A in stream 6 header"),
    ("header_vapor_B_holdup", "lb-mol", "Holdup of component B in stream 6 header"),
    ("header_vapor_C_holdup", "lb-mol", "Holdup of component C in stream 6 header"),
    ("header_vapor_D_holdup", "lb-mol", "Holdup of component D in stream 6 header"),
    ("header_vapor_E_holdup", "lb-mol", "Holdup of component E in stream 6 header"),
    ("header_vapor_F_holdup", "lb-mol", "Holdup of component F in stream 6 header"),
    ("header_vapor_G_holdup", "lb-mol", "Holdup of component G in stream 6 header"),
    ("header_vapor_H_holdup", "lb-mol", "Holdup of component H in stream 6 header"),
    ("header_internal_energy", "MMBTU", "Internal energy of stream 6 header"),
    ("reactor_cooling_water_outlet_temperature", "degC", "Temperature cooling water outlet of reactor"),
    ("separator_cooling_water_outlet_temperature", "degC", "Temperature cooling water outlet of separator"),
]

XMV_DESCRIPTIONS = [
    ("d_feed_valve", "Valve position feed component D (stream 2)"),
    ("e_feed_valve", "Valve position feed component E (stream 3)"),
    ("a_feed_valve", "Valve position feed component A (stream 1)"),
    ("ac_feed_valve", "Valve position feed components A and C (stream 4)"),
    ("compressor_recycle_valve", "Valve position compressor recycle"),
    ("purge_valve", "Valve position purge (stream 9)"),
    ("separator_underflow_valve", "Valve position underflow separator (stream 10)"),
    ("stripper_underflow_valve", "Valve position underflow stripper (stream 11)"),
    ("stripper_steam_valve", "Valve position stripper steam"),
    ("reactor_cooling_water_valve", "Valve position cooling water outlet of reactor"),
    ("separator_cooling_water_valve", "Valve position cooling water outlet of separator"),
    ("reactor_agitator_speed", "Rotation of agitator of reactor"),
]

MEASUREMENT_DESCRIPTIONS = [
    ("feed_A_flow", "kscmh", "Feed flow component A (stream 1)"),
    ("feed_D_flow", "kg/h", "Feed flow component D (stream 2)"),
    ("feed_E_flow", "kg/h", "Feed flow component E (stream 3)"),
    ("feed_AC_flow", "kscmh", "Feed flow components A and C (stream 4)"),
    ("recycle_flow", "kscmh", "Recycle flow to reactor from separator (stream 8)"),
    ("reactor_feed_flow", "kscmh", "Reactor feed (stream 6)"),
    ("reactor_pressure", "kPa gauge", "Reactor pressure"),
    ("reactor_level", "%", "Reactor level"),
    ("reactor_temperature", "degC", "Reactor temperature"),
    ("purge_flow", "kscmh", "Purge flow (stream 9)"),
    ("separator_temperature", "degC", "Separator temperature"),
    ("separator_level", "%", "Separator level"),
    ("separator_pressure", "kPa gauge", "Separator pressure"),
    ("separator_underflow", "m3/h", "Separator underflow liquid phase"),
    ("stripper_level", "%", "Stripper level"),
    ("stripper_pressure", "kPa gauge", "Stripper pressure"),
    ("stripper_underflow", "m3/h", "Stripper underflow (stream 11)"),
    ("stripper_temperature", "degC", "Stripper temperature"),
    ("stripper_steam_flow", "kg/h", "Stripper steam flow"),
    ("compressor_work", "kW", "Compressor work"),
    ("reactor_cooling_water_outlet_temperature_meas", "degC", "Reactor cooling water outlet temperature"),
    ("condenser_cooling_water_outlet_temperature", "degC", "Condenser cooling water outlet temperature"),
]

MEASURED_COMPOSITION_DESCRIPTIONS = [
    ("reactor_feed_A_concentration", "stream 6", "A", "Concentration of A in reactor feed (stream 6)"),
    ("reactor_feed_B_concentration", "stream 6", "B", "Concentration of B in reactor feed (stream 6)"),
    ("reactor_feed_C_concentration", "stream 6", "C", "Concentration of C in reactor feed (stream 6)"),
    ("reactor_feed_D_concentration", "stream 6", "D", "Concentration of D in reactor feed (stream 6)"),
    ("reactor_feed_E_concentration", "stream 6", "E", "Concentration of E in reactor feed (stream 6)"),
    ("reactor_feed_F_concentration", "stream 6", "F", "Concentration of F in reactor feed (stream 6)"),
    ("purge_A_concentration", "stream 9", "A", "Concentration of A in purge (stream 9)"),
    ("purge_B_concentration", "stream 9", "B", "Concentration of B in purge (stream 9)"),
    ("purge_C_concentration", "stream 9", "C", "Concentration of C in purge (stream 9)"),
    ("purge_D_concentration", "stream 9", "D", "Concentration of D in purge (stream 9)"),
    ("purge_E_concentration", "stream 9", "E", "Concentration of E in purge (stream 9)"),
    ("purge_F_concentration", "stream 9", "F", "Concentration of F in purge (stream 9)"),
    ("purge_G_concentration", "stream 9", "G", "Concentration of G in purge (stream 9)"),
    ("purge_H_concentration", "stream 9", "H", "Concentration of H in purge (stream 9)"),
    ("stripper_underflow_D_concentration", "stream 11", "D", "Concentration of D in stripper underflow (stream 11)"),
    ("stripper_underflow_E_concentration", "stream 11", "E", "Concentration of E in stripper underflow (stream 11)"),
    ("stripper_underflow_F_concentration", "stream 11", "F", "Concentration of F in stripper underflow (stream 11)"),
    ("stripper_underflow_G_concentration", "stream 11", "G", "Concentration of G in stripper underflow (stream 11)"),
    ("stripper_underflow_H_concentration", "stream 11", "H", "Concentration of H in stripper underflow (stream 11)"),
]

DISTURBANCE_DESCRIPTIONS = [
    "A/C ratio of stream 4, B composition constant",
    "B composition of stream 4, A/C ratio constant",
    "D feed temperature",
    "Reactor cooling water inlet temperature",
    "Separator cooling water inlet temperature",
    "A feed loss",
    "C header pressure loss",
    "Random A/B/C composition of stream 4",
    "Random D feed temperature",
    "Random C feed temperature",
    "Random reactor cooling water inlet temperature",
    "Random separator cooling water inlet temperature",
    "Reaction kinetics drift",
    "Reactor cooling water valve stiction",
    "Separator cooling water valve stiction",
    "Random stripper heat transfer deviation",
    "Random reactor heat transfer deviation",
    "Random condenser heat transfer deviation",
    "Valve stiction group",
    "Unknown random disturbance",
    "Random A feed temperature",
    "Random E feed temperature",
    "Random A feed pressure/flow",
    "Random D feed pressure/flow",
    "Random E feed pressure/flow",
    "Random A and C feed pressure/flow",
    "Random reactor cooling water pressure/flow",
    "Random condenser cooling water pressure/flow",
]


def _variables(items: list[tuple[str, str, str]], role: str, offset: int = 0) -> tuple[Variable, ...]:
    return tuple(
        Variable(name=name, unit=unit, role=role, index=i + offset, description=description)
        for i, (name, unit, description) in enumerate(items)
    )


def _measured_compositions() -> tuple[Variable, ...]:
    return tuple(
        Variable(
            name=name,
            unit="mol %",
            role="measurement",
            index=i + 22,
            description=description,
            legacy_symbol=f"XMEAS({i + 23})",
            legacy_index=i + 23,
            stream=stream,
            component=component,
            physical_type="composition",
            measurement_noise="legacy measured analyzer output",
        )
        for i, (name, stream, component, description) in enumerate(MEASURED_COMPOSITION_DESCRIPTIONS)
    )


ADDITIONAL_MEASUREMENT_DESCRIPTIONS = [
    ("feed_A_temperature", "degC", "Feed component A temperature (stream 1)", "stream 1", None, "temperature"),
    ("feed_D_temperature", "degC", "Feed component D temperature (stream 2)", "stream 2", None, "temperature"),
    ("feed_E_temperature", "degC", "Feed component E temperature (stream 3)", "stream 3", None, "temperature"),
    ("feed_AC_temperature", "degC", "Feed components A and C temperature (stream 4)", "stream 4", None, "temperature"),
    ("reactor_cooling_water_inlet_temperature", "degC", "Reactor cooling-water inlet temperature", None, None, "temperature"),
    ("reactor_cooling_water_flow", "m3/h", "Reactor cooling-water flow", None, None, "flow"),
    ("condenser_cooling_water_inlet_temperature", "degC", "Condenser cooling-water inlet temperature", None, None, "temperature"),
    ("condenser_cooling_water_flow", "m3/h", "Condenser cooling-water flow", None, None, "flow"),
]

for stream_name, stream_label in (
    ("feed_A", "stream 1"),
    ("feed_D", "stream 2"),
    ("feed_E", "stream 3"),
    ("feed_AC", "stream 4"),
):
    for component in ("A", "B", "C", "D", "E", "F"):
        ADDITIONAL_MEASUREMENT_DESCRIPTIONS.append(
            (
                f"{stream_name}_{component}_concentration",
                "mol %",
                f"Concentration of {component} in {stream_name.replace('_', ' ')} ({stream_label})",
                stream_label,
                component,
                "composition",
            )
        )


DISTURBANCE_MONITOR_DESCRIPTIONS = [
    ("idv08_stream4_A_concentration", "mol %", "IDV(8) concentration of component A in stream 4"),
    ("idv08_stream4_B_concentration", "mol %", "IDV(8) concentration of component B in stream 4"),
    ("idv08_stream4_C_concentration", "mol %", "IDV(8) concentration of component C in stream 4"),
    ("idv09_D_feed_temperature", "degC", "IDV(9) feed component D temperature (stream 2)"),
    ("idv10_AC_feed_temperature", "degC", "IDV(10) feed components A and C temperature (stream 4)"),
    ("idv11_reactor_cooling_water_inlet_temperature", "degC", "IDV(11) reactor cooling-water inlet temperature"),
    ("idv12_condenser_cooling_water_inlet_temperature", "degC", "IDV(12) condenser cooling-water inlet temperature"),
    ("idv13_reaction_1_kinetics_deviation", "1", "IDV(13) kinetics deviation for reaction A + C + D -> G"),
    ("idv13_reaction_2_kinetics_deviation", "1", "IDV(13) kinetics deviation for reaction A + C + E -> F"),
    ("idv16_stripper_heat_transfer_deviation", "1", "IDV(16) stripper heat-transfer deviation"),
    ("idv17_reactor_heat_transfer_deviation", "1", "IDV(17) reactor heat-transfer deviation"),
    ("idv18_condenser_heat_transfer_deviation", "1", "IDV(18) condenser heat-transfer deviation"),
    ("idv20_unknown_random_disturbance", "legacy", "IDV(20) unknown random disturbance monitor"),
    ("idv21_A_feed_temperature", "degC", "IDV(21) feed component A temperature (stream 1)"),
    ("idv22_E_feed_temperature", "degC", "IDV(22) feed component E temperature (stream 3)"),
    ("idv23_A_feed_pressure_flow_deviation", "kmol/h", "IDV(23) feed component A pressure/flow deviation (stream 1)"),
    ("idv24_D_feed_pressure_flow_deviation", "kmol/h", "IDV(24) feed component D pressure/flow deviation (stream 2)"),
    ("idv25_E_feed_pressure_flow_deviation", "kmol/h", "IDV(25) feed component E pressure/flow deviation (stream 3)"),
    ("idv26_AC_feed_pressure_flow_deviation", "kmol/h", "IDV(26) feed components A and C pressure/flow deviation (stream 4)"),
    ("idv27_reactor_cooling_water_flow_deviation", "m3/h", "IDV(27) reactor cooling-water supply pressure/flow deviation"),
    ("idv28_condenser_cooling_water_flow_deviation", "m3/h", "IDV(28) condenser cooling-water supply pressure/flow deviation"),
]


PROCESS_MONITOR_DESCRIPTIONS = [
    ("reactor_A_consumption", "kmol/h", "Consumption of component A in reactor; value is negative"),
    ("reactor_C_consumption", "kmol/h", "Consumption of component C in reactor; value is negative"),
    ("reactor_D_consumption", "kmol/h", "Consumption of component D in reactor; value is negative"),
    ("reactor_E_consumption", "kmol/h", "Consumption of component E in reactor; value is negative"),
    ("reactor_F_generation", "kmol/h", "Generation of component F in reactor; value is positive"),
    ("reactor_G_generation", "kmol/h", "Generation of component G in reactor; value is positive"),
    ("reactor_H_generation", "kmol/h", "Generation of component H in reactor; value is positive"),
]

for component in ("A", "B", "C", "D", "E", "F", "G", "H"):
    PROCESS_MONITOR_DESCRIPTIONS.append(
        (f"reactor_{component}_partial_pressure", "kPa abs", f"Partial pressure of component {component} in reactor")
    )
for stream_name, stream_label, components in (
    ("reactor_feed", "stream 6", ("A", "B", "C", "D", "E", "F")),
    ("purge", "stream 9", ("A", "B", "C", "D", "E", "F", "G", "H")),
    ("stripper_underflow", "stream 11", ("H", "D", "E", "F", "G")),
    ("feed_A", "stream 1", ("A", "B", "C", "D", "E", "F")),
    ("feed_D", "stream 2", ("A", "B", "C", "D", "E", "F")),
    ("feed_E", "stream 3", ("A", "B", "C", "D", "E", "F")),
    ("feed_AC", "stream 4", ("A", "B", "C", "D", "E", "F")),
):
    for component in components:
        PROCESS_MONITOR_DESCRIPTIONS.append(
            (
                f"delay_free_{stream_name}_{component}_concentration",
                "mol %",
                f"Delay-free concentration of {component} in {stream_name.replace('_', ' ')} ({stream_label})",
            )
        )
PROCESS_MONITOR_DESCRIPTIONS += [
    ("production_cost_measured_per_product", "ct/kmol product", "Production cost based on measured noise-corrupted values per amount of product"),
    ("production_cost_internal_per_product", "ct/kmol product", "Production cost based on internal noise-free values per amount of product"),
    ("operating_cost_measured_per_hour", "$/h", "Operating cost based on measured noise-corrupted values per time"),
    ("operating_cost_internal_per_hour", "$/h", "Operating cost based on internal noise-free values per time"),
]


def _additional_measurements() -> tuple[Variable, ...]:
    return tuple(
        Variable(
            name=name,
            unit=unit,
            role="additional_measurement",
            index=i,
            description=description,
            legacy_symbol=f"XMEASADD({i + 1})",
            legacy_index=i + 42,
            stream=stream,
            component=component,
            physical_type=physical_type,
            measurement_noise="legacy additional measured output",
        )
        for i, (name, unit, description, stream, component, physical_type) in enumerate(ADDITIONAL_MEASUREMENT_DESCRIPTIONS)
    )


def _disturbance_monitors() -> tuple[Variable, ...]:
    return tuple(
        Variable(
            name=name,
            unit=unit,
            role="disturbance_monitor",
            index=i,
            description=description,
            legacy_symbol=f"XMEASDIST({i + 1})",
            legacy_index=i + 1,
            available_online=False,
            physical_type="disturbance_monitor",
            measurement_noise="noise-free monitor",
        )
        for i, (name, unit, description) in enumerate(DISTURBANCE_MONITOR_DESCRIPTIONS)
    )


def _process_monitors() -> tuple[Variable, ...]:
    return tuple(
        Variable(
            name=name,
            unit=unit,
            role="process_monitor",
            index=i,
            description=description,
            legacy_symbol=f"XMEASMONITOR({i + 1})",
            legacy_index=i + 1,
            available_online=False,
            physical_type="process_monitor",
            measurement_noise="internal monitor",
        )
        for i, (name, unit, description) in enumerate(PROCESS_MONITOR_DESCRIPTIONS)
    )


def _concentration_monitors() -> tuple[Variable, ...]:
    sections = (
        ("feed_D", "Feed component D (stream 2)", "stream 2"),
        ("feed_E", "Feed component E (stream 3)", "stream 3"),
        ("feed_A", "Feed component A (stream 1)", "stream 1"),
        ("feed_AC", "Feed components A and C (stream 4)", "stream 4"),
        ("stripper_overhead", "Stripper overhead (stream 5)", "stream 5"),
        ("reactor_feed", "Reactor feed (stream 6)", "stream 6"),
        ("reactor_effluent", "Reactor effluent (stream 7)", "stream 7"),
        ("recycle", "Recycle to reactor from separator (stream 8)", "stream 8"),
        ("purge", "Purge (stream 9)", "stream 9"),
        ("separator_underflow", "Separator underflow (stream 10)", "stream 10"),
        ("stripper_sump_inlet", "Stripper liquid entering sump", None),
        ("stripper_underflow", "Stripper underflow (stream 11)", "stream 11"),
    )
    variables: list[Variable] = []
    for section_index, (section_name, section_description, stream) in enumerate(sections):
        for component_index, component in enumerate(("A", "B", "C", "D", "E", "F", "G", "H")):
            index = section_index * 8 + component_index
            variables.append(
                Variable(
                    name=f"{section_name}_{component}_concentration",
                    unit="mol %",
                    role="concentration_monitor",
                    index=index,
                    description=f"Concentration of {component} in {section_description}",
                    legacy_symbol=f"XMEASCOMP({index + 1})",
                    legacy_index=index + 1,
                    stream=stream,
                    component=component,
                    physical_type="composition",
                    measurement_noise="internal concentration monitor",
                )
            )
    return tuple(variables)


states = _variables(STATE_DESCRIPTIONS, "state")
states += tuple(
    Variable(name=name, unit="%", role="state", index=i + 38, description=description, lower=0.0, upper=100.0)
    for i, (name, description) in enumerate(XMV_DESCRIPTIONS)
)

TEP_SCHEMA = ProcessSchema(
    name="modified_tennessee_eastman_process",
    states=states,
    manipulated_variables=tuple(
        Variable(name=name, unit="%", role="manipulated_variable", index=i, description=description, lower=0.0, upper=100.0)
        for i, (name, description) in enumerate(XMV_DESCRIPTIONS)
    ),
    disturbances=tuple(
        Variable(name=f"idv_{i + 1:02d}", unit="activation", role="disturbance", index=i, description=description, lower=0.0, upper=1.0)
        for i, description in enumerate(DISTURBANCE_DESCRIPTIONS)
    ),
    measurements=_variables(MEASUREMENT_DESCRIPTIONS, "measurement") + _measured_compositions(),
    additional_measurements=_additional_measurements(),
    disturbance_monitors=_disturbance_monitors(),
    process_monitors=_process_monitors(),
    concentration_monitors=_concentration_monitors(),
)
