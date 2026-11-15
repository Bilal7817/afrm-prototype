# CR-001 verification results (v1.1.0)

- AFRM source: `/Users/bilalahmad/Documents/afrm-prototype/src/afrm`
- Commit: `15a53f64da6e6690de318daa4bdc03240e37a685`
- Environment: macOS-15.6-arm64-arm-64bit-Mach-O, Python 3.14.9
- Settings: window 600 s, threshold 75 kg
- Leak starts at 40 min; detection time = leak start to first alert
- Run time: 1.9 s

## Acceptance criteria

| ID | Criterion | Result | Pass |
|---|---|---|---|
| AC-1 | 1,200 kg/h detected within 11 min in >= 95/100 | 100/100 | PASS |
| AC-2 | 600 kg/h detected within 22 min in >= 95/100 | 100/100 | PASS |
| AC-3 | No alerts in 2,000 leak-free nominal and headwind flights | 0 alerts | PASS |
| AC-4 | No GREEN to AMBER/RED escalations in 1,000 nominal flights | 0 escalations | PASS |
| AC-5 | Standard PLF unchanged from v1.0.1 when no alert is active | identical (100 leak-free flights) | PASS |

AC-3 interpretation: a headwind flight uses the same fuel-on-board and fuel-flow noise
as the nominal flight with the same seed (the headwind changes ground speed only), so
843 of 1,000 pairs give an identical largest discrepancy. The 2,000 flights are
therefore about 1,000 independent tests of the detector. Zero alerts gives an
approximate 95% upper bound of 0.3% per flight (rule of three, 3/1,000), not 0.15%.
It does not show the false-alarm rate is zero.

Largest leak-free discrepancy: 73.9 kg (threshold 75 kg).

## Evaluation metrics (100 seeds each)

| Leak | Detected | Detection median / 95th pct (min) | Flights warned v1.0.0 → v1.1.0 | First AMBER/RED v1.0.0 → v1.1.0 (median min) | Leak-rate error at +20 min (mean abs, kg/h) | Adjusted PLF error at +20 min (mean abs, kg) |
|---|---|---|---|---|---|---|
| 300 kg/h | 93/100 | 26 / 61 | 0 → 24 | n/a → 58 | 175 | 175 |
| 600 kg/h | 100/100 | 8 / 9 | 100 → 100 | 95 → 48 | 64 | 64 |
| 1,200 kg/h | 100/100 | 4 / 5 | 100 → 100 | 68 → 44 | 70 | 71 |

Alert stability (flicker): switch-offs = times the alert goes from on to off;
off time = total minutes with the alert off from its first alert to landing (summed,
not consecutive). Medians and maxima include only flights where the alert came on.
Detection delay (AC-1, AC-2) and alert stability are different measures: the
acceptance criteria cover time to first alert, not continuous alert reliability.

| Leak | Flights with a switch-off | Switch-offs per flight (median / max) | Off time per flight (median / max, min) |
|---|---|---|---|
| 300 kg/h | 93/93 | 2 / 6 | 44 / 66 |
| 600 kg/h | 94/100 | 3 / 7 | 3 / 8 |
| 1,200 kg/h | 11/100 | 0 / 1 | 0 / 1 |

Warning medians exclude flights that never warn. Errors are measured only on flights
where the alert is active 20 min after the leak starts.

## Skipped readings (every 7th fuel-flow reading invalid)

| Leak | Detected within AC limit | Detection median (min) | Clean data median (min) |
|---|---|---|---|
| 1,200 kg/h | 100/100 | 4 | 4 |
| 600 kg/h | 100/100 | 8 | 8 |

## Runtime (100 nominal flights, median of 5 runs, same machine)

| Monitor | Time (ms) | Per sample (µs) |
|---|---|---|
| Without leak detection (v1.0.1 behaviour) | 14.1 | 1.2 |
| With leak detection (v1.1.0) | 41.6 | 3.7 |

Leak detection adds 195% runtime. Memory stays constant per flight: the window holds about 11 readings.
