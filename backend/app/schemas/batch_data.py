"""Response models for the batch data endpoint (``GET /api/data``)."""

from pydantic import BaseModel, Field

from app.schemas.price import DatedOHLCV, IndicatorResponse


class SymbolBatchData(BaseModel):
    """Per-symbol payload of the batch query.

    Only the requested fields are set — the router serializes with
    ``response_model_exclude_none=True``, so absent fields are dropped from
    the JSON rather than emitted as ``null``. ``error`` replaces the data
    fields when the symbol failed entirely.

    ``quote`` and ``snapshot`` stay provider-shaped dicts for now — typing
    them is tracked in #580.
    """

    quote: dict | None = Field(
        default=None, description="Real-time quote: price, change, volume, market state."
    )
    snapshot: dict | None = Field(
        default=None, description="Latest indicator values and derived signals."
    )
    prices: list[DatedOHLCV] | None = Field(
        default=None, description="OHLCV price history for the requested period."
    )
    indicators: list[IndicatorResponse] | None = Field(
        default=None, description="Full indicator time series for the requested period."
    )
    error: str | None = Field(
        default=None, description="Why no data could be returned for this symbol."
    )
