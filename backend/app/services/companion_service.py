"""Assemble the companion-app config and portfolio-index bundles."""

import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.repositories.thesis_repo import ThesisRepository
from app.schemas.companion import (
    CONFIG_VERSION,
    PORTFOLIO_INDEX_VERSION,
    CompanionConfig,
    CompanionPortfolioIndex,
    ConfigGroup,
    ConfigThesis,
    ConfigTicker,
)
from app.services import group_service, tag_service
from app.services.compute.portfolio import compute_portfolio_index
from app.services.currency_service import lookup as currency_lookup


def _ticker(asset: Asset) -> ConfigTicker:
    display_currency, _ = currency_lookup(asset.currency)
    return ConfigTicker(
        name=asset.name,
        type=asset.type,
        currency=display_currency,
        tags=[tag.name for tag in asset.tags],
    )


async def build_config(db: AsyncSession) -> CompanionConfig:
    """Build the normalized config bundle (groups ordered, tickers deduped)."""
    groups = await group_service.list_groups(db)
    tags = await tag_service.list_tags(db)
    theses = await ThesisRepository(db).list_all()

    config_groups: list[ConfigGroup] = []
    tickers: dict[str, ConfigTicker] = {}

    for group in groups:  # already ordered by position, name
        symbols: list[str] = []
        # group_assets is an unordered M:N (no ordinal column), so sort by symbol
        # for a stable, reproducible bundle — the app relies on deterministic order.
        for asset in sorted(group.assets, key=lambda a: a.symbol):
            symbols.append(asset.symbol)
            if asset.symbol not in tickers:
                tickers[asset.symbol] = _ticker(asset)
        config_groups.append(
            ConfigGroup(
                name=group.name,
                icon=group.icon,
                is_default=group.is_default,
                position=group.position,
                symbols=symbols,
            )
        )

    config_theses: list[ConfigThesis] = []
    for thesis in theses:  # ordered by name, as GET /api/theses returns them
        members = sorted(thesis.assets, key=lambda a: a.symbol)
        for asset in members:
            if asset.symbol not in tickers:
                tickers[asset.symbol] = _ticker(asset)
        config_theses.append(
            ConfigThesis(name=thesis.name, color=thesis.color, symbols=[a.symbol for a in members])
        )

    return CompanionConfig(
        version=CONFIG_VERSION,
        generated_at=datetime.datetime.now(datetime.UTC),
        groups=config_groups,
        tickers=tickers,
        tags={tag.name: tag.color for tag in tags},
        theses=config_theses,
    )


async def build_portfolio_index(db: AsyncSession, period: str) -> CompanionPortfolioIndex:
    """Wrap the web's portfolio index, turning its zero placeholders for an empty index into nulls."""
    index = await compute_portfolio_index(db, period)
    empty = not index["dates"]
    return CompanionPortfolioIndex(
        version=PORTFOLIO_INDEX_VERSION,
        generated_at=datetime.datetime.now(datetime.UTC),
        period=period,
        dates=index["dates"],
        values=index["values"],
        current=None if empty else index["current"],
        change=None if empty else index["change"],
        change_pct=None if empty else index["change_pct"],
    )
