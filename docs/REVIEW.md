# Release Review: v1.1.0 (CR-001 Suspected Fuel Leak Detection)

| Field | Value |
|---|---|
| Item reviewed | CR-001 implementation (`feat/leak-detection`) and verification results |
| Baseline | v1.0.1 |
| Proposed release | v1.1.0 |
| Change request | `docs/CR-001-leak-detection.md` (issue #17) |
| Evidence | `results/v1.1.0/verification.md`, `results/v1.1.0/figures/`, CI runs on the pull requests |
| Reviewer | Developer (self-review) |
| Date | 14 November 2026 |

## 1. Checklist

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Change implements only what CR-001 approved | Yes | Changes limited to the files in CR-001 Section 4, plus the simulator leak option for testing |
| 2 | Every new requirement (REQ-11 to REQ-14) is traced to tests | Yes | `docs/requirements.md` traceability matrix |
| 3 | Planning and validation behaviour unchanged | Yes | All v1.0.1 tests pass unchanged; baseline leak tests unchanged (leak detection off) |
| 4 | Standard landing-fuel prediction unchanged (AC-5) | Yes | `test_standard_plf_is_unchanged`; verification AC-5 |
| 5 | Regression suite and coverage | Pass | 135 tests; 100% statement and branch coverage |
| 6 | Static analysis | Pass | Ruff and mypy --strict clean; CI passing on Ubuntu and macOS |
| 7 | Boundary values of the alert threshold tested | Yes | 74.99 / 75.00 / 75.01 kg in `test_leak.py` |
| 8 | Acceptance criteria AC-1 to AC-5 | All pass | `results/v1.1.0/verification.md` |
| 9 | Acceptance criteria unchanged since approval | Yes | Same wording as CR-001 Section 5 and issue #17 |
| 10 | Results reproducible and tied to a commit | Yes | Seeds fixed; script records commit and environment |
| 11 | Configuration control: version, changelog, release history | Yes | `pyproject.toml`, `CHANGELOG.md`, `docs/CONFIGURATION.md` |

## 2. Findings

| ID | Finding | Severity | Disposition |
|---|---|---|---|
| R-01 | CR-001 stated that 0 alerts in 2,000 flights bounds the false-alarm rate at 0.15%. Headwind flights reuse the same sensor noise as the nominal flight with the same seed (843 of 1,000 pairs identical), so there are only about 1,000 independent tests. The bound is about 0.3%. | Minor (documentation) | Corrected in `verification.md`; note added to CR-001. AC-3 itself still passes as written. |
| R-02 | The maximum observed leak-free discrepancy was 73.9 kg, a margin of only 1.1 kg below the 75 kg threshold. No false alerts occurred in the tested sample, but the narrow margin shows sensitivity to the assumed sensor-noise characteristics. | Major | Accepted for the prototype and reported. Future work: validate the threshold on a larger independent seed set and other noise assumptions. |
| R-03 | Alert instability without persistence: at 600 kg/h the alert switched off in 94 of 100 flights (median 3 times, about 3 min in total per flight; maximum 7 times, 8 min), because the 10-min signal (100 kg) is close to the 75 kg threshold. Status can briefly return to GREEN, which could confuse users and reduce trust in the warning. At 1,200 kg/h the alert was stable (11 flights, at most one 1-min drop-out). | Major | Accepted (CR-001 design decision). Measured and reported; hysteresis or persistence is a recommended future change. |
| R-04 | Unnecessary (conservative) status escalation for small leaks: at 300 kg/h a leak is genuinely present, but the aircraft still lands GREEN (1,938 kg). 24 of 100 flights showed AMBER, because early alerts occur when noise inflates the discrepancy and the leak rate is over-estimated. The leak alert is correct; the fuel status is over-pessimistic. | Major | Accepted and reported (failure F3, pessimistic). Not covered by an acceptance criterion; the status policy needs operational assessment. |
| R-05 | Window dilution: at the first alert the window still contains pre-leak readings, so the leak rate is under-estimated for up to 10 min (Figure: leak-adjusted PLF 1,480 kg at alert against 850 kg actual). | Minor | Known limitation (CR-001 Section 7). Prediction converges once the window is inside the leak. |
| R-06 | Endurance and range are still calculated from metered fuel flow only, not leak-adjusted. | Minor | Out of CR-001 scope. Recorded as a future change. |
| R-07 | The review was carried out by the developer of the change, who may overlook assumptions embedded in their own implementation. This gives less assurance than an independent review, a principle DO-178C applies to verification of higher-criticality software. The prototype does not claim DO-178C compliance or a formally assigned software level. | Process | Recorded as a limitation of this academic project. |

## 3. Decision

All acceptance criteria pass and no finding prevents release. Findings R-02 to R-04 are design trade-offs of the approved CR-001 design and are reported rather than fixed, so that the criteria are not changed after seeing the results.

**Decision:** approved for release as **v1.1.0**.
