import datetime

from pydantic import BaseModel, Field


class AnnotationCreate(BaseModel):
    date: datetime.date = Field(description="Date the annotation refers to (shown as a marker on the chart)")
    title: str = Field(description="Short annotation title")
    body: str | None = Field(default=None, description="Optional extended body text (Markdown supported)")
    color: str = Field(default="#3b82f6", description="Marker colour as a hex code")


class AnnotationResponse(BaseModel):
    id: int = Field(description="Annotation ID")
    date: datetime.date = Field(description="Annotation date")
    title: str = Field(description="Short annotation title")
    body: str | None = Field(description="Extended body text")
    color: str = Field(description="Marker colour hex code")
    created_at: datetime.datetime = Field(description="Creation timestamp")

    model_config = {"from_attributes": True}
