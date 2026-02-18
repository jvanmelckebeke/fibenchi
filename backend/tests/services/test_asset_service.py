"""Unit tests for asset_service — tests service logic with mocked repos."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import Asset, AssetType
from app.services.asset_service import create_asset, delete_asset, list_assets

pytestmark = pytest.mark.asyncio(loop_scope="function")


def _make_asset(**overrides) -> Asset:
    defaults = dict(
        id=1, symbol="AAPL", name="Apple Inc.",
        type=AssetType.STOCK, currency="USD",
    )
    defaults.update(overrides)
    asset = Asset(**defaults)
    return asset


def _make_default_group(assets=None):
    group = MagicMock()
    group.id = 1
    group.name = "Watchlist"
    group.is_default = True
    group.assets = list(assets or [])
    return group


@patch("app.services.asset_service.AssetRepository")
async def test_list_assets_delegates_to_repo(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    expected = [_make_asset()]
    mock_repo.list_in_any_group = AsyncMock(return_value=expected)

    result = await list_assets(db)

    MockRepo.assert_called_once_with(db)
    mock_repo.list_in_any_group.assert_awaited_once()
    assert result == expected


@patch("app.services.asset_service.GroupRepository")
@patch("app.services.asset_service.validate_symbol", new_callable=AsyncMock)
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_uppercase_symbol(MockAssetRepo, mock_validate, MockGroupRepo):
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.return_value = {"symbol": "AAPL", "name": "Apple Inc.", "type": "EQUITY", "currency": "USD"}
    new_asset = _make_asset()
    mock_repo.create = AsyncMock(return_value=new_asset)

    mock_group_repo = MockGroupRepo.return_value
    mock_group_repo.get_default = AsyncMock(return_value=_make_default_group())
    mock_group_repo.save = AsyncMock()

    result = await create_asset(db, symbol="aapl", name="Apple", asset_type=AssetType.STOCK, add_to_default_group=True)

    mock_repo.create.assert_awaited_once()
    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["symbol"] == "AAPL"


@patch("app.services.asset_service.GroupRepository")
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_existing_adds_to_default_group(MockAssetRepo, MockGroupRepo):
    """When an existing asset is not in the default group, adding with
    add_to_default_group=True adds it to the group."""
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    existing = _make_asset()
    mock_repo.find_by_symbol = AsyncMock(return_value=existing)

    default_group = _make_default_group(assets=[])  # asset not in group
    mock_group_repo = MockGroupRepo.return_value
    mock_group_repo.get_default = AsyncMock(return_value=default_group)
    mock_group_repo.save = AsyncMock()

    result = await create_asset(db, symbol="AAPL", name="Apple", asset_type=AssetType.STOCK, add_to_default_group=True)

    assert result is existing
    assert existing in default_group.assets
    mock_group_repo.save.assert_awaited_once()


@patch("app.services.asset_service.GroupRepository")
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_existing_already_in_group_returns_existing(MockAssetRepo, MockGroupRepo):
    """When an existing asset is already in the default group, just return it."""
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    existing = _make_asset()
    mock_repo.find_by_symbol = AsyncMock(return_value=existing)

    default_group = _make_default_group(assets=[existing])  # already in group
    mock_group_repo = MockGroupRepo.return_value
    mock_group_repo.get_default = AsyncMock(return_value=default_group)

    result = await create_asset(db, symbol="AAPL", name="Apple", asset_type=AssetType.STOCK, add_to_default_group=True)

    assert result is existing
    mock_group_repo.save.assert_not_called()


@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_existing_no_group_returns_existing(MockRepo):
    """When asset already exists and caller passes add_to_default_group=False (e.g. pseudo-ETF
    constituent picker), return the existing record without touching groups."""
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    existing = _make_asset()
    mock_repo.find_by_symbol = AsyncMock(return_value=existing)

    result = await create_asset(db, symbol="AAPL", name="Apple", asset_type=AssetType.STOCK, add_to_default_group=False)

    assert result is existing
    mock_repo.save.assert_not_called()
    mock_repo.create.assert_not_called()


@patch("app.services.asset_service.GroupRepository")
@patch("app.services.asset_service.validate_symbol", new_callable=AsyncMock)
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_auto_resolves_from_yahoo(MockAssetRepo, mock_validate, MockGroupRepo):
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)

    mock_validate.return_value = {"symbol": "NVDA", "name": "NVIDIA Corporation", "type": "EQUITY", "currency": "USD"}
    new_asset = _make_asset(symbol="NVDA", name="NVIDIA Corporation")
    mock_repo.create = AsyncMock(return_value=new_asset)

    mock_group_repo = MockGroupRepo.return_value
    mock_group_repo.get_default = AsyncMock(return_value=_make_default_group())
    mock_group_repo.save = AsyncMock()

    result = await create_asset(db, symbol="NVDA", name=None, asset_type=AssetType.STOCK, add_to_default_group=True)

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
        await create_asset(db, symbol="XXXX", name=None, asset_type=AssetType.STOCK, add_to_default_group=True)
    assert exc_info.value.status_code == 404


@patch("app.services.asset_service.GroupRepository")
@patch("app.services.asset_service.validate_symbol", new_callable=AsyncMock)
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_detects_etf_type(MockAssetRepo, mock_validate, MockGroupRepo):
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.return_value = {"symbol": "SPY", "name": "SPDR S&P 500", "type": "ETF", "currency": "USD"}
    new_asset = _make_asset(symbol="SPY", type=AssetType.ETF)
    mock_repo.create = AsyncMock(return_value=new_asset)

    mock_group_repo = MockGroupRepo.return_value
    mock_group_repo.get_default = AsyncMock(return_value=_make_default_group())
    mock_group_repo.save = AsyncMock()

    await create_asset(db, symbol="SPY", name=None, asset_type=AssetType.STOCK, add_to_default_group=True)

    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["type"] == AssetType.ETF


@patch("app.services.asset_service.GroupRepository")
@patch("app.services.asset_service.validate_symbol", new_callable=AsyncMock)
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_krw_currency_from_yahoo(MockAssetRepo, mock_validate, MockGroupRepo):
    """Regression test for #213: KRW-denominated assets should detect currency correctly."""
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.return_value = {
        "symbol": "006260.KS", "name": "LS Corp", "type": "EQUITY", "currency": "KRW",
    }
    new_asset = _make_asset(symbol="006260.KS", name="LS Corp", currency="KRW")
    mock_repo.create = AsyncMock(return_value=new_asset)

    mock_group_repo = MockGroupRepo.return_value
    mock_group_repo.get_default = AsyncMock(return_value=_make_default_group())
    mock_group_repo.save = AsyncMock()

    result = await create_asset(db, symbol="006260.KS", name=None, asset_type=AssetType.STOCK, add_to_default_group=True)

    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["currency"] == "KRW"


@patch("app.services.asset_service.GroupRepository")
@patch("app.services.asset_service.validate_symbol", new_callable=AsyncMock)
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_with_name_still_detects_currency(MockAssetRepo, mock_validate, MockGroupRepo):
    """When name is provided, currency should still be detected from Yahoo Finance."""
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.return_value = {
        "symbol": "006260.KS", "name": "LS Corp", "type": "EQUITY", "currency": "KRW",
    }
    new_asset = _make_asset(symbol="006260.KS", name="LS Corp", currency="KRW")
    mock_repo.create = AsyncMock(return_value=new_asset)

    mock_group_repo = MockGroupRepo.return_value
    mock_group_repo.get_default = AsyncMock(return_value=_make_default_group())
    mock_group_repo.save = AsyncMock()

    # Even with name provided, currency should come from Yahoo
    result = await create_asset(
        db, symbol="006260.KS", name="LS Corp", asset_type=AssetType.STOCK, add_to_default_group=True,
    )

    mock_validate.assert_awaited_once_with("006260.KS")
    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["currency"] == "KRW"
    assert call_kwargs["name"] == "LS Corp"  # user-provided name preserved


@patch("app.services.asset_service.GroupRepository")
@patch("app.services.asset_service.validate_symbol", new_callable=AsyncMock)
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_with_name_yahoo_fails_uses_suffix(MockAssetRepo, mock_validate, MockGroupRepo):
    """When name is provided but Yahoo fails, fall back to exchange suffix for currency."""
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.return_value = None  # Yahoo validation fails

    new_asset = _make_asset(symbol="006260.KS", name="LS Corp", currency="KRW")
    mock_repo.create = AsyncMock(return_value=new_asset)

    mock_group_repo = MockGroupRepo.return_value
    mock_group_repo.get_default = AsyncMock(return_value=_make_default_group())
    mock_group_repo.save = AsyncMock()

    result = await create_asset(
        db, symbol="006260.KS", name="LS Corp", asset_type=AssetType.STOCK, add_to_default_group=True,
    )

    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["currency"] == "KRW"  # from suffix fallback


@patch("app.services.asset_service.GroupRepository")
@patch("app.services.asset_service.AssetRepository")
async def test_delete_asset_removes_from_default_group(MockAssetRepo, MockGroupRepo):
    db = AsyncMock()
    asset = _make_asset()
    default_group = _make_default_group(assets=[asset])

    mock_group_repo = MockGroupRepo.return_value
    mock_group_repo.get_default = AsyncMock(return_value=default_group)
    mock_group_repo.save = AsyncMock()

    with patch("app.services.asset_service.get_asset", new_callable=AsyncMock, return_value=asset):
        await delete_asset(db, "AAPL")

    assert asset not in default_group.assets
    mock_group_repo.save.assert_awaited_once()
