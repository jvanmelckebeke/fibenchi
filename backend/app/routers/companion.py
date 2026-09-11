import hashlib
import json

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.companion import CompanionCalendar, CompanionConfig
from app.services import companion_calendar_service, companion_service

router = APIRouter(prefix="/api/companion", tags=["companion"])


@router.get("/config", response_model=CompanionConfig, summary="Companion app config bundle")
async def get_companion_config(db: AsyncSession = Depends(get_db)):
    """Versioned config bundle (groups + tickers + tags) for the mobile companion.

    The companion fetches live market data directly from Yahoo on-device; this
    endpoint only tells it *what to track*.
    """
    return await companion_service.build_config(db)


@router.get("/calendar", response_model=CompanionCalendar, summary="Companion app venue calendar")
async def get_companion_calendar(
    request: Request,
    venues: str | None = Query(
        None, description="Comma-separated exchange_calendars names; defaults to the tracked book's venues"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Venue closures and half-days the companion can't compute for itself.

    Separate from ``/config`` on purpose: the calendar changes about once a
    year and group config whenever a group is touched, so the two want
    different cache lifetimes and must not invalidate each other.
    """
    bundle = await companion_calendar_service.build_calendar(
        db, venues=venues.split(",") if venues else None
    )
    body = bundle.model_dump(by_alias=True, mode="json")

    # generatedAt is excluded from the digest: it moves on every request, and an
    # ETag that never matches is the same as having none. What identifies the
    # payload is the window plus the calendar data in it.
    digest = json.dumps(
        {k: v for k, v in body.items() if k != "generatedAt"}, sort_keys=True, separators=(",", ":")
    )
    etag = f'W/"{hashlib.sha256(digest.encode()).hexdigest()[:32]}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(body, headers={"ETag": etag})
