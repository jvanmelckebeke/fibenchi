"""Tests for the indicator computation service (no DB needed)."""

import numpy as np
import pandas as pd
import pytest

from app.services.compute.indicators import compute_indicators, get_all_output_fields, rsi, sma, macd


def _make_price_df(n: int = 100, start_price: float = 100.0) -> pd.DataFrame:
    """Generate synthetic price data for testing."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    returns = np.random.normal(0.001, 0.02, n)
    prices = start_price * np.cumprod(1 + returns)

    return pd.DataFrame({
        "open": prices * (1 - np.random.uniform(0, 0.01, n)),
        "high": prices * (1 + np.random.uniform(0, 0.02, n)),
        "low": prices * (1 - np.random.uniform(0, 0.02, n)),
        "close": prices,
        "volume": np.random.randint(1_000_000, 10_000_000, n),
    }, index=dates)


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
