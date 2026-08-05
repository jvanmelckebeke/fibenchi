"""Instrument — what a ticker's shape says about it, decided once.

The one-pass ``classify`` is the single place ticker characters are
interpreted. It decides *everything* the shape can tell — what kind of
instrument it is, which venue calendar governs it, and its inferred
currency — captured together in an :class:`Instrument` so no later code
ever re-inspects the characters ("is this a future?" is
``ref.kind.is_future``, not another ``endswith`` somewhere).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AssetKind(str, Enum):
    """What kind of instrument a ticker's shape says it is.

    Distinct from the DB-level ``AssetType`` (stock/etf/index, set by Yahoo
    metadata): this is inferred from the ticker alone and covers shapes the
    app never stores as assets (FX, futures).
    """

    EQUITY = "equity"    # exchange-listed security (incl. ETFs)
    INDEX = "index"
    CRYPTO = "crypto"
    FX = "fx"
    FUTURE = "future"
    UNKNOWN = "unknown"

    @property
    def is_equity(self) -> bool:
        return self is AssetKind.EQUITY

    @property
    def is_index(self) -> bool:
        return self is AssetKind.INDEX

    @property
    def is_crypto(self) -> bool:
        return self is AssetKind.CRYPTO

    @property
    def is_fx(self) -> bool:
        return self is AssetKind.FX

    @property
    def is_future(self) -> bool:
        return self is AssetKind.FUTURE


@dataclass(frozen=True)
class Instrument:
    """Everything a ticker's shape can tell, decided once by ``classify``."""

    kind: AssetKind
    calendar: str | None = None
    currency: str | None = None


def classify(ticker: str) -> Instrument:
    """One-pass classification of a Yahoo ticker into its instrument traits."""
    # Imported here, not at module top: the listing tables live in
    # market_calendar, whose package init imports back into app.domain
    # (schedule → classify). Keeping this module import-pure at load time is
    # the one seam that keeps the two package inits acyclic.
    from app.services.market_calendar.listings import (
        CRYPTO_QUOTE_CURRENCIES,
        DEFAULT_US_CALENDAR,
        FIAT_QUOTES,
        INDEX_CALENDARS,
        SUFFIX_LISTINGS,
        Listing,
    )

    sym = ticker.upper().strip()
    if not sym:
        return Instrument(AssetKind.UNKNOWN)
    if sym in INDEX_CALENDARS:
        return Instrument(AssetKind.INDEX, calendar=INDEX_CALENDARS[sym])
    if sym.startswith("^"):
        return Instrument(AssetKind.INDEX)  # unknown index — don't guess a venue
    if sym.endswith("=X"):
        return Instrument(AssetKind.FX)      # not exchange-session shaped
    if sym.endswith("=F"):
        return Instrument(AssetKind.FUTURE)  # not exchange-session shaped
    if "-" in sym:
        quote = sym.rsplit("-", 1)[1]
        if quote in CRYPTO_QUOTE_CURRENCIES:
            # Crypto pairs (BTC-USD): every day is a session; the quote
            # leg is the display currency when it's fiat.
            return Instrument(
                AssetKind.CRYPTO,
                calendar="24/7",
                currency=quote if quote in FIAT_QUOTES else None,
            )
    if "." in sym:
        listing = SUFFIX_LISTINGS.get(sym.rsplit(".", 1)[1], Listing(None, None))
        return Instrument(AssetKind.EQUITY, listing.calendar, listing.currency)
    return Instrument(AssetKind.EQUITY, DEFAULT_US_CALENDAR, "USD")
