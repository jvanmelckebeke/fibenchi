"""Unit tests for asset_service — tests service logic with mocked repos."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import Asset, AssetType
from app.services.asset_service import create_asset, delete_asset, list_assets

pytestmark = pytest.mark.asyncio(loop_scope="function")


def _make_asset(**overrides) -> Asset:
    defaults = dict(
        id=1, symbol="AAPL", name="Apple Inc.",
        type=AssetType.STOCK, currency="USD", watchlisted=True,
    )
    defaults.update(overrides)
    asset = Asset(**defaults)
    return asset


@patch("app.services.asset_service.AssetRepository")
async def test_list_assets_delegates_to_repo(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    expected = [_make_asset()]
    mock_repo.list_watchlisted = AsyncMock(return_value=expected)

    result = await list_assets(db)

    MockRepo.assert_called_once_with(db)
    mock_repo.list_watchlisted.assert_awaited_once()
    assert result == expected


@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_uppercase_symbol(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    new_asset = _make_asset()
    mock_repo.create = AsyncMock(return_value=new_asset)

    result = await create_asset(db, symbol="aapl", name="Apple", asset_type=AssetType.STOCK, watchlisted=True)

    mock_repo.create.assert_awaited_once()
    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["symbol"] == "AAPL"


@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_reactivates_unwatchlisted(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    existing = _make_asset(watchlisted=False)
    mock_repo.find_by_symbol = AsyncMock(return_value=existing)
    mock_repo.save = AsyncMock(return_value=existing)

    result = await create_asset(db, symbol="AAPL", name="Apple", asset_type=AssetType.STOCK, watchlisted=True)

    mock_repo.save.assert_awaited_once()
    assert existing.watchlisted is True


@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_duplicate_raises_400(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    existing = _make_asset(watchlisted=True)
    mock_repo.find_by_symbol = AsyncMock(return_value=existing)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await create_asset(db, symbol="AAPL", name="Apple", asset_type=AssetType.STOCK, watchlisted=True)
    assert exc_info.value.status_code == 400


@patch("app.services.asset_service.validate_symbol", new_callable=AsyncMock)
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_auto_resolves_from_yahoo(MockRepo, mock_validate):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)

    mock_validate.return_value = {"symbol": "NVDA", "name": "NVIDIA Corporation", "type": "EQUITY", "currency": "USD"}
    new_asset = _make_asset(symbol="NVDA", name="NVIDIA Corporation")
    mock_repo.create = AsyncMock(return_value=new_asset)

    result = await create_asset(db, symbol="NVDA", name=None, asset_type=AssetType.STOCK, watchlisted=True)

    mock_validate.assert_awaited_once_with("NVDA")
    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["name"] == "NVIDIA Corporation"
    assert call_kwargs["currency"] == "USD"


@patch("app.services.asset_service.validate_symbol", new_callable=AsyncMock)
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_yahoo_not_found_raises_404(MockRepo, mock_validate):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.return_value = None

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await create_asset(db, symbol="XXXX", name=None, asset_type=AssetType.STOCK, watchlisted=True)
    assert exc_info.value.status_code == 404


@patch("app.services.asset_service.validate_symbol", new_callable=AsyncMock)
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_detects_etf_type(MockRepo, mock_validate):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.return_value = {"symbol": "SPY", "name": "SPDR S&P 500", "type": "ETF", "currency": "USD"}
    new_asset = _make_asset(symbol="SPY", type=AssetType.ETF)
    mock_repo.create = AsyncMock(return_value=new_asset)

    await create_asset(db, symbol="SPY", name=None, asset_type=AssetType.STOCK, watchlisted=True)

    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["type"] == AssetType.ETF


@patch("app.services.asset_service.AssetRepository")
async def test_delete_asset_soft_deletes(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    asset = _make_asset(watchlisted=True)
    mock_repo.save = AsyncMock(return_value=asset)

    with patch("app.services.asset_service.get_asset", new_callable=AsyncMock, return_value=asset):
        await delete_asset(db, "AAPL")

    assert asset.watchlisted is False
    mock_repo.save.assert_awaited_once()
