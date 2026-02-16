import datetime

from pydantic import BaseModel, Field


class PriceResponse(BaseModel):
    date: datetime.date = Field(description="Trading date")
    open: float = Field(description="Opening price")
    high: float = Field(description="Highest price of the day")
    low: float = Field(description="Lowest price of the day")
    close: float = Field(description="Closing price")
    volume: int = Field(description="Trading volume")

    model_config = {"from_attributes": True}


class IndicatorResponse(BaseModel):
    date: datetime.date = Field(description="Trading date")
    close: float = Field(description="Closing price")
    rsi: float | None = Field(default=None, description="Relative Strength Index (14-period)")
    sma_20: float | None = Field(default=None, description="20-day Simple Moving Average")
    sma_50: float | None = Field(default=None, description="50-day Simple Moving Average")
    bb_upper: float | None = Field(default=None, description="Upper Bollinger Band (20-day, 2 std dev)")
    bb_middle: float | None = Field(default=None, description="Middle Bollinger Band (20-day SMA)")
    bb_lower: float | None = Field(default=None, description="Lower Bollinger Band (20-day, 2 std dev)")
    macd: float | None = Field(default=None, description="MACD line (12-period EMA minus 26-period EMA)")
    macd_signal: float | None = Field(default=None, description="MACD signal line (9-period EMA of MACD)")
    macd_hist: float | None = Field(default=None, description="MACD histogram (MACD minus signal)")


class HoldingResponse(BaseModel):
    symbol: str = Field(description="Holding ticker symbol")
    name: str = Field(description="Holding company name")
    percent: float = Field(description="Holding weight as a percentage of the ETF")


class SectorWeighting(BaseModel):
    sector: str = Field(description="Sector name")
    percent: float = Field(description="Sector weight as a percentage")


class EtfHoldingsResponse(BaseModel):
    top_holdings: list[HoldingResponse] = Field(description="Top holdings by weight")
    sector_weightings: list[SectorWeighting] = Field(description="Sector allocation breakdown")
    total_percent: float = Field(description="Sum of top holding weights (may be < 100%)")


class IndicatorSnapshotBase(BaseModel):
    """Shared indicator fields for holding and constituent snapshot responses."""
    close: float | None = Field(default=None, description="Latest closing price")
    change_pct: float | None = Field(default=None, description="1-day percentage change")
    rsi: float | None = Field(default=None, description="RSI (14-period)")
    sma_20: float | None = Field(default=None, description="20-day SMA")
    sma_50: float | None = Field(default=None, description="50-day SMA")
    macd: float | None = Field(default=None, description="MACD line")
    macd_signal: float | None = Field(default=None, description="MACD signal line")
    macd_hist: float | None = Field(default=None, description="MACD histogram")
    macd_signal_dir: str | None = Field(default=None, description="MACD signal direction: 'bullish' or 'bearish'")
    bb_upper: float | None = Field(default=None, description="Upper Bollinger Band")
    bb_middle: float | None = Field(default=None, description="Middle Bollinger Band")
    bb_lower: float | None = Field(default=None, description="Lower Bollinger Band")
    bb_position: str | None = Field(default=None, description="Price position vs Bollinger Bands: 'above', 'upper', 'lower', or 'below'")


class HoldingIndicatorResponse(IndicatorSnapshotBase):
    symbol: str = Field(description="Holding ticker symbol")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
