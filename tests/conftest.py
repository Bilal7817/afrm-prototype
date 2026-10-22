from __future__ import annotations

from pathlib import Path

import pytest

from afrm.models import AfrmConfig, FuelPlan, FuelSample, MonitoringLimits, load_config
from afrm.planner import plan_fuel

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "afrm_config.json"


@pytest.fixture(scope="session")
def config() -> AfrmConfig:
    return load_config(CONFIG_PATH)


@pytest.fixture(scope="session")
def plan(config: AfrmConfig) -> FuelPlan:
    return plan_fuel(config)


@pytest.fixture(scope="session")
def limits(config: AfrmConfig) -> MonitoringLimits:
    return config.monitoring


def sample(
    time_s: float = 0.0,
    fob_kg: float = 6800.0,
    fuel_flow_kg_h: float = 2400.0,
    ground_speed_km_h: float = 800.0,
    remaining_km: float = 1500.0,
) -> FuelSample:
    """Valid nominal sample; override one field to build a test case."""
    return FuelSample(time_s, fob_kg, fuel_flow_kg_h, ground_speed_km_h, remaining_km)
