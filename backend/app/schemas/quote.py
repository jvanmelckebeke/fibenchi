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
    prior_session_date: str | None = Field(
        default=None,
        description="Exchange-local ISO date of the trading session immediately before "
        "`session_date`, from the venue calendar — the session `previous_close` belongs "
        "to. A snapshot whose `as_of` equals this is the quote's prior bar exactly; no "
        "tolerance, and no calendar needed on the client. None when the venue is unknown.",
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
