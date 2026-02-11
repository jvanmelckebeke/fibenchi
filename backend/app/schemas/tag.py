from datetime import datetime

from pydantic import BaseModel

from app.schemas.asset import AssetResponse


class TagCreate(BaseModel):
    name: str
    color: str = "#3b82f6"


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class TagResponse(BaseModel):
    id: int
    name: str
    color: str
    created_at: datetime
    assets: list[AssetResponse] = []

    model_config = {"from_attributes": True}
