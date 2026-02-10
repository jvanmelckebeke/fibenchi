from datetime import datetime

from pydantic import BaseModel


class ThesisUpdate(BaseModel):
    content: str


class ThesisResponse(BaseModel):
    content: str
    updated_at: datetime

    model_config = {"from_attributes": True}
