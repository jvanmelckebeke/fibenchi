"""Tests for the indicator computation service (no DB needed)."""

import numpy as np
import pandas as pd
import pytest

from app.services.compute.indicators import (
    _true_range,
    adx,
    atr,
    build_indicator_snapshot,
    chaikin_money_flow,
    choppiness_index,
    compute_indicators,
    get_all_output_fields,
    macd,
    normalized_force_index,
    rsi,
    sma,
)
from tests.helpers import make_price_df as _make_price_df


def test_rsi_range():
    df = _make_price_df()
    result = rsi(df["close"])
    valid = result.dropna()
    assert all(0 <= v <= 100 for v in valid)


def test_rsi_period_start_is_nan():
    df = _make_price_df()
    result = rsi(df["close"], period=14)
    assert pd.isna(result.iloc[0])


def test_sma_correct():
    data = pd.Series([1, 2, 3, 4, 5], dtype=float)
    result = sma(data, 3)
    assert result.iloc[2] == pytest.approx(2.0)
    assert result.iloc[4] == pytest.approx(4.0)


def test_macd_keys():
    df = _make_price_df()
    result = macd(df["close"])
    assert "macd" in result
    assert "signal" in result
    assert "histogram" in result


def test_compute_indicators_columns():
    df = _make_price_df()
    result = compute_indicators(df)
    expected_cols = {"close"} | set(get_all_output_fields())
    assert set(result.columns) == expected_cols


def test_compute_indicators_length():
    df = _make_price_df(100)
    result = compute_indicators(df)
    assert len(result) == 100


# ---------------------------------------------------------------------------
# ATR tests (#214)
# ---------------------------------------------------------------------------


def test_true_range_basic():
    """True Range should equal High - Low when there's no gap."""
    df = pd.DataFrame({
        "high": [12.0, 12.0, 12.0],
        "low": [10.0, 10.0, 10.0],
        "close": [11.0, 11.0, 11.0],
    })
    tr = _true_range(df)
    # First row: prev close is NaN, but hl = 2.0 is valid so max(skipna) = 2.0
    assert tr.iloc[0] == pytest.approx(2.0)
    # Subsequent rows: no gap, so TR = high - low = 2.0
    assert tr.iloc[1] == pytest.approx(2.0)
    assert tr.iloc[2] == pytest.approx(2.0)


def test_true_range_with_gap():
    """True Range should account for gaps (prev close outside today's range)."""
    df = pd.DataFrame({
        "high": [10.0, 15.0],
        "low": [8.0, 13.0],
        "close": [9.0, 14.0],
    })
    tr = _true_range(df)
    # Row 1: hl = 2, |high - prev_close| = |15 - 9| = 6, |low - prev_close| = |13 - 9| = 4
    # TR = max(2, 6, 4) = 6
    assert tr.iloc[1] == pytest.approx(6.0)


def test_atr_positive():
    """ATR values should always be positive (volatility can't be negative)."""
    df = _make_price_df(100)
    result = atr(df)
    valid = result.dropna()
    assert len(valid) > 0
    assert all(v > 0 for v in valid)


def test_atr_length():
    """ATR output should have same length as input."""
    df = _make_price_df(100)
    result = atr(df)
    assert len(result) == 100


def test_atr_warmup_nans():
    """ATR should have NaN values during the warmup period."""
    df = _make_price_df(30)
    result = atr(df, period=14)
    # First row is always NaN (no prev close for TR), plus warmup
    assert pd.isna(result.iloc[0])


def test_atr_in_compute_indicators():
    """ATR should appear in compute_indicators output."""
    df = _make_price_df(100)
    result = compute_indicators(df)
    assert "atr" in result.columns
    valid = result["atr"].dropna()
    assert len(valid) > 0
    assert all(v > 0 for v in valid)


# ---------------------------------------------------------------------------
# ADX tests (#215)
# ---------------------------------------------------------------------------


def test_adx_keys():
    """ADX function should return adx, plus_di, and minus_di."""
    df = _make_price_df(100)
    result = adx(df)
    assert "adx" in result
    assert "plus_di" in result
    assert "minus_di" in result


def test_adx_range():
    """ADX and DI values should be between 0 and 100 (when valid)."""
    df = _make_price_df(200)
    result = adx(df)
    for key in ["adx", "plus_di", "minus_di"]:
        valid = result[key].dropna()
        # Filter out inf values that can occur with division
        valid = valid[np.isfinite(valid)]
        assert len(valid) > 0
        assert all(v >= 0 for v in valid), f"{key} has negative values"
        assert all(v <= 100 for v in valid), f"{key} has values > 100"


def test_adx_length():
    """ADX output series should have same length as input."""
    df = _make_price_df(100)
    result = adx(df)
    for key in ["adx", "plus_di", "minus_di"]:
        assert len(result[key]) == 100


def test_adx_in_compute_indicators():
    """ADX, +DI, -DI should appear in compute_indicators output."""
    df = _make_price_df(100)
    result = compute_indicators(df)
    assert "adx" in result.columns
    assert "plus_di" in result.columns
    assert "minus_di" in result.columns


def test_adx_strong_trend():
    """ADX should be high for a consistently trending series."""
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    # Strong uptrend: price increases monotonically
    prices = [100.0 + i * 1.0 for i in range(n)]
    df = pd.DataFrame({
        "open": [p - 0.2 for p in prices],
        "high": [p + 0.5 for p in prices],
        "low": [p - 0.5 for p in prices],
        "close": prices,
    }, index=dates)
    result = adx(df)
    # Last ADX value should indicate a strong trend (> 25)
    last_valid = result["adx"].dropna().iloc[-1]
    assert last_valid > 25, f"ADX should be > 25 for strong trend, got {last_valid}"


def test_adx_snapshot_derived():
    """ADX snapshot should classify trend strength."""
    df = _make_price_df(200)
    indicators = compute_indicators(df)
    snapshot = build_indicator_snapshot(indicators)
    assert "values" in snapshot
    assert "adx_trend" in snapshot["values"]
    # Should be one of the valid classifications or None
    assert snapshot["values"]["adx_trend"] in ("strong", "weak", "absent", None)


# ---------------------------------------------------------------------------
# ATR% tests (#399)
# ---------------------------------------------------------------------------


def test_atr_pct_in_snapshot():
    """atr_pct should appear in snapshot values and be positive."""
    df = _make_price_df(200)
    indicators = compute_indicators(df)
    snapshot = build_indicator_snapshot(indicators)
    assert "values" in snapshot
    assert "atr_pct" in snapshot["values"]
    assert snapshot["values"]["atr_pct"] is not None
    assert snapshot["values"]["atr_pct"] > 0


def test_atr_pct_calculation():
    """atr_pct should equal round(atr / close * 100, 2)."""
    df = _make_price_df(200)
    indicators = compute_indicators(df)
    snapshot = build_indicator_snapshot(indicators)
    atr_val = snapshot["values"]["atr"]
    close_val = snapshot["close"]
    expected = round(atr_val / close_val * 100, 2)
    assert snapshot["values"]["atr_pct"] == expected


def test_atr_pct_none_when_close_zero():
    """atr_pct should be None when close price is zero (division guard)."""
    row = pd.Series({"atr": 5.0, "close": 0.0})
    from app.services.compute.indicators import _atr_snapshot_derived
    result = _atr_snapshot_derived(row)
    assert result == {"atr_pct": None}


def test_atr_pct_none_when_atr_nan():
    """atr_pct should be None when ATR is NaN."""
    row = pd.Series({"atr": float("nan"), "close": 100.0})
    from app.services.compute.indicators import _atr_snapshot_derived
    result = _atr_snapshot_derived(row)
    assert result == {"atr_pct": None}


def test_atr_pct_in_compute_indicators():
    """atr_pct should appear as a per-bar column in compute_indicators output."""
    df = _make_price_df(100)
    result = compute_indicators(df)
    assert "atr_pct" in result.columns
    valid = result["atr_pct"].dropna()
    assert len(valid) > 0
    assert all(v > 0 for v in valid)


def test_atr_adx_in_all_output_fields():
    """ATR and ADX fields should be listed in get_all_output_fields."""
    fields = get_all_output_fields()
    assert "atr" in fields
    assert "adx" in fields
    assert "plus_di" in fields
    assert "minus_di" in fields


# ---------------------------------------------------------------------------
# Choppiness Index tests (#482)
# ---------------------------------------------------------------------------


def test_chop_range():
    """Choppiness Index values should be between 0 and 100."""
    df = _make_price_df(200)
    result = choppiness_index(df)
    valid = result.dropna()
    assert len(valid) > 0
    assert all(0 <= v <= 100 for v in valid), "CHOP values out of 0-100 range"


def test_chop_length():
    """Choppiness Index output should have same length as input."""
    df = _make_price_df(100)
    result = choppiness_index(df)
    assert len(result) == 100


def test_chop_warmup_nans():
    """Choppiness Index should have NaN values during the warmup period."""
    df = _make_price_df(30)
    result = choppiness_index(df, period=14)
    assert pd.isna(result.iloc[0])


def test_chop_in_compute_indicators():
    """Choppiness Index should appear in compute_indicators output."""
    df = _make_price_df(100)
    result = compute_indicators(df)
    assert "chop" in result.columns
    valid = result["chop"].dropna()
    assert len(valid) > 0
    assert all(0 <= v <= 100 for v in valid)


def test_chop_high_for_ranging_market():
    """CHOP should be high for a sideways/ranging market."""
    n = 200
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    # Ranging market: oscillate between 100 and 102
    prices = [100.0 + (i % 4) * 0.5 for i in range(n)]
    df = pd.DataFrame({
        "open": [p - 0.3 for p in prices],
        "high": [p + 0.5 for p in prices],
        "low": [p - 0.5 for p in prices],
        "close": prices,
    }, index=dates)
    result = choppiness_index(df)
    last_valid = result.dropna().iloc[-1]
    assert last_valid > 50, f"CHOP should be >50 for ranging market, got {last_valid}"


def test_chop_snapshot_derived():
    """Choppiness snapshot should classify market regime."""
    df = _make_price_df(200)
    indicators = compute_indicators(df)
    snapshot = build_indicator_snapshot(indicators)
    assert "values" in snapshot
    assert "chop_state" in snapshot["values"]
    assert snapshot["values"]["chop_state"] in ("choppy", "trending", "neutral", None)


# ---------------------------------------------------------------------------
# Chaikin Money Flow tests (#483)
# ---------------------------------------------------------------------------


def test_cmf_range():
    """CMF values should be between -1 and +1."""
    df = _make_price_df(200)
    result = chaikin_money_flow(df)
    valid = result.dropna()
    assert len(valid) > 0
    assert all(-1 <= v <= 1 for v in valid), "CMF values out of -1 to +1 range"


def test_cmf_length():
    """CMF output should have same length as input."""
    df = _make_price_df(100)
    result = chaikin_money_flow(df)
    assert len(result) == 100


def test_cmf_warmup_nans():
    """CMF should have NaN values during the warmup period."""
    df = _make_price_df(30)
    result = chaikin_money_flow(df, period=20)
    assert pd.isna(result.iloc[0])


def test_cmf_in_compute_indicators():
    """CMF should appear in compute_indicators output."""
    df = _make_price_df(100)
    result = compute_indicators(df)
    assert "cmf" in result.columns
    valid = result["cmf"].dropna()
    assert len(valid) > 0
    assert all(-1 <= v <= 1 for v in valid)


def test_cmf_positive_for_closes_near_high():
    """CMF should be positive when closes are consistently near highs."""
    n = 100
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    df = pd.DataFrame({
        "open": [100.0] * n,
        "high": [105.0] * n,
        "low": [95.0] * n,
        "close": [104.0] * n,  # Close near high → positive MF multiplier
        "volume": [1_000_000] * n,
    }, index=dates)
    result = chaikin_money_flow(df)
    last_valid = result.dropna().iloc[-1]
    assert last_valid > 0, f"CMF should be positive for closes near highs, got {last_valid}"


def test_cmf_snapshot_derived():
    """CMF snapshot should classify buying/selling pressure."""
    df = _make_price_df(200)
    indicators = compute_indicators(df)
    snapshot = build_indicator_snapshot(indicators)
    assert "values" in snapshot
    assert "cmf_signal" in snapshot["values"]
    assert snapshot["values"]["cmf_signal"] in ("buying", "selling", None)


# ---------------------------------------------------------------------------
# Normalized Elder's Force Index (NEFI) tests (#484)
# ---------------------------------------------------------------------------


def test_nefi_keys():
    """NEFI should return nefi_short and nefi_long."""
    df = _make_price_df(300)
    result = normalized_force_index(df)
    assert "nefi_short" in result
    assert "nefi_long" in result


def test_nefi_length():
    """NEFI output should have same length as input."""
    df = _make_price_df(300)
    result = normalized_force_index(df)
    assert len(result["nefi_short"]) == 300
    assert len(result["nefi_long"]) == 300


def test_nefi_in_compute_indicators():
    """NEFI fields should appear in compute_indicators output."""
    df = _make_price_df(300)
    result = compute_indicators(df)
    assert "nefi_short" in result.columns
    assert "nefi_long" in result.columns


def test_nefi_scales_with_price_not_volume():
    """NEFI should be comparable across assets with different volume levels.

    Two assets with identical price moves but 10× different volume
    should produce similar short NEFI values (since volume cancels out).
    """
    n = 100
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    prices = [100.0 + i * 0.5 for i in range(n)]

    # Asset A: low volume
    df_a = pd.DataFrame({
        "open": [p - 0.3 for p in prices],
        "high": [p + 0.5 for p in prices],
        "low": [p - 0.5 for p in prices],
        "close": prices,
        "volume": [100_000] * n,
    }, index=dates)

    # Asset B: 10× higher volume, same prices
    df_b = pd.DataFrame({
        "open": [p - 0.3 for p in prices],
        "high": [p + 0.5 for p in prices],
        "low": [p - 0.5 for p in prices],
        "close": prices,
        "volume": [1_000_000] * n,
    }, index=dates)

    nefi_a = normalized_force_index(df_a)["nefi_short"].dropna().iloc[-1]
    nefi_b = normalized_force_index(df_b)["nefi_short"].dropna().iloc[-1]

    # Should be approximately equal (volume normalizes out)
    assert abs(nefi_a - nefi_b) < 0.01, f"NEFI should normalize volume: A={nefi_a}, B={nefi_b}"


def test_nefi_snapshot_crossover_signal():
    """NEFI snapshot should classify bullish/bearish based on short vs long crossover."""
    df = _make_price_df(300)
    indicators = compute_indicators(df)
    snapshot = build_indicator_snapshot(indicators)
    assert "values" in snapshot
    assert "nefi_signal" in snapshot["values"]
    assert snapshot["values"]["nefi_signal"] in ("bullish", "bearish", None)
