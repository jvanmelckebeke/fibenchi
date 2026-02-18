"""Tests for AssetRepository — query methods against real SQLite DB."""

import pytest

from app.models import Asset, AssetType, Group
from app.models.group import group_assets
from app.repositories.asset_repo import AssetRepository
from app.repositories.group_repo import GroupRepository

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _create_asset(db, symbol: str, **kwargs) -> Asset:
    defaults = dict(name=f"{symbol} Inc.", type=AssetType.STOCK, currency="USD")
    defaults.update(kwargs)
    asset = Asset(symbol=symbol, **defaults)
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


async def _add_to_default_group(db, asset: Asset) -> None:
    """Add an asset to the default group."""
    default_group = await GroupRepository(db).get_default()
    default_group.assets.append(asset)
    await db.commit()


async def test_find_by_symbol_existing(db):
    await _create_asset(db, "AAPL")
    repo = AssetRepository(db)
    result = await repo.find_by_symbol("AAPL")
    assert result is not None
    assert result.symbol == "AAPL"


async def test_find_by_symbol_not_found(db):
    repo = AssetRepository(db)
    result = await repo.find_by_symbol("NOPE")
    assert result is None


async def test_find_by_symbol_case_insensitive(db):
    await _create_asset(db, "AAPL")
    repo = AssetRepository(db)
    result = await repo.find_by_symbol("aapl")
    assert result is not None
    assert result.symbol == "AAPL"


async def test_list_in_any_group_filters(db):
    aapl = await _create_asset(db, "AAPL")
    await _create_asset(db, "MSFT")  # not in any group
    await _add_to_default_group(db, aapl)

    repo = AssetRepository(db)
    result = await repo.list_in_any_group()
    symbols = [a.symbol for a in result]
    assert "AAPL" in symbols
    assert "MSFT" not in symbols


async def test_list_in_any_group_orders_by_symbol(db):
    msft = await _create_asset(db, "MSFT")
    aapl = await _create_asset(db, "AAPL")
    await _add_to_default_group(db, msft)
    await _add_to_default_group(db, aapl)

    repo = AssetRepository(db)
    result = await repo.list_in_any_group()
    assert [a.symbol for a in result] == ["AAPL", "MSFT"]


async def test_list_in_any_group_ids(db):
    a1 = await _create_asset(db, "AAPL")
    a2 = await _create_asset(db, "MSFT")  # not in any group
    await _add_to_default_group(db, a1)

    repo = AssetRepository(db)
    ids = await repo.list_in_any_group_ids()
    assert a1.id in ids
    assert a2.id not in ids


async def test_list_in_any_group_symbols(db):
    aapl = await _create_asset(db, "AAPL")
    await _create_asset(db, "MSFT")  # not in any group
    await _add_to_default_group(db, aapl)

    repo = AssetRepository(db)
    symbols = await repo.list_in_any_group_symbols()
    assert "AAPL" in symbols
    assert "MSFT" not in symbols


async def test_list_in_group_id_symbol_pairs(db):
    aapl = await _create_asset(db, "AAPL")
    msft = await _create_asset(db, "MSFT")
    await _add_to_default_group(db, aapl)

    default_group = await GroupRepository(db).get_default()
    repo = AssetRepository(db)
    pairs = await repo.list_in_group_id_symbol_pairs(default_group.id)
    symbols = [s for _, s in pairs]
    assert "AAPL" in symbols
    assert "MSFT" not in symbols


async def test_list_all_includes_ungrouped(db):
    aapl = await _create_asset(db, "AAPL")
    await _create_asset(db, "MSFT")  # not in any group
    await _add_to_default_group(db, aapl)

    repo = AssetRepository(db)
    result = await repo.list_all()
    assert len(result) == 2


async def test_create_and_save(db):
    repo = AssetRepository(db)
    asset = await repo.create(
        symbol="AAPL", name="Apple", type=AssetType.STOCK, currency="USD",
    )
    assert asset.id is not None
    assert asset.symbol == "AAPL"

    # Verify save (update)
    asset.name = "Apple Inc."
    saved = await repo.save(asset)
    assert saved.name == "Apple Inc."


async def test_get_by_ids(db):
    a1 = await _create_asset(db, "AAPL")
    a2 = await _create_asset(db, "MSFT")
    a3 = await _create_asset(db, "GOOGL")
    repo = AssetRepository(db)

    result = await repo.get_by_ids([a1.id, a3.id])
    symbols = {a.symbol for a in result}
    assert symbols == {"AAPL", "GOOGL"}


async def test_get_by_ids_empty(db):
    repo = AssetRepository(db)
    result = await repo.get_by_ids([])
    assert result == []
