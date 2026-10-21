"""Typed, immutable data models and JSON configuration loading.

Every quantity carries its unit in its name (``_kg``, ``_km``, ``_km_h``,
``_kg_h``, ``_s``, ``_h``) so that a unit mismatch is visible at the call site.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class DispatchStatus(StrEnum):
    """Pre-departure fuel check result (REQ-02)."""

    DISPATCHABLE = "DISPATCHABLE"
    NOT_DISPATCHABLE = "NOT DISPATCHABLE"


class FuelStatus(StrEnum):
    """In-flight fuel status (REQ-05, REQ-07)."""

    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"
    DATA_INVALID = "DATA INVALID"


@dataclass(frozen=True, slots=True)
class Aircraft:
    name: str
    cruise_fuel_flow_kg_h: float
    planned_ground_speed_km_h: float
    holding_fuel_flow_kg_h: float
    taxi_fuel_kg: float


@dataclass(frozen=True, slots=True)
class Route:
    origin: str
    destination: str
    alternate: str
    trip_distance_km: float
    alternate_distance_km: float


@dataclass(frozen=True, slots=True)
class ReservePolicy:
    contingency_fraction: float
    final_reserve_h: float


@dataclass(frozen=True, slots=True)
class MonitoringLimits:
    sample_interval_s: float
    max_gap_s: float
    smoothing_window: int
    fuel_flow_min_kg_h: float
    fuel_flow_max_kg_h: float
    ground_speed_min_km_h: float
    ground_speed_max_km_h: float


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    description: str
    loaded_fuel_kg: float
    headwind_after_km: float | None
    headwind_ground_speed_km_h: float | None


@dataclass(frozen=True, slots=True)
class NoiseModel:
    fuel_flow_rel_sigma: float
    fob_sigma_kg: float
    ground_speed_sigma_km_h: float


@dataclass(frozen=True, slots=True)
class AfrmConfig:
    aircraft: Aircraft
    route: Route
    reserve_policy: ReservePolicy
    monitoring: MonitoringLimits
    scenarios: tuple[Scenario, ...]
    noise: NoiseModel

    def scenario(self, name: str) -> Scenario:
        for scenario in self.scenarios:
            if scenario.name == name:
                return scenario
        known = ", ".join(s.name for s in self.scenarios)
        raise KeyError(f"Unknown scenario '{name}'. Known scenarios: {known}")


@dataclass(frozen=True, slots=True)
class FuelPlan:
    """Pre-departure fuel plan (REQ-01). All values in kg except trip time."""

    trip_time_h: float
    taxi_kg: float
    trip_kg: float
    contingency_kg: float
    alternate_kg: float
    final_reserve_kg: float

    @property
    def minimum_block_fuel_kg(self) -> float:
        return (
            self.taxi_kg
            + self.trip_kg
            + self.contingency_kg
            + self.alternate_kg
            + self.final_reserve_kg
        )

    @property
    def green_threshold_kg(self) -> float:
        """Landing fuel needed to still divert and land with final reserve."""
        return self.alternate_kg + self.final_reserve_kg

    @property
    def red_threshold_kg(self) -> float:
        return self.final_reserve_kg


@dataclass(frozen=True, slots=True)
class FuelSample:
    """One simulated sensor sample (REQ-10 units in field names)."""

    time_s: float
    fob_kg: float
    fuel_flow_kg_h: float
    ground_speed_km_h: float
    remaining_km: float


@dataclass(frozen=True, slots=True)
class Assessment:
    """Monitor output for one sample. Numeric fields are None when invalid."""

    time_s: float
    status: FuelStatus
    predicted_landing_fuel_kg: float | None
    endurance_h: float | None
    range_km: float | None
    reason: str = ""


# ------------------------------------------------------------------ loading


def _positive(value: float, field: str) -> float:
    if not value > 0:
        raise ValueError(f"Configuration value '{field}' must be > 0, got {value}")
    return value


def config_from_dict(raw: dict[str, Any]) -> AfrmConfig:
    """Build and validate an AfrmConfig from parsed JSON (REQ-08)."""
    aircraft = Aircraft(**raw["aircraft"])
    route = Route(**raw["route"])
    policy = ReservePolicy(**raw["reserve_policy"])
    monitoring = MonitoringLimits(**raw["monitoring"])
    scenarios = tuple(Scenario(**s) for s in raw["scenarios"])
    noise = NoiseModel(**raw["noise"])

    for field in (
        "cruise_fuel_flow_kg_h",
        "planned_ground_speed_km_h",
        "holding_fuel_flow_kg_h",
    ):
        _positive(getattr(aircraft, field), f"aircraft.{field}")
    _positive(route.trip_distance_km, "route.trip_distance_km")
    _positive(monitoring.sample_interval_s, "monitoring.sample_interval_s")
    if monitoring.smoothing_window < 1:
        raise ValueError("monitoring.smoothing_window must be >= 1")
    if not 0 <= policy.contingency_fraction < 1:
        raise ValueError("reserve_policy.contingency_fraction must be in [0, 1)")

    return AfrmConfig(aircraft, route, policy, monitoring, scenarios, noise)


def load_config(path: str | Path) -> AfrmConfig:
    """Load the JSON configuration file."""
    with Path(path).open(encoding="utf-8") as handle:
        raw: dict[str, Any] = json.load(handle)
    return config_from_dict(raw)
