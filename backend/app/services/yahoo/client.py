"""Single client for all Yahoo Finance access.

Every Yahoo HTTP call in the codebase goes through :data:`yahoo_client`.
That gives us one place to apply the throttle (:mod:`rate_limit`),
quote/holdings caches, and the retry-once-with-fresh-session pattern.

Direct ``from yahooquery import Ticker`` imports anywhere else in the
codebase are a code smell — route the call through this client instead.

The client's behaviour is split across one mixin per concern
(``_quotes.py``, ``_history.py``, …) so each file stays small and
focused. They all reach the upstream library through :meth:`_ticker`,
which is the single place ``Ticker`` is instantiated — tests patch
``app.services.yahoo.client.Ticker`` to substitute the upstream library
across every operation in one shot.
"""

import logging
from typing import Any, Callable, TypeVar

from yahooquery import Ticker

from app.services.yahoo._base import _YahooBase
from app.services.yahoo._earnings import _EarningsMixin
from app.services.yahoo._fundamentals import _FundamentalsMixin
from app.services.yahoo._history import _HistoryMixin
from app.services.yahoo._holdings import _HoldingsMixin
from app.services.yahoo._intraday import _IntradayMixin
from app.services.yahoo._quotes import _QuotesMixin
from app.services.yahoo._search import _SearchMixin
from app.services.yahoo._validation import _ValidationMixin
from app.services.yahoo.rate_limit import (
    CrumbRejected,
    YahooThrottle,
    yahoo_throttle as _shared_throttle,
)
from app.utils import TTLCache

logger = logging.getLogger(__name__)

# Quote response cache TTL — tuned to the SSE stream's market-hours
# interval (15s) so callers asking for the same set within the window
# share one upstream call.
QUOTE_CACHE_TTL = 12.0

# Holdings change at most quarterly, so a long TTL is safe and saves
# many Yahoo round trips.
HOLDINGS_CACHE_TTL = 86_400  # 24h

_T = TypeVar("_T")


class YahooClient(
    _QuotesMixin,
    _HistoryMixin,
    _FundamentalsMixin,
    _ValidationMixin,
    _HoldingsMixin,
    _SearchMixin,
    _EarningsMixin,
    _IntradayMixin,
    _YahooBase,
):
    """Single point of access for Yahoo Finance.

    Owns the throttle, retry policy, and provider-side caches; per-
    concern operations live on the inherited mixin classes.
    """

    def __init__(
        self,
        throttle: YahooThrottle | None = None,
        quote_cache_ttl: float = QUOTE_CACHE_TTL,
        holdings_cache_ttl: float = HOLDINGS_CACHE_TTL,
    ):
        self._throttle = throttle or _shared_throttle
        self._quote_cache = TTLCache(default_ttl=quote_cache_ttl, thread_safe=True)
        self._holdings_cache = TTLCache(
            default_ttl=holdings_cache_ttl, max_size=100, thread_safe=True,
        )

    def _ticker(self, symbols: list[str] | str) -> Any:
        """Single ``Ticker`` instantiation point. Tests patch
        ``app.services.yahoo.client.Ticker`` to mock the upstream library."""
        return Ticker(symbols)

    def _call(
        self,
        fetch: Callable[[], _T],
        fallback: Callable[[], _T],
        *,
        retries: int = 1,
    ) -> _T:
        """Run ``fetch`` under the throttle and circuit breaker.

        - If the breaker is tripped, returns ``fallback()`` immediately.
        - Otherwise waits for throttle clearance, then runs ``fetch``.
        - On :class:`CrumbRejected`, retries up to ``retries`` more times
          (each preceded by a fresh throttle wait) before tripping the
          breaker and returning ``fallback()``.
        - Any other exception propagates so transient errors aren't masked.
        """
        if self._throttle.is_blocked():
            return fallback()

        for attempt in range(retries + 1):
            self._throttle.wait()
            try:
                result = fetch()
            except CrumbRejected:
                if attempt < retries:
                    logger.warning(
                        "Yahoo crumb rejected — retry %d/%d with fresh session",
                        attempt + 1, retries,
                    )
                    continue
                self._throttle.record_invalid_crumb()
                return fallback()
            self._throttle.record_success()
            return result

        return fallback()  # unreachable; quiets the type checker


# Process-wide singleton — every consumer imports this.
yahoo_client = YahooClient()


__all__ = [
    "QUOTE_CACHE_TTL",
    "HOLDINGS_CACHE_TTL",
    "YahooClient",
    "yahoo_client",
]
