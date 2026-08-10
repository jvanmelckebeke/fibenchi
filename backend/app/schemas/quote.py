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


class Quote(QuoteResponse):
    """The full provider quote as parsed from Yahoo (``parse_quote_row``).

    :class:`QuoteResponse` plus the internal reconciliation field — this is
    what circulates through the app (price-sync anchors, price heal, the SSE
    ``quotes`` event, ``SymbolBatchData.quote``). The REST ``GET /api/quotes``
    boundary re-validates into plain ``QuoteResponse``, dropping
    ``session_date``.

    ``market_state`` stays a raw string on purpose: it's Yahoo's open-world
    vocabulary, canonically interpreted by the ``app.domain.market_state``
    trait table (unknown codes degrade conservatively there).
    """

    session_date: str | None = Field(
        default=None,
        description="Exchange-local ISO date of the quote's live session; "
        "internal aid for price-sync's settled-bar reconciliation.",
    )

    @classmethod
    def placeholder(cls, symbol: str) -> "Quote":
        """Symbol-only placeholder for a degraded fetch (breaker open, Yahoo
        returned garbage). Consumers can iterate it without crashing."""
        return cls(symbol=symbol)

    @property
    def is_placeholder(self) -> bool:
        """True when the quote carries no data beyond its symbol."""
        return self == Quote(symbol=self.symbol)
