import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.asset import AssetType
from app.services.currency_service import lookup as currency_lookup


class AssetCreate(BaseModel):
    symbol: str = Field(max_length=20, description="Ticker symbol (e.g. AAPL, VOO). Validated against Yahoo Finance.")
    name: str | None = Field(default=None, max_length=200, description="Display name. Auto-detected from Yahoo Finance if omitted.")
    type: AssetType = Field(default=AssetType.STOCK, description="Asset type: stock or etf. Auto-detected if name is omitted.")


class AssetUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200, description="New display name.")
    type: AssetType | None = Field(default=None, description="Override asset type (stock/etf/index).")
    currency: str | None = Field(default=None, max_length=10, description="Override currency code (e.g. 'USD', 'EUR').")


class TagBrief(BaseModel):
    id: int = Field(description="Tag ID")
    name: str = Field(description="Tag label (e.g. 'tech', 'growth')")
    color: str = Field(description="Hex colour code (e.g. '#3b82f6')")

    model_config = {"from_attributes": True}


class AssetAttachments(BaseModel):
    """What is attached to an asset, for the remove dialog to warn before an orphan
    or a hard delete. ``groups`` drives the last-group warning; ``pseudo_etfs`` and
    ``theses`` are the silent-mutation risks a hard delete would cascade into."""

    symbol: str = Field(description="Ticker symbol")
    groups: list[str] = Field(default=[], description="Names of groups containing this asset")
    theses: list[str] = Field(default=[], description="Names of theses this asset is a member of")
    pseudo_etfs: list[str] = Field(default=[], description="Names of pseudo-ETFs this asset is a constituent of")
    tags: list[str] = Field(default=[], description="Tag names attached to this asset")
    has_note: bool = Field(default=False, description="Whether the asset has a non-empty note")
    annotation_count: int = Field(default=0, description="Number of chart annotations")


class AssetResponse(BaseModel):
    id: int = Field(description="Internal asset ID")
    symbol: str = Field(description="Ticker symbol")
    name: str = Field(description="Display name")
    type: AssetType = Field(description="Asset type: stock or etf")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    created_at: datetime.datetime = Field(description="Timestamp when the asset was first added")
    tags: list[TagBrief] = Field(default=[], description="Tags attached to this asset")

    model_config = {"from_attributes": True}

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        """Convert raw Yahoo code (e.g. 'GBp') to display code ('GBP') for API responses."""
        display, _ = currency_lookup(v)
        return display
