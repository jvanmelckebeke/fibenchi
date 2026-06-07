"""Assemble the companion-app config bundle from groups, assets, and tags."""

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.companion import CONFIG_VERSION, CompanionConfig, ConfigGroup, ConfigTicker
from app.services import group_service, tag_service
from app.services.currency_service import lookup as currency_lookup


async def build_config(db: AsyncSession) -> CompanionConfig:
    """Build the normalized config bundle (groups ordered, tickers deduped)."""
    groups = await group_service.list_groups(db)
    tags = await tag_service.list_tags(db)

    config_groups: list[ConfigGroup] = []
    tickers: dict[str, ConfigTicker] = {}

    for group in groups:  # already ordered by position, name
        symbols: list[str] = []
        for asset in group.assets:
            symbols.append(asset.symbol)
            if asset.symbol not in tickers:
                display_currency, _ = currency_lookup(asset.currency)
                tickers[asset.symbol] = ConfigTicker(
                    name=asset.name,
                    type=asset.type,
                    currency=display_currency,
                    tags=[tag.name for tag in asset.tags],
                )
        config_groups.append(
            ConfigGroup(
                name=group.name,
                icon=group.icon,
                is_default=group.is_default,
                position=group.position,
                symbols=symbols,
            )
        )

    return CompanionConfig(
        version=CONFIG_VERSION,
        generated_at=datetime.datetime.now(datetime.UTC),
        groups=config_groups,
        tickers=tickers,
        tags={tag.name: tag.color for tag in tags},
    )
