"""Shared constants for period and indicator warmup calculations."""

# Calendar days for each period string used across price, group, and portfolio endpoints.
PERIOD_DAYS: dict[str, int] = {
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 730,
    "5y": 1825,
}

# Extra calendar days to fetch for indicator warmup (~50 trading days for SMA50).
WARMUP_DAYS: int = 80
