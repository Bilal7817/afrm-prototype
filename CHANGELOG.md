# Changelog

All notable changes to the AFRM application are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Change request CR-001, suspected fuel leak detection (`docs/CR-001-leak-detection.md`), with requirements REQ-11 to REQ-14 and acceptance criteria AC-1 to AC-5.

### Known issues
- **F-01:** unexplained fuel loss is not detected; warnings lag a loss-aware reference by up to 64 min (TC-B04). To be addressed by CR-001.

## [1.0.1] – 2026-11-14

Corrective release for defect DR-001. No change to the fuel planning or monitoring algorithms.

### Fixed
- **DR-001:** simulated timestamps carried floating-point error (e.g. 3,899.9999999999995 s instead of 3,900 s). After a single invalid reading, the next valid reading appeared 120.00000000000045 s after the last accepted one and was wrongly rejected by the 120 s gap rule. Timestamps are now generated in whole seconds (`simulator.py`). The two DR-001 regression tests now pass (previously expected failures).

### Added
- Configuration management documentation (`docs/CONFIGURATION.md`) identifying v1.0.0 as the controlled baseline.
- Test plan with failure-impact (criticality) assessment (`docs/TEST_PLAN.md`), revised to 1.1 (simplified scope).
- Baseline test campaign against v1.0.0: abnormal fuel-loss characterisation, MC/DC of the input range check, noise-stability and invalid-data robustness tests, profiling (`tests/`, `scripts/`, `results/baseline/`).

### Changed
- CI: `actions/checkout` updated from v5 to v7 (Dependabot, pull request #7). No change to source, configuration or tests.

## [1.0.0] – 2026-10-22

Initial controlled baseline (tag `v1.0.0`, commit `755a087`).

### Added
- Fuel planning and dispatch check: trip, contingency, alternate, final reserve and minimum block fuel (REQ-01, REQ-02).
- In-flight monitoring: five-reading fuel-flow smoothing, predicted landing fuel, endurance and range (REQ-03, REQ-04).
- GREEN / AMBER / RED status classification and DATA INVALID handling with timestamp recovery (REQ-05 to REQ-07).
- JSON configuration, seeded flight simulator and CSV input/output (REQ-08 to REQ-10).
- Command-line interface: `plan`, `simulate`, `monitor`, `run-all`.
- 90 automated tests with 100% statement and branch coverage; Ruff and mypy --strict.
- GitHub Actions CI on Ubuntu and macOS; `protect-main` ruleset; Dependabot monthly checks.
- Streaming versus NumPy benchmark.
