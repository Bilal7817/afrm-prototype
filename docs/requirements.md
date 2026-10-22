# AFRM Requirements and Traceability

Specification v2.1, frozen 21 October 2026. All values are illustrative and held in
`config/afrm_config.json`; they are not regulatory requirements for any real operation.

## Requirements

| ID | Requirement |
|---|---|
| REQ-01 | Minimum block fuel = taxi + trip + contingency (5% of trip) + alternate + final reserve (30 min at holding fuel flow). |
| REQ-02 | DISPATCHABLE if loaded fuel ≥ minimum block fuel, otherwise NOT DISPATCHABLE. |
| REQ-03 | Predicted landing fuel (PLF) = fuel on board − smoothed fuel flow × (remaining distance ÷ ground speed). Endurance and range above final reserve are also reported. |
| REQ-04 | Fuel flow is smoothed over up to 5 valid readings (partial window at start). Ground speed uses the latest valid reading. |
| REQ-05 | GREEN if PLF ≥ alternate + final reserve (1,750 kg); AMBER if final reserve (1,000 kg) ≤ PLF < 1,750 kg; RED if PLF < 1,000 kg. |
| REQ-06 | A sample is invalid if: fuel on board is negative or non-finite; fuel flow is non-finite or outside 0–10,000 kg/h; ground speed is non-finite or outside 100–1,200 km/h; remaining distance is negative, non-finite or greater than the last accepted value; the timestamp is not increasing or follows a gap over 120 s. |
| REQ-07 | An invalid sample reports DATA INVALID, is excluded from smoothing, and monitoring continues. After a non-increasing timestamp the next sample is checked against the last accepted timestamp. After a gap the smoothing window is cleared and the gap sample's timestamp becomes the re-synchronisation reference. |
| REQ-08 | All parameters are loaded from JSON configuration and validated. |
| REQ-09 | The same seed produces identical simulated data. |
| REQ-10 | Units are kg, km, km/h, kg/h, s (timestamps) and h (durations) throughout, named in every field. |

## Traceability matrix

Tests are tagged with `@pytest.mark.req(...)`. Counts include parametrised cases.

| Requirement | Test cases | Verified by |
|---|---|---|
| REQ-01 | 2 | `test_planner.py::test_fuel_plan_components_match_hand_calculation`, `test_status_thresholds_derived_from_plan` |
| REQ-02 | 5 | `test_planner.py::test_exact_minimum_block_fuel_is_dispatchable`, `test_just_below_minimum_block_fuel_is_not_dispatchable`, `test_scenario_dispatch` |
| REQ-03 | 6 | `test_monitor.py::test_predicted_landing_fuel_hand_calculation`, `test_endurance_and_range_above_final_reserve`, `test_zero_fuel_flow_is_valid_but_endurance_undefined`; `test_scenarios.py` exact scenario tests |
| REQ-04 | 6 | `test_monitor.py::test_moving_average_of_up_to_five_readings`, `test_ground_speed_uses_latest_reading_not_smoothed`; `test_scenarios.py::test_headwind_exact_transition` |
| REQ-05 | 34 | `test_monitor.py::test_status_boundaries`; `test_scenarios.py` (exact, noisy and 20-seed headwind tests) |
| REQ-06 | 25 | `test_monitor.py` validation, range-limit, distance, timestamp and gap tests; `test_simulator.py::test_malformed_csv_value_becomes_data_invalid` |
| REQ-07 | 19 | `test_monitor.py::test_invalid_sample_is_excluded_from_smoothing`, `test_out_of_order_timestamp_checked_against_last_accepted`, `test_gap_is_rejected_then_monitoring_resynchronises` and others |
| REQ-08 | 8 | `test_planner.py::test_config_change_changes_plan_without_code_change`, `test_invalid_config_is_rejected`, `test_unknown_scenario_is_reported` |
| REQ-09 | 26 | `test_simulator.py::test_same_seed_gives_identical_data`, `test_different_seed_gives_different_data`, `test_csv_round_trip`; seeded scenario tests |
| REQ-10 | 2 | `test_simulator.py::test_samples_are_regular_and_end_at_destination`, `test_csv_round_trip` |

## Scenario expectations

| Scenario | Loaded fuel | Expected PLF (noise-free) | Expected outcome |
|---|---|---|---|
| nominal | 7,000 kg | 2,300 kg | DISPATCHABLE, GREEN |
| headwind (800 → 600 km/h after 750 km) | 7,000 kg | 2,300 → 1,550 kg | DISPATCHABLE, GREEN → AMBER |
| low_uplift (hypothetical replay) | 5,500 kg | 800 kg | NOT DISPATCHABLE, RED |
