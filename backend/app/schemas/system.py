"""Response models for operational/system endpoints."""

import datetime

from pydantic import BaseModel, Field


class HoleSymbol(BaseModel):
    symbol: str = Field(description="Ticker with missing sessions in its stored history")
    missing_sessions: list[datetime.date] = Field(
        description="Scheduled trading sessions with no stored bar"
    )


class DataHealthResponse(BaseModel):
    """State of the price-history self-heal: what's broken and when the next
    repair scan runs. Symbols listed here typically show a blank σ-Move until
    the background heal backfills them."""

    hole_symbols: list[HoleSymbol] = Field(
        description="Symbols with interior session holes, newest hole first (heal priority order)"
    )
    total_missing_sessions: int = Field(description="Missing session bars across all symbols")
    expected_session_bars: int = Field(
        description="Scheduled session bars in the scan window across all covered symbols "
        "(denominator for a completeness percentage)"
    )
    covered_symbols: int = Field(
        description="Symbols the coverage scan can check (grouped, with a resolvable venue "
        "calendar) — denominator for the affected-symbol count"
    )
    next_scan_in_seconds: int = Field(
        description="Approximate seconds until the next self-heal scan is eligible to run"
    )
    heals_per_scan: int = Field(description="Symbols repaired per scan (worst-case drain rate)")
    scan_window_days: int = Field(description="How far back the scan looks for holes")


class OrphanAsset(BaseModel):
    """An asset row referenced by nothing — no group, thesis, or pseudo-ETF.
    Leftovers of removals; re-adoptable, or hard-deletable once you know the cost.

    "Referenced by nothing" is about *containers*, not content: an orphan can
    still carry a note and annotations, which the hard delete cascades away.
    Those are hand-written and unrecoverable — unlike price bars, which Yahoo
    re-supplies — so they are reported separately and the UI warns on them.
    """

    id: int = Field(description="Asset ID (for add-to-group/thesis calls)")
    symbol: str = Field(description="Ticker symbol")
    name: str = Field(description="Asset display name")
    type: str = Field(description="Asset type (stock/etf/index)")
    price_bars: int = Field(description="Stored daily bars that would be deleted with it")
    latest_bar: datetime.date | None = Field(description="Newest stored daily bar")
    annotations: int = Field(
        description="Hand-written chart annotations that would be deleted with it "
        "(not re-fetchable)"
    )
    has_note: bool = Field(
        description="Whether a hand-written thesis note would be deleted with it "
        "(not re-fetchable)"
    )


class StatsResponse(BaseModel):
    """Collection-size numbers for the stats page."""

    assets_total: int = Field(description="Asset rows in the database")
    assets_tracked: int = Field(description="Assets in at least one group")
    assets_thesis_or_etf_only: int = Field(
        description="Ungrouped assets whose row is kept because a thesis or "
        "pseudo-ETF references it (the soft delete preserves these on purpose)"
    )
    assets_orphaned: int = Field(
        description="Ungrouped assets referenced by nothing — leftovers of removals"
    )
    # Asset mix: one bucket per *tracked* asset (in ≥1 group) — sums to
    # assets_tracked. Ticker-shape classification (AssetRef.kind) refined by
    # the stored Yahoo type for the stock/ETF split.
    stocks: int = Field(description="Exchange-listed stocks")
    etfs: int = Field(description="ETFs")
    indexes: int = Field(description="Indexes")
    crypto: int = Field(description="Crypto pairs")
    futures: int = Field(description="Futures contracts")
    fx: int = Field(description="FX pairs")
    price_bars: int = Field(description="Daily OHLCV bars stored")
    earliest_bar: datetime.date | None = Field(description="Oldest stored daily bar")
    latest_bar: datetime.date | None = Field(description="Newest stored daily bar")
    collected_days: int = Field(description="Calendar span of the stored daily history")
    intraday_bars: int = Field(description="1-minute intraday bars currently stored")
    groups: int = Field(description="Asset groups")
    pseudo_etfs: int = Field(description="User-created pseudo-ETF baskets")
    theses: int = Field(description="Investment theses")
    tags: int = Field(description="Tags")
    annotations: int = Field(description="Chart annotations")
    symbol_directory_entries: int = Field(description="Symbols in the search directory")
