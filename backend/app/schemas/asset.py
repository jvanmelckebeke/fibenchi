from datetime import datetime

from pydantic import BaseModel

from app.models.asset import AssetType


class AssetCreate(BaseModel):
    symbol: str
    name: str | None = None
    type: AssetType = AssetType.STOCK
    watchlisted: bool = True


class TagBrief(BaseModel):
    id: int
    name: str
    color: str

    model_config = {"from_attributes": True}


class AssetResponse(BaseModel):
    id: int
    symbol: str
    name: str
    type: AssetType
    watchlisted: bool
    created_at: datetime
    tags: list[TagBrief] = []

    model_config = {"from_attributes": True}
