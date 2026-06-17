from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset
from app.models.group import group_assets


class AssetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_symbol(self, symbol: str) -> Asset | None:
        result = await self.db.execute(
            select(Asset).where(Asset.symbol == symbol.upper())
        )
        return result.scalar_one_or_none()

    async def list_in_any_group(self) -> list[Asset]:
        """Return all assets that belong to at least one group, ordered by symbol."""
        result = await self.db.execute(
            select(Asset)
            .where(exists().where(group_assets.c.asset_id == Asset.id))
            .order_by(Asset.symbol)
        )
        return list(result.scalars().all())

    async def list_in_any_group_ids(self) -> list[int]:
        """Return IDs of all assets that belong to at least one group."""
        result = await self.db.execute(
            select(Asset.id)
            .where(exists().where(group_assets.c.asset_id == Asset.id))
        )
        return list(result.scalars().all())

    async def list_in_any_group_id_symbol_pairs(self) -> list[tuple[int, str]]:
        """Return (id, symbol) pairs for all assets in at least one group."""
        result = await self.db.execute(
            select(Asset.id, Asset.symbol)
            .where(exists().where(group_assets.c.asset_id == Asset.id))
        )
        return list(result.all())

    async def list_in_any_group_symbols(self) -> list[str]:
        """Return symbols for all assets in at least one group."""
        result = await self.db.execute(
            select(Asset.symbol)
            .where(exists().where(group_assets.c.asset_id == Asset.id))
        )
        return [row[0] for row in result.all()]

    async def list_in_group_id_symbol_pairs(self, group_id: int) -> list[tuple[int, str]]:
        """Return (id, symbol) pairs for assets in a specific group."""
        result = await self.db.execute(
            select(Asset.id, Asset.symbol)
            .join(group_assets, Asset.id == group_assets.c.asset_id)
            .where(group_assets.c.group_id == group_id)
        )
        return list(result.all())

    async def list_id_symbol_pairs_by_symbols(self, symbols: list[str]) -> list[tuple[int, str]]:
        """Return (id, symbol) pairs for the given symbols (tracked assets only).

        Unknown symbols are silently omitted. Symbols are matched case-insensitively
        (stored upper-cased, mirroring ``find_by_symbol``).
        """
        if not symbols:
            return []
        upper = [s.upper() for s in symbols]
        result = await self.db.execute(
            select(Asset.id, Asset.symbol).where(Asset.symbol.in_(upper))
        )
        return list(result.all())

    async def list_all(self) -> list[Asset]:
        result = await self.db.execute(select(Asset).order_by(Asset.symbol))
        return list(result.scalars().all())

    async def get_by_ids(self, ids: list[int]) -> list[Asset]:
        if not ids:
            return []
        result = await self.db.execute(select(Asset).where(Asset.id.in_(ids)))
        return list(result.scalars().all())

    async def create(self, **kwargs) -> Asset:
        asset = Asset(**kwargs)
        self.db.add(asset)
        await self.db.commit()
        await self.db.refresh(asset)
        return asset

    async def save(self, asset: Asset) -> Asset:
        await self.db.commit()
        await self.db.refresh(asset)
        return asset
