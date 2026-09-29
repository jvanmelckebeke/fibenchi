"""The indicator contract: registry metadata the companion app implements against.

Built by ``scripts/export_indicator_contract.py`` from ``INDICATOR_REGISTRY`` and
exported both as data (``indicator.contract.json``) and as its own JSON Schema
(``indicator.contract.schema.json``), which the contract package turns into a Zod
schema and TypeScript types.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

Platform = Literal["web", "app"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class IndicatorSpec(_CamelModel):
    """One registry entry, with the Python callables reduced to stable string ids."""

    key: str = Field(description="Registry key, e.g. sma_20")
    kernel: str = Field(description="Id of the numeric kernel that computes it; several keys can share one")
    params: dict[str, int | float] = Field(description="Kernel parameters")
    output_fields: list[str] = Field(description="Fields the kernel produces directly")
    delta_fields: list[str] = Field(description="Analysis fields the backend post-computes from the kernel output")
    decimals: int = Field(description="Rounding for the output fields")
    field_decimals: dict[str, int] = Field(description="Per-field rounding overrides")
    warmup: int = Field(description="Bars needed before the first valid value")
    uses_ohlc: bool = Field(description="Whether the kernel reads high/low as well as close")
    snapshot_derived: str | None = Field(description="Id of the snapshot-derived callback, if any")
    platforms: list[Platform] = Field(description="Where it is implemented")


class IndicatorContract(_CamelModel):
    version: Literal[1] = Field(description="Contract version")
    indicators: list[IndicatorSpec] = Field(description="Every registered indicator, in registry order")
