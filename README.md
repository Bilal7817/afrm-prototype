# AFRM — Aircraft Fuel and Range Management Prototype

> **Simulated data — not for operational use.** Academic prototype for DN6MD0003
> Aerospace Application Development (Assignment 1). All aircraft, route and reserve
> values are illustrative.

The prototype:

1. **Plans** pre-departure fuel: trip, contingency, alternate, final reserve and minimum block fuel, then checks whether the loaded fuel is **DISPATCHABLE**.
2. **Monitors** simulated in-flight samples: validates each one, smooths fuel flow, predicts landing fuel, endurance and range, and classifies the status as **GREEN / AMBER / RED** or **DATA INVALID**.

## Quick start

Requires Python 3.14 (pinned to 3.14.9 in `.python-version`).

```bash
python3.14 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt
python -m pip install -e .

afrm run-all                         # all scenarios -> results/*.csv
afrm monitor --scenario headwind     # status changes for one flight
afrm plan --scenario low_uplift      # fuel plan and dispatch check
afrm simulate --scenario nominal --out data/nominal.csv
afrm monitor --csv data/nominal.csv  # monitor recorded data
```

Add `--no-noise` for exact, noise-free values and `--seed N` to change the noise.

## Quality checks (same as CI)

```bash
ruff check .            # lint: E, F, B, UP, N, SIM
ruff format --check .   # formatting
mypy                    # strict static type checking
pytest --cov            # 90 tests, branch coverage (fails below 90%)
```

GitHub Actions runs these on Ubuntu and macOS for every push and pull request to `main`.

## Benchmark (sustainability evaluation)

```bash
python -m pip install -r requirements-bench.txt   # NumPy: benchmark only
python bench/benchmark.py
```

This compares standard-library streaming with NumPy batch processing at 200 and
1,000,000 samples. It reports median runtime, peak traced memory and the cost of
importing NumPy, and writes `results/benchmark.csv`. Memory is measured with
`tracemalloc`. It covers Python allocations made during the run, not total process memory.

## Project structure

```
config/afrm_config.json   aircraft, route, reserve policy, limits, scenarios, noise
src/afrm/models.py        typed immutable data models + JSON loading
src/afrm/planner.py       fuel plan and dispatch check        (REQ-01, 02)
src/afrm/monitor.py       validation, smoothing, status       (REQ-03 to 07)
src/afrm/simulator.py     seeded flight data, CSV I/O         (REQ-09)
src/afrm/cli.py           command-line interface
tests/                    pytest suite tagged by requirement
bench/benchmark.py        streaming vs NumPy benchmark
docs/requirements.md      requirements and traceability matrix
results/                  generated outputs (scenario summary, PLF series, benchmark)
```

## Fuel model and status rules

The planner and the monitor use the same steady-cruise model: fuel = fuel flow × time,
where time = distance ÷ ground speed.

| Status | Predicted landing fuel at destination |
|---|---|
| GREEN | ≥ alternate + final reserve (1,750 kg) |
| AMBER | ≥ final reserve (1,000 kg) and < 1,750 kg |
| RED | < final reserve (1,000 kg) |
| DATA INVALID | Sample fails a validation rule (see `docs/requirements.md`) |

These categories are prototype criteria. They are loosely inspired by the ICAO
reserve structure, but they are not ICAO or EASA fuel declarations.

## Assumptions and limitations

- Steady cruise only. There is no climb, descent, weight change or altitude effect on fuel flow.
- A headwind changes ground speed only. Remaining distance is treated as exact.
- Sensor noise is Gaussian and seeded: fuel flow 1%, fuel on board 10 kg, ground speed 5 km/h.
- The runtime uses the Python standard library only. It has no third-party dependencies.
