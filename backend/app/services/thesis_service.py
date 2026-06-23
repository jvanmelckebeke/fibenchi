"""Global Thesis CRUD + membership business logic.

A thesis is a cross-cutting basket of tickers tracked under one hypothesis.
Membership is many-to-many (an asset can be in several theses). Every thesis
returned carries ``aggregate_pct`` — the equal-weight mean member return since
``opened_at`` (see ``compute/thesis.py``).
"""

from collections import defaultdict
from datetime import date

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thesis import Thesis, ThesisStatus
from app.repositories.asset_repo import AssetRepository
from app.repositories.price_repo import PriceRepository
from app.repositories.thesis_repo import ThesisRepository
from app.services.compute.thesis import aggregate_return_pct, aggregate_return_series
from app.services.entity_lookups import get_thesis
from app.utils import TTLCache

# Batch per-thesis performance curves (for the all-theses sparklines). Keyed by a
# signature of every thesis (id, open date, member set) + latest price date, so it
# auto-invalidates on price sync, membership changes, or an open-date edit.
_thesis_perf_cache: TTLCache = TTLCache(default_ttl=600)


async def _compute_aggregate(db: AsyncSession, thesis: Thesis) -> float | None:
    """Equal-weight mean member return since ``opened_at`` (percent).

    Loads each member's closes on/after the open date and delegates the maths
    to the pure ``aggregate_return_pct``. Members are measured from the thesis
    open date regardless of when they were added — a late addition counts as if
    it had been there from the start.
    """
    asset_ids = [a.id for a in thesis.assets]
    if not asset_ids:
        return None
    rows = await PriceRepository(db).list_by_assets_since(asset_ids, thesis.opened_at)
    by_asset: dict[int, list[float]] = defaultdict(list)
    for p in rows:
        by_asset[p.asset_id].append(p.close)
    return aggregate_return_pct([by_asset.get(aid, []) for aid in asset_ids])


async def _attach_aggregate(db: AsyncSession, thesis: Thesis) -> Thesis:
    # transient attribute read by ThesisResponse.from_attributes (not persisted)
    thesis.aggregate_pct = await _compute_aggregate(db, thesis)  # type: ignore[attr-defined]
    return thesis


async def list_theses(db: AsyncSession):
    theses = await ThesisRepository(db).list_all()
    for thesis in theses:
        await _attach_aggregate(db, thesis)
    return theses


async def list_thesis_performance(db: AsyncSession) -> list[dict]:
    """Equal-weight performance curve per thesis, for the all-theses sparklines.

    Returns ``[{"thesis_id": int, "points": [{"date", "pct"}, ...]}, ...]``. Loads
    every member's prices in a single query (anchored to the earliest open date),
    then slices per thesis. Cached — see ``_thesis_perf_cache``.
    """
    theses = await ThesisRepository(db).list_all()
    if not theses:
        return []

    all_ids = sorted({a.id for t in theses for a in t.assets})
    if not all_ids:
        return [{"thesis_id": t.id, "points": []} for t in theses]

    price_repo = PriceRepository(db)
    latest_date = await price_repo.get_latest_date(all_ids)
    cache_key = (
        frozenset(
            (t.id, t.opened_at.isoformat(), frozenset(a.id for a in t.assets))
            for t in theses
        ),
        latest_date,
    )
    cached = _thesis_perf_cache.get_value(cache_key)
    if cached is not None:
        return cached

    rows = await price_repo.list_by_assets_since(all_ids, min(t.opened_at for t in theses))
    by_asset: dict[int, list[tuple[date, float]]] = defaultdict(list)
    for p in rows:  # rows arrive ordered by (asset_id, date) → ascending per asset
        by_asset[p.asset_id].append((p.date, p.close))

    out = [
        {
            "thesis_id": t.id,
            "points": aggregate_return_series(
                [
                    [(d, c) for d, c in by_asset.get(a.id, []) if d >= t.opened_at]
                    for a in t.assets
                ]
            ),
        }
        for t in theses
    ]
    _thesis_perf_cache.set_value(cache_key, out)
    return out


async def get_thesis_detail(db: AsyncSession, thesis_id: int):
    return await _attach_aggregate(db, await get_thesis(thesis_id, db))


async def create_thesis(
    db: AsyncSession,
    name: str,
    color: str,
    icon: str | None,
    description: str | None,
    status: ThesisStatus,
    opened_at: date | None,
):
    repo = ThesisRepository(db)
    if await repo.get_by_name(name):
        raise HTTPException(400, f"Thesis '{name}' already exists")
    thesis = await repo.create(
        name=name,
        color=color,
        icon=icon,
        description=description,
        status=status.value,
        opened_at=opened_at or date.today(),
    )
    return await _attach_aggregate(db, thesis)


async def update_thesis(db: AsyncSession, thesis_id: int, data: dict):
    thesis = await get_thesis(thesis_id, db)
    repo = ThesisRepository(db)
    name = data.get("name")
    if name is not None and name != thesis.name:
        if await repo.get_by_name(name):
            raise HTTPException(400, f"Thesis '{name}' already exists")
        thesis.name = name
    if "color" in data:
        thesis.color = data["color"]
    if "icon" in data:
        thesis.icon = data["icon"]
    if "description" in data:
        thesis.description = data["description"]
    if data.get("status") is not None:
        status = data["status"]
        thesis.status = status.value if isinstance(status, ThesisStatus) else status
    if data.get("opened_at") is not None:
        thesis.opened_at = data["opened_at"]
    saved = await repo.save(thesis)
    return await _attach_aggregate(db, saved)


async def delete_thesis(db: AsyncSession, thesis_id: int):
    thesis = await get_thesis(thesis_id, db)
    await ThesisRepository(db).delete(thesis)


async def add_assets(db: AsyncSession, thesis_id: int, asset_ids: list[int]):
    thesis = await get_thesis(thesis_id, db)
    assets = await AssetRepository(db).get_by_ids(asset_ids)
    missing = set(asset_ids) - {a.id for a in assets}
    if missing:
        raise HTTPException(404, f"Asset(s) not found: {sorted(missing)}")
    existing_ids = {a.id for a in thesis.assets}
    for asset in assets:
        if asset.id not in existing_ids:
            thesis.assets.append(asset)
    saved = await ThesisRepository(db).save(thesis)
    return await _attach_aggregate(db, saved)


async def remove_asset(db: AsyncSession, thesis_id: int, asset_id: int):
    thesis = await get_thesis(thesis_id, db)
    thesis.assets = [a for a in thesis.assets if a.id != asset_id]
    saved = await ThesisRepository(db).save(thesis)
    return await _attach_aggregate(db, saved)
