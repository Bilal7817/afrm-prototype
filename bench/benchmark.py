"""Sustainability benchmark: standard-library streaming vs NumPy batch.

Both approaches ingest the same lazily produced sensor stream and compute the
same outputs (smoothed fuel flow, predicted landing fuel, status, endurance
and range). The NumPy version implements the value checks only; the stateful
timestamp/distance recovery rules (REQ-07) are inherently sequential.

Usage (from the repository root, with requirements-bench.txt installed)::

    python bench/benchmark.py
    python bench/benchmark.py --sizes 200 1000000 --repeats 15 5

Reports median wall-clock runtime, peak traced memory (tracemalloc) and the
one-off cost of importing NumPy. No energy figure is measured.
"""

from __future__ import annotations

import argparse
import csv
import os
import platform
import random
import statistics
import subprocess
import sys
import time
import tracemalloc
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from afrm.models import AfrmConfig, FuelPlan, FuelSample, FuelStatus, load_config
from afrm.monitor import monitor_flight
from afrm.planner import plan_fuel

ROOT = Path(__file__).resolve().parents[1]
STATUS_CODES = {FuelStatus.GREEN: 0, FuelStatus.AMBER: 1, FuelStatus.RED: 2}


# ------------------------------------------------------------ data source


def sensor_stream(n: int, seed: int = 42) -> Iterator[FuelSample]:
    """Valid, noisy samples at 60 s intervals, produced lazily."""
    rng = random.Random(seed)
    step_km = 800.0 / 60.0
    for i in range(n):
        yield FuelSample(
            time_s=60.0 * i,
            fob_kg=6800.0 - 40.0 * (i % 100) + rng.gauss(0.0, 10.0),
            fuel_flow_kg_h=2400.0 * (1.0 + rng.gauss(0.0, 0.01)),
            ground_speed_km_h=800.0 + rng.gauss(0.0, 5.0),
            remaining_km=step_km * (n - i),
        )


# ------------------------------------------------------------ baseline


def run_source_only(n: int) -> int:
    """Cost of producing the sensor stream itself, common to both approaches."""
    count = 0
    for _ in sensor_stream(n):
        count += 1
    return count


# ------------------------------------------------------------ approach A: streaming


def run_streaming(n: int, config: AfrmConfig, plan: FuelPlan) -> Counter[FuelStatus]:
    """Constant-memory processing: keep only a status tally."""
    tally: Counter[FuelStatus] = Counter()
    for assessment in monitor_flight(sensor_stream(n), plan, config.monitoring):
        tally[assessment.status] += 1
    return tally


# ------------------------------------------------------------ approach B: NumPy batch


def run_numpy(n: int, config: AfrmConfig, plan: FuelPlan) -> tuple[Any, Any, Any, Any]:
    """Batch processing: load every sample into arrays, then compute in one pass.

    Returns arrays of predicted landing fuel, status code, endurance and range.
    """
    import numpy as np  # imported here so its cost is measured separately

    limits = config.monitoring
    data = np.array(
        [
            (s.time_s, s.fob_kg, s.fuel_flow_kg_h, s.ground_speed_km_h, s.remaining_km)
            for s in sensor_stream(n)
        ],
        dtype=np.float64,
    ).reshape(-1, 5)
    fob, flow, gs, rem = data[:, 1], data[:, 2], data[:, 3], data[:, 4]

    valid = (
        np.isfinite(data).all(axis=1)
        & (fob >= 0)
        & (flow >= limits.fuel_flow_min_kg_h)
        & (flow <= limits.fuel_flow_max_kg_h)
        & (gs >= limits.ground_speed_min_km_h)
        & (gs <= limits.ground_speed_max_km_h)
        & (rem >= 0)
    )
    # Moving average over up to `window` readings (partial window at start).
    window = limits.smoothing_window
    cumulative = np.concatenate(([0.0], np.cumsum(flow)))
    index = np.arange(len(flow))
    start = np.maximum(0, index - window + 1)
    smoothed = (cumulative[index + 1] - cumulative[start]) / (index + 1 - start)

    plf = fob - smoothed * (rem / gs)
    status = np.select(
        [plf >= plan.green_threshold_kg, plf >= plan.red_threshold_kg], [0, 1], default=2
    )
    status = np.where(valid, status, -1)  # -1 = DATA INVALID
    endurance = (fob - plan.final_reserve_kg) / smoothed
    return plf, status, endurance, endurance * gs


# ------------------------------------------------------------ equivalence check


def check_equivalence(config: AfrmConfig, plan: FuelPlan, n: int = 200) -> float:
    """Return the largest PLF difference; raise if statuses differ."""
    import numpy as np

    streamed = list(monitor_flight(sensor_stream(n), plan, config.monitoring))
    batch_plf, batch_status, _, _ = run_numpy(n, config, plan)
    stream_plf = np.array([a.predicted_landing_fuel_kg for a in streamed], dtype=np.float64)
    stream_status = np.array([STATUS_CODES[a.status] for a in streamed])
    if not np.array_equal(stream_status, batch_status):
        raise AssertionError("Streaming and NumPy statuses differ")
    return float(np.max(np.abs(stream_plf - batch_plf)))


# ------------------------------------------------------------ measurement


def median_runtime_s(func: Callable[[], object], repeats: int) -> float:
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return statistics.median(times)


def peak_memory_mib(func: Callable[[], object]) -> float:
    tracemalloc.start()
    func()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / 2**20


def _python_output(code: str) -> float:
    """Run a snippet in a fresh interpreter and return the number it prints."""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    return float(result.stdout)


def numpy_import_cost(repeats: int = 10) -> tuple[float, float]:
    """Median time (s) and traced memory (MiB) to import NumPy in a fresh process."""
    time_code = "import time; t = time.perf_counter(); import numpy; print(time.perf_counter() - t)"
    memory_code = (
        "import tracemalloc; tracemalloc.start(); import numpy; "
        "print(tracemalloc.get_traced_memory()[1])"
    )
    times = [_python_output(time_code) for _ in range(repeats)]
    return statistics.median(times), _python_output(memory_code) / 2**20


def environment() -> str:
    mac = platform.mac_ver()[0]
    system = f"macOS {mac}" if mac else f"{platform.system()} {platform.release()}"
    return (
        f"{system}, {platform.machine()}, {os.cpu_count()} logical CPUs, "
        f"Python {platform.python_version()}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[200, 1_000_000])
    parser.add_argument("--repeats", type=int, nargs="+", default=[15, 5])
    parser.add_argument("--out", default=str(ROOT / "results" / "benchmark.csv"))
    args = parser.parse_args()
    if len(args.repeats) != len(args.sizes):
        parser.error("--repeats needs one value per size")

    config = load_config(ROOT / "config" / "afrm_config.json")
    plan = plan_fuel(config)

    print(f"Environment: {environment()}")
    max_diff = check_equivalence(config, plan)
    print(f"Equivalence (200 samples): identical statuses, max PLF difference {max_diff:.2e} kg")
    import_s, import_mib = numpy_import_cost()
    print(f"NumPy import: median {import_s * 1000:.1f} ms, {import_mib:.1f} MiB traced\n")

    rows: list[list[str]] = []
    print("| Approach | Samples | Median runtime | Peak memory | Repeats |")
    print("|---|---|---|---|---|")
    for n, repeats in zip(args.sizes, args.repeats, strict=True):
        for name, func in (
            ("Data source only (baseline)", lambda n=n: run_source_only(n)),
            ("Python streaming", lambda n=n: run_streaming(n, config, plan)),
            ("NumPy batch", lambda n=n: run_numpy(n, config, plan)),
        ):
            runtime = median_runtime_s(func, repeats)
            memory = peak_memory_mib(func)
            print(f"| {name} | {n:,} | {runtime * 1000:,.2f} ms | {memory:,.3f} MiB | {repeats} |")
            rows.append([name, str(n), f"{runtime * 1000:.4f}", f"{memory:.4f}", str(repeats)])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["# " + environment()])
        writer.writerow(
            ["# numpy_import_ms", f"{import_s * 1000:.2f}", "numpy_import_mib", f"{import_mib:.2f}"]
        )
        writer.writerow(["approach", "samples", "median_runtime_ms", "peak_memory_mib", "repeats"])
        writer.writerows(rows)
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
