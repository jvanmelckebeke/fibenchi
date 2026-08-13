"""Unit tests for asset_service — tests service logic with mocked repos."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain import UnitKind
from app.domain.provenance import FieldSource
from app.models import AssetType
from app.services.asset_service import create_asset, delete_asset, list_assets, update_asset
from tests.helpers import make_model_asset as _make_asset

# Patch ensure_currency globally for all tests in this module since
# asset_service.create_asset() now calls it and the mock DB can't support it
_ensure_patch = "app.services.asset_service.ensure_currency"

pytestmark = pytest.mark.asyncio(loop_scope="function")


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
    mock_repo.list_all = AsyncMock(return_value=expected)

    result = await list_assets(db)

    MockRepo.assert_called_once_with(db)
    mock_repo.list_all.assert_awaited_once()
    assert result == expected


@patch(_ensure_patch, new_callable=AsyncMock)
@patch("app.services.asset_service.yahoo_client")
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_uppercase_symbol(MockAssetRepo, mock_validate, _mock_ensure):
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.validate = AsyncMock(); mock_validate.validate.return_value = {"symbol": "AAPL", "name": "Apple Inc.", "type": "EQUITY", "currency": "USD", "currency_code": "USD"}
    new_asset = _make_asset()
    mock_repo.create = AsyncMock(return_value=new_asset)

    await create_asset(db, symbol="aapl", name="Apple", asset_type=AssetType.STOCK)

    mock_repo.create.assert_awaited_once()
    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["symbol"] == "AAPL"


@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_existing_returns_record_without_group_mutation(MockAssetRepo):
    """When the asset already exists, return it without touching any group.

    Regression: previously the existing-asset branch silently re-added the
    asset to the default Watchlist group, which clobbered intentional
    removals.
    """
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    existing = _make_asset()
    mock_repo.find_by_symbol = AsyncMock(return_value=existing)

    with patch("app.services.asset_service.GroupRepository") as MockGroupRepo:
        result = await create_asset(db, symbol="AAPL", name="Apple", asset_type=AssetType.STOCK)

    assert result is existing
    mock_repo.save.assert_not_called()
    mock_repo.create.assert_not_called()
    MockGroupRepo.assert_not_called()


@patch(_ensure_patch, new_callable=AsyncMock)
@patch("app.services.asset_service.yahoo_client")
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_does_not_touch_groups(MockAssetRepo, mock_validate, _mock_ensure):
    """A successful create should never load or mutate any group."""
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.validate = AsyncMock(); mock_validate.validate.return_value = {"symbol": "AAPL", "name": "Apple Inc.", "type": "EQUITY", "currency": "USD", "currency_code": "USD"}
    mock_repo.create = AsyncMock(return_value=_make_asset())

    with patch("app.services.asset_service.GroupRepository") as MockGroupRepo:
        await create_asset(db, symbol="AAPL", name="Apple", asset_type=AssetType.STOCK)

    MockGroupRepo.assert_not_called()


@patch(_ensure_patch, new_callable=AsyncMock)
@patch("app.services.asset_service.yahoo_client")
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_auto_resolves_from_yahoo(MockAssetRepo, mock_validate, _mock_ensure):
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)

    mock_validate.validate = AsyncMock(); mock_validate.validate.return_value = {"symbol": "NVDA", "name": "NVIDIA Corporation", "type": "EQUITY", "currency": "USD", "currency_code": "USD"}
    new_asset = _make_asset(symbol="NVDA", name="NVIDIA Corporation")
    mock_repo.create = AsyncMock(return_value=new_asset)

    await create_asset(db, symbol="NVDA", name=None, asset_type=AssetType.STOCK)

    mock_validate.validate.assert_awaited_once_with("NVDA")
    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["name"] == "NVIDIA Corporation"
    assert call_kwargs["currency"] == "USD"


@patch("app.services.asset_service.yahoo_client")
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_yahoo_not_found_raises_404(MockRepo, mock_validate):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.validate = AsyncMock(); mock_validate.validate.return_value = None

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await create_asset(db, symbol="XXXX", name=None, asset_type=AssetType.STOCK)
    assert exc_info.value.status_code == 404


@patch(_ensure_patch, new_callable=AsyncMock)
@patch("app.services.asset_service.yahoo_client")
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_detects_etf_type(MockAssetRepo, mock_validate, _mock_ensure):
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.validate = AsyncMock(); mock_validate.validate.return_value = {"symbol": "SPY", "name": "SPDR S&P 500", "type": "ETF", "currency": "USD", "currency_code": "USD"}
    new_asset = _make_asset(symbol="SPY", type=AssetType.ETF)
    mock_repo.create = AsyncMock(return_value=new_asset)

    # None = "you decide". An explicit STOCK here would be a user choice and
    # would win — see test_create_asset_explicit_type_beats_detection.
    await create_asset(db, symbol="SPY", name=None, asset_type=None)

    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["type"] == AssetType.ETF
    assert call_kwargs["type_source"] is FieldSource.AUTO


@patch(_ensure_patch, new_callable=AsyncMock)
@patch("app.services.asset_service.yahoo_client")
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_detects_index_type(MockAssetRepo, mock_validate, _mock_ensure):
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.validate = AsyncMock(); mock_validate.validate.return_value = {
        "symbol": "^TYX", "name": "Treasury Yield 30 Years", "type": "INDEX", "currency": "USD", "currency_code": "USD",
    }
    new_asset = _make_asset(symbol="^TYX", type=AssetType.INDEX)
    mock_repo.create = AsyncMock(return_value=new_asset)

    await create_asset(db, symbol="^TYX", name=None, asset_type=None)

    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["type"] == AssetType.INDEX
    # Shape also says how the number reads: a yield is a rate, not a price.
    assert call_kwargs["unit_kind"] is UnitKind.PERCENT
    assert call_kwargs["unit_source"] is FieldSource.AUTO


@patch(_ensure_patch, new_callable=AsyncMock)
@patch("app.services.asset_service.yahoo_client")
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_explicit_type_beats_detection(MockAssetRepo, mock_validate, _mock_ensure):
    """A supplied type is a human decision: detection yields to it, and the row
    records that a human made the call so suggestions stay quiet afterwards."""
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.validate = AsyncMock(); mock_validate.validate.return_value = {
        "symbol": "^TYX", "name": "Treasury Yield 30 Years", "type": "INDEX", "currency": "USD", "currency_code": "USD",
    }
    mock_repo.create = AsyncMock(return_value=_make_asset(symbol="^TYX", type=AssetType.STOCK))

    await create_asset(db, symbol="^TYX", name=None, asset_type=AssetType.STOCK)

    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["type"] == AssetType.STOCK
    assert call_kwargs["type_source"] is FieldSource.USER


@patch(_ensure_patch, new_callable=AsyncMock)
@patch("app.services.asset_service.yahoo_client")
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_krw_currency_from_yahoo(MockAssetRepo, mock_validate, _mock_ensure):
    """Regression test for #213: KRW-denominated assets should detect currency correctly."""
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.validate = AsyncMock(); mock_validate.validate.return_value = {
        "symbol": "006260.KS", "name": "LS Corp", "type": "EQUITY", "currency": "KRW", "currency_code": "KRW",
    }
    new_asset = _make_asset(symbol="006260.KS", name="LS Corp", currency="KRW")
    mock_repo.create = AsyncMock(return_value=new_asset)

    await create_asset(db, symbol="006260.KS", name=None, asset_type=AssetType.STOCK)

    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["currency"] == "KRW"


@patch(_ensure_patch, new_callable=AsyncMock)
@patch("app.services.asset_service.yahoo_client")
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_with_name_still_detects_currency(MockAssetRepo, mock_validate, _mock_ensure):
    """When name is provided, currency should still be detected from Yahoo Finance."""
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.validate = AsyncMock(); mock_validate.validate.return_value = {
        "symbol": "006260.KS", "name": "LS Corp", "type": "EQUITY", "currency": "KRW", "currency_code": "KRW",
    }
    new_asset = _make_asset(symbol="006260.KS", name="LS Corp", currency="KRW")
    mock_repo.create = AsyncMock(return_value=new_asset)

    await create_asset(db, symbol="006260.KS", name="LS Corp", asset_type=AssetType.STOCK)

    mock_validate.validate.assert_awaited_once_with("006260.KS")
    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["currency"] == "KRW"
    assert call_kwargs["name"] == "LS Corp"  # user-provided name preserved


@patch(_ensure_patch, new_callable=AsyncMock)
@patch("app.services.asset_service.yahoo_client")
@patch("app.services.asset_service.AssetRepository")
async def test_create_asset_with_name_yahoo_fails_uses_suffix(MockAssetRepo, mock_validate, _mock_ensure):
    """When name is provided but Yahoo fails, fall back to exchange suffix for currency."""
    db = AsyncMock()
    mock_repo = MockAssetRepo.return_value
    mock_repo.find_by_symbol = AsyncMock(return_value=None)
    mock_validate.validate = AsyncMock(); mock_validate.validate.return_value = None  # Yahoo validation fails

    new_asset = _make_asset(symbol="006260.KS", name="LS Corp", currency="KRW")
    mock_repo.create = AsyncMock(return_value=new_asset)

    await create_asset(db, symbol="006260.KS", name="LS Corp", asset_type=AssetType.STOCK)

    call_kwargs = mock_repo.create.call_args[1]
    assert call_kwargs["currency"] == "KRW"  # from suffix fallback


@patch("app.services.asset_service.AssetRepository")
async def test_update_asset_partial_fields_left_untouched(MockAssetRepo):
    """Only fields explicitly provided are mutated; the rest stay as they were."""
    db = AsyncMock()
    asset = _make_asset(name="Old Name", type=AssetType.STOCK, currency="USD")
    db.get = AsyncMock(return_value=asset)
    mock_repo = MockAssetRepo.return_value
    mock_repo.save = AsyncMock(return_value=asset)

    await update_asset(db, asset_id=1, asset_type=AssetType.INDEX)

    assert asset.type == AssetType.INDEX
    assert asset.name == "Old Name"
    assert asset.currency == "USD"
    mock_repo.save.assert_awaited_once_with(asset)


@patch(_ensure_patch, new_callable=AsyncMock)
@patch("app.services.asset_service.AssetRepository")
async def test_update_asset_currency_ensures_registration(MockAssetRepo, mock_ensure):
    """Updating the currency must register it via ensure_currency before assigning."""
    db = AsyncMock()
    asset = _make_asset(currency="USD")
    db.get = AsyncMock(return_value=asset)
    mock_repo = MockAssetRepo.return_value
    mock_repo.save = AsyncMock(return_value=asset)

    await update_asset(db, asset_id=1, currency="EUR")

    mock_ensure.assert_awaited_once_with(db, "EUR")
    assert asset.currency == "EUR"


async def test_update_asset_missing_raises_404():
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await update_asset(db, asset_id=999, name="x")
    assert exc_info.value.status_code == 404


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


@patch("app.services.asset_service.GroupRepository")
@patch("app.services.asset_service.AssetRepository")
async def test_delete_asset_raises_when_no_default_group(MockAssetRepo, MockGroupRepo):
    """Regression for #507: silently no-op'ing when no group has is_default=true
    is the worst-case UX. Surface it as 500 instead so the misconfig is loud."""
    from fastapi import HTTPException

    db = AsyncMock()
    asset = _make_asset()

    mock_group_repo = MockGroupRepo.return_value
    mock_group_repo.get_default = AsyncMock(return_value=None)
    mock_group_repo.save = AsyncMock()

    with patch("app.services.asset_service.get_asset", new_callable=AsyncMock, return_value=asset):
        with pytest.raises(HTTPException) as exc_info:
            await delete_asset(db, "AAPL")

    assert exc_info.value.status_code == 500
    mock_group_repo.save.assert_not_called()
