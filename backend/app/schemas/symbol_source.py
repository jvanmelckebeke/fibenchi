from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SymbolSourceCreate(BaseModel):
    name: str = Field(description="Display name (e.g. 'Euronext')")
    provider_type: str = Field(description="Provider type key (e.g. 'euronext')")
    config: dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")


class SymbolSourceUpdate(BaseModel):
    enabled: Optional[bool] = None
    config: Optional[dict[str, Any]] = None
    name: Optional[str] = None


class SymbolSourceResponse(BaseModel):
    id: int
    name: str
    provider_type: str
    enabled: bool
    config: dict[str, Any]
    last_synced_at: Optional[datetime] = None
    symbol_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SymbolSourceSyncResponse(BaseModel):
    source_id: int
    symbols_synced: int
    message: str
