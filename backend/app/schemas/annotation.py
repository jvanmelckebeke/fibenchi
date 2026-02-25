import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas._validators import validate_hex_color


class AnnotationCreate(BaseModel):
    date: datetime.date = Field(description="Date the annotation refers to (shown as a marker on the chart)")
    title: str = Field(description="Short annotation title")
    body: str | None = Field(default=None, description="Optional extended body text (Markdown supported)")
    color: str = Field(default="#3b82f6", description="Marker colour as a hex code")

    @field_validator("color")
    @classmethod
    def _validate_hex_color(cls, v: str) -> str:
        return validate_hex_color(v)


class AnnotationResponse(BaseModel):
    id: int = Field(description="Annotation ID")
    date: datetime.date = Field(description="Annotation date")
    title: str = Field(description="Short annotation title")
    body: str | None = Field(description="Extended body text")
    color: str = Field(description="Marker colour hex code")
    created_at: datetime.datetime = Field(description="Creation timestamp")

    model_config = {"from_attributes": True}
