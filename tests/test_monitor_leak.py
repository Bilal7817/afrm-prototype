"""Leak detection inside the monitor (CR-001: REQ-12, REQ-13, REQ-14, AC-5)."""

from __future__ import annotations

import dataclasses
import math

import pytest

from afrm.models import AfrmConfig, FuelPlan, FuelStatus
from afrm.monitor import classify, monitor_flight
from afrm.simulator import generate_flight
from scripts.baseline_leak import inject_leak

LEAK_START_MIN = 40.0


@pytest.mark.req("REQ-03")
def test_detection_is_off_unless_settings_are_given(config: AfrmConfig, plan: FuelPlan) -> None:
    """Without leak settings the monitor behaves as v1.0.1."""
    samples = generate_flight(config, config.scenario("nominal"), seed=42, leak_rate_kg_h=1200.0)
    results = list(monitor_flight(samples, plan, config.monitoring))
    assert not any(a.leak_alert or a.discrepancy_kg is not None for a in results)


@pytest.mark.req("REQ-13")
@pytest.mark.parametrize("leak_rate_kg_h", [0.0, 600.0, 1200.0])
def test_standard_plf_is_unchanged(
    config: AfrmConfig, plan: FuelPlan, leak_rate_kg_h: float
) -> None:
    """AC-5: the standard PLF is identical with and without leak detection."""
    for seed in range(20):
        samples = generate_flight(
            config, config.scenario("nominal"), seed=seed, leak_rate_kg_h=leak_rate_kg_h
        )
        before = list(monitor_flight(samples, plan, config.monitoring))
        after = list(monitor_flight(samples, plan, config.monitoring, config.leak_detection))
        assert [a.predicted_landing_fuel_kg for a in after] == [
            a.predicted_landing_fuel_kg for a in before
        ]
        if leak_rate_kg_h == 0.0:
            assert [a.status for a in after] == [a.status for a in before]


@pytest.mark.req("REQ-14")
def test_status_uses_lower_plf_only_while_alert_is_active(
    config: AfrmConfig, plan: FuelPlan
) -> None:
    samples = generate_flight(config, config.scenario("nominal"), seed=42, leak_rate_kg_h=1200.0)
    results = list(monitor_flight(samples, plan, config.monitoring, config.leak_detection))
    assert any(a.leak_alert for a in results)
    for a in results:
        assert a.predicted_landing_fuel_kg is not None
        if a.leak_alert:
            assert a.leak_adjusted_plf_kg is not None
            lower = min(a.predicted_landing_fuel_kg, a.leak_adjusted_plf_kg)
            assert a.status is classify(lower, plan)
        else:
            assert a.leak_adjusted_plf_kg is None
            assert a.status is classify(a.predicted_landing_fuel_kg, plan)


@pytest.mark.req("REQ-12")
def test_invalid_readings_never_enter_the_window(config: AfrmConfig, plan: FuelPlan) -> None:
    """A rejected fuel-on-board reading cannot cause a leak alert."""
    clean = generate_flight(config, config.scenario("nominal"), noisy=False)
    corrupted = [dataclasses.replace(s, fob_kg=-1.0) if i == 50 else s for i, s in enumerate(clean)]
    results = list(monitor_flight(corrupted, plan, config.monitoring, config.leak_detection))
    assert results[50].status is FuelStatus.DATA_INVALID
    assert not any(a.leak_alert for a in results)
    assert all(abs(a.discrepancy_kg) < 1e-6 for a in results if a.discrepancy_kg is not None)


@pytest.mark.req("REQ-07", "REQ-12")
def test_gap_clears_the_leak_window(config: AfrmConfig, plan: FuelPlan) -> None:
    """Removing two readings makes a 180 s gap; the window restarts after it."""
    samples = generate_flight(
        config, config.scenario("nominal"), noisy=False, leak_rate_kg_h=1200.0
    )
    gapped = [s for i, s in enumerate(samples) if i not in (60, 61)]
    results = list(monitor_flight(gapped, plan, config.monitoring, config.leak_detection))
    by_min = {round(a.time_s / 60): a for a in results}
    assert by_min[59].leak_alert
    assert "gap" in by_min[62].reason  # first reading after the gap is rejected
    assert all(by_min[m].discrepancy_kg is None for m in range(63, 72))  # window refilling
    assert by_min[73].leak_alert  # full window again after 10 min


@pytest.mark.req("REQ-12")
def test_simulator_leak_matches_baseline_injection(config: AfrmConfig) -> None:
    """The simulator's leak option reproduces the leak used in baseline testing."""
    simulated = generate_flight(config, config.scenario("nominal"), seed=42, leak_rate_kg_h=600.0)
    injected = inject_leak(generate_flight(config, config.scenario("nominal"), seed=42), 600.0)
    assert [s.fob_kg for s in simulated] == pytest.approx([s.fob_kg for s in injected])


@pytest.mark.req("REQ-12", "REQ-14")
def test_1200_kg_h_leak_detected_and_red_much_earlier(config: AfrmConfig, plan: FuelPlan) -> None:
    """Seed 42: alert within 11 min of leak start (AC-1 limit); RED long before
    v1.0.0's 105 min (results/baseline)."""
    samples = generate_flight(config, config.scenario("nominal"), seed=42, leak_rate_kg_h=1200.0)
    results = list(monitor_flight(samples, plan, config.monitoring, config.leak_detection))
    first_alert_min = next(a.time_s for a in results if a.leak_alert) / 60.0
    first_red_min = next(a.time_s for a in results if a.status is FuelStatus.RED) / 60.0
    assert first_alert_min - LEAK_START_MIN <= 11.0
    assert first_red_min < 105.0


@pytest.mark.req("REQ-12")
def test_threshold_of_infinity_disables_alerts(config: AfrmConfig, plan: FuelPlan) -> None:
    settings = dataclasses.replace(config.leak_detection, threshold_kg=math.inf)
    samples = generate_flight(config, config.scenario("nominal"), seed=42, leak_rate_kg_h=1200.0)
    assert not any(a.leak_alert for a in monitor_flight(samples, plan, config.monitoring, settings))
