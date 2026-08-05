"""Symbol — a ``str`` subclass that knows its venue and currency.

The single place ticker shape is interpreted: everything downstream reads
the traits ``Symbol`` derives, never the ticker's characters.
"""

from __future__ import annotations

from functools import cached_property

from app.services.market_calendar.listings import (
    CRYPTO_QUOTE_CURRENCIES,
    DEFAULT_US_CALENDAR,
    FIAT_QUOTES,
    INDEX_CALENDARS,
    SUFFIX_LISTINGS,
    Listing,
)
from app.services.market_calendar.venue import Venue, _venue_for


class Symbol(str):
    """A Yahoo ticker that knows its venue: ``Symbol("IWDA.AS").venue``.

    A ``str`` subclass, so it drops in anywhere a plain symbol string is
    used (dict keys, comparisons, serialization) — wrap at the point where
    venue questions arise, no need to thread a new type through the app.
    Venue resolution is cached on the instance; the Venue itself is shared
    per calendar. Note that str operations (``.upper()`` etc.) return plain
    ``str`` — re-wrap if you still need ``.venue`` afterwards.
    """

    @cached_property
    def _instrument(self) -> Listing:
        """One-pass ticker-shape classification — the single place shape is
        interpreted. Everything else reads the resulting traits."""
        sym = self.upper().strip()
        if not sym:
            return Listing(None, None)
        if sym in INDEX_CALENDARS:
            return Listing(INDEX_CALENDARS[sym], None)
        if sym.startswith("^"):
            return Listing(None, None)  # unknown index — don't guess a venue
        if sym.endswith("=X") or sym.endswith("=F"):
            return Listing(None, None)  # FX / futures — not exchange-session shaped
        if "-" in sym:
            quote = sym.rsplit("-", 1)[1]
            if quote in CRYPTO_QUOTE_CURRENCIES:
                # Crypto pairs (BTC-USD): every day is a session; the quote
                # leg is the display currency when it's fiat.
                return Listing("24/7", quote if quote in FIAT_QUOTES else None)
        if "." in sym:
            return SUFFIX_LISTINGS.get(sym.rsplit(".", 1)[1], Listing(None, None))
        return Listing(DEFAULT_US_CALENDAR, "USD")

    @property
    def calendar_name(self) -> str | None:
        """The exchange_calendars name for this ticker, or None."""
        return self._instrument.calendar

    @property
    def currency(self) -> str | None:
        """The venue/pair currency inferred from ticker shape, or None.

        A fallback only — Yahoo's own currency field wins when present (see
        ``resolve_currency``); this answers when Yahoo doesn't.
        """
        return self._instrument.currency

    @cached_property
    def venue(self) -> Venue | None:
        """This ticker's trading venue, or None when it can't be resolved."""
        name = self.calendar_name
        return _venue_for(name) if name else None
