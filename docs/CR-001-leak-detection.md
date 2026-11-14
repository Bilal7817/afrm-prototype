# CR-001: Suspected Fuel Leak Detection

| Field | Value |
|---|---|
| Change request | CR-001 |
| GitHub issue | #17 |
| Baseline | v1.0.1 |
| Target version | v1.1.0 (new feature, backwards compatible) |
| Requirements | REQ-11 to REQ-14 (`docs/requirements.md`) |
| Status | Approved for implementation, 14 Nov 2026 |

## 1. Problem

v1.0.x predicts landing fuel from the reported fuel flow only. Fuel lost without passing through the flow meter (a leak) is not detected, so warnings come late. Baseline testing of v1.0.0 (TC-B04, `results/baseline/`) showed:

| Leak | Actual landing fuel | v1.0.0 first AMBER/RED | v1.0.0 first RED |
|---|---|---|---|
| 300 kg/h | 1,938 kg (GREEN) | never | never |
| 600 kg/h | 1,575 kg (AMBER) | 94 min | never |
| 1,200 kg/h | 850 kg (RED) | 67 min | 105 min |

The leak starts at 40 min in each case.

## 2. Proposed change

Add a leak detector that compares the fuel actually used (drop in fuel on board) with the fuel the flow meter says was used, over a sliding window.

```
for each ACCEPTED reading (the monitor rejects invalid readings first):
    if the monitor cleared its smoothing window after a gap → clear the leak window
    add the reading; the window starts at the latest reading at least 10 min old

    if the window spans at least 10 min:
        expected burn = Σ (flow at start + flow at end of interval) / 2 × interval time
        observed burn = fuel on board at window start − fuel on board now
        discrepancy   = observed burn − expected burn
        alert         = discrepancy > 75 kg            → "SUSPECTED FUEL LEAK"
        leak rate     = discrepancy ÷ window duration  (only while the alert is on)

monitor:
    standard PLF       = unchanged (REQ-03)
    leak-adjusted PLF  = fuel on board − (smoothed flow + leak rate) × time remaining
    status             = from the lower of the two PLFs while the alert is on,
                         otherwise from the standard PLF
```

Design decisions:

- **One window, one threshold, one leak rate.** No persistence counter, confidence intervals or second algorithm, to keep the detector simple to verify.
- **The monitor stays responsible for validation.** The detector only ever sees accepted readings.
- **Trapezoidal rule for expected burn.** It is symmetric, so a single step change in reported flow produces only a small, bounded discrepancy (tested explicitly).
- **Standard PLF is preserved.** The leak-adjusted PLF is reported alongside it, so the crew-facing figure never silently changes meaning.

## 3. Configuration

| Parameter | Value | Justification |
|---|---|---|
| `leak_window_s` | 600 | Short enough for the leak rate to settle within 10 min of leak start |
| `leak_threshold_kg` | 75 | About 5 × the discrepancy noise (σ ≈ 15 kg, measured on simulated nominal flights) |

75 kg over 10 min corresponds to 450 kg/h. This is the threshold-equivalent rate, not a guaranteed detection limit: at that rate about half of the windows would alert.

## 4. Impact

| Item | Change |
|---|---|
| `src/afrm/leak.py` | New module (leak detector) |
| `src/afrm/monitor.py` | Calls the detector; adds leak-adjusted PLF and alert to each assessment |
| `src/afrm/models.py`, `config/afrm_config.json` | Two new parameters; new assessment fields |
| `src/afrm/cli.py` | Shows the alert and leak-adjusted PLF |
| Tests | New detector tests; existing tests must still pass |

Planning (REQ-01, REQ-02) and validation (REQ-06, REQ-07) are not changed.

## 5. Acceptance criteria

Fixed before implementation. If a criterion fails, it is reported and investigated, not changed.

| ID | Criterion |
|---|---|
| AC-1 | Detect a 1,200 kg/h leak within 11 min in at least 95 of 100 seeded simulations. |
| AC-2 | Detect a 600 kg/h leak within 22 min in at least 95 of 100 seeded simulations. |
| AC-3 | Produce no suspected-leak alerts in 2,000 predefined leak-free nominal and headwind simulations. |
| AC-4 | Produce no false GREEN-to-AMBER or GREEN-to-RED escalations in the nominal simulations. |
| AC-5 | Preserve the standard landing-fuel calculation from v1.0.1 when no leak alert is active. |

Definitions:

- **Detection time** = time from the simulated leak start (40 min) to the first SUSPECTED FUEL LEAK alert.
- AC-1 and AC-2 limits are the time for the leak to use the 225 kg contingency fuel (11.25 min and 22.5 min).
- Seeds: 0–99 for AC-1 and AC-2; 0–999 for each of nominal and headwind for AC-3 and AC-4.
- AC-3 interpretation: zero alerts in 2,000 independent flights gives an approximate 95% upper bound of 0.15% per flight (rule of three). It does not show the false-alarm rate is zero.

## 6. Evaluation metrics (reported, not acceptance criteria)

- 300 kg/h leak: fraction of seeds detected and detection time (known sensitivity limit).
- Warning delay: time to first AMBER/RED compared with v1.0.0.
- Alert transitions per flight (flickering, since there is no persistence counter).
- Leak-rate and leak-adjusted PLF error compared with the actual landing fuel.
- Sudden flow-change test: discrepancy caused by a step change in reported flow with no leak.
- Effect of skipped (invalid) readings on detection time.
- Runtime and memory compared with v1.0.1.

## 7. Known limitations

- A leak that starts part-way through a window is diluted by pre-leak readings, so the first alerts and leak-rate estimates are low.
- Simulated noise is independent and Gaussian; real fuel-quantity sensors also have bias, slosh and attitude effects.
- Review is by the developer only; DO-178C would require independent review at higher software levels.
