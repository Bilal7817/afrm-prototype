# Baseline abnormal fuel-loss characterisation (TC-B04)

- AFRM source: `/Users/bilalahmad/Documents/afrm-v1.0.0/src/afrm`
- Commit: `755a087b391bb9a10463451c0a663ca60351cf9d`
- Environment: macOS-15.6-arm64-arm-64bit-Mach-O, Python 3.14.9
- Flight: nominal, seed 42; fuel loss starts at 40 min

| Loss rate (kg/h) | Actual landing fuel (kg) | Actual landing status | Reference: first AMBER/RED (min) | Reference: first RED (min) | Baseline: first AMBER/RED (min) | Baseline: first RED (min) | Baseline lag behind reference (min) |
|---|---|---|---|---|---|---|---|
| 0 | 2,300 | GREEN | never | never | never | never | n/a |
| 300 | 1,938 | GREEN | never | never | never | never | n/a |
| 600 | 1,575 | AMBER | 41 | never | 94 | never | 53 |
| 1200 | 850 | RED | 41 | 41 | 67 | 105 | 26 |

The reference is the status a monitor would show if it knew the loss rate exactly.
It is a best case, not an achievable detector.
