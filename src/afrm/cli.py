"""Command-line interface for the AFRM prototype.

Examples::

    afrm plan --scenario nominal
    afrm simulate --scenario headwind --out data/headwind.csv
    afrm monitor --scenario headwind
    afrm monitor --leak-rate 1200          # simulated leak from 40 min
    afrm monitor --csv data/headwind.csv --scenario headwind
    afrm run-all --out results
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Sequence
from pathlib import Path

from afrm.models import AfrmConfig, Assessment, FuelPlan, FuelStatus, Scenario, load_config
from afrm.monitor import monitor_flight
from afrm.planner import check_dispatch, plan_fuel
from afrm.simulator import generate_flight, read_csv, write_csv

DEFAULT_CONFIG = Path("config") / "afrm_config.json"
DISCLAIMER = "SIMULATED DATA - NOT FOR OPERATIONAL USE"


def _format_plan(plan: FuelPlan, scenario: Scenario) -> str:
    dispatch = check_dispatch(plan, scenario.loaded_fuel_kg)
    rows = [
        ("Trip time", f"{plan.trip_time_h:.3f} h"),
        ("Taxi", f"{plan.taxi_kg:,.0f} kg"),
        ("Trip", f"{plan.trip_kg:,.0f} kg"),
        ("Contingency", f"{plan.contingency_kg:,.0f} kg"),
        ("Alternate", f"{plan.alternate_kg:,.0f} kg"),
        ("Final reserve", f"{plan.final_reserve_kg:,.0f} kg"),
        ("Minimum block fuel", f"{plan.minimum_block_fuel_kg:,.0f} kg"),
        (f"Loaded fuel ({scenario.name})", f"{scenario.loaded_fuel_kg:,.0f} kg"),
        ("Dispatch status", dispatch.value),
    ]
    width = max(len(label) for label, _ in rows)
    return "\n".join(f"  {label:<{width}}  {value}" for label, value in rows)


def _transitions(assessments: Sequence[Assessment]) -> list[Assessment]:
    """First sample of each new status or leak-alert state (including the first)."""
    out: list[Assessment] = []
    previous: tuple[FuelStatus, bool] | None = None
    for a in assessments:
        state = (a.status, a.leak_alert)
        if state != previous:
            out.append(a)
            previous = state
    return out


def _status_sequence(assessments: Sequence[Assessment]) -> str:
    """Status changes only, e.g. 'GREEN -> AMBER'."""
    out: list[str] = []
    for a in assessments:
        if not out or out[-1] != a.status.value:
            out.append(a.status.value)
    return " -> ".join(out)


def _format_assessment(a: Assessment) -> str:
    minutes = a.time_s / 60.0
    if a.predicted_landing_fuel_kg is None:
        return f"  t={minutes:6.1f} min  {a.status.value:<12}  ({a.reason})"
    endurance = "n/a" if a.endurance_h is None else f"{a.endurance_h:5.2f} h"
    rng = "n/a" if a.range_km is None else f"{a.range_km:6,.0f} km"
    line = (
        f"  t={minutes:6.1f} min  {a.status.value:<12}  "
        f"PLF {a.predicted_landing_fuel_kg:7,.0f} kg  "
        f"endurance {endurance}  range {rng}"
    )
    if a.leak_alert and a.leak_rate_kg_h is not None and a.leak_adjusted_plf_kg is not None:
        line += (
            f"\n      SUSPECTED FUEL LEAK  ~{a.leak_rate_kg_h:,.0f} kg/h  "
            f"leak-adjusted PLF {a.leak_adjusted_plf_kg:7,.0f} kg"
        )
    return line


def _kg(value: float | None) -> str:
    """Format an optional fuel value for CSV output (blank when invalid)."""
    return "" if value is None else f"{value:.1f}"


def _run_monitor(
    config: AfrmConfig,
    scenario: Scenario,
    seed: int,
    noisy: bool,
    csv_path: str | None,
    leak_rate_kg_h: float = 0.0,
) -> list[Assessment]:
    plan = plan_fuel(config)
    if csv_path:
        samples = read_csv(csv_path)
    else:
        samples = generate_flight(
            config, scenario, seed=seed, noisy=noisy, leak_rate_kg_h=leak_rate_kg_h
        )
    return list(monitor_flight(samples, plan, config.monitoring, config.leak_detection))


def cmd_plan(args: argparse.Namespace, config: AfrmConfig) -> int:
    scenario = config.scenario(args.scenario)
    print(f"AFRM fuel plan - {config.route.origin} to {config.route.destination}")
    print(_format_plan(plan_fuel(config), scenario))
    return 0


def cmd_simulate(args: argparse.Namespace, config: AfrmConfig) -> int:
    scenario = config.scenario(args.scenario)
    samples = generate_flight(
        config, scenario, seed=args.seed, noisy=not args.no_noise, leak_rate_kg_h=args.leak_rate
    )
    write_csv(samples, args.out)
    print(f"Wrote {len(samples)} samples for '{scenario.name}' to {args.out}")
    return 0


def cmd_monitor(args: argparse.Namespace, config: AfrmConfig) -> int:
    scenario = config.scenario(args.scenario)
    assessments = _run_monitor(
        config, scenario, args.seed, not args.no_noise, args.csv, args.leak_rate
    )
    print(f"AFRM monitor - scenario '{scenario.name}'  [{DISCLAIMER}]")
    print(_format_plan(plan_fuel(config), scenario))
    print("Status changes:")
    for a in _transitions(assessments):
        print(_format_assessment(a))
    print("Final sample:")
    print(_format_assessment(assessments[-1]))
    return 0


def _write_rows(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def cmd_run_all(args: argparse.Namespace, config: AfrmConfig) -> int:
    plan = plan_fuel(config)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: list[list[str]] = []
    series: list[list[str]] = []

    noise = "off" if args.no_noise else "on"
    print(f"AFRM run-all  [{DISCLAIMER}]  seed={args.seed} noise={noise}")
    for scenario in config.scenarios:
        assessments = _run_monitor(config, scenario, args.seed, not args.no_noise, None)
        dispatch = check_dispatch(plan, scenario.loaded_fuel_kg).value
        statuses = _status_sequence(assessments)
        final = assessments[-1]
        print(f"  {scenario.name:<11} {dispatch:<17} {statuses}")

        summary.append(
            [
                scenario.name,
                f"{scenario.loaded_fuel_kg:.0f}",
                dispatch,
                statuses,
                _kg(final.predicted_landing_fuel_kg),
                f"{final.time_s / 60:.1f}",
            ]
        )
        for a in assessments:
            series.append(
                [
                    scenario.name,
                    f"{a.time_s / 60:.2f}",
                    a.status.value,
                    _kg(a.predicted_landing_fuel_kg),
                    "1" if a.leak_alert else "0",
                    _kg(a.leak_adjusted_plf_kg),
                ]
            )

    _write_rows(
        out_dir / "summary.csv",
        [
            "scenario",
            "loaded_fuel_kg",
            "dispatch",
            "status_sequence",
            "final_plf_kg",
            "flight_time_min",
        ],
        summary,
    )
    _write_rows(
        out_dir / "plf_timeseries.csv",
        [
            "scenario",
            "time_min",
            "status",
            "predicted_landing_fuel_kg",
            "leak_alert",
            "leak_adjusted_plf_kg",
        ],
        series,
    )
    print(f"Wrote {out_dir / 'summary.csv'} and {out_dir / 'plf_timeseries.csv'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="afrm", description=f"AFRM prototype ({DISCLAIMER})")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="JSON configuration file")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--seed", type=int, default=42, help="random seed (default 42)")
        p.add_argument("--no-noise", action="store_true", help="disable sensor noise")

    def leak_option(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--leak-rate",
            type=float,
            default=0.0,
            help="simulated fuel leak in kg/h, starting at 40 min (default 0)",
        )

    p_plan = sub.add_parser("plan", help="pre-departure fuel plan and dispatch check")
    p_plan.add_argument("--scenario", default="nominal")

    p_sim = sub.add_parser("simulate", help="generate simulated flight data as CSV")
    p_sim.add_argument("--scenario", default="nominal")
    p_sim.add_argument("--out", required=True)
    common(p_sim)
    leak_option(p_sim)

    p_mon = sub.add_parser("monitor", help="run the in-flight fuel monitor")
    p_mon.add_argument("--scenario", default="nominal")
    p_mon.add_argument("--csv", default=None, help="read samples from CSV instead")
    common(p_mon)
    leak_option(p_mon)

    p_all = sub.add_parser("run-all", help="run every scenario and write results CSVs")
    p_all.add_argument("--out", default="results")
    common(p_all)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    handlers = {
        "plan": cmd_plan,
        "simulate": cmd_simulate,
        "monitor": cmd_monitor,
        "run-all": cmd_run_all,
    }
    return handlers[args.command](args, config)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
