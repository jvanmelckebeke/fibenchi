from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.asset import AssetResponse


class PseudoETFCreate(BaseModel):
    name: str
    description: str | None = None
    base_date: date
    base_value: float = 100.0


class PseudoETFUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    base_date: date | None = None


class PseudoETFAddConstituents(BaseModel):
    asset_ids: list[int]


class PseudoETFResponse(BaseModel):
    id: int
    name: str
    description: str | None
    base_date: date
    base_value: float
    created_at: datetime
    constituents: list[AssetResponse] = []

    model_config = {"from_attributes": True}


class PerformancePoint(BaseModel):
    date: date
    value: float
