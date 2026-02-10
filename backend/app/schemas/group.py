from datetime import datetime

from pydantic import BaseModel

from app.schemas.asset import AssetResponse


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class GroupAddAssets(BaseModel):
    asset_ids: list[int]


class GroupResponse(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime
    assets: list[AssetResponse] = []

    model_config = {"from_attributes": True}
