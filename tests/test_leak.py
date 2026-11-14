"""Unit tests for the leak detector (CR-001: REQ-11, REQ-12, REQ-13).

Readings are built by hand with exact values, so every expected discrepancy
can be checked by hand: 2,400 kg/h for 60 s is exactly 40 kg.
"""

from __future__ import annotations

import pytest

from afrm.leak import LeakCheck, LeakDetector
from afrm.models import LeakSettings

SETTINGS = LeakSettings(window_s=600.0, threshold_kg=75.0)
FLOW = 2400.0  # kg/h, i.e. 40 kg per 60 s


def feed(
    detector: LeakDetector, times_s: list[float], extra_loss_kg: float = 0.0
) -> list[LeakCheck]:
    """Feed metered readings; extra_loss_kg is removed at the last reading only."""
    checks = []
    for i, t in enumerate(times_s):
        fob = 6800.0 - FLOW * t / 3600.0
        if i == len(times_s) - 1:
            fob -= extra_loss_kg
        checks.append(detector.update(t, fob, FLOW))
    return checks


def minutes(*mins: int) -> list[float]:
    return [60.0 * m for m in mins]


@pytest.mark.req("REQ-11")
def test_no_check_until_window_spans_full_period() -> None:
    checks = feed(LeakDetector(SETTINGS), minutes(*range(11)))
    assert all(c.discrepancy_kg is None for c in checks[:10])  # 0 to 9 min
    assert checks[10].discrepancy_kg == pytest.approx(0.0)  # 10 min


@pytest.mark.req("REQ-11")
def test_metered_burn_gives_zero_discrepancy() -> None:
    checks = feed(LeakDetector(SETTINGS), minutes(*range(30)))
    assert all(c.discrepancy_kg == pytest.approx(0.0, abs=1e-9) for c in checks[10:])
    assert not any(c.alert for c in checks)


@pytest.mark.req("REQ-12")
@pytest.mark.parametrize(
    ("extra_loss_kg", "alert"),
    [(0.0, False), (74.99, False), (75.0, False), (75.01, True), (200.0, True)],
)
def test_alert_threshold_boundary(extra_loss_kg: float, alert: bool) -> None:
    """Boundary values: the alert needs a discrepancy strictly above 75 kg."""
    last = feed(LeakDetector(SETTINGS), minutes(*range(11)), extra_loss_kg)[-1]
    assert last.discrepancy_kg == pytest.approx(extra_loss_kg)
    assert last.alert is alert


@pytest.mark.req("REQ-13")
def test_leak_rate_uses_the_same_window() -> None:
    """100 kg unmetered loss over 10 min is 600 kg/h."""
    last = feed(LeakDetector(SETTINGS), minutes(*range(11)), extra_loss_kg=100.0)[-1]
    assert last.leak_rate_kg_h == pytest.approx(600.0)


@pytest.mark.req("REQ-13")
def test_leak_rate_only_while_alert_is_active() -> None:
    last = feed(LeakDetector(SETTINGS), minutes(*range(11)), extra_loss_kg=50.0)[-1]
    assert last.alert is False
    assert last.leak_rate_kg_h is None


@pytest.mark.req("REQ-11")
def test_window_slides_and_drops_old_readings() -> None:
    """A loss early in the flight leaves the window after 10 min."""
    detector = LeakDetector(SETTINGS)
    detector.update(0.0, 6800.0, FLOW)
    detector.update(60.0, 6800.0 - 40.0 - 200.0, FLOW)  # 200 kg lost in the first minute
    checks = [
        detector.update(t, 6800.0 - 200.0 - FLOW * t / 3600.0, FLOW) for t in minutes(*range(2, 13))
    ]
    at_10, at_11 = checks[8], checks[9]
    assert at_10.alert  # window 0 to 10 min includes the loss
    assert at_11.discrepancy_kg == pytest.approx(0.0)  # window 1 to 11 min does not
    assert not at_11.alert


@pytest.mark.req("REQ-11", "REQ-12")
def test_skipped_reading_uses_actual_elapsed_time() -> None:
    """A missing reading (5 min) leaves a 120 s interval; metered burn is still exact."""
    times = [t for t in minutes(*range(11)) if t != 300.0]
    last = feed(LeakDetector(SETTINGS), times)[-1]
    assert last.discrepancy_kg == pytest.approx(0.0)


@pytest.mark.req("REQ-11")
def test_skipped_reading_does_not_shorten_a_full_window() -> None:
    """Once 10 min of history exists, the window never drops below 10 min."""
    times = [t for t in minutes(*range(13)) if t != 60.0]
    checks = feed(LeakDetector(SETTINGS), times)
    assert all(c.discrepancy_kg is not None for c in checks[9:])  # 10, 11, 12 min


@pytest.mark.req("REQ-11")
def test_sudden_flow_change_gives_small_bounded_discrepancy() -> None:
    """Reported flow steps from 2,400 to 3,000 kg/h at 5 min with no leak.

    The trapezoidal rule averages the interval before the step, so it
    over-estimates metered burn by (600 / 2) kg/h x 60 s = 5 kg. That is far
    below the 75 kg threshold.
    """
    detector = LeakDetector(SETTINGS)
    fob, last = 6800.0, None
    for i, t in enumerate(minutes(*range(11))):
        flow = FLOW if t < 300.0 else 3000.0
        if i > 0:
            fob -= (FLOW if t <= 300.0 else 3000.0) * 60.0 / 3600.0
        last = detector.update(t, fob, flow)
    assert last is not None
    assert last.discrepancy_kg == pytest.approx(-5.0)
    assert not last.alert


@pytest.mark.req("REQ-12")
def test_reset_clears_the_window() -> None:
    detector = LeakDetector(SETTINGS)
    feed(detector, minutes(*range(11)))
    detector.reset()
    checks = feed(detector, minutes(*range(20, 30)))
    assert all(c.discrepancy_kg is None for c in checks)
