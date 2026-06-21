"""Editable view of the controller tuning, and a seam to apply overrides.

The controller is defined by ``RICKER_MODE1`` (a ``RickerRegistry`` of declarative
loop/override/nominal data). This module exposes that tuning as a flat, ordered
catalogue of ``parameter -> value`` rows (for an editable table) and an
``apply_tuning`` function that returns a registry with a subset of those values
overridden — without mutating the shared default. Parameter keys are dotted paths:

    <pi_loop>.kc / <pi_loop>.ti_hours          e.g. "reactor_pressure.kc"
    feed.<feed loop name>.kc / .ti_hours        e.g. "feed.A feed.kc"
    override.<override name>.threshold / .gain   e.g. "override.high_pressure_to_production.gain"
    nominal.production_sp_rate_limit / .pct_g_sp_rate_limit
"""

from __future__ import annotations

import dataclasses as dc

from tep_studio.control.loops import RickerRegistry
from tep_studio.control.registry import RICKER_MODE1

# The named positional PI loops, in display order.
_PI_FIELDS = (
    "production",
    "reactor_level",
    "reactor_pressure",
    "reactor_temperature",
    "separator_level",
    "separator_temperature",
    "stripper_level",
    "pct_g",
    "ya",
    "yac",
)


def tuning_rows(registry: RickerRegistry = RICKER_MODE1) -> list[dict]:
    """The full editable catalogue as ``[{group, parameter, value}, ...]`` rows."""
    rows: list[dict] = []

    def add(group: str, key: str, value) -> None:
        rows.append({"group": group, "parameter": key, "value": None if value is None else float(value)})

    for field in _PI_FIELDS:
        loop = getattr(registry, field)
        add("PI loop", f"{field}.kc", loop.kc)
        add("PI loop", f"{field}.ti_hours", loop.ti_hours)
    for loop in registry.feed_loops:
        add("Feed loop", f"feed.{loop.name}.kc", loop.kc)
        add("Feed loop", f"feed.{loop.name}.ti_hours", loop.ti_hours)
    for ov in registry.overrides:
        add("Override", f"override.{ov.name}.threshold", ov.threshold)
        add("Override", f"override.{ov.name}.gain", ov.gain)
    add("Setpoint ramp", "nominal.production_sp_rate_limit", registry.nominal.production_sp_rate_limit)
    add("Setpoint ramp", "nominal.pct_g_sp_rate_limit", registry.nominal.pct_g_sp_rate_limit)
    return rows


def tuning_defaults(registry: RickerRegistry = RICKER_MODE1) -> dict[str, float]:
    """Flat ``parameter -> default value`` map (the source of truth for valid keys)."""
    return {r["parameter"]: r["value"] for r in tuning_rows(registry)}


def apply_tuning(registry: RickerRegistry, overrides: dict[str, float]) -> RickerRegistry:
    """Return a copy of ``registry`` with ``overrides`` applied (default unchanged)."""
    if not overrides:
        return registry

    pi: dict[str, dict[str, float]] = {}
    feed: dict[str, dict[str, float]] = {}
    ovr: dict[str, dict[str, float]] = {}
    nominal: dict[str, float] = {}
    for key, value in overrides.items():
        value = float(value)
        parts = key.split(".")
        head = parts[0]
        if head == "feed":
            feed.setdefault(".".join(parts[1:-1]), {})[parts[-1]] = value
        elif head == "override":
            ovr.setdefault(".".join(parts[1:-1]), {})[parts[-1]] = value
        elif head == "nominal":
            nominal[parts[1]] = value
        else:
            pi.setdefault(head, {})[parts[1]] = value

    repl: dict[str, object] = {field: dc.replace(getattr(registry, field), **changes) for field, changes in pi.items()}
    if feed:
        repl["feed_loops"] = tuple(dc.replace(loop, **feed[loop.name]) if loop.name in feed else loop for loop in registry.feed_loops)
    if ovr:
        repl["overrides"] = tuple(dc.replace(o, **ovr[o.name]) if o.name in ovr else o for o in registry.overrides)
    if nominal:
        repl["nominal"] = dc.replace(registry.nominal, **nominal)
    return dc.replace(registry, **repl)
