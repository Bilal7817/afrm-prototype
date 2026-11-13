"""TC-B03: MC/DC analysis of the input range-check decision.

Decision (monitor._in_range):

    D = isfinite(v)  AND  low <= v  AND  v <= high
        condition A       condition B    condition C

MC/DC requires, for each condition, a pair of cases where only that condition
changes and the decision changes with it.

| Case | v    | low | high | A | B | C | D     |
|------|------|-----|------|---|---|---|-------|
| 1    | 500  | 0   | 1000 | T | T | T | True  |
| 2    | inf  | 0   | inf  | F | T | T | False |  (pairs with 3 for A)
| 3    | 500  | 0   | inf  | T | T | T | True  |
| 4    | -1   | 0   | 1000 | T | F | T | False |  (pairs with 1 for B)
| 5    | 1001 | 0   | 1000 | T | T | F | False |  (pairs with 1 for C)

Finding: A can only change independently when the range is unbounded
(high = inf), as in the fuel-on-board and remaining-distance checks. For a
bounded range, every non-finite value (NaN, +inf, -inf) also makes B or C
false, so A is redundant there but necessary for unbounded checks.
"""

from __future__ import annotations

import math

import pytest

from afrm.monitor import _in_range


@pytest.mark.req("REQ-06")
@pytest.mark.parametrize(
    ("case", "value", "low", "high", "expected"),
    [
        (1, 500.0, 0.0, 1000.0, True),
        (2, math.inf, 0.0, math.inf, False),
        (3, 500.0, 0.0, math.inf, True),
        (4, -1.0, 0.0, 1000.0, False),
        (5, 1001.0, 0.0, 1000.0, False),
    ],
)
def test_mcdc_range_check(case: int, value: float, low: float, high: float, expected: bool) -> None:
    assert _in_range(value, low, high) is expected


@pytest.mark.req("REQ-06")
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_values_fail_bounded_range_even_without_isfinite(value: float) -> None:
    """Supports the finding: for a bounded range, B or C alone rejects non-finite values."""
    assert not (0.0 <= value <= 1000.0)
    assert _in_range(value, 0.0, 1000.0) is False
