"""TC-B05 and TC-B06: status stability under noise and intermittent invalid data."""

from __future__ import annotations

import dataclasses
import math

import pytest

from afrm.models import AfrmConfig, FuelPlan, FuelStatus
from afrm.monitor import monitor_flight
from afrm.simulator import generate_flight

SEEDS = range(100)


@pytest.mark.req("REQ-05", "REQ-09")
def test_nominal_status_stable_across_100_seeds(config: AfrmConfig, plan: FuelPlan) -> None:
    """TC-B05: no nominal flight ever leaves GREEN because of sensor noise."""
    escalated = 0
    for seed in SEEDS:
        samples = generate_flight(config, config.scenario("nominal"), seed=seed)
        statuses = {a.status for a in monitor_flight(samples, plan, config.monitoring)}
        if statuses != {FuelStatus.GREEN}:
            escalated += 1
    assert escalated == 0


@pytest.mark.req("REQ-06")
def test_simulated_timestamps_are_exact_multiples_of_interval(config: AfrmConfig) -> None:
    """DR-001 regression: timestamps must be exact multiples of the interval.
    v1.0.0 produced e.g. 3899.9999999999995 s instead of 3900 s."""
    samples = generate_flight(config, config.scenario("nominal"), seed=42)
    inexact = [s.time_s for i, s in enumerate(samples[:-1]) if s.time_s != 60.0 * i]
    assert inexact == []


@pytest.mark.req("REQ-06", "REQ-07")
def test_isolated_invalid_samples_are_skipped(config: AfrmConfig, plan: FuelPlan) -> None:
    """TC-B06a: every 7th fuel-flow reading corrupted; monitoring continues.

    DR-001 regression: in v1.0.0 the valid sample after invalid index 66
    arrived 120.00000000000045 s after the last accepted one and was wrongly
    rejected by the 120 s gap rule.
    """
    clean = generate_flight(config, config.scenario("nominal"), seed=42)
    corrupted = [
        dataclasses.replace(s, fuel_flow_kg_h=math.nan) if i % 7 == 3 else s
        for i, s in enumerate(clean)
    ]
    results = list(monitor_flight(corrupted, plan, config.monitoring))
    # DR-001: valid sample 67 (after invalid 66) must be accepted.
    assert results[67].status is FuelStatus.GREEN, results[67].reason

    invalid = [a for a in results if a.status is FuelStatus.DATA_INVALID]
    valid = [a for a in results if a.status is not FuelStatus.DATA_INVALID]

    assert len(invalid) == sum(1 for i in range(len(clean)) if i % 7 == 3)
    assert {a.status for a in valid} == {FuelStatus.GREEN}

    clean_final = list(monitor_flight(clean, plan, config.monitoring))[-1]
    assert valid[-1].predicted_landing_fuel_kg == pytest.approx(
        clean_final.predicted_landing_fuel_kg, abs=30.0
    )


@pytest.mark.req("REQ-06", "REQ-07")
def test_two_consecutive_invalid_samples_cost_a_third(config: AfrmConfig, plan: FuelPlan) -> None:
    """TC-B06b (finding): two invalid samples in a row make the next valid sample
    arrive 180 s after the last accepted one, so the gap rule rejects it too and
    clears the smoothing window."""
    clean = generate_flight(config, config.scenario("nominal"), seed=42)
    corrupted = [
        dataclasses.replace(s, fuel_flow_kg_h=math.nan) if i in (20, 21) else s
        for i, s in enumerate(clean)
    ]
    results = list(monitor_flight(corrupted, plan, config.monitoring))
    assert [results[i].status for i in (20, 21, 22, 23)] == [
        FuelStatus.DATA_INVALID,
        FuelStatus.DATA_INVALID,
        FuelStatus.DATA_INVALID,
        FuelStatus.GREEN,
    ]
    assert "gap" in results[22].reason
