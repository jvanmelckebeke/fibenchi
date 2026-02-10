from datetime import date, datetime

from pydantic import BaseModel


class AnnotationCreate(BaseModel):
    date: date
    title: str
    body: str | None = None
    color: str = "#3b82f6"


class AnnotationResponse(BaseModel):
    id: int
    date: date
    title: str
    body: str | None
    color: str
    created_at: datetime

    model_config = {"from_attributes": True}
