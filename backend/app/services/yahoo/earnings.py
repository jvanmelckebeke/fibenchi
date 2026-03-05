"""Yahoo Finance earnings date fetching."""

import datetime
import logging

from yahooquery import Ticker

from app.utils import async_threadable

logger = logging.getLogger(__name__)


def _parse_earnings_date(raw: object) -> datetime.date | None:
    """Parse Yahoo earnings date format into a date.

    Yahoo returns formats like "2026-04-30 16:30:S" or plain "2026-04-30".
    """
    if raw is None:
        return None
    try:
        s = str(raw).strip().split(" ")[0]
        return datetime.date.fromisoformat(s)
    except (ValueError, IndexError):
        logger.debug("Could not parse earnings date: %r", raw)
        return None


def _extract_last_reported_date(earnings_data: dict) -> datetime.date | None:
    """Extract the most recent reportedDate from earningsChart.quarterly.

    Yahoo stores this as a unix timestamp in the quarterly entries.
    """
    chart = earnings_data.get("earningsChart", {})
    if not isinstance(chart, dict):
        return None
    quarterly = chart.get("quarterly", [])
    if not isinstance(quarterly, list) or not quarterly:
        return None

    # Find the most recent reportedDate
    latest_ts = None
    for q in quarterly:
        if not isinstance(q, dict):
            continue
        ts = q.get("reportedDate")
        if ts is not None and isinstance(ts, (int, float)):
            if latest_ts is None or ts > latest_ts:
                latest_ts = ts

    if latest_ts is None:
        return None

    try:
        return datetime.date.fromtimestamp(latest_ts)
    except (OSError, ValueError):
        return None


def _fetch_earnings_date_sync(symbol: str) -> dict[str, object] | None:
    """Fetch earnings dates from Yahoo Finance.

    Uses calendar_events for the next earnings date, and earnings chart
    for the most recent reported date (post-earnings detection).

    Returns {"earnings_date": date, "is_estimate": bool,
             "last_reported_date": date | None} or None.
    """
    try:
        ticker = Ticker(symbol)
        cal = ticker.calendar_events
    except Exception:
        logger.exception("Failed to fetch calendar_events for %s", symbol)
        return None

    # Yahoo returns a string error when data is unavailable
    if not isinstance(cal, dict):
        return None

    sym_data = cal.get(symbol)
    if not isinstance(sym_data, dict):
        return None

    earnings = sym_data.get("earnings", {})
    if not isinstance(earnings, dict):
        return None

    dates = earnings.get("earningsDate", [])
    if not isinstance(dates, list) or not dates:
        return None

    raw_date = dates[0]
    parsed = _parse_earnings_date(raw_date)
    if parsed is None:
        return None

    is_estimate = bool(earnings.get("isEarningsDateEstimate", True))

    # Also try to get the last reported date from earnings chart
    last_reported: datetime.date | None = None
    try:
        earnings_full = ticker.earnings
        if isinstance(earnings_full, dict):
            sym_earnings = earnings_full.get(symbol)
            if isinstance(sym_earnings, dict):
                last_reported = _extract_last_reported_date(sym_earnings)
    except Exception:
        logger.debug("Could not fetch earnings history for %s", symbol)

    return {
        "earnings_date": parsed,
        "is_estimate": is_estimate,
        "last_reported_date": last_reported,
    }


@async_threadable
def fetch_earnings_date(symbol: str) -> dict[str, object] | None:
    """Async wrapper for earnings date fetch."""
    return _fetch_earnings_date_sync(symbol)
