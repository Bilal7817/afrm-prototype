"""Pre-departure fuel planning and dispatch check (REQ-01, REQ-02).

The same steady-cruise model is used here and in the in-flight monitor:
fuel = fuel flow x time, with time = distance / ground speed.
"""

from __future__ import annotations

from afrm.models import AfrmConfig, DispatchStatus, FuelPlan


def plan_fuel(config: AfrmConfig) -> FuelPlan:
    """Calculate the minimum block fuel components (REQ-01)."""
    aircraft = config.aircraft
    route = config.route
    policy = config.reserve_policy

    trip_time_h = route.trip_distance_km / aircraft.planned_ground_speed_km_h
    trip_kg = aircraft.cruise_fuel_flow_kg_h * trip_time_h
    alternate_time_h = route.alternate_distance_km / aircraft.planned_ground_speed_km_h

    return FuelPlan(
        trip_time_h=trip_time_h,
        taxi_kg=aircraft.taxi_fuel_kg,
        trip_kg=trip_kg,
        contingency_kg=policy.contingency_fraction * trip_kg,
        alternate_kg=aircraft.cruise_fuel_flow_kg_h * alternate_time_h,
        final_reserve_kg=aircraft.holding_fuel_flow_kg_h * policy.final_reserve_h,
    )


def check_dispatch(plan: FuelPlan, loaded_fuel_kg: float) -> DispatchStatus:
    """DISPATCHABLE when loaded fuel is at least minimum block fuel (REQ-02)."""
    if loaded_fuel_kg >= plan.minimum_block_fuel_kg:
        return DispatchStatus.DISPATCHABLE
    return DispatchStatus.NOT_DISPATCHABLE
