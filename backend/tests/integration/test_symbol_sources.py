"""Integration tests for the symbol sources router."""

from unittest.mock import AsyncMock, patch

import pytest

from app.models.symbol_source import SymbolSource
from app.models.symbol_directory import SymbolDirectory
from tests.conftest import TestSession

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _create_source(client, name: str = "Test Source", provider_type: str = "euronext") -> dict:
    resp = await client.post("/api/symbol-sources", json={
        "name": name,
        "provider_type": provider_type,
        "config": {"markets": ["amsterdam"]},
    })
    assert resp.status_code == 201
    return resp.json()


class TestListSources:
    async def test_empty_list(self, client):
        resp = await client.get("/api/symbol-sources")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_created_sources(self, client):
        await _create_source(client, name="Euronext")
        resp = await client.get("/api/symbol-sources")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Euronext"
        assert data[0]["provider_type"] == "euronext"


class TestListProviders:
    async def test_returns_available_providers(self, client):
        resp = await client.get("/api/symbol-sources/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "euronext" in data
        assert "xetra" in data
        assert "key" in data["euronext"]
        assert "markets" in data["euronext"]


class TestCreateSource:
    async def test_creates_source(self, client):
        data = await _create_source(client)
        assert data["name"] == "Test Source"
        assert data["provider_type"] == "euronext"
        assert data["enabled"] is True
        assert data["symbol_count"] == 0

    async def test_invalid_provider_type(self, client):
        resp = await client.post("/api/symbol-sources", json={
            "name": "Bad", "provider_type": "nonexistent", "config": {},
        })
        assert resp.status_code == 400
        assert "Unknown provider" in resp.json()["detail"]


class TestUpdateSource:
    async def test_update_name(self, client):
        source = await _create_source(client)
        resp = await client.patch(f"/api/symbol-sources/{source['id']}", json={"name": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    async def test_disable_source(self, client):
        source = await _create_source(client)
        resp = await client.patch(f"/api/symbol-sources/{source['id']}", json={"enabled": False})
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    async def test_update_config(self, client):
        source = await _create_source(client)
        new_config = {"markets": ["amsterdam", "brussels"]}
        resp = await client.patch(f"/api/symbol-sources/{source['id']}", json={"config": new_config})
        assert resp.status_code == 200
        assert resp.json()["config"] == new_config

    async def test_404_for_nonexistent(self, client):
        resp = await client.patch("/api/symbol-sources/999", json={"name": "X"})
        assert resp.status_code == 404


class TestTriggerSync:
    async def test_trigger_sync(self, client):
        source = await _create_source(client)
        resp = await client.post(f"/api/symbol-sources/{source['id']}/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_id"] == source["id"]
        assert data["message"] == "Sync started in background"

    async def test_404_for_nonexistent(self, client):
        resp = await client.post("/api/symbol-sources/999/sync")
        assert resp.status_code == 404


class TestDeleteSource:
    async def test_deletes_source(self, client):
        source = await _create_source(client)
        resp = await client.delete(f"/api/symbol-sources/{source['id']}")
        assert resp.status_code == 204

        # Verify it's gone
        list_resp = await client.get("/api/symbol-sources")
        assert list_resp.json() == []

    async def test_404_for_nonexistent(self, client):
        resp = await client.delete("/api/symbol-sources/999")
        assert resp.status_code == 404

    async def test_nullifies_symbol_directory_refs(self, client, db):
        """Deleting a source should set source_id to NULL on related symbols."""
        source = await _create_source(client)
        source_id = source["id"]

        # Seed a symbol directory entry linked to this source
        sym = SymbolDirectory(symbol="TEST.XX", name="Test Corp", source_id=source_id)
        db.add(sym)
        await db.commit()

        await client.delete(f"/api/symbol-sources/{source_id}")

        await db.refresh(sym)
        assert sym.source_id is None
