from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SymbolSourceCreate(BaseModel):
    name: str = Field(description="Display name (e.g. 'Euronext')")
    provider_type: str = Field(description="Provider type key (e.g. 'euronext')")
    config: dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")


class SymbolSourceUpdate(BaseModel):
    enabled: bool | None = None
    config: dict[str, Any] | None = None
    name: str | None = None


class SymbolSourceResponse(BaseModel):
    id: int
    name: str
    provider_type: str
    enabled: bool
    config: dict[str, Any]
    last_synced_at: datetime | None = None
    symbol_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SymbolSourceSyncResponse(BaseModel):
    source_id: int
    symbols_synced: int
    message: str
