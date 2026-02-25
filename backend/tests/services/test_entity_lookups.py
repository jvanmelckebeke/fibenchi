"""Tests for entity lookup helpers (find_asset, get_asset, get_group, get_pseudo_etf)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.entity_lookups import find_asset, get_asset, get_group, get_pseudo_etf

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestFindAsset:
    @patch("app.services.entity_lookups.AssetRepository")
    async def test_returns_asset_when_found(self, mock_repo_cls, db):
        asset = MagicMock()
        asset.symbol = "AAPL"
        mock_repo_cls.return_value.find_by_symbol = AsyncMock(return_value=asset)

        result = await find_asset("AAPL", db)
        assert result.symbol == "AAPL"

    @patch("app.services.entity_lookups.AssetRepository")
    async def test_returns_none_when_not_found(self, mock_repo_cls, db):
        mock_repo_cls.return_value.find_by_symbol = AsyncMock(return_value=None)

        result = await find_asset("UNKNOWN", db)
        assert result is None


class TestGetAsset:
    @patch("app.services.entity_lookups.AssetRepository")
    async def test_returns_asset_when_found(self, mock_repo_cls, db):
        asset = MagicMock()
        asset.symbol = "AAPL"
        mock_repo_cls.return_value.find_by_symbol = AsyncMock(return_value=asset)

        result = await get_asset("AAPL", db)
        assert result.symbol == "AAPL"

    @patch("app.services.entity_lookups.AssetRepository")
    async def test_raises_404_when_not_found(self, mock_repo_cls, db):
        mock_repo_cls.return_value.find_by_symbol = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_asset("UNKNOWN", db)
        assert exc_info.value.status_code == 404
        assert "UNKNOWN" in str(exc_info.value.detail)


class TestGetPseudoEtf:
    @patch("app.services.entity_lookups.PseudoEtfRepository")
    async def test_returns_etf_when_found(self, mock_repo_cls, db):
        etf = MagicMock()
        etf.id = 1
        mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=etf)

        result = await get_pseudo_etf(1, db)
        assert result.id == 1

    @patch("app.services.entity_lookups.PseudoEtfRepository")
    async def test_raises_404_when_not_found(self, mock_repo_cls, db):
        mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_pseudo_etf(999, db)
        assert exc_info.value.status_code == 404
        assert "Pseudo-ETF" in str(exc_info.value.detail)


class TestGetGroup:
    @patch("app.services.entity_lookups.GroupRepository")
    async def test_returns_group_when_found(self, mock_repo_cls, db):
        group = MagicMock()
        group.id = 1
        group.name = "Tech"
        mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=group)

        result = await get_group(1, db)
        assert result.name == "Tech"

    @patch("app.services.entity_lookups.GroupRepository")
    async def test_raises_404_when_not_found(self, mock_repo_cls, db):
        mock_repo_cls.return_value.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_group(999, db)
        assert exc_info.value.status_code == 404
        assert "Group" in str(exc_info.value.detail)
