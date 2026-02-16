import datetime

from pydantic import BaseModel, Field

from app.schemas.asset import AssetResponse


class TagCreate(BaseModel):
    name: str = Field(description="Unique tag label (e.g. 'tech', 'dividend')")
    color: str = Field(default="#3b82f6", description="Hex colour code for the badge")


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, description="New tag label")
    color: str | None = Field(default=None, description="New hex colour code")


class TagResponse(BaseModel):
    id: int = Field(description="Tag ID")
    name: str = Field(description="Tag label")
    color: str = Field(description="Hex colour code")
    created_at: datetime.datetime = Field(description="Creation timestamp")
    assets: list[AssetResponse] = Field(default=[], description="Assets that have this tag")

    model_config = {"from_attributes": True}
