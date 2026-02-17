from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Asset


class AssetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_symbol(self, symbol: str) -> Asset | None:
        result = await self.db.execute(
            select(Asset).where(Asset.symbol == symbol.upper())
        )
        return result.scalar_one_or_none()

    async def list_watchlisted(self) -> list[Asset]:
        result = await self.db.execute(
            select(Asset).where(Asset.watchlisted.is_(True)).order_by(Asset.symbol)
        )
        return list(result.scalars().all())

    async def list_watchlisted_ids(self) -> list[int]:
        result = await self.db.execute(
            select(Asset.id).where(Asset.watchlisted.is_(True))
        )
        return list(result.scalars().all())

    async def list_watchlisted_id_symbol_pairs(self) -> list[tuple[int, str]]:
        result = await self.db.execute(
            select(Asset.id, Asset.symbol).where(Asset.watchlisted.is_(True))
        )
        return list(result.all())

    async def list_watchlisted_symbols(self) -> list[str]:
        result = await self.db.execute(
            select(Asset.symbol).where(Asset.watchlisted.is_(True))
        )
        return [row[0] for row in result.all()]

    async def list_all(self) -> list[Asset]:
        result = await self.db.execute(select(Asset))
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
