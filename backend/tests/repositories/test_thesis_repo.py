"""Tests for ThesisRepository — query methods against real SQLite DB."""

import pytest

from app.models import Asset, AssetType, Thesis
from app.repositories.thesis_repo import ThesisRepository

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _create_asset(db, symbol: str, watchlisted: bool = True, **kwargs) -> Asset:
    defaults = dict(name=f"{symbol} Inc.", type=AssetType.STOCK, currency="USD")
    defaults.update(kwargs)
    asset = Asset(symbol=symbol, watchlisted=watchlisted, **defaults)
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


async def test_get_by_asset_returns_none_when_not_found(db):
    asset = await _create_asset(db, "AAPL")
    repo = ThesisRepository(db)

    result = await repo.get_by_asset(asset.id)
    assert result is None


async def test_get_by_asset_finds_existing(db):
    asset = await _create_asset(db, "AAPL")
    repo = ThesisRepository(db)

    await repo.upsert(asset.id, "Strong moat and growing services revenue")

    result = await repo.get_by_asset(asset.id)
    assert result is not None
    assert result.asset_id == asset.id
    assert result.content == "Strong moat and growing services revenue"


async def test_upsert_creates_new_thesis(db):
    asset = await _create_asset(db, "AAPL")
    repo = ThesisRepository(db)

    thesis = await repo.upsert(asset.id, "Initial thesis content")

    assert thesis.id is not None
    assert thesis.asset_id == asset.id
    assert thesis.content == "Initial thesis content"


async def test_upsert_updates_existing_thesis(db):
    asset = await _create_asset(db, "AAPL")
    repo = ThesisRepository(db)

    original = await repo.upsert(asset.id, "Original content")
    original_id = original.id

    updated = await repo.upsert(asset.id, "Updated content")

    assert updated.id == original_id
    assert updated.content == "Updated content"

    fetched = await repo.get_by_asset(asset.id)
    assert fetched.content == "Updated content"
