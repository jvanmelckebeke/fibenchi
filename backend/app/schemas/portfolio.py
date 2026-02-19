from datetime import date

from pydantic import BaseModel

from app.models.asset import AssetType


class PortfolioIndexResponse(BaseModel):
    dates: list[date]
    values: list[float]
    current: float
    change: float
    change_pct: float


class AssetPerformance(BaseModel):
    symbol: str
    name: str
    type: AssetType
    change_pct: float
