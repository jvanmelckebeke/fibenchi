from datetime import date

from pydantic import BaseModel


class PriceResponse(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int

    model_config = {"from_attributes": True}


class IndicatorResponse(BaseModel):
    date: date
    close: float
    rsi: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None
