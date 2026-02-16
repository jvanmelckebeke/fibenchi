import datetime

from pydantic import BaseModel, Field

from app.models.asset import AssetType


class AssetCreate(BaseModel):
    symbol: str = Field(description="Ticker symbol (e.g. AAPL, VOO). Validated against Yahoo Finance.")
    name: str | None = Field(default=None, description="Display name. Auto-detected from Yahoo Finance if omitted.")
    type: AssetType = Field(default=AssetType.STOCK, description="Asset type: stock or etf. Auto-detected if name is omitted.")
    watchlisted: bool = Field(default=True, description="Whether the asset appears on the watchlist")


class TagBrief(BaseModel):
    id: int = Field(description="Tag ID")
    name: str = Field(description="Tag label (e.g. 'tech', 'growth')")
    color: str = Field(description="Hex colour code (e.g. '#3b82f6')")

    model_config = {"from_attributes": True}


class AssetResponse(BaseModel):
    id: int = Field(description="Internal asset ID")
    symbol: str = Field(description="Ticker symbol")
    name: str = Field(description="Display name")
    type: AssetType = Field(description="Asset type: stock or etf")
    watchlisted: bool = Field(description="Whether the asset is currently on the watchlist")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    created_at: datetime.datetime = Field(description="Timestamp when the asset was first added")
    tags: list[TagBrief] = Field(default=[], description="Tags attached to this asset")

    model_config = {"from_attributes": True}
