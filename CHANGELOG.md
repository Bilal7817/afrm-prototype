# Changelog

All notable changes to the AFRM application are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Configuration management documentation (`docs/CONFIGURATION.md`) identifying v1.0.0 as the controlled baseline.
- Test plan with failure-impact (criticality) assessment (`docs/TEST_PLAN.md`).

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
