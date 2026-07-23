import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.thesis import ThesisStatus
from app.schemas._validators import validate_hex_color
from app.schemas.asset import AssetResponse


class ThesisCreate(BaseModel):
    name: str = Field(max_length=120, description="Unique thesis name (e.g. 'El Niño', 'Cables')")
    color: str = Field(default="#3b82f6", description="Hex colour for the thesis badge")
    icon: str | None = Field(default=None, max_length=50, description="Lucide icon name (e.g. 'lightbulb', 'flame')")
    description: str | None = Field(default=None, max_length=50_000, description="The hypothesis (Markdown supported)")
    status: ThesisStatus = Field(default=ThesisStatus.WATCHING, description="Lifecycle status")
    opened_at: datetime.date | None = Field(default=None, description="Date the thesis was formed (defaults to today)")

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str) -> str:
        return validate_hex_color(v)


class ThesisUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120, description="New thesis name")
    color: str | None = Field(default=None, description="New hex colour")
    icon: str | None = Field(default=None, max_length=50, description="New Lucide icon name")
    description: str | None = Field(default=None, max_length=50_000, description="New hypothesis text")
    status: ThesisStatus | None = Field(default=None, description="New lifecycle status")
    opened_at: datetime.date | None = Field(default=None, description="New open date")

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str | None) -> str | None:
        if v is not None:
            return validate_hex_color(v)
        return v


class ThesisAddAssets(BaseModel):
    asset_ids: list[int] = Field(description="Asset IDs to add as members of the thesis")


class ThesisResponse(BaseModel):
    id: int = Field(description="Thesis ID")
    name: str = Field(description="Thesis name")
    color: str = Field(description="Hex colour")
    icon: str | None = Field(default=None, description="Lucide icon name")
    description: str | None = Field(description="The hypothesis (Markdown)")
    status: ThesisStatus = Field(description="Lifecycle status")
    opened_at: datetime.date = Field(description="Date the thesis was formed")
    created_at: datetime.datetime = Field(description="Creation timestamp")
    assets: list[AssetResponse] = Field(
        default=[],
        description="Member assets as full rows (type/currency/tags), so callers can "
        "render every member — including ones that are in no group.",
    )
    aggregate_pct: float | None = Field(
        default=None,
        description="Equal-weight mean return of members since opened_at, in percent (null if no price data)",
    )

    model_config = {"from_attributes": True}


class ThesisPerformancePoint(BaseModel):
    date: datetime.date = Field(description="Date of the point")
    pct: float = Field(description="Equal-weight return since opened_at, in percent")


class ThesisPerformanceSeries(BaseModel):
    thesis_id: int = Field(description="Thesis ID")
    points: list[ThesisPerformancePoint] = Field(
        default=[],
        description="Downsampled equal-weight performance curve since opened_at (for sparklines)",
    )
