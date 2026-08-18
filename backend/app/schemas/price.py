import datetime

from pydantic import BaseModel, Field


class OHLCV(BaseModel):
    """One bar of open/high/low/close/volume."""

    open: float = Field(description="Opening price")
    high: float = Field(description="Highest price of the day")
    low: float = Field(description="Lowest price of the day")
    close: float = Field(description="Closing price")
    volume: int = Field(description="Trading volume")


class DatedOHLCV(OHLCV):
    """An OHLCV bar bound to its trading date.

    Validates from anything bar-shaped (``PriceHistory`` ORM rows,
    ``PriceResponse`` models) via ``from_attributes``.
    """

    date: datetime.date = Field(description="Trading date")

    model_config = {"from_attributes": True}


class PriceResponse(DatedOHLCV):
    """A daily price bar as served by the price endpoints."""


class IndicatorResponse(BaseModel):
    date: datetime.date = Field(description="Trading date")
    close: float = Field(description="Closing price")
    values: dict[str, float | None] = Field(
        default_factory=dict,
        description="Indicator values keyed by field name (e.g. rsi, sma_20, macd)",
    )


class AssetDetailResponse(BaseModel):
    prices: list[PriceResponse] = Field(description="OHLCV price history for the requested period")
    indicators: list[IndicatorResponse] = Field(description="Technical indicators for the requested period")


class HoldingResponse(BaseModel):
    symbol: str = Field(description="Holding ticker symbol")
    name: str = Field(description="Holding company name")
    percent: float = Field(description="Holding weight as a percentage of the ETF")


class SectorWeighting(BaseModel):
    sector: str = Field(description="Sector name")
    percent: float = Field(description="Sector weight as a percentage")


class EtfHoldingsResponse(BaseModel):
    top_holdings: list[HoldingResponse] = Field(description="Top holdings by weight")
    sector_weightings: list[SectorWeighting] = Field(description="Sector allocation breakdown")
    total_percent: float = Field(description="Sum of top holding weights (may be < 100%)")


class IndicatorSnapshotBase(BaseModel):
    """The indicator snapshot — service-level object AND response shape.

    Built by ``build_indicator_snapshot`` and cached by the compute layer;
    the group/symbol indicator endpoints serve it as-is. ``values`` is an
    open map on purpose: its keys are driven by ``INDICATOR_REGISTRY``
    (output fields + ``snapshot_derived``) and the fundamentals cache merges
    more keys in *after* construction — instances must therefore stay
    mutable (no ``frozen=True``), and a closed per-field model would lie
    about the payload. A degenerate snapshot (insufficient history) is an
    all-default instance, not a missing entry.
    """

    close: float | None = Field(default=None, description="Latest closing price")
    as_of: datetime.date | None = Field(
        default=None,
        description="Exchange-local date of the last bar behind this snapshot. Lets a "
        "client identify which session `close`/`change_pct`/`vnr` describe — pair it "
        "with a quote's `session_date`/`prior_session_date` — instead of inferring it "
        "from price similarity. None for a degenerate snapshot with no bars.",
    )
    change_pct: float | None = Field(default=None, description="1-day percentage change")
    bars: int | None = Field(
        default=None,
        description="Price bars behind this snapshot's computation. Lets clients tell "
        "'building baseline' (fewer bars than an indicator's warmup, e.g. σ-Move's 60 "
        "sessions) apart from other null-indicator causes. None when nothing was computed.",
    )
    values: dict[str, float | str | None] = Field(
        default_factory=dict,
        description="Indicator values keyed by field name (includes derived fields like macd_signal_dir, bb_position)",
    )


class CurrencyIndicatorSnapshot(IndicatorSnapshotBase):
    """A snapshot with its display currency but no symbol — the batch data
    endpoint's ``snapshot`` field, where the symbol is already the payload
    key. Serializing a :class:`SymbolIndicatorSnapshot` through a field of
    this type strips ``symbol`` (declared-type serialization)."""

    currency: str = Field(default="USD", description="ISO 4217 currency code")


class SymbolIndicatorSnapshot(CurrencyIndicatorSnapshot):
    """A snapshot bound to its symbol — the shape
    ``compute_batch_indicator_snapshots`` returns (holdings, pseudo-ETF
    constituents, batch data)."""

    symbol: str = Field(description="Ticker symbol")


class HoldingIndicatorResponse(SymbolIndicatorSnapshot):
    """Per-holding indicator snapshot as served by the holdings endpoint."""


class SparklinePointResponse(BaseModel):
    date: str = Field(description="Trading date as ISO 8601 string")
    close: float = Field(description="Closing price")


class RefreshResponse(BaseModel):
    symbol: str = Field(description="Ticker symbol that was refreshed")
    synced: int = Field(description="Number of price points upserted")
