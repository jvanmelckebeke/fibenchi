"""Reset the dev database to a fixed set of groups/assets/tags.

Usage (from inside the backend container):
    python scripts/seed_dev_db.py            # structure only (fast)
    python scripts/seed_dev_db.py --prices   # also fetch 1y of prices via Yahoo

Reads ``scripts/dev_seed_groups.json`` if present (gitignored — your own
portfolio snapshot from ``GET /api/groups``), otherwise falls back to
``scripts/dev_seed_groups.example.json`` (a small public-ticker sample
checked into the repo). Wipes existing groups/assets/tags (including
price history, theses, annotations) and re-seeds with the original IDs
preserved.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Allow running as `python scripts/seed_dev_db.py` from the /app dir
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, text  # noqa: E402

from app.database import async_session  # noqa: E402
from app.models import Asset, AssetType, Group, Tag  # noqa: E402
from app.models.annotation import Annotation  # noqa: E402
from app.models.group import group_assets  # noqa: E402
from app.models.price import PriceHistory  # noqa: E402
from app.models.tag import tag_assets  # noqa: E402
from app.models.thesis import Thesis  # noqa: E402


_SCRIPTS_DIR = Path(__file__).parent
PERSONAL_SEED = _SCRIPTS_DIR / "dev_seed_groups.json"
EXAMPLE_SEED = _SCRIPTS_DIR / "dev_seed_groups.example.json"


def _resolve_seed_path() -> Path:
    if PERSONAL_SEED.exists():
        return PERSONAL_SEED
    if EXAMPLE_SEED.exists():
        return EXAMPLE_SEED
    raise FileNotFoundError(
        f"No seed file found. Expected {PERSONAL_SEED} or {EXAMPLE_SEED}."
    )

# Postgres sequences to reset after explicit-ID inserts so subsequent
# auto-increment inserts don't collide.
SEQUENCES = [
    ("groups_id_seq", "groups"),
    ("assets_id_seq", "assets"),
    ("tags_id_seq", "tags"),
]


async def _wipe(db) -> None:
    """Drop everything that depends on assets/groups/tags."""
    await db.execute(delete(Annotation))
    await db.execute(delete(Thesis))
    await db.execute(delete(PriceHistory))
    await db.execute(delete(group_assets))
    await db.execute(delete(tag_assets))
    await db.execute(delete(Group))
    await db.execute(delete(Asset))
    await db.execute(delete(Tag))
    await db.commit()


async def _seed(db, data: list[dict]) -> tuple[int, int, int]:
    # Collect unique tags + assets across all groups (assets may appear in
    # multiple groups; the JSON repeats them).
    tags_by_id: dict[int, dict] = {}
    assets_by_id: dict[int, dict] = {}
    asset_to_tag_ids: dict[int, set[int]] = {}

    for group in data:
        for asset in group["assets"]:
            assets_by_id[asset["id"]] = asset
            asset_to_tag_ids.setdefault(asset["id"], set())
            for tag in asset["tags"]:
                tags_by_id[tag["id"]] = tag
                asset_to_tag_ids[asset["id"]].add(tag["id"])

    for tag in tags_by_id.values():
        db.add(Tag(id=tag["id"], name=tag["name"], color=tag["color"]))

    for asset in assets_by_id.values():
        db.add(Asset(
            id=asset["id"],
            symbol=asset["symbol"],
            name=asset["name"],
            type=AssetType(asset["type"]),
            currency=asset["currency"],
            created_at=datetime.fromisoformat(asset["created_at"]),
        ))

    await db.flush()

    for asset_id, tag_ids in asset_to_tag_ids.items():
        for tag_id in tag_ids:
            await db.execute(
                tag_assets.insert().values(asset_id=asset_id, tag_id=tag_id)
            )

    for group in data:
        db.add(Group(
            id=group["id"],
            name=group["name"],
            description=group["description"],
            icon=group["icon"],
            is_default=group["is_default"],
            position=group["position"],
            created_at=datetime.fromisoformat(group["created_at"]),
        ))
    await db.flush()

    for group in data:
        for asset in group["assets"]:
            await db.execute(
                group_assets.insert().values(group_id=group["id"], asset_id=asset["id"])
            )

    await db.commit()

    # Bump sequences past the highest manually-assigned ID
    for seq, table in SEQUENCES:
        await db.execute(text(
            f"SELECT setval('{seq}', (SELECT COALESCE(MAX(id), 1) FROM {table}))"
        ))
    await db.commit()

    return len(data), len(assets_by_id), len(tags_by_id)


async def _sync_prices() -> None:
    from app.services.price_providers import init_price_provider
    from app.services.price_sync import sync_all_prices

    init_price_provider()
    async with async_session() as db:
        counts = await sync_all_prices(db)
        total = sum(counts.values())
        print(f"Synced prices: {len(counts)} assets, {total} price points")


async def main(with_prices: bool) -> None:
    seed_path = _resolve_seed_path()
    print(f"Seeding from {seed_path.name}")
    data = json.loads(seed_path.read_text())

    async with async_session() as db:
        await _wipe(db)
        n_groups, n_assets, n_tags = await _seed(db, data)

    print(f"Seeded {n_groups} groups, {n_assets} assets, {n_tags} tags")

    if with_prices:
        print("Fetching prices from Yahoo (this may take a minute)...")
        await _sync_prices()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset the dev database to a fixed set of groups/assets/tags.")
    parser.add_argument(
        "--prices", action="store_true",
        help="Also fetch 1 year of prices via Yahoo (slow, network-dependent)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.prices))
