import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from app.config import settings
from sqlalchemy import text

from app.database import async_session, engine, Base
from app.models import Asset  # noqa: F401 - ensure models are imported for create_all
from app.routers import annotations, assets, groups, holdings, prices, pseudo_etfs, thesis
from app.services.price_sync import sync_all_prices

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


app = FastAPI(title="fibenchi", lifespan=lifespan)

app.include_router(assets.router)
app.include_router(groups.router)
app.include_router(prices.router)
app.include_router(holdings.router)
app.include_router(thesis.router)
app.include_router(annotations.router)
app.include_router(pseudo_etfs.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
