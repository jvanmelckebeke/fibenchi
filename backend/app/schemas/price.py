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
    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    macd_hist: float | None = None


class HoldingResponse(BaseModel):
    symbol: str
    name: str
    percent: float


class SectorWeighting(BaseModel):
    sector: str
    percent: float


class EtfHoldingsResponse(BaseModel):
    top_holdings: list[HoldingResponse]
    sector_weightings: list[SectorWeighting]
    total_percent: float


class HoldingIndicatorResponse(BaseModel):
    symbol: str
    close: float | None = None
    change_pct: float | None = None
    rsi: float | None = None
    sma_20: float | None = None
    sma_50: float | None = None
    macd_signal_dir: str | None = None  # "bullish" | "bearish"
    bb_position: str | None = None  # "above" | "upper" | "middle" | "lower" | "below"
