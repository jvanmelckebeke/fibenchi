import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_SETTINGS_BYTES = 65_536  # 64 KB


class AppSettingsData(BaseModel):
    """Typed settings schema mirroring the frontend's AppSettings interface.

    All fields are optional so partial updates (patches) are accepted.
    Unknown keys from newer frontend versions are preserved via extra="allow".
    """

    indicator_visibility: dict[str, list[str]] | None = None
    group_macd_style: Literal["classic", "divergence"] | None = None
    group_show_sparkline: bool | None = None
    group_view_mode: Literal["card", "table", "scanner", "live"] | None = None
    group_type_filter: Literal["all", "stock", "etf"] | None = None
    group_sort_by: str | None = None
    group_sort_dir: Literal["asc", "desc"] | None = None
    group_table_columns: dict[str, bool] | None = None
    group_table_column_widths: dict[str, float] | None = None
    chart_default_period: str | None = None
    chart_type: Literal["candle", "line"] | None = None
    theme: Literal["dark", "light", "system"] | None = None
    compact_mode: bool | None = None
    compact_numbers: bool | None = None
    show_asset_type_badge: bool | None = None
    decimal_places: int | None = None
    sync_pseudo_etf_crosshairs: bool | None = None
    show_indicator_deltas: bool | None = None
    thousands_separator: bool | None = None

    model_config = {"extra": "allow"}


class SettingsResponse(BaseModel):
    data: dict = Field(description="Settings object with typed keys (see AppSettingsData)")

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    data: AppSettingsData = Field(description="Settings object — validated against AppSettingsData schema")

    @field_validator("data", mode="before")
    @classmethod
    def limit_payload_size(cls, v: dict | AppSettingsData) -> dict | AppSettingsData:
        raw = v if isinstance(v, dict) else v.model_dump(exclude_none=True)
        size = len(json.dumps(raw, separators=(",", ":")))
        if size > MAX_SETTINGS_BYTES:
            raise ValueError(f"settings payload too large ({size} bytes, max {MAX_SETTINGS_BYTES})")
        return v
