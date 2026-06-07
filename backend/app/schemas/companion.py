"""Companion-app config contract — the single source of truth.

This Pydantic model is the SoT for the mobile companion (jvanmelckebeke/fibenchi-app).
Its JSON Schema (see ``scripts/export_companion_schema.py``) is the input to the
app's Zod codegen, so the contract cannot drift between Fibenchi and the app.

Shape is normalized: groups reference symbols, and ``tickers`` holds each symbol's
metadata once (a symbol commonly lives in several groups via the M:N group_assets).

Serialized camelCase (alias generator) for the TypeScript consumer; constructed
with snake_case field names internally (populate_by_name).
"""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.asset import AssetType

#: Current contract version. Bump on any breaking shape change; the app gates on it.
CONFIG_VERSION = 1


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ConfigTicker(_CamelModel):
    """Metadata for a single tracked symbol (defined once across all groups)."""

    name: str = Field(description="Display name")
    type: AssetType = Field(description="Asset type: stock, etf, or index")
    currency: str = Field(default="USD", description="ISO 4217 display code (normalized, e.g. GBp -> GBP)")
    tags: list[str] = Field(default_factory=list, description="Tag names attached to this symbol")


class ConfigGroup(_CamelModel):
    """A user group as ordered symbol references."""

    name: str = Field(description="Group name")
    icon: str | None = Field(default=None, description="Lucide icon name")
    is_default: bool = Field(description="Whether this is the protected default group (Watchlist)")
    position: int = Field(description="Display order (0 = first)")
    symbols: list[str] = Field(default_factory=list, description="Ticker symbols in this group, in order")


class CompanionConfig(_CamelModel):
    """The full config bundle the companion app pulls and caches."""

    version: Literal[1] = Field(description="Contract version the app gates on (always sent; required so the app's gate can't be bypassed by an absent field)")
    generated_at: datetime.datetime = Field(description="When this bundle was produced (UTC)")
    groups: list[ConfigGroup] = Field(default_factory=list, description="User groups, ordered")
    tickers: dict[str, ConfigTicker] = Field(default_factory=dict, description="symbol -> metadata")
    tags: dict[str, str] = Field(default_factory=dict, description="tag name -> hex colour")
