"""Scenario verification: exact values (noise-free) and statuses (seeded noise)."""

from __future__ import annotations

import pytest

from afrm.models import AfrmConfig, Assessment, FuelPlan, FuelStatus
from afrm.monitor import monitor_flight
from afrm.simulator import generate_flight


def _run(config: AfrmConfig, plan: FuelPlan, name: str, *, noisy: bool) -> list[Assessment]:
    samples = generate_flight(config, config.scenario(name), seed=42, noisy=noisy)
    return list(monitor_flight(samples, plan, config.monitoring))


def _sequence(assessments: list[Assessment]) -> list[FuelStatus]:
    seq: list[FuelStatus] = []
    for a in assessments:
        if not seq or seq[-1] is not a.status:
            seq.append(a.status)
    return seq


def _plfs(assessments: list[Assessment]) -> list[float]:
    return [a.predicted_landing_fuel_kg for a in assessments if a.predicted_landing_fuel_kg]


# ------------------------------------------------------------ noise-free, exact


@pytest.mark.req("REQ-03", "REQ-05")
def test_nominal_exact_landing_fuel(config: AfrmConfig, plan: FuelPlan) -> None:
    results = _run(config, plan, "nominal", noisy=False)
    assert all(p == pytest.approx(2300.0) for p in _plfs(results))
    assert _sequence(results) == [FuelStatus.GREEN]
    assert results[-1].time_s / 60 == pytest.approx(112.5)  # 1,500 km at 800 km/h


@pytest.mark.req("REQ-03", "REQ-04", "REQ-05")
def test_headwind_exact_transition(config: AfrmConfig, plan: FuelPlan) -> None:
    results = _run(config, plan, "headwind", noisy=False)
    before = [a for a in results if a.time_s / 3600 < 0.9375]  # 750 km at 800 km/h
    after = [a for a in results if a.time_s / 3600 > 0.9375]
    assert all(a.predicted_landing_fuel_kg == pytest.approx(2300.0) for a in before)
    assert all(a.predicted_landing_fuel_kg == pytest.approx(1550.0) for a in after)
    assert _sequence(results) == [FuelStatus.GREEN, FuelStatus.AMBER]
    # 56.25 min to the headwind point + 750 km at 600 km/h (75 min)
    assert results[-1].time_s / 60 == pytest.approx(131.25)


@pytest.mark.req("REQ-03", "REQ-05")
def test_low_uplift_exact_landing_fuel(config: AfrmConfig, plan: FuelPlan) -> None:
    results = _run(config, plan, "low_uplift", noisy=False)
    assert all(p == pytest.approx(800.0) for p in _plfs(results))
    assert _sequence(results) == [FuelStatus.RED]


# ------------------------------------------------------------ seeded noise, statuses


@pytest.mark.req("REQ-05", "REQ-09")
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("nominal", [FuelStatus.GREEN]),
        ("headwind", [FuelStatus.GREEN, FuelStatus.AMBER]),
        ("low_uplift", [FuelStatus.RED]),
    ],
)
def test_noisy_scenarios_reach_expected_status(
    config: AfrmConfig, plan: FuelPlan, name: str, expected: list[FuelStatus]
) -> None:
    results = _run(config, plan, name, noisy=True)
    assert _sequence(results) == expected
    assert all(a.status is not FuelStatus.DATA_INVALID for a in results)


@pytest.mark.req("REQ-05", "REQ-09")
@pytest.mark.parametrize("seed", range(20))
def test_headwind_status_robust_across_seeds(config: AfrmConfig, plan: FuelPlan, seed: int) -> None:
    samples = generate_flight(config, config.scenario("headwind"), seed=seed, noisy=True)
    results = list(monitor_flight(samples, plan, config.monitoring))
    assert _sequence(results) == [FuelStatus.GREEN, FuelStatus.AMBER]
