"""Tests for symbol sync service (provider execution and symbol_directory upserts)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.symbol_source import SymbolSource
from app.services.symbol_providers.base import SymbolEntry
from app.services.symbol_sync_service import (
    nullify_source_symbols,
    sync_all_enabled,
    sync_source,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


def _make_source(id: int = 1, name: str = "Test", provider_type: str = "euronext") -> SymbolSource:
    """Create a SymbolSource model instance."""
    source = SymbolSource(
        id=id, name=name, provider_type=provider_type,
        enabled=True, config={}, symbol_count=0,
    )
    return source


class TestSyncSource:
    async def test_raises_on_missing_source(self, db):
        with pytest.raises(ValueError, match="Symbol source 999 not found"):
            await sync_source(999, db)

    @patch("app.services.symbol_sync_service.get_provider")
    async def test_returns_zero_when_provider_returns_empty(self, mock_get_provider, db):
        source = _make_source()
        db.add(source)
        await db.commit()

        provider = MagicMock()
        provider.fetch_symbols = AsyncMock(return_value=[])
        mock_get_provider.return_value = provider

        count = await sync_source(source.id, db)
        assert count == 0

    @patch("app.services.symbol_sync_service.get_provider")
    async def test_syncs_symbols_and_updates_stats(self, mock_get_provider, db):
        source = _make_source()
        db.add(source)
        await db.commit()

        entries = [
            SymbolEntry(symbol="AAPL", name="Apple", exchange="NASDAQ", currency="USD", type="stock"),
            SymbolEntry(symbol="MSFT", name="Microsoft", exchange="NASDAQ", currency="USD", type="stock"),
        ]
        provider = MagicMock()
        provider.fetch_symbols = AsyncMock(return_value=entries)
        mock_get_provider.return_value = provider

        # Mock db.execute to avoid PG-specific ON CONFLICT syntax
        original_execute = db.execute
        async def _mock_execute(stmt, *args, **kwargs):
            from sqlalchemy.dialects.postgresql import Insert
            if isinstance(stmt, Insert):
                return MagicMock()
            return await original_execute(stmt, *args, **kwargs)

        with patch.object(db, "execute", side_effect=_mock_execute):
            count = await sync_source(source.id, db)

        assert count == 2

    @patch("app.services.symbol_sync_service.get_provider")
    async def test_updates_last_synced_at(self, mock_get_provider, db):
        source = _make_source()
        db.add(source)
        await db.commit()

        entries = [SymbolEntry(symbol="AAPL", name="Apple", exchange="NASDAQ", currency="USD", type="stock")]
        provider = MagicMock()
        provider.fetch_symbols = AsyncMock(return_value=entries)
        mock_get_provider.return_value = provider

        original_execute = db.execute
        async def _mock_execute(stmt, *args, **kwargs):
            from sqlalchemy.dialects.postgresql import Insert
            if isinstance(stmt, Insert):
                return MagicMock()
            return await original_execute(stmt, *args, **kwargs)

        with patch.object(db, "execute", side_effect=_mock_execute):
            await sync_source(source.id, db)

        await db.refresh(source)
        assert source.last_synced_at is not None
        assert source.symbol_count == 1


class TestSyncAllEnabled:
    @patch("app.services.symbol_sync_service.sync_source", new_callable=AsyncMock)
    async def test_syncs_all_enabled_sources(self, mock_sync_source, db):
        s1 = _make_source(id=None, name="Source1")
        s2 = _make_source(id=None, name="Source2")
        db.add_all([s1, s2])
        await db.commit()

        mock_sync_source.side_effect = lambda sid, session: 10

        counts = await sync_all_enabled(db)
        assert len(counts) == 2
        assert all(v == 10 for v in counts.values())

    @patch("app.services.symbol_sync_service.sync_source", new_callable=AsyncMock)
    async def test_disabled_sources_skipped(self, mock_sync_source, db):
        s1 = _make_source(id=None, name="Enabled")
        s2 = _make_source(id=None, name="Disabled")
        s2.enabled = False
        db.add_all([s1, s2])
        await db.commit()

        mock_sync_source.return_value = 5

        counts = await sync_all_enabled(db)
        assert len(counts) == 1

    @patch("app.services.symbol_sync_service.sync_source", new_callable=AsyncMock)
    async def test_failed_source_returns_zero(self, mock_sync_source, db):
        source = _make_source(id=None, name="Failing")
        db.add(source)
        await db.commit()

        mock_sync_source.side_effect = Exception("Provider error")

        counts = await sync_all_enabled(db)
        assert list(counts.values()) == [0]


class TestNullifySourceSymbols:
    async def test_nullifies_source_id(self, db):
        """Test that nullify works at the SQL level (uses SQLite for test)."""
        # Create a SymbolSource first since we need a valid FK
        source = _make_source(id=None)
        db.add(source)
        await db.commit()

        from app.models.symbol_directory import SymbolDirectory
        sym = SymbolDirectory(symbol="AAPL", name="Apple", source_id=source.id)
        db.add(sym)
        await db.commit()

        await nullify_source_symbols(source.id, db)
        await db.commit()

        await db.refresh(sym)
        assert sym.source_id is None
