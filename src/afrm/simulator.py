"""Deterministic simulated flight data (REQ-09) and CSV input/output.

Model assumptions (stated in the report):
* steady cruise from t = 0 (after taxi) to the destination; no climb/descent;
* true fuel flow is constant at the planned cruise value;
* a headwind lowers ground speed only - fuel flow per hour is unchanged;
* remaining distance comes from navigation and is treated as exact;
* sensor noise is Gaussian and seeded, so the same seed gives the same data.
"""

from __future__ import annotations

import csv
import random
from collections.abc import Iterable
from pathlib import Path

from afrm.models import AfrmConfig, FuelSample, Scenario

CSV_FIELDS = ("time_s", "fob_kg", "fuel_flow_kg_h", "ground_speed_km_h", "remaining_km")


def generate_flight(
    config: AfrmConfig,
    scenario: Scenario,
    *,
    seed: int = 42,
    noisy: bool = True,
) -> list[FuelSample]:
    """Generate one sample per interval from t = 0 until arrival."""
    rng = random.Random(seed)
    noise = config.noise
    trip_km = config.route.trip_distance_km
    planned_gs = config.aircraft.planned_ground_speed_km_h
    flow = config.aircraft.cruise_fuel_flow_kg_h
    start_fob_kg = scenario.loaded_fuel_kg - config.aircraft.taxi_fuel_kg

    # The flight has two legs: planned ground speed up to the headwind point,
    # then the headwind ground speed. Without a headwind, leg 2 has zero length.
    switch_km = trip_km
    slow_gs = planned_gs
    if scenario.headwind_after_km is not None and scenario.headwind_ground_speed_km_h:
        switch_km = scenario.headwind_after_km
        slow_gs = scenario.headwind_ground_speed_km_h
    switch_h = switch_km / planned_gs
    arrival_h = switch_h + (trip_km - switch_km) / slow_gs

    # Sample every interval, plus a final sample on arrival.
    step_h = config.monitoring.sample_interval_s / 3600.0
    times_h = []
    i = 0
    while i * step_h < arrival_h:
        times_h.append(i * step_h)
        i += 1
    times_h.append(arrival_h)

    samples = []
    for t_h in times_h:
        if t_h < switch_h:
            distance_km, gs = planned_gs * t_h, planned_gs
        else:
            distance_km, gs = switch_km + slow_gs * (t_h - switch_h), slow_gs
        fob_kg = start_fob_kg - flow * t_h
        measured_flow = flow
        if noisy:
            fob_kg += rng.gauss(0.0, noise.fob_sigma_kg)
            measured_flow *= 1.0 + rng.gauss(0.0, noise.fuel_flow_rel_sigma)
            gs += rng.gauss(0.0, noise.ground_speed_sigma_km_h)
        samples.append(
            FuelSample(
                time_s=t_h * 3600.0,
                fob_kg=fob_kg,
                fuel_flow_kg_h=measured_flow,
                ground_speed_km_h=gs,
                remaining_km=max(0.0, trip_km - distance_km),
            )
        )
    return samples


def write_csv(samples: Iterable[FuelSample], path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_FIELDS)
        for s in samples:
            writer.writerow(
                [
                    f"{s.time_s:.3f}",
                    f"{s.fob_kg:.3f}",
                    f"{s.fuel_flow_kg_h:.3f}",
                    f"{s.ground_speed_km_h:.3f}",
                    f"{s.remaining_km:.3f}",
                ]
            )


def read_csv(path: str | Path) -> list[FuelSample]:
    """Read samples; malformed numbers become NaN so the monitor rejects them."""

    def number(text: str) -> float:
        try:
            return float(text)
        except ValueError:
            return float("nan")

    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            FuelSample(
                time_s=number(row["time_s"]),
                fob_kg=number(row["fob_kg"]),
                fuel_flow_kg_h=number(row["fuel_flow_kg_h"]),
                ground_speed_km_h=number(row["ground_speed_km_h"]),
                remaining_km=number(row["remaining_km"]),
            )
            for row in reader
        ]
