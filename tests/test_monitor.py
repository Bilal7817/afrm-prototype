from __future__ import annotations

import math
from collections.abc import Iterator

import pytest

from afrm.models import FuelPlan, FuelSample, FuelStatus, MonitoringLimits
from afrm.monitor import (
    FuelMonitor,
    classify,
    endurance_and_range,
    monitor_flight,
    predict_landing_fuel,
)
from tests.conftest import sample

# ------------------------------------------------------------ calculations


@pytest.mark.req("REQ-03")
def test_predicted_landing_fuel_hand_calculation() -> None:
    # 6,800 kg on board, 1,500 km to go at 800 km/h burning 2,400 kg/h
    assert predict_landing_fuel(6800.0, 2400.0, 1500.0, 800.0) == pytest.approx(2300.0)


@pytest.mark.req("REQ-03")
def test_endurance_and_range_above_final_reserve() -> None:
    endurance_h, range_km = endurance_and_range(3400.0, 1000.0, 2400.0, 800.0)
    assert endurance_h == pytest.approx(1.0)
    assert range_km == pytest.approx(800.0)


@pytest.mark.req("REQ-03", "REQ-06")
def test_zero_fuel_flow_is_valid_but_endurance_undefined(
    plan: FuelPlan, limits: MonitoringLimits
) -> None:
    assert endurance_and_range(3400.0, 1000.0, 0.0, 800.0) == (None, None)
    result = FuelMonitor(plan, limits).assess(sample(fuel_flow_kg_h=0.0))
    assert result.status is FuelStatus.GREEN
    assert result.predicted_landing_fuel_kg == pytest.approx(6800.0)
    assert result.endurance_h is None


# ------------------------------------------------------------ thresholds


@pytest.mark.req("REQ-05")
@pytest.mark.parametrize(
    ("plf_kg", "expected"),
    [
        (2300.0, FuelStatus.GREEN),
        (1750.0, FuelStatus.GREEN),  # exactly alternate + final reserve
        (1749.99, FuelStatus.AMBER),
        (1000.0, FuelStatus.AMBER),  # exactly final reserve
        (999.99, FuelStatus.RED),
        (0.0, FuelStatus.RED),
        (-50.0, FuelStatus.RED),
    ],
)
def test_status_boundaries(plan: FuelPlan, plf_kg: float, expected: FuelStatus) -> None:
    assert classify(plf_kg, plan) is expected


# ------------------------------------------------------------ smoothing


def _feed(monitor: FuelMonitor, flows: list[float]) -> float:
    """Feed valid samples one minute apart; return the last PLF."""
    plf = math.nan
    for i, flow in enumerate(flows):
        result = monitor.assess(sample(time_s=60.0 * i, fuel_flow_kg_h=flow, remaining_km=800.0))
        assert result.predicted_landing_fuel_kg is not None
        plf = result.predicted_landing_fuel_kg
    return plf


@pytest.mark.req("REQ-04")
@pytest.mark.parametrize(
    ("flows", "expected_mean"),
    [
        ([2000.0], 2000.0),  # one reading: no waiting for a full window
        ([2000.0, 3000.0], 2500.0),
        ([1000.0, 2000.0, 3000.0, 4000.0, 5000.0], 3000.0),
        ([9000.0, 1000.0, 2000.0, 3000.0, 4000.0, 5000.0], 3000.0),  # oldest dropped
    ],
)
def test_moving_average_of_up_to_five_readings(
    plan: FuelPlan, limits: MonitoringLimits, flows: list[float], expected_mean: float
) -> None:
    monitor = FuelMonitor(plan, limits)
    plf = _feed(monitor, flows)
    # remaining 800 km at 800 km/h = 1 h, so PLF = FOB - mean flow
    assert plf == pytest.approx(6800.0 - expected_mean)
    assert monitor.smoothing_count == min(len(flows), 5)


@pytest.mark.req("REQ-04")
def test_ground_speed_uses_latest_reading_not_smoothed(
    plan: FuelPlan, limits: MonitoringLimits
) -> None:
    monitor = FuelMonitor(plan, limits)
    monitor.assess(sample(time_s=0.0, ground_speed_km_h=800.0, remaining_km=1200.0))
    result = monitor.assess(sample(time_s=60.0, ground_speed_km_h=600.0, remaining_km=1200.0))
    assert result.predicted_landing_fuel_kg == pytest.approx(6800.0 - 2400.0 * 2.0)


# ------------------------------------------------------------ validation


@pytest.mark.req("REQ-06", "REQ-07")
@pytest.mark.parametrize(
    ("bad", "reason"),
    [
        (sample(fob_kg=-1.0), "fuel on board"),
        (sample(fob_kg=math.nan), "fuel on board"),
        (sample(fob_kg=math.inf), "fuel on board"),
        (sample(fuel_flow_kg_h=-0.01), "fuel flow"),
        (sample(fuel_flow_kg_h=10000.01), "fuel flow"),
        (sample(fuel_flow_kg_h=math.nan), "fuel flow"),
        (sample(fuel_flow_kg_h=math.inf), "fuel flow"),
        (sample(ground_speed_km_h=0.0), "ground speed"),
        (sample(ground_speed_km_h=99.99), "ground speed"),
        (sample(ground_speed_km_h=1200.01), "ground speed"),
        (sample(ground_speed_km_h=math.nan), "ground speed"),
        (sample(remaining_km=-0.01), "remaining distance"),
        (sample(remaining_km=math.inf), "remaining distance"),
        (sample(time_s=math.nan), "timestamp"),
    ],
)
def test_invalid_values_report_data_invalid(
    plan: FuelPlan, limits: MonitoringLimits, bad: FuelSample, reason: str
) -> None:
    result = FuelMonitor(plan, limits).assess(bad)
    assert result.status is FuelStatus.DATA_INVALID
    assert result.predicted_landing_fuel_kg is None
    assert reason in result.reason


@pytest.mark.req("REQ-06")
@pytest.mark.parametrize(
    "good",
    [
        sample(fuel_flow_kg_h=10000.0),
        sample(ground_speed_km_h=100.0),
        sample(ground_speed_km_h=1200.0),
        sample(remaining_km=0.0),
        sample(fob_kg=0.0),
    ],
)
def test_values_on_range_limits_are_accepted(
    plan: FuelPlan, limits: MonitoringLimits, good: FuelSample
) -> None:
    assert FuelMonitor(plan, limits).assess(good).status is not FuelStatus.DATA_INVALID


@pytest.mark.req("REQ-06")
def test_increasing_remaining_distance_is_rejected(
    plan: FuelPlan, limits: MonitoringLimits
) -> None:
    monitor = FuelMonitor(plan, limits)
    monitor.assess(sample(time_s=0.0, remaining_km=1000.0))
    result = monitor.assess(sample(time_s=60.0, remaining_km=1000.5))
    assert result.status is FuelStatus.DATA_INVALID
    assert "remaining distance increased" in result.reason


@pytest.mark.req("REQ-07")
def test_invalid_sample_is_excluded_from_smoothing(
    plan: FuelPlan, limits: MonitoringLimits
) -> None:
    monitor = FuelMonitor(plan, limits)
    monitor.assess(sample(time_s=0.0, fuel_flow_kg_h=2000.0, remaining_km=800.0))
    bad = monitor.assess(sample(time_s=60.0, fuel_flow_kg_h=-5.0, remaining_km=800.0))
    good = monitor.assess(sample(time_s=120.0, fuel_flow_kg_h=3000.0, remaining_km=800.0))
    assert bad.status is FuelStatus.DATA_INVALID
    assert monitor.smoothing_count == 2
    assert good.predicted_landing_fuel_kg == pytest.approx(6800.0 - 2500.0)


@pytest.mark.req("REQ-06", "REQ-07")
def test_out_of_order_timestamp_checked_against_last_accepted(
    plan: FuelPlan, limits: MonitoringLimits
) -> None:
    monitor = FuelMonitor(plan, limits)
    assert monitor.assess(sample(time_s=600.0)).status is FuelStatus.GREEN
    stale = monitor.assess(sample(time_s=540.0))
    duplicate = monitor.assess(sample(time_s=600.0))
    # 660 s is 60 s after the last ACCEPTED sample (600 s), so it is valid.
    recovered = monitor.assess(sample(time_s=660.0))
    assert stale.status is FuelStatus.DATA_INVALID
    assert duplicate.status is FuelStatus.DATA_INVALID
    assert "not increasing" in stale.reason
    assert recovered.status is FuelStatus.GREEN


@pytest.mark.req("REQ-06", "REQ-07")
def test_gap_is_rejected_then_monitoring_resynchronises(
    plan: FuelPlan, limits: MonitoringLimits
) -> None:
    monitor = FuelMonitor(plan, limits)
    for t in (0.0, 60.0, 120.0):
        monitor.assess(sample(time_s=t))
    assert monitor.smoothing_count == 3

    gap = monitor.assess(sample(time_s=300.0))  # 180 s after last accepted
    assert gap.status is FuelStatus.DATA_INVALID
    assert "gap" in gap.reason
    assert monitor.smoothing_count == 0  # stale readings discarded

    resumed = monitor.assess(sample(time_s=360.0))  # 60 s after the resync point
    assert resumed.status is FuelStatus.GREEN
    assert monitor.smoothing_count == 1


@pytest.mark.req("REQ-06")
def test_gap_exactly_at_limit_is_accepted(plan: FuelPlan, limits: MonitoringLimits) -> None:
    monitor = FuelMonitor(plan, limits)
    monitor.assess(sample(time_s=0.0))
    assert monitor.assess(sample(time_s=120.0)).status is FuelStatus.GREEN


@pytest.mark.req("REQ-07")
def test_monitor_flight_is_lazy(plan: FuelPlan, limits: MonitoringLimits) -> None:
    def endless() -> Iterator[FuelSample]:
        t = 0.0
        while True:
            yield sample(time_s=t)
            t += 60.0

    stream = monitor_flight(endless(), plan, limits)
    first_three = [next(stream) for _ in range(3)]
    assert all(a.status is FuelStatus.GREEN for a in first_three)
