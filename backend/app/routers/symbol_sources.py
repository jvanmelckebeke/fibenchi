import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.database import async_session, get_db
from app.models.symbol_source import SymbolSource
from app.schemas.symbol_source import (
    SymbolSourceCreate,
    SymbolSourceResponse,
    SymbolSourceSyncResponse,
    SymbolSourceUpdate,
)
from app.services.symbol_providers import get_available_providers, get_provider
from app.services.symbol_sync_service import nullify_source_symbols, sync_source

router = APIRouter(prefix="/api/symbol-sources", tags=["symbol-sources"])


@router.get("", response_model=list[SymbolSourceResponse], summary="List symbol sources")
async def list_sources(db: AsyncSession = Depends(get_db)):
    """Return all configured symbol sources with their stats."""
    result = await db.execute(select(SymbolSource).order_by(SymbolSource.id))
    return result.scalars().all()


@router.get("/providers", summary="List available providers")
async def list_providers():
    """Return metadata about all available provider types (for the 'Add Source' UI)."""
    return get_available_providers()


@router.post("", response_model=SymbolSourceResponse, status_code=201, summary="Create symbol source")
async def create_source(body: SymbolSourceCreate, db: AsyncSession = Depends(get_db)):
    """Create a new symbol source configuration."""
    # Validate provider type exists
    try:
        get_provider(body.provider_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown provider type: {body.provider_type}")

    source = SymbolSource(
        name=body.name,
        provider_type=body.provider_type,
        config=body.config,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@router.patch("/{source_id}", response_model=SymbolSourceResponse, summary="Update symbol source")
async def update_source(
    source_id: int, body: SymbolSourceUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a symbol source's config, enabled state, or name."""
    source = await db.get(SymbolSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Symbol source not found")

    if body.enabled is not None:
        source.enabled = body.enabled
    if body.config is not None:
        source.config = body.config
    if body.name is not None:
        source.name = body.name

    await db.commit()
    await db.refresh(source)
    return source


@router.post(
    "/{source_id}/sync",
    response_model=SymbolSourceSyncResponse,
    summary="Sync symbol source",
)
async def trigger_sync(
    source_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual sync for a symbol source. Runs in the background."""
    source = await db.get(SymbolSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Symbol source not found")

    async def _run_sync(sid: int):
        async with async_session() as session:
            try:
                await sync_source(sid, session)
            except Exception:
                logger.exception("Background sync failed for source %d", sid)

    background_tasks.add_task(_run_sync, source_id)

    return SymbolSourceSyncResponse(
        source_id=source_id,
        symbols_synced=source.symbol_count,
        message="Sync started in background",
    )


@router.delete("/{source_id}", status_code=204, summary="Delete symbol source")
async def delete_source(source_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a symbol source. Symbols are kept but their source_id is set to NULL."""
    source = await db.get(SymbolSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Symbol source not found")

    await nullify_source_symbols(source_id, db)
    await db.delete(source)
    await db.commit()
