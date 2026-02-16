from pydantic import BaseModel, Field


class QuoteResponse(BaseModel):
    symbol: str = Field(description="Ticker symbol (e.g. AAPL)")
    price: float | None = Field(default=None, description="Latest traded price")
    previous_close: float | None = Field(default=None, description="Previous session close price")
    change: float | None = Field(default=None, description="Absolute price change from previous close")
    change_percent: float | None = Field(default=None, description="Percentage change from previous close")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    market_state: str | None = Field(default=None, description="Market state: REGULAR, PRE, POST, PREPRE, POSTPOST, or CLOSED")
