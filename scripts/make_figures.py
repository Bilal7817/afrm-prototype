"""Report figures generated from project data (CR-001, v1.1.0).

Run after scripts.verify_cr001, from the repository root:

    python -m pip install matplotlib      # figures only, not needed by AFRM
    python -m scripts.make_figures

Writes PNG files to results/v1.1.0/figures/.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402

from afrm.models import FuelStatus, load_config  # noqa: E402
from afrm.monitor import monitor_flight  # noqa: E402
from afrm.planner import plan_fuel  # noqa: E402
from afrm.simulator import generate_flight  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "v1.1.0"
OUT = RESULTS / "figures"

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
LEAK_START_MIN = 40.0


def _style(ax: Axes) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def figure_plf(rate_kg_h: float = 1200.0, seed: int = 42) -> Path:
    """Standard (v1.0.0 behaviour) vs leak-adjusted PLF for one leaking flight."""
    config = load_config(ROOT / "config" / "afrm_config.json")
    plan = plan_fuel(config)
    samples = generate_flight(
        config, config.scenario("nominal"), seed=seed, leak_rate_kg_h=rate_kg_h
    )
    results = list(monitor_flight(samples, plan, config.monitoring, config.leak_detection))
    actual = generate_flight(
        config, config.scenario("nominal"), noisy=False, leak_rate_kg_h=rate_kg_h
    )[-1].fob_kg

    t = [a.time_s / 60 for a in results]
    nan = math.nan  # gaps in a line where there is no value
    standard = [
        nan if a.predicted_landing_fuel_kg is None else a.predicted_landing_fuel_kg for a in results
    ]
    adjusted = [nan if a.leak_adjusted_plf_kg is None else a.leak_adjusted_plf_kg for a in results]
    first_alert = next(a.time_s / 60 for a in results if a.leak_alert)
    red_v110 = next(a.time_s / 60 for a in results if a.status is FuelStatus.RED)
    red_v100 = next(
        a.time_s / 60
        for a in monitor_flight(samples, plan, config.monitoring)
        if a.status is FuelStatus.RED
    )

    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=200)
    _style(ax)
    for level, label in (
        (plan.green_threshold_kg, "GREEN ≥ 1,750 kg"),
        (plan.red_threshold_kg, "RED < 1,000 kg"),
    ):
        ax.axhline(level, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
        ax.text(1, level + 25, label, color=MUTED, fontsize=8)
    ax.axhline(actual, color=AQUA, linewidth=1.2)
    ax.text(1, actual - 90, f"Actual landing fuel {actual:,.0f} kg", color=MUTED, fontsize=8)

    ax.plot(t, standard, color=BLUE, linewidth=2, label="Standard PLF (as v1.0.0)")
    ax.plot(t, adjusted, color=ORANGE, linewidth=2, label="Leak-adjusted PLF (v1.1.0, while alert)")
    ax.axvline(LEAK_START_MIN, color=INK, linewidth=0.8)
    ax.text(LEAK_START_MIN + 1, 2650, "Leak starts", fontsize=8, color=INK)
    alert_plf = next(a.leak_adjusted_plf_kg for a in results if a.leak_adjusted_plf_kg is not None)
    ax.plot([first_alert], [alert_plf], marker="o", markersize=5, color=INK)
    ax.annotate(
        f"Alert {first_alert:.0f} min",
        (first_alert, alert_plf),
        xytext=(8, 4),
        textcoords="offset points",
        fontsize=8,
        color=INK,
    )
    for x, label, offset, align in (
        (red_v110, f"v1.1.0 RED {red_v110:.0f} min", (8, 6), "left"),
        (red_v100, f"v1.0.0 RED {red_v100:.0f} min", (4, -40), "right"),
    ):
        ax.plot([x], [plan.red_threshold_kg], marker="o", markersize=5, color=INK)
        ax.annotate(
            label,
            (x, plan.red_threshold_kg),
            xytext=offset,
            textcoords="offset points",
            ha=align,
            fontsize=8,
            color=INK,
        )

    ax.set_xlim(0, max(t) + 2)
    ax.set_ylim(500, 2800)
    ax.set_xlabel("Flight time (min)", color=MUTED, fontsize=9)
    ax.set_ylabel("Predicted landing fuel (kg)", color=MUTED, fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    fig.tight_layout()
    path = OUT / f"fig_plf_{rate_kg_h:.0f}kgh_seed{seed}.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def figure_detection_times() -> Path:
    """Detection time per seed for each leak rate, with the AC limits."""
    with (RESULTS / "detection_times.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rates = (300.0, 600.0, 1200.0)
    limits = {600.0: 22.0, 1200.0: 11.0}

    fig, ax = plt.subplots(figsize=(7.5, 3.2), dpi=200)
    _style(ax)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    for y, rate in enumerate(rates):
        times = [
            float(r["detection_min"])
            for r in rows
            if float(r["leak_rate_kg_h"]) == rate and r["detection_min"]
        ]
        missed = sum(
            1 for r in rows if float(r["leak_rate_kg_h"]) == rate and not r["detection_min"]
        )
        jitter = [y + ((i * 37) % 21 - 10) / 50 for i in range(len(times))]
        ax.scatter(times, jitter, s=12, color=BLUE, alpha=0.6, linewidths=0)
        if rate in limits:
            ax.plot([limits[rate]] * 2, [y - 0.35, y + 0.35], color=ORANGE, linewidth=2)
            ax.text(
                limits[rate] + 0.8,
                y + 0.2,
                f"AC limit {limits[rate]:.0f} min",
                color=INK,
                fontsize=8,
            )
        if missed:
            ax.text(max(times) + 2, y - 0.05, f"{missed} not detected", color=INK, fontsize=8)
    ax.set_yticks(range(len(rates)), [f"{r:,.0f} kg/h" for r in rates])
    ax.set_xlabel(
        "Detection time after leak start (min), 100 seeds per leak rate", color=MUTED, fontsize=9
    )
    fig.tight_layout()
    path = OUT / "fig_detection_times.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def figure_false_alarm_margin() -> Path:
    """Largest discrepancy per leak-free flight against the 75 kg threshold."""
    with (RESULTS / "nominal_discrepancy.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # Nominal flights only: headwind flights share the same noise (verification.md).
    values = [float(r["nominal_max_discrepancy_kg"]) for r in rows]
    threshold = load_config(ROOT / "config" / "afrm_config.json").leak_detection.threshold_kg

    fig, ax = plt.subplots(figsize=(7.5, 3.4), dpi=200)
    _style(ax)
    ax.hist(values, bins=range(0, 82, 2), color=BLUE, edgecolor="white", linewidth=1)
    ax.axvline(threshold, color=ORANGE, linewidth=2)
    ax.text(
        threshold - 1,
        ax.get_ylim()[1] * 0.9,
        f"Threshold {threshold:.0f} kg",
        color=INK,
        fontsize=8,
        ha="right",
    )
    largest = max(values)
    ax.plot([largest], [0], marker="v", markersize=7, color=INK, clip_on=False)
    ax.annotate(
        f"Largest {largest:.1f} kg (1 flight)",
        (largest, 0),
        xytext=(-6, 40),
        textcoords="offset points",
        ha="right",
        fontsize=8,
        color=INK,
        arrowprops={"arrowstyle": "-", "color": INK, "linewidth": 0.8},
    )
    ax.set_xlabel(
        f"Largest discrepancy in a leak-free nominal flight (kg), {len(values):,} flights",
        color=MUTED,
        fontsize=9,
    )
    ax.set_ylabel("Flights", color=MUTED, fontsize=9)
    fig.tight_layout()
    path = OUT / "fig_false_alarm_margin.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for path in (figure_plf(), figure_detection_times(), figure_false_alarm_margin()):
        print(f"Wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
