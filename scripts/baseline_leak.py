"""Characterise how the AFRM monitor responds to unexplained fuel loss (TC-B04).

The fuel loss is added to simulated samples here, outside the AFRM code:
fuel on board falls faster than the reported fuel flow explains, as it would
with a leak. The AFRM source is not modified.

Run against the exact v1.0.0 baseline using an isolated checkout:

    git worktree add ../afrm-v1.0.0 v1.0.0
    PYTHONPATH=../afrm-v1.0.0/src python -m scripts.baseline_leak

Writes leak_characterisation.csv and leak_characterisation.md to results/baseline/.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import platform
import subprocess
from collections.abc import Sequence
from pathlib import Path

import afrm
from afrm.models import AfrmConfig, Assessment, FuelPlan, FuelSample, FuelStatus, load_config
from afrm.monitor import classify, monitor_flight
from afrm.planner import plan_fuel
from afrm.simulator import generate_flight

ROOT = Path(__file__).resolve().parents[1]
LEAK_RATES_KG_H = (0.0, 300.0, 600.0, 1200.0)
LEAK_START_MIN = 40.0
NOT_GREEN = {FuelStatus.AMBER, FuelStatus.RED}


def describe() -> dict[str, str]:
    """Which AFRM code was actually imported, and on what machine."""
    source = Path(afrm.__file__).resolve().parent
    commit = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    env = f"{platform.platform()}, Python {platform.python_version()}"
    return {"afrm_source": str(source), "commit": commit or "unknown", "environment": env}


def inject_leak(
    samples: Sequence[FuelSample], rate_kg_h: float, start_min: float = LEAK_START_MIN
) -> list[FuelSample]:
    """Reduce fuel on board after start_min without changing reported fuel flow."""
    start_s = start_min * 60.0
    return [
        dataclasses.replace(s, fob_kg=s.fob_kg - rate_kg_h * max(0.0, s.time_s - start_s) / 3600.0)
        for s in samples
    ]


def first_time_min(assessments: Sequence[Assessment], wanted: set[FuelStatus]) -> float | None:
    """Time (min) of the first assessment with one of the wanted statuses."""
    for a in assessments:
        if a.status in wanted:
            return a.time_s / 60.0
    return None


@dataclasses.dataclass(frozen=True)
class LeakResult:
    leak_rate_kg_h: float
    actual_landing_fuel_kg: float
    actual_landing_status: FuelStatus
    reference_first_not_green_min: float | None
    reference_first_red_min: float | None
    baseline_first_not_green_min: float | None
    baseline_first_red_min: float | None


def characterise(
    config: AfrmConfig, plan: FuelPlan, rate_kg_h: float, seed: int = 42
) -> LeakResult:
    """Compare the monitor's statuses with a reference that knows the loss rate."""
    scenario = config.scenario("nominal")
    noisy = inject_leak(generate_flight(config, scenario, seed=seed, noisy=True), rate_kg_h)
    clean = inject_leak(generate_flight(config, scenario, noisy=False), rate_kg_h)
    assessments = list(monitor_flight(noisy, plan, config.monitoring))

    # Reference: predicted landing fuel if the loss rate were known exactly.
    flow = config.aircraft.cruise_fuel_flow_kg_h
    reference: list[Assessment] = []
    for s in clean:
        loss = rate_kg_h if s.time_s > LEAK_START_MIN * 60.0 else 0.0
        plf = s.fob_kg - (flow + loss) * s.remaining_km / s.ground_speed_km_h
        reference.append(Assessment(s.time_s, classify(plf, plan), plf, None, None))

    actual = clean[-1].fob_kg
    return LeakResult(
        leak_rate_kg_h=rate_kg_h,
        actual_landing_fuel_kg=actual,
        actual_landing_status=classify(actual, plan),
        reference_first_not_green_min=first_time_min(reference, NOT_GREEN),
        reference_first_red_min=first_time_min(reference, {FuelStatus.RED}),
        baseline_first_not_green_min=first_time_min(assessments, NOT_GREEN),
        baseline_first_red_min=first_time_min(assessments, {FuelStatus.RED}),
    )


def _fmt(value: float | None) -> str:
    return "never" if value is None else f"{value:.0f}"


def _lag(baseline: float | None, reference: float | None) -> str:
    if reference is None:
        return "n/a"
    if baseline is None:
        return "never warned"
    return f"{baseline - reference:.0f}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "results" / "baseline"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    config = load_config(ROOT / "config" / "afrm_config.json")
    plan = plan_fuel(config)
    info = describe()
    results = [characterise(config, plan, rate, args.seed) for rate in LEAK_RATES_KG_H]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "leak_characterisation.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([f.name for f in dataclasses.fields(LeakResult)])
        for r in results:
            writer.writerow(
                [
                    r.leak_rate_kg_h,
                    f"{r.actual_landing_fuel_kg:.1f}",
                    r.actual_landing_status.value,
                    _fmt(r.reference_first_not_green_min),
                    _fmt(r.reference_first_red_min),
                    _fmt(r.baseline_first_not_green_min),
                    _fmt(r.baseline_first_red_min),
                ]
            )

    lines = [
        "# Baseline abnormal fuel-loss characterisation (TC-B04)",
        "",
        f"- AFRM source: `{info['afrm_source']}`",
        f"- Commit: `{info['commit']}`",
        f"- Environment: {info['environment']}",
        f"- Flight: nominal, seed {args.seed}; fuel loss starts at {LEAK_START_MIN:.0f} min",
        "",
        "| Loss rate (kg/h) | Actual landing fuel (kg) | Actual landing status "
        "| Reference: first AMBER/RED (min) | Reference: first RED (min) "
        "| Baseline: first AMBER/RED (min) | Baseline: first RED (min) "
        "| Baseline lag behind reference (min) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.leak_rate_kg_h:.0f} | {r.actual_landing_fuel_kg:,.0f} "
            f"| {r.actual_landing_status.value} | {_fmt(r.reference_first_not_green_min)} "
            f"| {_fmt(r.reference_first_red_min)} | {_fmt(r.baseline_first_not_green_min)} "
            f"| {_fmt(r.baseline_first_red_min)} "
            f"| {_lag(r.baseline_first_not_green_min, r.reference_first_not_green_min)} |"
        )
    lines += [
        "",
        "The reference is the status a monitor would show if it knew the loss rate exactly.",
        "It is a best case, not an achievable detector.",
    ]
    (out / "leak_characterisation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
