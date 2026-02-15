from pydantic import BaseModel


class SettingsResponse(BaseModel):
    data: dict

    model_config = {"from_attributes": True}


class SettingsUpdate(BaseModel):
    data: dict
