import datetime

from pydantic import BaseModel


class EarningsResponse(BaseModel):
    earnings_date: datetime.date | None = None
    is_estimate: bool = True
    last_reported_date: datetime.date | None = None
