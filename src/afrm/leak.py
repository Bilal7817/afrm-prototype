"""Suspected fuel leak detection (CR-001).

REQ-11  sliding window; expected, observed and discrepancy
REQ-12  SUSPECTED FUEL LEAK when the discrepancy exceeds the threshold
REQ-13  leak rate from the same window

The detector compares the fuel actually used (drop in fuel on board) with the
fuel the flow meter says was used. It only ever receives samples that the
monitor has already accepted; the monitor also clears it after a data gap.

The window holds about ten readings, so each update is O(window) and memory
is constant per flight.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from itertools import pairwise
from typing import NamedTuple

from afrm.models import LeakSettings

SECONDS_PER_HOUR = 3600.0


class _Reading(NamedTuple):
    time_s: float
    fob_kg: float
    fuel_flow_kg_h: float


@dataclass(frozen=True, slots=True)
class LeakCheck:
    """Result of one detector update.

    ``discrepancy_kg`` is None until the window spans the full period.
    ``leak_rate_kg_h`` is set only while the alert is active.
    """

    alert: bool
    discrepancy_kg: float | None
    leak_rate_kg_h: float | None


def expected_burn_kg(readings: list[_Reading]) -> float:
    """Metered fuel used over the readings (trapezoidal rule, REQ-11).

    Each interval uses the mean of the flow readings at its start and end,
    multiplied by the actual time between them.
    """
    return sum(
        (a.fuel_flow_kg_h + b.fuel_flow_kg_h) / 2.0 * (b.time_s - a.time_s) / SECONDS_PER_HOUR
        for a, b in pairwise(readings)
    )


class LeakDetector:
    """Sliding-window comparison of observed and metered fuel burn."""

    def __init__(self, settings: LeakSettings) -> None:
        self._window_s = settings.window_s
        self._threshold_kg = settings.threshold_kg
        self._readings: deque[_Reading] = deque()

    def reset(self) -> None:
        """Clear the window (called by the monitor after a data gap)."""
        self._readings.clear()

    def update(self, time_s: float, fob_kg: float, fuel_flow_kg_h: float) -> LeakCheck:
        """Add one accepted reading and check for a suspected leak."""
        self._readings.append(_Reading(time_s, fob_kg, fuel_flow_kg_h))

        # The window starts at the latest reading that is at least window_s old.
        while len(self._readings) >= 2 and time_s - self._readings[1].time_s >= self._window_s:
            self._readings.popleft()

        start = self._readings[0]
        duration_s = time_s - start.time_s
        if duration_s < self._window_s:
            return LeakCheck(alert=False, discrepancy_kg=None, leak_rate_kg_h=None)

        observed_kg = start.fob_kg - fob_kg
        discrepancy_kg = observed_kg - expected_burn_kg(list(self._readings))

        if discrepancy_kg > self._threshold_kg:
            rate_kg_h = discrepancy_kg / (duration_s / SECONDS_PER_HOUR)
            return LeakCheck(alert=True, discrepancy_kg=discrepancy_kg, leak_rate_kg_h=rate_kg_h)
        return LeakCheck(alert=False, discrepancy_kg=discrepancy_kg, leak_rate_kg_h=None)
