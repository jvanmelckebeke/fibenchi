from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    data: dict = Field(description="Free-form settings object (e.g. watchlist_show_rsi, compact_mode)")

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    data: dict = Field(description="Complete settings object — replaces the existing value")
