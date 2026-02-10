from datetime import datetime

from pydantic import BaseModel

from app.models.asset import AssetType


class AssetCreate(BaseModel):
    symbol: str
    name: str | None = None
    type: AssetType = AssetType.STOCK


class AssetResponse(BaseModel):
    id: int
    symbol: str
    name: str
    type: AssetType
    created_at: datetime

    model_config = {"from_attributes": True}
