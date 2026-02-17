"""Unit tests for pseudo_etf_service — CRUD, constituents, thesis, annotations."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import Asset
from app.models.pseudo_etf import PseudoETF, PseudoEtfAnnotation, PseudoEtfThesis
from app.services.pseudo_etf_service import (
    add_constituents,
    create_annotation,
    create_pseudo_etf,
    delete_annotation,
    get_thesis,
    remove_constituent,
    upsert_thesis,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")

# Patch where the name is bound (top-level import in pseudo_etf_service)
_PATCH_GET_ETF = "app.services.pseudo_etf_service.get_pseudo_etf"


def _make_etf(**overrides) -> PseudoETF:
    from datetime import date, datetime
    defaults = dict(id=1, name="Quantum", base_date=date(2025, 1, 1), base_value=100.0)
    defaults.update(overrides)
    etf = MagicMock(spec=PseudoETF)
    for k, v in defaults.items():
        setattr(etf, k, v)
    etf.constituents = []
    etf.created_at = datetime(2025, 1, 1)
    return etf


def _make_asset(id: int, symbol: str) -> Asset:
    asset = MagicMock(spec=Asset)
    asset.id = id
    asset.symbol = symbol
    return asset


@patch("app.services.pseudo_etf_service.PseudoEtfRepository")
async def test_create_duplicate_name_raises_400(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.get_by_name = AsyncMock(return_value=_make_etf())

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await create_pseudo_etf(db, name="Quantum", base_date="2025-01-01")
    assert exc_info.value.status_code == 400


@patch("app.services.pseudo_etf_service.AssetRepository")
@patch("app.services.pseudo_etf_service.PseudoEtfRepository")
async def test_add_constituents_skips_duplicates(MockPetfRepo, MockAssetRepo):
    db = AsyncMock()
    etf = _make_etf()
    existing_asset = _make_asset(1, "AAPL")
    new_asset = _make_asset(2, "MSFT")
    etf.constituents = [existing_asset]

    mock_petf_repo = MockPetfRepo.return_value
    mock_petf_repo.save = AsyncMock(return_value=etf)
    mock_asset_repo = MockAssetRepo.return_value
    mock_asset_repo.get_by_ids = AsyncMock(return_value=[existing_asset, new_asset])

    with patch(_PATCH_GET_ETF, new_callable=AsyncMock, return_value=etf):
        await add_constituents(db, etf_id=1, asset_ids=[1, 2])

    assert new_asset in etf.constituents
    mock_petf_repo.save.assert_awaited_once()


@patch("app.services.pseudo_etf_service.PseudoEtfRepository")
async def test_remove_constituent_not_found_raises_404(MockRepo):
    db = AsyncMock()
    etf = _make_etf()
    etf.constituents = []

    with patch(_PATCH_GET_ETF, new_callable=AsyncMock, return_value=etf):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await remove_constituent(db, etf_id=1, asset_id=999)
        assert exc_info.value.status_code == 404


@patch("app.services.pseudo_etf_service.PseudoEtfRepository")
async def test_get_thesis_empty_returns_default(MockRepo):
    db = AsyncMock()
    etf = _make_etf()

    mock_repo = MockRepo.return_value
    mock_repo.get_thesis = AsyncMock(return_value=None)

    with patch(_PATCH_GET_ETF, new_callable=AsyncMock, return_value=etf):
        result = await get_thesis(db, etf_id=1)

    assert result.content == ""


@patch("app.services.pseudo_etf_service.PseudoEtfRepository")
async def test_upsert_thesis_creates_new(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    thesis = MagicMock(spec=PseudoEtfThesis)
    thesis.content = "New thesis"
    mock_repo.upsert_thesis = AsyncMock(return_value=thesis)

    with patch(_PATCH_GET_ETF, new_callable=AsyncMock):
        result = await upsert_thesis(db, etf_id=1, content="New thesis")

    mock_repo.upsert_thesis.assert_awaited_once_with(1, "New thesis")
    assert result.content == "New thesis"


@patch("app.services.pseudo_etf_service.PseudoEtfRepository")
async def test_create_annotation(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    annotation = MagicMock(spec=PseudoEtfAnnotation)
    mock_repo.create_annotation = AsyncMock(return_value=annotation)

    with patch(_PATCH_GET_ETF, new_callable=AsyncMock):
        await create_annotation(db, etf_id=1, date="2025-01-15", title="Event")

    mock_repo.create_annotation.assert_awaited_once()


@patch("app.services.pseudo_etf_service.PseudoEtfRepository")
async def test_delete_annotation_not_found_raises_404(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.get_annotation = AsyncMock(return_value=None)

    with patch(_PATCH_GET_ETF, new_callable=AsyncMock):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await delete_annotation(db, etf_id=1, annotation_id=999)
        assert exc_info.value.status_code == 404
