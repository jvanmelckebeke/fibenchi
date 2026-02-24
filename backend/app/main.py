import logging
from contextlib import asynccontextmanager
from pathlib import Path

from datetime import date

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from app.config import settings as app_settings

from app.database import async_session, engine
from app.routers import annotations, assets, groups, holdings, portfolio, prices, pseudo_etfs, pseudo_etf_analysis, quotes, search, settings as settings_router, symbol_sources, tags, thesis
from app.services.price_sync import sync_all_prices
from app.services.compute.group import compute_and_cache_indicators
from app.services.currency_service import load_cache as load_currency_cache
from app.services.intraday import fetch_and_store_intraday, cleanup_old_intraday
from app.services.symbol_sync_service import sync_all_enabled as sync_all_symbol_sources

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


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

    # Pre-compute indicator snapshots so the first group page request is instant
    async with async_session() as db:
        try:
            indicators = await compute_and_cache_indicators(db)
            logger.info(f"Pre-computed indicators for {len(indicators)} assets")
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
    if date.today().weekday() >= 5:
        return

    from app.repositories.asset_repo import AssetRepository
    from app.services.yahoo import batch_fetch_quotes

    async with async_session() as db:
        try:
            pairs = await AssetRepository(db).list_in_any_group_id_symbol_pairs()
            if not pairs:
                return

            symbols = [sym for _, sym in pairs]
            asset_map = {sym: aid for aid, sym in pairs}

            # Sample across the list to detect mixed-timezone market activity
            sample_size = min(10, len(symbols))
            step = max(1, len(symbols) // sample_size)
            sample = symbols[::step][:sample_size]
            quotes = await batch_fetch_quotes(sample)
            market_states = {q.get("market_state") for q in quotes if q.get("market_state")}
            active_states = {"REGULAR", "PRE", "POST", "PREPRE", "POSTPOST"}
            if not market_states & active_states:
                return

            count = await fetch_and_store_intraday(db, symbols, asset_map)
            if count:
                logger.info(f"Intraday sync: {count} bars for {len(symbols)} symbols")
        except Exception:
            logger.exception("Intraday sync failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
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

        scheduler.start()
        logger.info(f"Scheduler started with cron: {app_settings.refresh_cron}")

    yield

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
            "name": "thesis",
            "description": "Free-text investment thesis per asset. Supports Markdown content.",
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
            "description": "User-created custom baskets (pseudo-ETFs) with equal-weight allocation and quarterly rebalancing. Includes constituent management, indexed performance with per-symbol breakdown, technical indicator snapshots, thesis, and annotations.",
        },
        {
            "name": "settings",
            "description": "User preference storage for indicator visibility, chart preferences, and display options.",
        },
        {
            "name": "system",
            "description": "Health checks and operational endpoints.",
        },
    ],
)

app.include_router(assets.router)
app.include_router(groups.router)
app.include_router(tags.router)
app.include_router(tags.asset_tag_router)
app.include_router(portfolio.router)
app.include_router(prices.router)
app.include_router(holdings.router)
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
