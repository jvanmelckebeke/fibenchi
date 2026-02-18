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
    values: dict[str, float | None] = Field(
        default_factory=dict,
        description="Indicator values keyed by field name (e.g. rsi, sma_20, macd)",
    )


class AssetDetailResponse(BaseModel):
    prices: list[PriceResponse] = Field(description="OHLCV price history for the requested period")
    indicators: list[IndicatorResponse] = Field(description="Technical indicators for the requested period")


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
    values: dict[str, float | str | None] = Field(
        default_factory=dict,
        description="Indicator values keyed by field name (includes derived fields like macd_signal_dir, bb_position)",
    )


class HoldingIndicatorResponse(IndicatorSnapshotBase):
    symbol: str = Field(description="Holding ticker symbol")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
