"""TC-B04: characterisation of the v1.0.0 monitor under unexplained fuel loss.

These tests record what the baseline actually does. They are not claims that
it detects leaks: they document that it does not, and by how much its
warnings lag a reference that knows the loss rate.
"""

from __future__ import annotations

import pytest

from afrm.models import AfrmConfig, FuelPlan, FuelStatus
from afrm.simulator import generate_flight
from scripts.baseline_leak import characterise, inject_leak


@pytest.mark.req("REQ-03")
def test_injected_loss_changes_fuel_on_board_only(config: AfrmConfig) -> None:
    clean = generate_flight(config, config.scenario("nominal"), noisy=False)
    leaking = inject_leak(clean, rate_kg_h=600.0, start_min=40.0)
    at_70_min = next(i for i, s in enumerate(clean) if s.time_s == 70 * 60)
    assert leaking[at_70_min].fob_kg == pytest.approx(clean[at_70_min].fob_kg - 300.0)
    assert all(a.fuel_flow_kg_h == b.fuel_flow_kg_h for a, b in zip(clean, leaking, strict=True))


@pytest.mark.req("REQ-05")
def test_no_loss_stays_green(config: AfrmConfig, plan: FuelPlan) -> None:
    r = characterise(config, plan, rate_kg_h=0.0)
    assert r.baseline_first_not_green_min is None
    assert r.actual_landing_status is FuelStatus.GREEN


@pytest.mark.req("REQ-05")
def test_300_kg_h_loss_is_not_indicated(config: AfrmConfig, plan: FuelPlan) -> None:
    """Lands above the GREEN threshold, but the loss itself is never indicated."""
    r = characterise(config, plan, rate_kg_h=300.0)
    assert r.actual_landing_status is FuelStatus.GREEN
    assert r.baseline_first_not_green_min is None


@pytest.mark.req("REQ-05")
def test_600_kg_h_loss_warning_lags_reference(config: AfrmConfig, plan: FuelPlan) -> None:
    r = characterise(config, plan, rate_kg_h=600.0)
    assert r.actual_landing_status is FuelStatus.AMBER
    assert r.reference_first_not_green_min == pytest.approx(41.0)
    assert r.baseline_first_not_green_min == pytest.approx(94.0)
    assert r.baseline_first_red_min is None


@pytest.mark.req("REQ-05")
def test_1200_kg_h_loss_red_lags_reference(config: AfrmConfig, plan: FuelPlan) -> None:
    """Lands below final reserve, yet stays GREEN for 26 min after the loss starts."""
    r = characterise(config, plan, rate_kg_h=1200.0)
    assert r.actual_landing_status is FuelStatus.RED
    assert r.reference_first_red_min == pytest.approx(41.0)
    assert r.baseline_first_not_green_min == pytest.approx(67.0)
    assert r.baseline_first_red_min == pytest.approx(105.0)
