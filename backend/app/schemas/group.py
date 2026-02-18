import datetime

from pydantic import BaseModel, Field

from app.schemas.asset import AssetResponse


class GroupCreate(BaseModel):
    name: str = Field(description="Unique group name")
    description: str | None = Field(default=None, description="Optional group description")


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, description="New group name")
    description: str | None = Field(default=None, description="New description")


class GroupAddAssets(BaseModel):
    asset_ids: list[int] = Field(description="List of asset IDs to add to the group")


class GroupResponse(BaseModel):
    id: int = Field(description="Group ID")
    name: str = Field(description="Group name")
    description: str | None = Field(description="Group description")
    is_default: bool = Field(description="Whether this is the protected default group (Watchlist)")
    position: int = Field(description="Display order position (0 = first)")
    created_at: datetime.datetime = Field(description="Creation timestamp")
    assets: list[AssetResponse] = Field(default=[], description="Assets in this group")

    model_config = {"from_attributes": True}
