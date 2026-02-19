"""Shared constants for period and indicator warmup calculations."""

from typing import Literal

# Canonical period type used by price, group, and portfolio endpoints.
PeriodType = Literal["1mo", "3mo", "6mo", "1y", "2y", "5y"]

# Calendar days for each period string used across price, group, and portfolio endpoints.
PERIOD_DAYS: dict[str, int] = {
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 730,
    "5y": 1825,
}


def _compute_warmup_days() -> int:
    """Derive warmup days from the indicator registry.

    Imported lazily to avoid circular imports at module level.
    ~2x the max warmup periods to account for weekends/holidays.
    """
    from app.services.compute.indicators import get_max_warmup_periods
    return int(get_max_warmup_periods() * 2.3)


# Extra calendar days to fetch for indicator warmup.
# Derived from the indicator registry (max warmup periods × 2.3 for calendar day conversion).
WARMUP_DAYS: int = _compute_warmup_days()
