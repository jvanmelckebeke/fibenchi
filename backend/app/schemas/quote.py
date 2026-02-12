from pydantic import BaseModel


class QuoteResponse(BaseModel):
    symbol: str
    price: float | None = None
    previous_close: float | None = None
    change: float | None = None
    change_percent: float | None = None
    currency: str = "USD"
    market_state: str | None = None
