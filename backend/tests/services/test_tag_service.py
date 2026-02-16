"""Unit tests for tag_service — CRUD, attach/detach M2M operations."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import Asset, Tag
from app.services.tag_service import (
    attach_tag,
    create_tag,
    delete_tag,
    detach_tag,
    update_tag,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")

# tag_service does: from app.routers.deps import get_asset
_PATCH_GET_ASSET = "app.routers.deps.get_asset"


def _make_tag(id: int = 1, name: str = "tech", color: str = "#3b82f6") -> Tag:
    tag = MagicMock(spec=Tag)
    tag.id = id
    tag.name = name
    tag.color = color
    return tag


def _make_asset(symbol: str = "AAPL") -> Asset:
    asset = MagicMock(spec=Asset)
    asset.symbol = symbol
    asset.tags = []
    return asset


@patch("app.services.tag_service.TagRepository")
async def test_create_tag_duplicate_raises_400(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.get_by_name = AsyncMock(return_value=_make_tag())

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await create_tag(db, name="tech", color="#3b82f6")
    assert exc_info.value.status_code == 400


@patch("app.services.tag_service.TagRepository")
async def test_update_tag_not_found_raises_404(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.get_by_id = AsyncMock(return_value=None)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await update_tag(db, tag_id=999, name="new", color=None)
    assert exc_info.value.status_code == 404


@patch("app.services.tag_service.TagRepository")
async def test_delete_tag_not_found_raises_404(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.get_by_id = AsyncMock(return_value=None)

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await delete_tag(db, tag_id=999)
    assert exc_info.value.status_code == 404


@patch("app.services.tag_service.AssetRepository")
@patch("app.services.tag_service.TagRepository")
async def test_attach_tag_to_asset(MockTagRepo, MockAssetRepo):
    db = AsyncMock()
    tag = _make_tag()
    asset = _make_asset()

    mock_tag_repo = MockTagRepo.return_value
    mock_tag_repo.get_by_id = AsyncMock(return_value=tag)
    mock_asset_repo = MockAssetRepo.return_value
    mock_asset_repo.save = AsyncMock(return_value=asset)

    with patch(_PATCH_GET_ASSET, new_callable=AsyncMock, return_value=asset):
        await attach_tag(db, symbol="AAPL", tag_id=1)

    assert tag in asset.tags


@patch("app.services.tag_service.AssetRepository")
@patch("app.services.tag_service.TagRepository")
async def test_attach_tag_idempotent(MockTagRepo, MockAssetRepo):
    db = AsyncMock()
    tag = _make_tag()
    asset = _make_asset()
    asset.tags = [tag]  # already attached

    mock_tag_repo = MockTagRepo.return_value
    mock_tag_repo.get_by_id = AsyncMock(return_value=tag)
    mock_asset_repo = MockAssetRepo.return_value
    mock_asset_repo.save = AsyncMock(return_value=asset)

    with patch(_PATCH_GET_ASSET, new_callable=AsyncMock, return_value=asset):
        await attach_tag(db, symbol="AAPL", tag_id=1)

    # Should not duplicate
    assert asset.tags.count(tag) == 1
    # save should NOT have been called since tag was already attached
    mock_asset_repo.save.assert_not_awaited()


@patch("app.services.tag_service.AssetRepository")
async def test_detach_tag_from_asset(MockAssetRepo):
    db = AsyncMock()
    tag1 = _make_tag(id=1, name="tech")
    tag2 = _make_tag(id=2, name="growth")
    asset = _make_asset()
    asset.tags = [tag1, tag2]

    mock_asset_repo = MockAssetRepo.return_value
    mock_asset_repo.save = AsyncMock(return_value=asset)

    with patch(_PATCH_GET_ASSET, new_callable=AsyncMock, return_value=asset):
        await detach_tag(db, symbol="AAPL", tag_id=1)

    assert len(asset.tags) == 1
    assert asset.tags[0].id == 2
