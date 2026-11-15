"""Verify CR-001 (suspected fuel leak detection) against its acceptance criteria.

Runs the predefined seeded experiments in docs/CR-001-leak-detection.md and
writes the results to results/v1.1.0/:

    verification.md          acceptance criteria and evaluation metrics
    detection_times.csv      per-seed detection and warning times (figures)
    nominal_discrepancy.csv  largest discrepancy per leak-free flight (figures)

Run from the repository root:

    python -m scripts.verify_cr001
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import math
import statistics
import time
from collections.abc import Sequence
from pathlib import Path

from afrm.models import AfrmConfig, Assessment, FuelPlan, FuelSample, FuelStatus, load_config
from afrm.monitor import monitor_flight
from afrm.planner import plan_fuel
from afrm.simulator import generate_flight
from scripts.baseline_leak import describe

ROOT = Path(__file__).resolve().parents[1]
LEAK_START_MIN = 40.0
AC_SEEDS = range(100)  # AC-1, AC-2 and evaluation metrics
FALSE_ALARM_SEEDS = range(1000)  # AC-3 and AC-4, per scenario
AC1_LIMIT_MIN = 11.0  # 1,200 kg/h uses the 225 kg contingency in 11.25 min
AC2_LIMIT_MIN = 22.0  # 600 kg/h uses it in 22.5 min
NOT_GREEN = {FuelStatus.AMBER, FuelStatus.RED}


@dataclasses.dataclass(frozen=True)
class FlightResult:
    leak_rate_kg_h: float
    seed: int
    detection_min: float | None  # leak start to first alert
    v100_warning_min: float | None  # first AMBER/RED without leak detection
    v110_warning_min: float | None  # first AMBER/RED with leak detection
    alert_switch_offs: int  # alert on -> off transitions (flicker)
    alert_off_min: float  # time with the alert off after the first alert (min)
    rate_error_kg_h: float | None  # estimated - true leak rate, 20 min after leak start
    adjusted_plf_error_kg: float | None  # leak-adjusted PLF - actual landing fuel, same time


def _first_min(assessments: Sequence[Assessment], wanted: set[FuelStatus]) -> float | None:
    return next((a.time_s / 60.0 for a in assessments if a.status in wanted), None)


def _off_minutes(assessments: Sequence[Assessment]) -> float:
    """Minutes with the alert off after it first came on (accepted samples only)."""
    accepted = [a for a in assessments if a.status is not FuelStatus.DATA_INVALID]
    first = next((i for i, a in enumerate(accepted) if a.leak_alert), None)
    if first is None:
        return 0.0
    return sum(
        (b.time_s - a.time_s) / 60.0
        for a, b in zip(accepted[first:], accepted[first + 1 :], strict=False)
        if not b.leak_alert
    )


def _switch_offs(assessments: Sequence[Assessment]) -> int:
    """Number of times the alert goes from on to off (accepted samples only)."""
    flags = [a.leak_alert for a in assessments if a.status is not FuelStatus.DATA_INVALID]
    return sum(1 for a, b in zip(flags, flags[1:], strict=False) if a and not b)


def run_flight(
    config: AfrmConfig,
    plan: FuelPlan,
    leak_rate_kg_h: float,
    seed: int,
    corrupt: bool = False,
) -> FlightResult:
    """One nominal flight with a leak from 40 min, with and without detection."""
    scenario = config.scenario("nominal")
    samples = generate_flight(config, scenario, seed=seed, leak_rate_kg_h=leak_rate_kg_h)
    if corrupt:  # every 7th fuel-flow reading invalid (skipped-reading experiment)
        samples = [
            dataclasses.replace(s, fuel_flow_kg_h=math.nan) if i % 7 == 3 else s
            for i, s in enumerate(samples)
        ]
    actual = generate_flight(config, scenario, noisy=False, leak_rate_kg_h=leak_rate_kg_h)[
        -1
    ].fob_kg

    before = list(monitor_flight(samples, plan, config.monitoring))
    after = list(monitor_flight(samples, plan, config.monitoring, config.leak_detection))

    first_alert = next((a.time_s / 60.0 for a in after if a.leak_alert), None)
    check = next((a for a in after if a.time_s == (LEAK_START_MIN + 20.0) * 60.0), None)
    rate_error = plf_error = None
    if check is not None and check.leak_rate_kg_h is not None:
        rate_error = check.leak_rate_kg_h - leak_rate_kg_h
    if check is not None and check.leak_adjusted_plf_kg is not None:
        plf_error = check.leak_adjusted_plf_kg - actual

    return FlightResult(
        leak_rate_kg_h=leak_rate_kg_h,
        seed=seed,
        detection_min=None if first_alert is None else first_alert - LEAK_START_MIN,
        v100_warning_min=_first_min(before, NOT_GREEN),
        v110_warning_min=_first_min(after, NOT_GREEN),
        alert_switch_offs=_switch_offs(after),
        alert_off_min=_off_minutes(after),
        rate_error_kg_h=rate_error,
        adjusted_plf_error_kg=plf_error,
    )


def max_discrepancy(samples: list[FuelSample], config: AfrmConfig, plan: FuelPlan) -> float:
    results = monitor_flight(samples, plan, config.monitoring, config.leak_detection)
    return max(a.discrepancy_kg for a in results if a.discrepancy_kg is not None)


def runtime_ms(config: AfrmConfig, plan: FuelPlan, with_detection: bool) -> float:
    """Median time (ms) to monitor 100 pre-generated nominal flights, 5 repeats."""
    flights = [generate_flight(config, config.scenario("nominal"), seed=s) for s in range(100)]
    leak = config.leak_detection if with_detection else None
    times = []
    for _ in range(5):
        start = time.perf_counter()
        for samples in flights:
            for _assessment in monitor_flight(samples, plan, config.monitoring, leak):
                pass
        times.append((time.perf_counter() - start) * 1000.0)
    return statistics.median(times)


def count_detected(results: Sequence[FlightResult], limit_min: float = math.inf) -> int:
    return sum(1 for r in results if r.detection_min is not None and r.detection_min <= limit_min)


def _stat(values: Sequence[float | None], q: float = 0.5) -> str:
    """Quantile of the non-missing values (0.5 = median)."""
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return "n/a"
    return f"{xs[min(len(xs) - 1, int(q * len(xs)))]:.0f}"


def _mean_abs(values: Sequence[float | None]) -> str:
    xs = [abs(v) for v in values if v is not None]
    return "n/a" if not xs else f"{statistics.mean(xs):.0f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "results" / "v1.1.0"))
    args = parser.parse_args()

    config = load_config(ROOT / "config" / "afrm_config.json")
    plan = plan_fuel(config)
    info = describe()
    started = time.perf_counter()

    by_rate = {
        rate: [run_flight(config, plan, rate, seed) for seed in AC_SEEDS]
        for rate in (300.0, 600.0, 1200.0)
    }
    corrupted = {
        rate: [run_flight(config, plan, rate, seed, corrupt=True) for seed in AC_SEEDS]
        for rate in (600.0, 1200.0)
    }

    # AC-3 and AC-4: leak-free flights.
    nominal_max: list[float] = []
    headwind_max: list[float] = []
    escalations = 0
    standard_identical = True
    for seed in FALSE_ALARM_SEEDS:
        for name, store in (("nominal", nominal_max), ("headwind", headwind_max)):
            samples = generate_flight(config, config.scenario(name), seed=seed)
            after = list(monitor_flight(samples, plan, config.monitoring, config.leak_detection))
            store.append(max(a.discrepancy_kg for a in after if a.discrepancy_kg is not None))
            if name == "nominal" and any(a.status in NOT_GREEN for a in after):
                escalations += 1
            if seed < 100:  # AC-5 on leak-free flights
                before = list(monitor_flight(samples, plan, config.monitoring))
                standard_identical &= [a.predicted_landing_fuel_kg for a in before] == [
                    a.predicted_landing_fuel_kg for a in after
                ] and [a.status for a in before] == [a.status for a in after]
    threshold = config.leak_detection.threshold_kg
    same = sum(1 for n, h in zip(nominal_max, headwind_max, strict=True) if n == h)
    false_alarms = sum(1 for d in nominal_max + headwind_max if d > threshold)
    elapsed = time.perf_counter() - started

    ac = [
        (
            "AC-1",
            f"1,200 kg/h detected within {AC1_LIMIT_MIN:.0f} min in >= 95/100",
            f"{count_detected(by_rate[1200.0], AC1_LIMIT_MIN)}/100",
            count_detected(by_rate[1200.0], AC1_LIMIT_MIN) >= 95,
        ),
        (
            "AC-2",
            f"600 kg/h detected within {AC2_LIMIT_MIN:.0f} min in >= 95/100",
            f"{count_detected(by_rate[600.0], AC2_LIMIT_MIN)}/100",
            count_detected(by_rate[600.0], AC2_LIMIT_MIN) >= 95,
        ),
        (
            "AC-3",
            "No alerts in 2,000 leak-free nominal and headwind flights",
            f"{false_alarms} alerts",
            false_alarms == 0,
        ),
        (
            "AC-4",
            "No GREEN to AMBER/RED escalations in 1,000 nominal flights",
            f"{escalations} escalations",
            escalations == 0,
        ),
        (
            "AC-5",
            "Standard PLF unchanged from v1.0.1 when no alert is active",
            "identical (100 leak-free flights)" if standard_identical else "DIFFERENT",
            standard_identical,
        ),
    ]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "detection_times.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([fld.name for fld in dataclasses.fields(FlightResult)])
        for results in by_rate.values():
            for r in results:
                writer.writerow(dataclasses.astuple(r))
    with (out / "nominal_discrepancy.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "nominal_max_discrepancy_kg", "headwind_max_discrepancy_kg"])
        for seed, (n, h) in enumerate(zip(nominal_max, headwind_max, strict=True)):
            writer.writerow([seed, f"{n:.2f}", f"{h:.2f}"])

    lines = [
        "# CR-001 verification results (v1.1.0)",
        "",
        f"- AFRM source: `{info['afrm_source']}`",
        f"- Commit: `{info['commit']}`",
        f"- Environment: {info['environment']}",
        f"- Settings: window {config.leak_detection.window_s:.0f} s, threshold {threshold:.0f} kg",
        f"- Leak starts at {LEAK_START_MIN:.0f} min; detection time = leak start to first alert",
        f"- Run time: {elapsed:.1f} s",
        "",
        "## Acceptance criteria",
        "",
        "| ID | Criterion | Result | Pass |",
        "|---|---|---|---|",
        *(f"| {i} | {c} | {r} | {'PASS' if ok else 'FAIL'} |" for i, c, r, ok in ac),
        "",
        "AC-3 interpretation: a headwind flight uses the same fuel-on-board and fuel-flow noise",
        "as the nominal flight with the same seed (the headwind changes ground speed only), so",
        f"{same} of 1,000 pairs give an identical largest discrepancy. The 2,000 flights are",
        "therefore about 1,000 independent tests of the detector. Zero alerts gives an",
        "approximate 95% upper bound of 0.3% per flight (rule of three, 3/1,000), not 0.15%.",
        "It does not show the false-alarm rate is zero.",
        "",
        f"Largest leak-free discrepancy: {max(nominal_max + headwind_max):.1f} kg "
        f"(threshold {threshold:.0f} kg).",
        "",
        "## Evaluation metrics (100 seeds each)",
        "",
        "| Leak | Detected | Detection median / 95th pct (min) "
        "| Flights warned v1.0.0 → v1.1.0 "
        "| First AMBER/RED v1.0.0 → v1.1.0 (median min) "
        "| Leak-rate error at +20 min (mean abs, kg/h) "
        "| Adjusted PLF error at +20 min (mean abs, kg) |",
        "|---|---|---|---|---|---|---|",
    ]
    for rate, results in by_rate.items():
        lines.append(
            f"| {rate:,.0f} kg/h | {count_detected(results)}/100 "
            f"| {_stat([r.detection_min for r in results])} / "
            f"{_stat([r.detection_min for r in results], 0.95)} "
            f"| {sum(1 for r in results if r.v100_warning_min is not None)} → "
            f"{sum(1 for r in results if r.v110_warning_min is not None)} "
            f"| {_stat([r.v100_warning_min for r in results])} → "
            f"{_stat([r.v110_warning_min for r in results])} "
            f"| {_mean_abs([r.rate_error_kg_h for r in results])} "
            f"| {_mean_abs([r.adjusted_plf_error_kg for r in results])} |"
        )
    lines += [
        "",
        "Alert stability (flicker): switch-offs = times the alert goes from on to off;",
        "off time = total minutes with the alert off from its first alert to landing (summed,",
        "not consecutive). Medians and maxima include only flights where the alert came on.",
        "Detection delay (AC-1, AC-2) and alert stability are different measures: the",
        "acceptance criteria cover time to first alert, not continuous alert reliability.",
        "",
        "| Leak | Flights with a switch-off | Switch-offs per flight (median / max) "
        "| Off time per flight (median / max, min) |",
        "|---|---|---|---|",
    ]
    for rate, results in by_rate.items():
        detected = [r for r in results if r.detection_min is not None]
        lines.append(
            f"| {rate:,.0f} kg/h | {sum(1 for r in detected if r.alert_switch_offs > 0)}"
            f"/{len(detected)} "
            f"| {_stat([float(r.alert_switch_offs) for r in detected])} / "
            f"{max(r.alert_switch_offs for r in detected)} "
            f"| {_stat([r.alert_off_min for r in detected])} / "
            f"{max(r.alert_off_min for r in detected):.0f} |"
        )
    lines += [
        "",
        "Warning medians exclude flights that never warn. Errors are measured only on flights",
        "where the alert is active 20 min after the leak starts.",
        "",
        "## Skipped readings (every 7th fuel-flow reading invalid)",
        "",
        "| Leak | Detected within AC limit | Detection median (min) | Clean data median (min) |",
        "|---|---|---|---|",
    ]
    for rate, limit in ((1200.0, AC1_LIMIT_MIN), (600.0, AC2_LIMIT_MIN)):
        lines.append(
            f"| {rate:,.0f} kg/h | {count_detected(corrupted[rate], limit)}/100 "
            f"| {_stat([r.detection_min for r in corrupted[rate]])} "
            f"| {_stat([r.detection_min for r in by_rate[rate]])} |"
        )
    n_samples = sum(
        len(generate_flight(config, config.scenario("nominal"), seed=s)) for s in range(100)
    )
    without_ms = runtime_ms(config, plan, with_detection=False)
    with_ms = runtime_ms(config, plan, with_detection=True)
    lines += [
        "",
        "## Runtime (100 nominal flights, median of 5 runs, same machine)",
        "",
        "| Monitor | Time (ms) | Per sample (µs) |",
        "|---|---|---|",
        f"| Without leak detection (v1.0.1 behaviour) | {without_ms:.1f} "
        f"| {without_ms * 1000 / n_samples:.1f} |",
        f"| With leak detection (v1.1.0) | {with_ms:.1f} | {with_ms * 1000 / n_samples:.1f} |",
        "",
        f"Leak detection adds {100 * (with_ms / without_ms - 1):.0f}% runtime. Memory stays "
        "constant per flight: the window holds about 11 readings.",
    ]
    (out / "verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
