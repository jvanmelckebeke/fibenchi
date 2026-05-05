"""Earnings calendar operations on :class:`YahooClient`."""

import asyncio
import datetime
import logging

from app.services.yahoo._base import _YahooBase
from app.services.yahoo._parsers import last_reported_date, parse_earnings_date
from app.services.yahoo.rate_limit import check_crumb

logger = logging.getLogger(__name__)


class _EarningsMixin(_YahooBase):
    async def earnings(self, symbol: str) -> dict[str, object] | None:
        """Fetch next earnings date + last reported date.

        Returns ``{earnings_date, is_estimate, last_reported_date}`` or
        ``None`` when unavailable.
        """
        def _fetch() -> dict[str, object] | None:
            try:
                ticker = self._ticker(symbol)
                cal = ticker.calendar_events
            except Exception:
                logger.exception("Failed to fetch calendar_events for %s", symbol)
                return None

            if not isinstance(cal, dict):
                return None
            check_crumb(cal)

            sym_data = cal.get(symbol)
            if not isinstance(sym_data, dict):
                return None
            earnings = sym_data.get("earnings", {})
            if not isinstance(earnings, dict):
                return None
            dates = earnings.get("earningsDate", [])
            if not isinstance(dates, list) or not dates:
                return None

            parsed = parse_earnings_date(dates[0])
            if parsed is None:
                return None
            is_estimate = bool(earnings.get("isEarningsDateEstimate", True))

            last_reported: datetime.date | None = None
            try:
                earnings_full = ticker.earnings
                if isinstance(earnings_full, dict):
                    sym_earnings = earnings_full.get(symbol)
                    if isinstance(sym_earnings, dict):
                        last_reported = last_reported_date(sym_earnings)
            except Exception:
                logger.debug("Could not fetch earnings history for %s", symbol)

            return {
                "earnings_date": parsed,
                "is_estimate": is_estimate,
                "last_reported_date": last_reported,
            }

        return await asyncio.to_thread(self._call, _fetch, lambda: None)
