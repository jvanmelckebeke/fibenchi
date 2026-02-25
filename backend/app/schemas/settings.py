import json

from pydantic import BaseModel, Field, field_validator

MAX_SETTINGS_BYTES = 65_536  # 64 KB


class SettingsResponse(BaseModel):
    data: dict = Field(description="Free-form settings object (e.g. group_show_rsi, compact_mode)")

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    data: dict = Field(description="Complete settings object — replaces the existing value")

    @field_validator("data")
    @classmethod
    def limit_payload_size(cls, v: dict) -> dict:
        size = len(json.dumps(v, separators=(",", ":")))
        if size > MAX_SETTINGS_BYTES:
            raise ValueError(f"settings payload too large ({size} bytes, max {MAX_SETTINGS_BYTES})")
        return v
