import datetime

from pydantic import BaseModel, Field


class ThesisUpdate(BaseModel):
    content: str = Field(max_length=50_000, description="Investment thesis text (Markdown supported)")


class ThesisResponse(BaseModel):
    content: str = Field(description="Investment thesis text (Markdown)")
    updated_at: datetime.datetime = Field(description="Last modification timestamp")

    model_config = {"from_attributes": True}
