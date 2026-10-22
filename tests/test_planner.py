from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from afrm.models import AfrmConfig, DispatchStatus, FuelPlan, config_from_dict
from afrm.planner import check_dispatch
from tests.conftest import CONFIG_PATH


def _raw() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return raw


@pytest.mark.req("REQ-01")
def test_fuel_plan_components_match_hand_calculation(plan: FuelPlan) -> None:
    assert plan.trip_time_h == pytest.approx(1.875)
    assert plan.taxi_kg == pytest.approx(200.0)
    assert plan.trip_kg == pytest.approx(4500.0)
    assert plan.contingency_kg == pytest.approx(225.0)
    assert plan.alternate_kg == pytest.approx(750.0)
    assert plan.final_reserve_kg == pytest.approx(1000.0)
    assert plan.minimum_block_fuel_kg == pytest.approx(6675.0)


@pytest.mark.req("REQ-01", "REQ-05")
def test_status_thresholds_derived_from_plan(plan: FuelPlan) -> None:
    assert plan.green_threshold_kg == pytest.approx(1750.0)
    assert plan.red_threshold_kg == pytest.approx(1000.0)


@pytest.mark.req("REQ-02")
def test_exact_minimum_block_fuel_is_dispatchable(plan: FuelPlan) -> None:
    assert check_dispatch(plan, plan.minimum_block_fuel_kg) is DispatchStatus.DISPATCHABLE


@pytest.mark.req("REQ-02")
def test_just_below_minimum_block_fuel_is_not_dispatchable(plan: FuelPlan) -> None:
    loaded = plan.minimum_block_fuel_kg - 0.01
    assert check_dispatch(plan, loaded) is DispatchStatus.NOT_DISPATCHABLE


@pytest.mark.req("REQ-02")
@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("nominal", DispatchStatus.DISPATCHABLE),
        ("headwind", DispatchStatus.DISPATCHABLE),
        ("low_uplift", DispatchStatus.NOT_DISPATCHABLE),
    ],
)
def test_scenario_dispatch(
    config: AfrmConfig, plan: FuelPlan, scenario: str, expected: DispatchStatus
) -> None:
    assert check_dispatch(plan, config.scenario(scenario).loaded_fuel_kg) is expected


@pytest.mark.req("REQ-08")
def test_config_change_changes_plan_without_code_change() -> None:
    raw = _raw()
    raw["reserve_policy"]["final_reserve_h"] = 0.75
    from afrm.planner import plan_fuel

    plan = plan_fuel(config_from_dict(raw))
    assert plan.final_reserve_kg == pytest.approx(1500.0)


@pytest.mark.req("REQ-08")
@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("aircraft", "planned_ground_speed_km_h", 0.0),
        ("aircraft", "cruise_fuel_flow_kg_h", -1.0),
        ("route", "trip_distance_km", 0.0),
        ("monitoring", "smoothing_window", 0),
        ("monitoring", "sample_interval_s", 0.0),
        ("reserve_policy", "contingency_fraction", 1.5),
    ],
)
def test_invalid_config_is_rejected(section: str, field: str, value: float) -> None:
    raw = copy.deepcopy(_raw())
    raw[section][field] = value
    with pytest.raises(ValueError, match=field):
        config_from_dict(raw)


@pytest.mark.req("REQ-08")
def test_unknown_scenario_is_reported(config: AfrmConfig) -> None:
    with pytest.raises(KeyError, match="Unknown scenario"):
        config.scenario("does_not_exist")
