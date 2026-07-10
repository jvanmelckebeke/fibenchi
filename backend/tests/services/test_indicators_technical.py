"""Tests for momentum / trend / volume-flow indicators: RSI, SMA, MACD, NEFI, CMF."""

import pandas as pd
import pytest

from app.services.compute.indicators import (
    build_indicator_snapshot,
    chaikin_money_flow,
    compute_indicators,
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
