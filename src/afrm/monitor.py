"""In-flight validation, smoothing and fuel-status classification.

REQ-03  predicted landing fuel, endurance and range
REQ-04  fuel flow smoothed over up to N valid readings; latest ground speed
REQ-05  GREEN / AMBER / RED thresholds
REQ-06  sample validation rules
REQ-07  DATA INVALID handling and timestamp recovery

The monitor processes one sample at a time and keeps only a fixed-size
window of fuel-flow readings, so memory use is O(1) per flight.
"""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable, Iterator

from afrm.models import Assessment, FuelPlan, FuelSample, FuelStatus, MonitoringLimits

# ------------------------------------------------------------ pure functions


def predict_landing_fuel(
    fob_kg: float,
    fuel_flow_kg_h: float,
    remaining_km: float,
    ground_speed_km_h: float,
) -> float:
    """Fuel on board minus the fuel needed to cover the remaining distance."""
    time_to_destination_h = remaining_km / ground_speed_km_h
    return fob_kg - fuel_flow_kg_h * time_to_destination_h


def endurance_and_range(
    fob_kg: float,
    final_reserve_kg: float,
    fuel_flow_kg_h: float,
    ground_speed_km_h: float,
) -> tuple[float | None, float | None]:
    """Endurance (h) and still-air-equivalent range (km) above final reserve.

    Undefined (None) when the smoothed fuel flow is zero.
    """
    if fuel_flow_kg_h == 0:
        return None, None
    endurance_h = (fob_kg - final_reserve_kg) / fuel_flow_kg_h
    return endurance_h, endurance_h * ground_speed_km_h


def classify(predicted_landing_fuel_kg: float, plan: FuelPlan) -> FuelStatus:
    """Map predicted landing fuel at the destination to a status (REQ-05)."""
    if predicted_landing_fuel_kg >= plan.green_threshold_kg:
        return FuelStatus.GREEN
    if predicted_landing_fuel_kg >= plan.red_threshold_kg:
        return FuelStatus.AMBER
    return FuelStatus.RED


def _in_range(value: float, low: float, high: float = math.inf) -> bool:
    """True if value is a finite number between low and high (inclusive)."""
    return math.isfinite(value) and low <= value <= high


def check_values(sample: FuelSample, limits: MonitoringLimits) -> str | None:
    """Return a reason if any measured value is invalid, else None (REQ-06)."""
    if not math.isfinite(sample.time_s):
        return "timestamp is not finite"
    if not _in_range(sample.fob_kg, 0.0):
        return "fuel on board is negative or not finite"
    if not _in_range(sample.fuel_flow_kg_h, limits.fuel_flow_min_kg_h, limits.fuel_flow_max_kg_h):
        return "fuel flow is outside the plausible range"
    if not _in_range(
        sample.ground_speed_km_h, limits.ground_speed_min_km_h, limits.ground_speed_max_km_h
    ):
        return "ground speed is outside the plausible range"
    if not _in_range(sample.remaining_km, 0.0):
        return "remaining distance is negative or not finite"
    return None


# ------------------------------------------------------------ stateful monitor


class FuelMonitor:
    """Streaming fuel monitor for one flight."""

    def __init__(self, plan: FuelPlan, limits: MonitoringLimits) -> None:
        self._plan = plan
        self._limits = limits
        self._flows: deque[float] = deque(maxlen=limits.smoothing_window)
        # Timestamp that the next sample is checked against: the last accepted
        # sample, or the re-synchronisation point after a data gap (REQ-07).
        self._reference_time_s: float | None = None
        self._last_remaining_km: float | None = None

    @property
    def smoothing_count(self) -> int:
        return len(self._flows)

    def _invalid(self, sample: FuelSample, reason: str) -> Assessment:
        return Assessment(sample.time_s, FuelStatus.DATA_INVALID, None, None, None, reason)

    def assess(self, sample: FuelSample) -> Assessment:
        reason = check_values(sample, self._limits)
        if reason is not None:
            return self._invalid(sample, reason)

        if self._last_remaining_km is not None and sample.remaining_km > self._last_remaining_km:
            return self._invalid(sample, "remaining distance increased")

        if self._reference_time_s is not None:
            elapsed_s = sample.time_s - self._reference_time_s
            if elapsed_s <= 0:
                # Reference unchanged: the next sample is checked against
                # the last accepted timestamp.
                return self._invalid(sample, "timestamp is not increasing")
            if elapsed_s > self._limits.max_gap_s:
                # Re-synchronise on this timestamp and discard stale readings,
                # otherwise every later sample would also fail the gap check.
                self._reference_time_s = sample.time_s
                self._flows.clear()
                return self._invalid(sample, "data gap exceeds maximum interval")

        # Sample accepted.
        self._reference_time_s = sample.time_s
        self._last_remaining_km = sample.remaining_km
        self._flows.append(sample.fuel_flow_kg_h)
        smoothed_flow = sum(self._flows) / len(self._flows)

        plf = predict_landing_fuel(
            sample.fob_kg, smoothed_flow, sample.remaining_km, sample.ground_speed_km_h
        )
        endurance_h, range_km = endurance_and_range(
            sample.fob_kg,
            self._plan.final_reserve_kg,
            smoothed_flow,
            sample.ground_speed_km_h,
        )
        return Assessment(sample.time_s, classify(plf, self._plan), plf, endurance_h, range_km)


def monitor_flight(
    samples: Iterable[FuelSample], plan: FuelPlan, limits: MonitoringLimits
) -> Iterator[Assessment]:
    """Assess samples lazily, one at a time (constant memory)."""
    monitor = FuelMonitor(plan, limits)
    for sample in samples:
        yield monitor.assess(sample)
