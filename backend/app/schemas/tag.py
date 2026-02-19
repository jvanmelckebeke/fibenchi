import datetime
import re

from pydantic import BaseModel, Field, field_validator

from app.schemas.asset import AssetResponse

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class TagCreate(BaseModel):
    name: str = Field(description="Unique tag label (e.g. 'tech', 'dividend')")
    color: str = Field(default="#3b82f6", description="Hex colour code for the badge")

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("color must be a valid hex code (e.g. '#3b82f6')")
        return v


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, description="New tag label")
    color: str | None = Field(default=None, description="New hex colour code")

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str | None) -> str | None:
        if v is not None and not _HEX_COLOR_RE.match(v):
            raise ValueError("color must be a valid hex code (e.g. '#3b82f6')")
        return v


class TagResponse(BaseModel):
    id: int = Field(description="Tag ID")
    name: str = Field(description="Tag label")
    color: str = Field(description="Hex colour code")
    created_at: datetime.datetime = Field(description="Creation timestamp")
    assets: list[AssetResponse] = Field(default=[], description="Assets that have this tag")

    model_config = {"from_attributes": True}
