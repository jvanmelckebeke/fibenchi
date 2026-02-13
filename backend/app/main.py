import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

from app.config import settings
from sqlalchemy import select, text

from app.database import async_session, engine, Base
from app.models import Asset  # noqa: F401 - ensure models are imported for create_all
from app.routers import annotations, assets, groups, holdings, portfolio, prices, pseudo_etfs, quotes, tags, thesis
from app.services.price_sync import sync_all_prices
from app.services.yahoo import batch_fetch_currencies

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def scheduled_refresh():
    """Background job: refresh all asset prices."""
    logger.info("Running scheduled price refresh...")
    async with async_session() as db:
        try:
            counts = await sync_all_prices(db)
            total = sum(counts.values())
            logger.info(f"Refreshed {len(counts)} assets, {total} price points")
        except Exception:
            logger.exception("Scheduled refresh failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migration: add watchlisted column to existing assets table
        await conn.execute(text(
            "ALTER TABLE assets ADD COLUMN IF NOT EXISTS watchlisted BOOLEAN DEFAULT TRUE NOT NULL"
        ))
        # Migration: add currency column to existing assets table
        await conn.execute(text(
            "ALTER TABLE assets ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'USD' NOT NULL"
        ))

    # Backfill currencies for existing assets that still have the default "USD"
    async with async_session() as db:
        result = await db.execute(select(Asset).where(Asset.currency == "USD"))
        usd_assets = result.scalars().all()
        if usd_assets:
            symbols = [a.symbol for a in usd_assets]
            try:
                currencies = batch_fetch_currencies(symbols)
                updated = 0
                for asset in usd_assets:
                    fetched = currencies.get(asset.symbol)
                    if fetched and fetched != "USD":
                        asset.currency = fetched
                        updated += 1
                if updated:
                    await db.commit()
                    logger.info(f"Backfilled currency for {updated} assets")
            except Exception:
                logger.exception("Currency backfill failed (non-fatal)")

    # Parse cron expression (minute hour day month dow)
    parts = settings.refresh_cron.split()
    if len(parts) == 5:
        trigger = CronTrigger(
            minute=parts[0], hour=parts[1], day=parts[2],
            month=parts[3], day_of_week=parts[4],
        )
        scheduler.add_job(scheduled_refresh, trigger, id="price_refresh")
        scheduler.start()
        logger.info(f"Scheduler started with cron: {settings.refresh_cron}")

    yield

    scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(
    title="Fibenchi",
    summary="Investment research dashboard for tracking stocks, ETFs, and custom baskets.",
    description=(
        "Fibenchi is a self-hosted investment research tool. It lets you maintain a watchlist "
        "of stocks and ETFs, view OHLCV price charts with technical indicators "
        "(RSI, SMA, Bollinger Bands, MACD), write investment theses, and annotate charts "
        "with dated notes.\n\n"
        "**Pseudo-ETFs** are user-created baskets of assets with equal-weight allocation and "
        "quarterly rebalancing. They have their own indexed performance chart, per-constituent "
        "breakdown, and indicator snapshots.\n\n"
        "**Key concepts:**\n"
        "- Assets are stocks or ETFs identified by ticker symbol. Deleting an asset soft-deletes "
        "it (sets `watchlisted=false`) to preserve pseudo-ETF relationships.\n"
        "- Prices are sourced from Yahoo Finance and cached in PostgreSQL. A daily cron job "
        "refreshes all watchlisted assets.\n"
        "- Ephemeral price views allow fetching prices for non-watchlisted symbols (e.g. ETF "
        "holdings) without persisting data.\n"
        "- Groups are user-defined collections of assets for organization.\n"
    ),
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "assets",
            "description": "Manage the watchlist of tracked stocks and ETFs. Assets are identified by ticker symbol and auto-validated against Yahoo Finance.",
        },
        {
            "name": "prices",
            "description": "OHLCV price data and technical indicators (RSI, SMA 20/50, Bollinger Bands, MACD) for individual assets. Supports both persisted (watchlisted) and ephemeral (non-watchlisted) price fetching.",
        },
        {
            "name": "holdings",
            "description": "ETF holdings breakdown and per-holding technical indicator snapshots. Only available for assets with type=etf.",
        },
        {
            "name": "portfolio",
            "description": "Portfolio-wide analytics: composite equal-weight index of all watchlisted assets, and top/bottom performer rankings by period return.",
        },
        {
            "name": "groups",
            "description": "User-defined groups for organizing assets into named collections (e.g. 'Tech', 'Dividend').",
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
            "description": "Real-time market quotes for one or more symbols. Lightweight endpoint for live price polling.",
        },
        {
            "name": "pseudo-etfs",
            "description": "User-created custom baskets (pseudo-ETFs) with equal-weight allocation and quarterly rebalancing. Includes constituent management, indexed performance with per-symbol breakdown, technical indicator snapshots, thesis, and annotations.",
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
app.include_router(quotes.router)


@app.get("/api/health", summary="Health check", tags=["system"])
async def health():
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
