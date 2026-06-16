import datetime

from pydantic import BaseModel, Field


class NoteUpdate(BaseModel):
    content: str = Field(max_length=50_000, description="Free-text note (Markdown supported)")


class NoteResponse(BaseModel):
    content: str = Field(description="Free-text note (Markdown)")
    updated_at: datetime.datetime = Field(description="Last modification timestamp")

    model_config = {"from_attributes": True}
