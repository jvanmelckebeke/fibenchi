"""Shared base for ``YahooClient`` mixins.

Each per-concern mixin (quotes, history, fundamentals, …) only needs to
know about the throttle, caches, and the orchestrator method that wraps
its fetch. Declaring those here lets each mixin file be type-checked in
isolation without a circular import to ``client.py``.

``YahooClient`` inherits from this base (and every mixin), so the
abstract signatures are satisfied at composition time.
"""

from abc import abstractmethod
from typing import Any, Callable

from app.services.yahoo.rate_limit import YahooThrottle
from app.utils import TTLCache


class _YahooBase:
    """Attributes + orchestrator hooks that every Yahoo mixin relies on."""

    _throttle: YahooThrottle
    _quote_cache: TTLCache
    _holdings_cache: TTLCache

    @abstractmethod
    def _call(
        self,
        fetch: Callable[[], Any],
        fallback: Callable[[], Any],
        *,
        retries: int = 1,
    ) -> Any:
        """Run ``fetch`` under the throttle/breaker; return ``fallback()`` on failure."""

    @abstractmethod
    def _ticker(self, symbols: list[str] | str) -> Any:
        """Single point where ``yahooquery.Ticker`` is instantiated.

        Tests patch ``app.services.yahoo.client.Ticker`` to substitute
        the upstream library.
        """
