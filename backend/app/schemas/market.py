"""Response models for market schedule endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.phases import Phase


class CalendarPhase(BaseModel):
    """Scheduled trading phase of one venue calendar.

    Deterministic and quote-feed-independent: derived from the venue's
    exchange calendar (half-day and holiday aware), so it keeps answering
    when the live quote feed is degraded. The live ``market_state`` from the
    SSE stream remains authoritative when present — it knows about halts.
    """

    phase: Phase = Field(description="Scheduled phase right now (premarket/open/aftermarket/closed)")
    next_change_at: datetime | None = Field(
        description="When the scheduled phase next changes (UTC); the venue's next bell "
        "or extended-hours edge. None when the calendar can't answer."
    )
    symbols: list[str] = Field(
        description="Grouped symbols trading on this calendar — the symbol→venue mapping "
        "lives backend-side (AssetRef), so clients get it here instead of re-deriving it "
        "from ticker shapes."
    )
