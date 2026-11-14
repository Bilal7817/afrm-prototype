# AFRM Requirements and Traceability

Specification v2.1, frozen 21 October 2026; REQ-11 to REQ-14 added by CR-001 (14 November 2026). All values are illustrative and held in
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
| REQ-11 | (CR-001) For each accepted sample, the leak detector keeps a sliding window starting at the latest accepted sample at least 10 min old. Expected burn = Σ mean fuel flow of each interval × interval duration (trapezoidal rule); observed burn = fuel on board at window start − current fuel on board; discrepancy = observed − expected. Evaluated only when the window spans at least 10 min. |
| REQ-12 | (CR-001) SUSPECTED FUEL LEAK is raised when the discrepancy exceeds 75 kg, re-evaluated at every accepted sample. Invalid samples never enter the window, and the window is cleared whenever the smoothing window is cleared after a gap (REQ-07). |
| REQ-13 | (CR-001) While the alert is active, leak rate = discrepancy ÷ window duration and leak-adjusted PLF = fuel on board − (smoothed fuel flow + leak rate) × (remaining distance ÷ ground speed). The standard PLF (REQ-03) is always reported unchanged. |
| REQ-14 | (CR-001) While the alert is active, the status rule (REQ-05) is applied to the lower of the standard and leak-adjusted PLF; otherwise to the standard PLF. |

## Traceability matrix

Tests are tagged with `@pytest.mark.req(...)`. Counts include parametrised cases.

| Requirement | Test cases | Verified by |
|---|---|---|
| REQ-01 | 2 | `test_planner.py::test_fuel_plan_components_match_hand_calculation`, `test_status_thresholds_derived_from_plan` |
| REQ-02 | 5 | `test_planner.py::test_exact_minimum_block_fuel_is_dispatchable`, `test_just_below_minimum_block_fuel_is_not_dispatchable`, `test_scenario_dispatch` |
| REQ-03 | 8 | `test_monitor.py::test_predicted_landing_fuel_hand_calculation`, `test_endurance_and_range_above_final_reserve`, `test_zero_fuel_flow_is_valid_but_endurance_undefined`; `test_scenarios.py` exact scenario tests; `test_baseline_leak.py`; `test_monitor_leak.py::test_detection_is_off_unless_settings_are_given` |
| REQ-04 | 6 | `test_monitor.py::test_moving_average_of_up_to_five_readings`, `test_ground_speed_uses_latest_reading_not_smoothed`; `test_scenarios.py::test_headwind_exact_transition` |
| REQ-05 | 39 | `test_monitor.py::test_status_boundaries`; `test_scenarios.py` (exact, noisy and 20-seed headwind tests); `test_baseline_leak.py`; `test_robustness.py::test_nominal_status_stable_across_100_seeds` |
| REQ-06 | 36 | `test_monitor.py` validation, range-limit, distance, timestamp and gap tests; `test_simulator.py::test_malformed_csv_value_becomes_data_invalid`; `test_mcdc.py`; `test_robustness.py` |
| REQ-07 | 22 | `test_monitor.py::test_invalid_sample_is_excluded_from_smoothing`, `test_out_of_order_timestamp_checked_against_last_accepted`, `test_gap_is_rejected_then_monitoring_resynchronises` and others; `test_robustness.py`; `test_monitor_leak.py::test_gap_clears_the_leak_window` |
| REQ-08 | 10 | `test_planner.py::test_config_change_changes_plan_without_code_change`, `test_invalid_config_is_rejected`, `test_unknown_scenario_is_reported` (including `leak_detection` values) |
| REQ-09 | 27 | `test_simulator.py::test_same_seed_gives_identical_data`, `test_different_seed_gives_different_data`, `test_csv_round_trip`; seeded scenario tests; `test_robustness.py::test_nominal_status_stable_across_100_seeds` |
| REQ-10 | 2 | `test_simulator.py::test_samples_are_regular_and_end_at_destination`, `test_csv_round_trip` |
| REQ-11 | 6 | `test_leak.py::test_no_check_until_window_spans_full_period`, `test_metered_burn_gives_zero_discrepancy`, `test_window_slides_and_drops_old_readings`, `test_skipped_reading_uses_actual_elapsed_time`, `test_skipped_reading_does_not_shorten_a_full_window`, `test_sudden_flow_change_gives_small_bounded_discrepancy` |
| REQ-12 | 13 | `test_leak.py::test_alert_threshold_boundary` (5 boundary values), `test_skipped_reading_uses_actual_elapsed_time`, `test_reset_clears_the_window`; `test_monitor_leak.py::test_invalid_readings_never_enter_the_window`, `test_gap_clears_the_leak_window`, `test_simulator_leak_matches_baseline_injection`, `test_1200_kg_h_leak_detected_and_red_much_earlier`, `test_threshold_of_infinity_disables_alerts`; `test_cli.py::test_monitor_shows_suspected_leak` |
| REQ-13 | 7 | `test_leak.py::test_leak_rate_uses_the_same_window`, `test_leak_rate_only_while_alert_is_active`; `test_monitor_leak.py::test_standard_plf_is_unchanged` (AC-5); `test_cli.py` leak tests |
| REQ-14 | 2 | `test_monitor_leak.py::test_status_uses_lower_plf_only_while_alert_is_active`, `test_1200_kg_h_leak_detected_and_red_much_earlier` |

## Scenario expectations

| Scenario | Loaded fuel | Expected PLF (noise-free) | Expected outcome |
|---|---|---|---|
| nominal | 7,000 kg | 2,300 kg | DISPATCHABLE, GREEN |
| headwind (800 → 600 km/h after 750 km) | 7,000 kg | 2,300 → 1,550 kg | DISPATCHABLE, GREEN → AMBER |
| low_uplift (hypothetical replay) | 5,500 kg | 800 kg | NOT DISPATCHABLE, RED |
