"""Wire models for intraday bars (the SSE ``intraday`` event).

There is no REST endpoint for intraday bars — the quote stream is the only
egress. The payload is ``{symbol: [IntradayBar, ...]}``; the frontend mirror
is ``IntradayPoint`` in ``frontend/src/lib/types.ts``.
"""

from typing import Literal

from pydantic import BaseModel, Field

# The 3-value session vocabulary stored on ``IntradayPrice.session`` and
# consumed by the live day view's session-colored chart segments.
Session = Literal["pre", "regular", "post"]


class IntradayBar(BaseModel):
    """One 1-minute bar as stored in the DB and pushed over SSE."""

    time: int = Field(description="Bar timestamp as Unix epoch seconds.")
    price: float = Field(description="Close price, currency-normalised.")
    volume: int = Field(description="Bar volume (0 when the feed omits it).")
    session: Session = Field(description="Trading session the bar falls in.")
