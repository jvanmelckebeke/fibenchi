import pytest

from tests.helpers import create_asset_via_api


pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_create_group(client):
    resp = await client.post("/api/groups", json={"name": "Tech", "description": "Tech stocks"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Tech"
    assert resp.json()["assets"] == []


async def test_list_groups(client):
    await client.post("/api/groups", json={"name": "Tech"})
    await client.post("/api/groups", json={"name": "Energy"})

    resp = await client.get("/api/groups")
    assert len(resp.json()) == 2


async def test_update_group(client):
    resp = await client.post("/api/groups", json={"name": "Tech"})
    gid = resp.json()["id"]

    resp = await client.put(f"/api/groups/{gid}", json={"name": "Technology", "description": "Updated"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Technology"
    assert resp.json()["description"] == "Updated"


async def test_delete_group(client):
    resp = await client.post("/api/groups", json={"name": "Tech"})
    gid = resp.json()["id"]

    resp = await client.delete(f"/api/groups/{gid}")
    assert resp.status_code == 204


async def test_add_assets_to_group(client):
    a1 = await create_asset_via_api(client, "AAPL", "Apple")
    a2 = await create_asset_via_api(client, "MSFT", "Microsoft")

    resp = await client.post("/api/groups", json={"name": "Tech"})
    gid = resp.json()["id"]

    resp = await client.post(f"/api/groups/{gid}/assets", json={"asset_ids": [a1["id"], a2["id"]]})
    assert resp.status_code == 200
    assert len(resp.json()["assets"]) == 2


async def test_remove_asset_from_group(client):
    a1 = await create_asset_via_api(client, "AAPL", "Apple")
    a2 = await create_asset_via_api(client, "MSFT", "Microsoft")

    resp = await client.post("/api/groups", json={"name": "Tech"})
    gid = resp.json()["id"]

    await client.post(f"/api/groups/{gid}/assets", json={"asset_ids": [a1["id"], a2["id"]]})

    resp = await client.delete(f"/api/groups/{gid}/assets/{a1['id']}")
    assert resp.status_code == 200
    assert len(resp.json()["assets"]) == 1
    assert resp.json()["assets"][0]["symbol"] == "MSFT"


async def test_duplicate_group_name(client):
    await client.post("/api/groups", json={"name": "Tech"})
    resp = await client.post("/api/groups", json={"name": "Tech"})
    assert resp.status_code == 400
