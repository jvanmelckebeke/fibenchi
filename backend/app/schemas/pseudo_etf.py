import datetime

from pydantic import BaseModel, Field

from app.schemas.asset import AssetResponse
from app.schemas.price import IndicatorSnapshotBase


class PseudoETFCreate(BaseModel):
    name: str = Field(description="Unique basket name")
    description: str | None = Field(default=None, description="Optional description")
    base_date: datetime.date = Field(description="Start date for performance indexing")
    base_value: float = Field(default=100.0, description="Starting index value (default 100)")


class PseudoETFUpdate(BaseModel):
    name: str | None = Field(default=None, description="New name")
    description: str | None = Field(default=None, description="New description")
    base_date: datetime.date | None = Field(default=None, description="New base date")


class PseudoETFAddConstituents(BaseModel):
    asset_ids: list[int] = Field(description="Asset IDs to add as constituents")


class PseudoETFResponse(BaseModel):
    id: int = Field(description="Pseudo-ETF ID")
    name: str = Field(description="Basket name")
    description: str | None = Field(description="Description")
    base_date: datetime.date = Field(description="Performance index start date")
    base_value: float = Field(description="Starting index value")
    created_at: datetime.datetime = Field(description="Creation timestamp")
    constituents: list[AssetResponse] = Field(default=[], description="Assets in this basket")

    model_config = {"from_attributes": True}


class PerformancePoint(BaseModel):
    date: datetime.date = Field(description="Trading date")
    value: float = Field(description="Composite index value")


class PerformanceBreakdownPoint(BaseModel):
    date: datetime.date = Field(description="Trading date")
    value: float = Field(description="Composite index value")
    breakdown: dict[str, float] = Field(default={}, description="Per-symbol contribution to the index value")


class ConstituentIndicatorResponse(IndicatorSnapshotBase):
    symbol: str = Field(description="Constituent ticker symbol")
    name: str | None = Field(default=None, description="Company name")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    weight_pct: float | None = Field(default=None, description="Current portfolio weight percentage")
