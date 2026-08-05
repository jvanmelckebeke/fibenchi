import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from app.config import settings as app_settings
from app.database import async_session, engine
from app.routers import (
    annotations,
    assets,
    companion,
    data,
    groups,
    holdings,
    indicators,
    note,
    portfolio,
    prices,
    pseudo_etf_analysis,
    pseudo_etfs,
    quotes,
    search,
    symbol_sources,
    tags,
    thesis,
)
from app.routers import settings as settings_router
from app.services.compute.group import compute_and_cache_indicators
from app.services.currency_service import load_cache as load_currency_cache
from app.services.intraday import cleanup_old_intraday, fetch_and_store_intraday
from app.services.market_calendar import any_venue_open
from app.services.price_heal import heal_interior_holes, heal_unreconciled_prices
from app.services.price_providers import init_price_provider
from app.services.price_sync import sync_all_prices
from app.services.symbol_sync_service import sync_all_enabled as sync_all_symbol_sources

# App loggers write through the root logger, which neither uvicorn nor docker
# configures — so every logger.info() (price heal, hole heal, refresh
# summaries, dropped-bar notices) was silently discarded and only WARNING+
# reached `docker logs`. That cost real diagnostic time in the 2026-08-05
# incident. basicConfig is a no-op when handlers already exist (pytest, etc.),
# and uvicorn's own loggers don't propagate to root, so nothing is duplicated.
logging.basicConfig(
    level=getattr(logging, app_settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def warm_all_group_caches() -> int:
    """Pre-compute indicator snapshots for every group so the first request
    on any group page hits a warm cache. Returns the number of groups warmed.

    Each group is warmed in its own DB session so a slow group doesn't hold
    a connection longer than necessary. Failures on one group are logged
    and do not stop subsequent groups.
    """
    from app.repositories.group_repo import GroupRepository

    async with async_session() as db:
        try:
            groups = await GroupRepository(db).list_all()
        except Exception:
            logger.exception("Failed to load groups for cache warming")
            return 0

    warmed = 0
    for group in groups:
        async with async_session() as db:
            try:
                snapshot = await compute_and_cache_indicators(db, group_id=group.id)
                if snapshot:
                    warmed += 1
            except Exception:
                logger.exception(f"Cache warm failed for group {group.id} ({group.name})")
    return warmed


async def scheduled_refresh():
    """Background job: refresh all asset prices, then warm indicator cache."""
    logger.info("Running scheduled price refresh...")
    async with async_session() as db:
        try:
            counts = await sync_all_prices(db)
            total = sum(counts.values())
            logger.info(f"Refreshed {len(counts)} assets, {total} price points")
        except Exception:
            logger.exception("Scheduled refresh failed")
            return

    try:
        warmed = await warm_all_group_caches()
        if warmed:
            logger.info(f"Pre-computed indicator caches for {warmed} groups")
    except Exception:
        logger.exception("Indicator pre-computation failed (non-fatal)")

    # Clean up old intraday data (keep only last 2 days)
    async with async_session() as db:
        try:
            deleted = await cleanup_old_intraday(db)
            if deleted:
                logger.info(f"Cleaned up {deleted} old intraday bars")
        except Exception:
            logger.exception("Intraday cleanup failed (non-fatal)")


async def _startup_warmup() -> None:
    """Pre-compute indicator caches at startup.

    Runs as a background task so the API is reachable immediately while
    the cache builds. Fundamentals lazy-fetch via
    :func:`merge_fundamentals_from_cache` so we don't burst at Yahoo at
    boot.
    """
    logger.info("Starting background cache warmup...")
    try:
        warmed = await warm_all_group_caches()
        if warmed:
            logger.info(f"Startup warmup complete: {warmed} groups cached")
    except Exception:
        logger.exception("Startup indicator warmup failed (non-fatal)")


async def scheduled_price_heal():
    """Background job: refresh symbols whose stored bars contradict live quotes."""
    async with async_session() as db:
        # While every tracked venue is closed, quotes are frozen and no stored
        # bar can newly diverge — skip the full portfolio quote scan. The venue
        # schedule replaces the old weekday() proxy, which ran all day on
        # global holidays, skipped crypto weekends, and used the server-local
        # date (Monday morning in Tokyo is still Sunday here).
        from app.repositories.asset_repo import AssetRepository

        refs = await AssetRepository(db).list_in_any_group_refs()
        if not refs or not any_venue_open(refs):
            return
        try:
            healed = await heal_unreconciled_prices(db)
            if healed:
                logger.info(
                    f"Price heal: refreshed {len(healed)} symbol(s): {', '.join(sorted(healed))}"
                )
        except Exception:
            logger.exception("Price heal failed")
        try:
            # Mid-series holes (issue #559): self-throttled to one scan per
            # HOLE_SCAN_INTERVAL, so piggybacking on this job costs nothing.
            filled = await heal_interior_holes(db)
            if filled:
                logger.info(
                    f"Hole heal: refreshed {len(filled)} symbol(s): {', '.join(sorted(filled))}"
                )
        except Exception:
            logger.exception("Hole heal failed")


async def scheduled_symbol_sync():
    """Background job: sync all enabled symbol directory sources."""
    logger.info("Running scheduled symbol directory sync...")
    async with async_session() as db:
        try:
            counts = await sync_all_symbol_sources(db)
            total = sum(counts.values())
            logger.info(f"Symbol sync complete: {len(counts)} sources, {total} symbols")
        except Exception:
            logger.exception("Scheduled symbol sync failed")


async def scheduled_intraday_sync():
    """Background job: fetch 1m intraday bars for all grouped assets."""
    from app.repositories.asset_repo import AssetRepository

    async with async_session() as db:
        try:
            refs = await AssetRepository(db).list_in_any_group_refs()
            if not refs:
                return

            # Venue-schedule gate. This replaces quoting 15 *random* symbols
            # per tick to sniff for an active market — a Yahoo round-trip
            # every 60s that could still miss the one open venue (3 Tokyo
            # listings in a 200-symbol portfolio → ~80% miss). The calendar
            # answer is deterministic, holiday-aware, and free.
            if not any_venue_open(refs):
                return

            count = await fetch_and_store_intraday(db, refs)
            if count:
                logger.info(f"Intraday sync: {count} bars for {len(refs)} symbols")
        except Exception:
            logger.exception("Intraday sync failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the price data provider (Yahoo, IBKR, etc.)
    init_price_provider()

    # Load currency lookup cache from DB
    async with async_session() as db:
        await load_currency_cache(db)

    # Parse cron expression (minute hour day month dow)
    parts = app_settings.refresh_cron.split()
    if len(parts) == 5:
        trigger = CronTrigger(
            minute=parts[0], hour=parts[1], day=parts[2],
            month=parts[3], day_of_week=parts[4],
        )
        scheduler.add_job(scheduled_refresh, trigger, id="price_refresh")

        # Supplemental daytime refreshes. The primary run above fires once at
        # REFRESH_CRON (23:00 UTC by default), but Yahoo publishes some markets'
        # daily bars well after their close — notably KRX (``.KS``), whose bar
        # for a session isn't in Yahoo's daily history until the *following* day.
        # A single nightly run therefore leaves Asian markets a full day stale
        # (a stale σ-Move/change sitting beside a live quote). Extra 08:00 and
        # 16:00 UTC runs catch the prior Asian session (published overnight) and
        # any late Yahoo publish, so no market stays stale longer than ~8h.
        scheduler.add_job(
            scheduled_refresh,
            CronTrigger(minute="0", hour="8,16"),
            id="price_refresh_supplemental",
        )

        # Weekly symbol directory sync (Sundays at 02:00)
        scheduler.add_job(
            scheduled_symbol_sync,
            CronTrigger(minute="0", hour="2", day_of_week="sun"),
            id="symbol_directory_sync",
        )

        # Intraday sync every 60 seconds
        scheduler.add_job(
            scheduled_intraday_sync,
            IntervalTrigger(seconds=60),
            id="intraday_sync",
        )

        # Self-heal stragglers the scheduled refreshes missed: when a symbol's
        # latest stored bar reconciles with neither the live price nor the
        # quote's previous close (the state that blanks σ-Move), refresh just
        # that symbol instead of waiting for the next full run.
        scheduler.add_job(
            scheduled_price_heal,
            IntervalTrigger(minutes=10),
            id="price_heal",
        )

        scheduler.start()
        logger.info(f"Scheduler started with cron: {app_settings.refresh_cron}")

    # Kick off cache warmup in the background — API is reachable immediately,
    # cache builds in parallel so the first group hit is warm.
    warmup_task = asyncio.create_task(_startup_warmup())

    yield

    warmup_task.cancel()
    scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(
    title="Fibenchi",
    summary="Investment research dashboard for tracking stocks, ETFs, and custom baskets.",
    description=(
        "Fibenchi is a self-hosted investment research tool. It lets you organize "
        "stocks and ETFs into groups, view OHLCV price charts with technical indicators "
        "(RSI, SMA, Bollinger Bands, MACD), write investment theses, and annotate charts "
        "with dated notes.\n\n"
        "**Pseudo-ETFs** are user-created baskets of assets with equal-weight allocation and "
        "quarterly rebalancing. They have their own indexed performance chart, per-constituent "
        "breakdown, and indicator snapshots.\n\n"
        "**Key concepts:**\n"
        "- Assets are stocks or ETFs identified by ticker symbol. Removing an asset from its "
        "last group preserves the row for pseudo-ETF relationships.\n"
        "- Prices are sourced from Yahoo Finance and cached in PostgreSQL. A daily cron job "
        "refreshes all grouped assets.\n"
        "- Ephemeral price views allow fetching prices for ungrouped symbols (e.g. ETF "
        "holdings) without persisting data.\n"
        "- Groups are user-defined collections of assets. The default 'Watchlist' group "
        "cannot be deleted or renamed. Per-group batch endpoints provide sparklines and "
        "indicator snapshots in a single request, avoiding N+1 queries.\n"
        "- Real-time quotes are delivered via SSE with delta compression — only symbols whose "
        "data changed since the last push are included.\n"
    ),
    version="1.1.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "assets",
            "description": "Manage tracked stocks and ETFs. Assets are identified by ticker symbol and auto-validated against Yahoo Finance.",
        },
        {
            "name": "data",
            "description": (
                "General-purpose batch data query for external tooling. Fetch quotes, indicator "
                "snapshots, prices, and/or technical indicators for multiple tickers in a single "
                "request. Works for any ticker — tracked assets use cached DB data, untracked "
                "symbols are fetched ephemerally from the price provider."
            ),
        },
        {
            "name": "prices",
            "description": "OHLCV price data and technical indicators (RSI, SMA 20/50, Bollinger Bands, MACD) for individual assets. Supports both persisted (grouped) and ephemeral (ungrouped) price fetching.",
        },
        {
            "name": "holdings",
            "description": "ETF holdings breakdown and per-holding technical indicator snapshots. Only available for assets with type=etf.",
        },
        {
            "name": "portfolio",
            "description": "Portfolio-wide analytics: composite equal-weight index of all grouped assets, and top/bottom performer rankings by period return.",
        },
        {
            "name": "groups",
            "description": "User-defined groups for organizing assets into named collections. The default 'Watchlist' group is protected. Per-group batch endpoints provide sparklines and indicator snapshots in a single request.",
        },
        {
            "name": "tags",
            "description": "Colored labels for categorizing assets (e.g. 'tech', 'growth', 'dividend'). Tags can be attached to assets and used for dashboard filtering.",
        },
        {
            "name": "note",
            "description": "Free-text note per asset. Supports Markdown content.",
        },
        {
            "name": "theses",
            "description": "Global cross-cutting theses: thematic baskets of tickers tracked under one hypothesis, with a lifecycle status and open date. An asset can belong to many theses.",
        },
        {
            "name": "annotations",
            "description": "Dated chart annotations per asset. Each annotation has a date, title, body, and color for visual markers on price charts.",
        },
        {
            "name": "quotes",
            "description": (
                "Real-time market quotes via REST and SSE. The REST endpoint returns quotes for "
                "arbitrary symbols. The SSE stream pushes quotes for all grouped assets with delta "
                "compression (only changed symbols are sent) and adaptive intervals: 15 s during "
                "regular market hours, 60 s pre/post-market, 300 s when markets are closed."
            ),
        },
        {
            "name": "pseudo-etfs",
            "description": "User-created custom baskets (pseudo-ETFs) with equal-weight allocation and quarterly rebalancing. Includes constituent management, indexed performance with per-symbol breakdown, technical indicator snapshots, note, and annotations.",
        },
        {
            "name": "settings",
            "description": "User preference storage for indicator visibility, chart preferences, and display options.",
        },
        {
            "name": "companion",
            "description": "Versioned config bundle (groups + tickers + tags) for the mobile companion app — tells it what to track; live data is fetched on-device.",
        },
        {
            "name": "system",
            "description": "Health checks and operational endpoints.",
        },
    ],
)

app.include_router(assets.router)
app.include_router(data.router)
app.include_router(groups.router)
app.include_router(companion.router)
app.include_router(tags.router)
app.include_router(tags.asset_tag_router)
app.include_router(portfolio.router)
app.include_router(prices.router)
app.include_router(holdings.router)
app.include_router(indicators.router)
app.include_router(note.router)
app.include_router(thesis.router)
app.include_router(annotations.router)
app.include_router(pseudo_etfs.router)
app.include_router(pseudo_etf_analysis.router)
app.include_router(quotes.router)
app.include_router(settings_router.router)
app.include_router(search.router)
app.include_router(symbol_sources.router)


@app.get("/api/health", summary="Health check", tags=["system"])
async def health():
    """Return `{\"status\": \"ok\"}` when the service is running."""
    return {"status": "ok"}


# --- SPA static serving (production only) ---
# In production the frontend is built into /app/static by the root Dockerfile.
# In dev this directory doesn't exist, so the mount is skipped entirely.
_SPA_DIR = Path(__file__).resolve().parent.parent / "static"

if (_SPA_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_SPA_DIR / "assets"), name="static-assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def _spa_fallback(path: str):
        file = _SPA_DIR / path
        if file.is_file() and file.resolve().is_relative_to(_SPA_DIR.resolve()):
            return FileResponse(file)
        return FileResponse(_SPA_DIR / "index.html")
