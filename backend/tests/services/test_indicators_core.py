"""Registry-level indicator tests — cross-cutting machinery that exercises the
whole INDICATOR_REGISTRY rather than any single indicator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.constants import PERIOD_DAYS, WARMUP_DAYS
from app.services.compute.indicators import (
    _batch_history_period,
    build_indicator_snapshot,
    compute_batch_indicator_snapshots,
    compute_indicators,
    get_all_output_fields,
)
from tests.helpers import make_price_df as _make_price_df

pytestmark = pytest.mark.asyncio(loop_scope="function")


def test_compute_indicators_columns():
    df = _make_price_df()
    result = compute_indicators(df)
    expected_cols = {"close"} | set(get_all_output_fields())
    assert set(result.columns) == expected_cols


def test_compute_indicators_length():
    df = _make_price_df(100)
    result = compute_indicators(df)
    assert len(result) == 100


def test_snapshot_reports_bar_count():
    """Every snapshot carries the bars behind it — the numerator of the
    "building baseline · N/60" copy on the dense board (#603)."""
    snap = build_indicator_snapshot(compute_indicators(_make_price_df(100)))
    assert snap.bars == 100
    tiny = build_indicator_snapshot(compute_indicators(_make_price_df(1)))
    assert tiny.bars == 1
    assert tiny.close is None  # degenerate snapshot, but bars still reported


def test_atr_adx_in_all_output_fields():
    """ATR and ADX fields should be listed in get_all_output_fields."""
    fields = get_all_output_fields()
    assert "atr" in fields
    assert "adx" in fields
    assert "plus_di" in fields
    assert "minus_di" in fields


def test_batch_history_period_covers_max_warmup():
    """The batch fetch period must span the registry's largest warmup.

    Regression for #601: a hardcoded "3mo" fetch (~63 bars) left NEFI's
    200-bar volume baseline unfilled, so nefi_long/nefi_signal were null
    on every live-fetch snapshot path.
    """
    assert PERIOD_DAYS[_batch_history_period()] >= WARMUP_DAYS


async def test_batch_snapshots_fetch_enough_history_for_nefi():
    """compute_batch_indicator_snapshots yields non-null NEFI fields given
    warmup-covering history — and requests a period that provides it."""
    provider = MagicMock()
    provider.batch_fetch_history = AsyncMock(return_value={"AAPL": _make_price_df(250)})
    provider.batch_fetch_currencies = AsyncMock(return_value={"AAPL": "USD"})

    with patch(
        "app.services.compute.indicators.get_price_provider", return_value=provider,
    ):
        results = await compute_batch_indicator_snapshots(["AAPL"])

    requested_period = provider.batch_fetch_history.await_args.kwargs["period"]
    assert PERIOD_DAYS[requested_period] >= WARMUP_DAYS

    (snap,) = results
    assert snap.values.get("nefi_long") is not None
    assert snap.values.get("nefi_signal") is not None
