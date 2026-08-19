from pydantic import BaseModel, Field


class QuoteResponse(BaseModel):
    symbol: str = Field(description="Ticker symbol (e.g. AAPL)")
    price: float | None = Field(default=None, description="Latest traded price")
    previous_close: float | None = Field(default=None, description="Previous session close price")
    change: float | None = Field(default=None, description="Absolute price change from previous close")
    change_percent: float | None = Field(default=None, description="Percentage change from previous close")
    volume: int | None = Field(default=None, description="Current session trading volume")
    avg_volume: int | None = Field(default=None, description="10-day average daily volume")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    market_state: str | None = Field(default=None, description="Market state: REGULAR, PRE, POST, PREPRE, POSTPOST, or CLOSED")
    session_date: str | None = Field(
        default=None,
        description="Exchange-local ISO date of the quote's live session. Together with "
        "an indicator snapshot's `as_of` this identifies which session each number "
        "describes, so a client never has to infer it from price similarity.",
    )
    recent_sessions: list[str] | None = Field(
        default=None,
        description="Exchange-local ISO dates of the venue's most recent trading "
        "sessions at or before `session_date`, newest first — so `recent_sessions[0]` "
        "is the live session and `[1]` is the one `previous_close` belongs to. A "
        "client finds how many sessions a stored bar is behind by looking up its "
        "`as_of` in this list; not present means older than the window, which is all "
        "the client needs to know. No tolerance, no calendar on the client, and no "
        "counting of business days (which turns every holiday into a hole). None when "
        "the venue is unknown.",
    )


class Quote(QuoteResponse):
    """The full provider quote as parsed from Yahoo (``parse_quote_row``).

    This is what circulates through the app (price-sync anchors, price heal,
    the SSE ``quotes`` event, ``SymbolBatchData.quote``) and, since #626, what
    the REST boundary serves too — ``session_date`` used to be stripped there
    as an internal reconciliation aid, but the display needs the same session
    identity the sync does.

    ``market_state`` stays a raw string on purpose: it's Yahoo's open-world
    vocabulary, canonically interpreted by the ``app.domain.market_state``
    trait table (unknown codes degrade conservatively there).
    """

    @classmethod
    def placeholder(cls, symbol: str) -> "Quote":
        """Symbol-only placeholder for a degraded fetch (breaker open, Yahoo
        returned garbage). Consumers can iterate it without crashing."""
        return cls(symbol=symbol)

    @property
    def is_placeholder(self) -> bool:
        """True when the quote carries no data beyond its symbol."""
        return self == Quote(symbol=self.symbol)
