"""Integration tests for the global thesis API — CRUD + membership."""

import pytest

from tests.helpers import create_asset_via_api

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_create_and_list_thesis(client):
    resp = await client.post("/api/theses", json={
        "name": "El Niño", "description": "advisories", "status": "live", "opened_at": "2026-03-01",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "El Niño"
    assert body["status"] == "live"
    assert body["opened_at"] == "2026-03-01"
    assert body["color"] == "#3b82f6"
    assert body["assets"] == []

    listing = await client.get("/api/theses")
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_create_defaults(client):
    resp = await client.post("/api/theses", json={"name": "Cables"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "watching"      # default lifecycle
    assert body["opened_at"]                 # defaulted to today
    assert body["color"] == "#3b82f6"        # default colour


async def test_duplicate_name_rejected(client):
    await client.post("/api/theses", json={"name": "Dupe"})
    resp = await client.post("/api/theses", json={"name": "Dupe"})
    assert resp.status_code == 400


async def test_invalid_color_rejected(client):
    resp = await client.post("/api/theses", json={"name": "BadColor", "color": "red"})
    assert resp.status_code == 422


async def test_invalid_status_rejected(client):
    resp = await client.post("/api/theses", json={"name": "BadStatus", "status": "bananas"})
    assert resp.status_code == 422


async def test_update_thesis(client):
    tid = (await client.post("/api/theses", json={"name": "Orig"})).json()["id"]
    resp = await client.put(f"/api/theses/{tid}", json={
        "name": "Renamed", "status": "played_out", "color": "#ff0000",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["status"] == "played_out"
    assert body["color"] == "#ff0000"


async def test_delete_thesis(client):
    tid = (await client.post("/api/theses", json={"name": "ToDelete"})).json()["id"]
    assert (await client.delete(f"/api/theses/{tid}")).status_code == 204
    assert (await client.get(f"/api/theses/{tid}")).status_code == 404


async def test_get_nonexistent_404(client):
    assert (await client.get("/api/theses/9999")).status_code == 404
    assert (await client.delete("/api/theses/9999/assets/1")).status_code == 404


async def test_add_and_remove_members(client):
    coco = await create_asset_via_api(client, "COCO.L", "Cocoa")
    ecaf = await create_asset_via_api(client, "ECAF.L", "Coffee")
    tid = (await client.post("/api/theses", json={"name": "El Niño"})).json()["id"]

    resp = await client.post(f"/api/theses/{tid}/assets", json={"asset_ids": [coco["id"], ecaf["id"]]})
    assert resp.status_code == 200
    assert {a["symbol"] for a in resp.json()["assets"]} == {"COCO.L", "ECAF.L"}

    # idempotent re-add does not duplicate
    resp = await client.post(f"/api/theses/{tid}/assets", json={"asset_ids": [coco["id"]]})
    assert len(resp.json()["assets"]) == 2

    # remove one
    resp = await client.delete(f"/api/theses/{tid}/assets/{coco['id']}")
    assert resp.status_code == 200
    assert {a["symbol"] for a in resp.json()["assets"]} == {"ECAF.L"}


async def test_asset_in_multiple_theses(client):
    coco = await create_asset_via_api(client, "COCO.L", "Cocoa")
    t1 = (await client.post("/api/theses", json={"name": "El Niño"})).json()["id"]
    t2 = (await client.post("/api/theses", json={"name": "Softs"})).json()["id"]

    await client.post(f"/api/theses/{t1}/assets", json={"asset_ids": [coco["id"]]})
    await client.post(f"/api/theses/{t2}/assets", json={"asset_ids": [coco["id"]]})

    for tid in (t1, t2):
        body = (await client.get(f"/api/theses/{tid}")).json()
        assert any(a["symbol"] == "COCO.L" for a in body["assets"])
