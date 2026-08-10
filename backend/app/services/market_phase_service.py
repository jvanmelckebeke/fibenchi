"""Scheduled market phases for the venue calendars the portfolio actually uses."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.asset_repo import AssetRepository
from app.schemas.market import CalendarPhase


async def collect_market_phases(db: AsyncSession) -> dict[str, CalendarPhase]:
    """Phase + next transition per in-use venue calendar.

    "In use" = the calendars of assets in any group (the same roster the SSE
    quote stream serves). Follows the market_calendar package's fail-safe
    convention: a symbol with no resolvable calendar, or a calendar that
    can't answer, is simply omitted — callers fall back to the live quote
    feed's market_state for those.
    """
    refs = await AssetRepository(db).list_in_any_group_refs()

    out: dict[str, CalendarPhase] = {}
    seen: set[str] = set()
    for ref in refs:
        name = ref.calendar_name
        if name is None or name in seen:
            continue
        seen.add(name)
        venue = ref.venue
        if venue is None:
            continue
        phase = venue.phase()
        if phase is None:
            continue
        out[name] = CalendarPhase(phase=phase, next_change_at=venue.next_phase_change())
    return out
