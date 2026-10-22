from __future__ import annotations

from pathlib import Path

import pytest

from afrm.models import AfrmConfig, FuelPlan, FuelStatus
from afrm.monitor import monitor_flight
from afrm.simulator import generate_flight, read_csv, write_csv


@pytest.mark.req("REQ-09")
def test_same_seed_gives_identical_data(config: AfrmConfig) -> None:
    scenario = config.scenario("headwind")
    assert generate_flight(config, scenario, seed=7) == generate_flight(config, scenario, seed=7)


@pytest.mark.req("REQ-09")
def test_different_seed_gives_different_data(config: AfrmConfig) -> None:
    scenario = config.scenario("headwind")
    assert generate_flight(config, scenario, seed=1) != generate_flight(config, scenario, seed=2)


@pytest.mark.req("REQ-10")
def test_samples_are_regular_and_end_at_destination(config: AfrmConfig) -> None:
    samples = generate_flight(config, config.scenario("nominal"), noisy=False)
    gaps = [b.time_s - a.time_s for a, b in zip(samples, samples[1:], strict=False)]
    assert all(0 < g <= config.monitoring.sample_interval_s + 1e-9 for g in gaps)
    assert samples[0].remaining_km == pytest.approx(1500.0)
    assert samples[0].fob_kg == pytest.approx(6800.0)  # loaded minus taxi
    assert samples[-1].remaining_km == pytest.approx(0.0)


@pytest.mark.req("REQ-09", "REQ-10")
def test_csv_round_trip(config: AfrmConfig, tmp_path: Path) -> None:
    samples = generate_flight(config, config.scenario("nominal"), seed=3)
    path = tmp_path / "flight.csv"
    write_csv(samples, path)
    loaded = read_csv(path)
    assert len(loaded) == len(samples)
    for original, restored in zip(samples, loaded, strict=True):
        assert restored.fob_kg == pytest.approx(original.fob_kg, abs=1e-3)
        assert restored.time_s == pytest.approx(original.time_s, abs=1e-3)


@pytest.mark.req("REQ-06", "REQ-07")
def test_malformed_csv_value_becomes_data_invalid(
    config: AfrmConfig, plan: FuelPlan, tmp_path: Path
) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "time_s,fob_kg,fuel_flow_kg_h,ground_speed_km_h,remaining_km\n"
        "0,6800,2400,800,1500\n"
        "60,6760,ERR,800,1486.667\n"
        "120,6720,2400,800,1473.333\n",
        encoding="utf-8",
    )
    statuses = [a.status for a in monitor_flight(read_csv(path), plan, config.monitoring)]
    assert statuses == [FuelStatus.GREEN, FuelStatus.DATA_INVALID, FuelStatus.GREEN]
