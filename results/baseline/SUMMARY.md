# Baseline Test Results (v1.0.0)

- **Code tested:** v1.0.0 (tag `v1.0.0`, commit `755a087`), unchanged.
- **Tests:** written for Assignment 2, run against a separate copy of v1.0.0.

| Test | Result |
|---|---|
| TC-B01 Existing 90 tests | Pass |
| TC-B02 Coverage | Pass: 100% statement and branch |
| TC-B03 MC/DC of the range check | Pass |
| TC-B04 Fuel leak scenarios | Leak never detected; warnings late (see below) |
| TC-B05 100 normal flights | Pass: none left GREEN |
| TC-B06a One invalid reading | **Fail: defect DR-001** (marked xfail) |
| TC-B06b Two invalid readings in a row | Next valid reading also rejected (gap rule) |
| TC-B07 Profiling | See `profile.txt` and `benchmark.csv` |

## Finding 1: leaks are not detected → CR-001

| Leak | Actual landing fuel | Should show | v1.0.0 shows AMBER/RED at | v1.0.0 shows RED at |
|---|---|---|---|---|
| 300 kg/h | 1,938 kg | GREEN | never | never |
| 600 kg/h | 1,575 kg | AMBER from 41 min | 94 min | never |
| 1,200 kg/h | 850 kg | RED from 41 min | 67 min | 105 min |

## Finding 2: DR-001, timestamp rounding defect → v1.0.1

Simulated timestamps carry tiny rounding errors (e.g. 3,899.9999999999995 s). After one invalid reading, the gap to the next reading is 120.00000000000045 s, just over the 120 s limit, so a valid reading is wrongly rejected.
