# AFRM Test Plan

| Field | Value |
|---|---|
| Document | AFRM Test Plan |
| Revision | 2 – baseline campaign and CR-001 verification |
| Software under test | AFRM v1.0.0 (baseline, Section 5) and v1.1.0 (CR-001, Section 5.1) |
| Date | 14 November 2026 |

> The AFRM is a simulated, non-operational prototype. The criticality levels below are **notional**. They are used to scale the rigour of testing, not to claim certification.

## 1. Purpose and scope

This plan defines how the v1.0.0 baseline is tested before any change is made. It covers:

- the failure-impact (criticality) assessment and the test rigour it justifies;
- test methods, environment and coverage targets;
- the baseline test cases and their pass/fail criteria.

Revision 2 adds verification of change request CR-001 (Section 5.1).

## 2. Failure-impact (criticality) assessment

Each function is assessed for its worst credible failure, assuming its output is relied upon during flight planning or monitoring. Severity uses the failure condition categories of aircraft safety assessment (catastrophic, hazardous, major, minor, no safety effect). The equivalent DO-178C software level sets the verification rigour.

| ID | Function | Worst credible failure | Effect | Mitigation outside AFRM | Severity | Notional level |
|---|---|---|---|---|---|---|
| F1 | Fuel plan and dispatch check (`planner.py`) | Minimum block fuel underestimated; aircraft shown DISPATCHABLE when it is not | Departure with insufficient reserves | Independent operator flight planning | Hazardous | B |
| F2 | Predicted landing fuel and status (`monitor.py`) | **Optimistic status: GREEN or AMBER shown when landing fuel will be below reserve** | Delayed recognition of a fuel shortage | Aircraft fuel quantity indication and crew procedures | Hazardous | B |
| F3 | Predicted landing fuel and status | Pessimistic status: AMBER or RED shown when fuel is sufficient | Unnecessary diversion or workload | Crew cross-check | Major | C |
| F4 | Input validation and recovery (`monitor.py`) | Invalid data accepted, corrupting the prediction | As F2 | As F2 | Hazardous | B |
| F5 | Input validation and recovery | Valid data rejected; monitoring lost (DATA INVALID) | Loss of advisory function | Reversion to other fuel information | Major | C |
| F6 | Fuel-flow smoothing (`monitor.py`) | Excessive lag after a change in fuel flow | Delayed status change | As F2 | Major | C |
| F7 | Abnormal fuel loss (not modelled in v1.0.0; addressed by CR-001 in v1.1.0) | Fuel lost without matching reported fuel flow is not recognised; prediction remains optimistic | As F2 | As F2 | Hazardous | B |
| F8 | Simulator, CSV input/output, CLI formatting | Incorrect test data or display formatting | Test or display error, no direct operational effect | Test review | Minor | D |

**Key finding for testing:** the highest-severity failures (F1, F2, F4, F7) are all *optimistic* outputs. An optimistic error is more dangerous than a pessimistic one, so testing focuses on boundaries where an optimistic result could occur, and on conditions the baseline does not model (F7).

### 2.1 Verification rigour derived from the assessment

| Notional level | Functions | Required verification |
|---|---|---|
| B | F1, F2, F4, F7 | Requirements-based normal and robustness tests; boundary-value tests; 100% statement and decision (branch) coverage. **MC/DC applied selectively** to the most critical compound decisions, as rigour above the Level B objective. |
| C | F3, F5, F6 | Requirements-based tests; 100% statement coverage |
| D | F8 | Requirements-based tests |

## 3. Test methods

| Method | Purpose | Applied to |
|---|---|---|
| Requirements-based testing | Show each requirement (REQ-01 to REQ-10) is met | All functions |
| Boundary-value analysis and equivalence partitioning | Test exact thresholds where an optimistic error could occur | Status thresholds (1,000 / 1,750 kg), minimum block fuel, validation limits, 120 s gap |
| Scenario testing | Show end-to-end behaviour on realistic flights | Nominal, headwind, low uplift |
| Robustness and fault-injection testing | Show behaviour under abnormal conditions | Abnormal fuel loss (F7), intermittent invalid data, timestamp gaps |
| Statistical (multi-seed) testing | Measure behaviour under sensor noise rather than one random sample | Status stability across seeded noisy flights |
| Structural coverage analysis | Measure which code the tests exercise | Statement and branch coverage; MC/DC on the input range-check decision |
| Performance profiling | Identify where processing time is spent | `cProfile` of `afrm run-all`; repeated benchmark runs |
| Interactive debugging | Inspect internal state during a failure scenario | VS Code debugger in the abnormal fuel-loss case |

## 4. Test environment

| Item | Configuration |
|---|---|
| Local hardware | MacBook Air, Apple Silicon (arm64), 8 logical CPUs, macOS 15.6 |
| Interpreter | Python 3.14.9 (pinned in `.python-version`) |
| Test tools | pytest 9.1.1, pytest-cov 7.1.0, coverage 7.16.2 |
| Static analysis | Ruff 0.17.1, mypy 2.4.0 (`--strict`) |
| Profiling and debugging | `cProfile` (standard library); VS Code Python debugger |
| CI | GitHub Actions, `ubuntu-latest` and `macos-latest` |
| Baseline isolation | Baseline tests run against an isolated checkout of the tag: `git worktree add ../afrm-v1.0.0 v1.0.0` |
| Test data | Seeded simulator (seed 42 unless stated); noise σ: fuel flow 1%, fuel on board 10 kg, ground speed 5 km/h |

## 5. Baseline test cases

| ID | Test | Method | Expected or recorded result | Type |
|---|---|---|---|---|
| TC-B01 | Full regression suite at v1.0.0 | Requirements-based | 90 tests pass | Pass/fail |
| TC-B02 | Structural coverage | Coverage analysis | 100% statement and branch coverage | Pass/fail |
| TC-B03 | MC/DC analysis of the input range-check decision (`_in_range`: finite, ≥ low, ≤ high) | Structural (MC/DC) | Each condition shown to independently affect the decision, or gaps recorded | Pass/fail |
| TC-B04 | Abnormal fuel loss: nominal flight plus 300, 600 and 1,200 kg/h loss from 40 min (seed 42) | Fault injection | Record first AMBER and RED times and actual landing fuel; compare with a reference that knows the loss rate | Characterisation |
| TC-B05 | Status stability on nominal flights across 100 seeds | Statistical | Record the number of flights whose status ever leaves GREEN | Characterisation |
| TC-B06a | Isolated invalid samples (every 7th fuel-flow reading corrupted) | Robustness | Only the corrupted samples are reported DATA INVALID; monitoring continues; statuses unaffected | Pass/fail |
| TC-B06b | Two consecutive invalid samples | Robustness | Record how the 120 s gap rule treats the next valid sample | Characterisation |
| TC-B07 | Performance profile of `afrm run-all`, plus benchmark median runtimes | Profiling | Record the functions with the largest cumulative time and the median runtimes | Characterisation |

### 5.1 CR-001 verification (v1.1.0)

Leak detection reduces F7 (optimistic status under a leak) but can add F3 (pessimistic status: a false alert or false escalation). Both are tested. All new decisions in `leak.py` and the status rule have a single condition, so decision coverage also gives MC/DC; the window-trimming condition (two conditions) is covered by the window tests.

| ID | Test | Method | Expected result | Type |
|---|---|---|---|---|
| TC-V01 | Full regression suite at v1.1.0 | Requirements-based | All tests pass, including all v1.0.1 tests unchanged | Pass/fail |
| TC-V02 | Structural coverage | Coverage analysis | 100% statement and branch coverage | Pass/fail |
| TC-V03 | Alert threshold boundary (74.99 / 75.00 / 75.01 kg), window filling, sliding, skipped readings, gap reset, sudden flow change | Boundary-value and robustness (`test_leak.py`, `test_monitor_leak.py`) | As REQ-11 to REQ-14 | Pass/fail |
| TC-V04 | AC-1: 1,200 kg/h leak, 100 seeds | Statistical | Detected within 11 min in ≥ 95 | Pass/fail |
| TC-V05 | AC-2: 600 kg/h leak, 100 seeds | Statistical | Detected within 22 min in ≥ 95 | Pass/fail |
| TC-V06 | AC-3: leak-free nominal and headwind flights, seeds 0–999 each | Statistical | No alerts | Pass/fail |
| TC-V07 | AC-4: leak-free nominal flights, seeds 0–999 | Statistical | No GREEN to AMBER/RED escalation | Pass/fail |
| TC-V08 | AC-5: standard PLF with and without leak detection | Comparison | Identical | Pass/fail |
| TC-V09 | 300 kg/h leak; alert flicker; leak-rate and adjusted PLF error; every 7th reading invalid; warning delay against v1.0.0 | Statistical | Recorded | Characterisation |
| TC-V10 | Runtime with and without leak detection; `cProfile` of `afrm run-all`; debugger inspection at the threshold check | Profiling and debugging | Recorded | Characterisation |

Run with `python -m scripts.verify_cr001` (results in `results/v1.1.0/verification.md`) and `python -m scripts.make_figures`.

**Characterisation** tests record what the baseline actually does. They have no pass/fail outcome on v1.0.0; their findings are used to identify and justify changes.

## 6. Entry and exit criteria

**Entry:** baseline identified (tag `v1.0.0`, commit `755a087`); no algorithm changes since the tag (see `docs/CONFIGURATION.md`); test environment as in Section 4.

**Exit:**
- all baseline test cases executed;
- pass/fail tests passed, or failures recorded with analysis;
- results stored in `results/baseline/` with the commit hash and environment details (summary in `results/baseline/SUMMARY.md`);
- findings reviewed and any resulting change requests raised.

## 7. Revision history

| Revision | Date | Description |
|---|---|---|
| 1 | 13 November 2026 | Initial plan: criticality assessment and baseline test campaign |
| 1.1 | 13 November 2026 | Scope simplified: property-based testing removed; MC/DC limited to the input range-check decision; TC-B06 split into isolated and consecutive invalid samples. Baseline results in `results/baseline/SUMMARY.md`. |
| 2 | 14 November 2026 | CR-001 verification added (Section 5.1, TC-V01 to TC-V10). |
