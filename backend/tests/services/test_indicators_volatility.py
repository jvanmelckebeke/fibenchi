"""Tests for volatility / range indicators: ATR, ATR%, ADX, Choppiness, and the
volatility-normalized return (sigma-move)."""

import numpy as np
import pandas as pd
import pytest

from app.services.compute.indicators import (
    _true_range,
    adx,
    atr,
    build_indicator_snapshot,
    choppiness_index,
    compute_indicators,
    get_all_output_fields,
    session_gap_days,
    volatility_normalized_return,
)
from tests.helpers import (
    make_price_df as _make_price_df,
)
from tests.helpers import (
    make_series_from_returns as _series_from_returns,
)


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


def test_vnr_length():
    """VNR output should have the same length as its input."""
    df = _make_price_df(100)
    result = volatility_normalized_return(df["close"])
    assert len(result) == 100


def test_vnr_first_value_nan():
    """First value is NaN — there is no prior close to compute a return from."""
    df = _make_price_df(100)
    result = volatility_normalized_return(df["close"])
    assert pd.isna(result.iloc[0])


def test_vnr_in_compute_indicators():
    """VNR should appear as a column in compute_indicators output."""
    df = _make_price_df(100)
    result = compute_indicators(df)
    assert "vnr" in result.columns
    valid = result["vnr"].dropna()
    assert len(valid) > 0


def test_vnr_in_snapshot():
    """vnr should appear in snapshot values."""
    df = _make_price_df(200)
    snapshot = build_indicator_snapshot(compute_indicators(df))
    assert "values" in snapshot
    assert "vnr" in snapshot["values"]


def test_vnr_in_all_output_fields():
    """vnr should be listed in get_all_output_fields."""
    assert "vnr" in get_all_output_fields()


def test_vnr_sign_matches_return():
    """A day that closes up gets a positive σ-move; a down day gets a negative one."""
    up = _series_from_returns([0.01, -0.01] * 40 + [0.02])
    down = _series_from_returns([0.01, -0.01] * 40 + [-0.02])
    assert volatility_normalized_return(up).iloc[-1] > 0
    assert volatility_normalized_return(down).iloc[-1] < 0


def test_vnr_normalizes_across_volatility_regimes():
    """The core property: a move that is 2× the asset's own typical move scores
    ~2σ regardless of the asset's absolute volatility level.

    Asset A oscillates ±1%/day; asset B ±4%/day (4× more volatile). Both take a
    final move of exactly twice their usual size. Their σ-moves should be nearly
    equal (~2.0) even though B's headline % move is 4× A's.
    """
    calm = _series_from_returns([0.01, -0.01] * 60 + [0.02])
    wild = _series_from_returns([0.04, -0.04] * 60 + [0.08])

    vnr_calm = volatility_normalized_return(calm).iloc[-1]
    vnr_wild = volatility_normalized_return(wild).iloc[-1]

    assert vnr_calm == pytest.approx(2.0, abs=0.05)
    assert vnr_wild == pytest.approx(2.0, abs=0.05)
    # Same normalized surprise despite a 4× difference in raw move size.
    assert abs(vnr_calm - vnr_wild) < 0.05


def test_vnr_flat_series_no_inf():
    """A flat (zero-volatility) series must not produce inf (division guard)."""
    result = volatility_normalized_return(pd.Series([100.0] * 50))
    assert not np.isinf(result.to_numpy()[~np.isnan(result.to_numpy())]).any()


def test_vnr_lambda_affects_result():
    """The decay `lam` must actually feed through: on a series with *varying*
    volatility, different decays produce different σ-moves. (On a constant-vol
    series every decay converges to the same estimate, so a real-world varying
    series is used here.)"""
    df = _make_price_df(200)
    fast = volatility_normalized_return(df["close"], lam=0.80).iloc[-1]
    slow = volatility_normalized_return(df["close"], lam=0.97).iloc[-1]
    assert fast != pytest.approx(slow)


def test_vnr_sigma_in_snapshot():
    """The forward vol forecast is exposed so the UI can score an in-progress day."""
    df = _make_price_df(200)
    snapshot = build_indicator_snapshot(compute_indicators(df))
    assert "vnr_sigma" in snapshot["values"]
    assert snapshot["values"]["vnr_sigma"] > 0


def test_vnr_sigma_reconstructs_live_move():
    """vnr_sigma is exactly the forecast that turns a next-day return into its σ-move.

    Mirrors the frontend live recompute: the DB snapshot holds bars through
    'yesterday'; today's live return divided by the snapshot's vnr_sigma must
    reproduce the σ-move the full series (with today's bar) computes for that day.
    """
    df = _make_price_df(200)
    # DB state = everything up to but excluding the final ("today") bar.
    db_snapshot = build_indicator_snapshot(compute_indicators(df.iloc[:-1]))
    vnr_sigma = db_snapshot["values"]["vnr_sigma"]

    closes = df["close"]
    today_return = closes.iloc[-1] / closes.iloc[-2] - 1
    live_vnr = today_return / vnr_sigma

    full = compute_indicators(df)
    assert live_vnr == pytest.approx(full["vnr"].iloc[-1], rel=1e-4)


# ---------------------------------------------------------------------------
# Gap guard — issue #559 (σ-Move inflated by √N across missing sessions)
# ---------------------------------------------------------------------------


def test_session_gap_days_basic():
    """1 for adjacent sessions (weekends free), >1 across a missing business day."""
    # Thu, Fri, Mon (weekend — fine), Wed (Tuesday missing)
    idx = pd.Index([
        pd.Timestamp("2026-07-30"), pd.Timestamp("2026-07-31"),
        pd.Timestamp("2026-08-03"), pd.Timestamp("2026-08-05"),
    ])
    gaps = session_gap_days(idx)
    assert pd.isna(gaps.iloc[0])
    assert gaps.iloc[1] == 1
    assert gaps.iloc[2] == 1  # Fri -> Mon: the weekend is not a gap
    assert gaps.iloc[3] == 2  # Mon -> Wed: Tuesday has no bar


def test_session_gap_days_non_date_index():
    """A synthetic (non-date) index yields all-NaN — treated as contiguous."""
    gaps = session_gap_days(pd.RangeIndex(5))
    assert gaps.isna().all()


def _gapped_df(n: int = 100, drop_offset: int = 5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """A business-day price df and a copy with one interior session removed.

    ``drop_offset`` counts back from the end; the dropped row is guaranteed to
    leave a >1-business-day hole between its neighbours.
    """
    full = _make_price_df(n)
    gapped = full.drop(full.index[n - drop_offset])
    return full, gapped


def test_vnr_gap_bar_is_nan():
    """The bar after a missing session must not report a σ-move at all."""
    full, gapped = _gapped_df()
    vnr = volatility_normalized_return(gapped["close"])
    # The bar right after the hole is suppressed…
    assert pd.isna(vnr.iloc[-4])
    # …while bars before the hole are untouched (identical to the full series).
    pd.testing.assert_series_equal(
        vnr.iloc[10:-4], volatility_normalized_return(full["close"]).iloc[10:-5],
        check_freq=False,
    )


def test_vnr_gap_sessions_flag_in_output():
    """compute_indicators exposes vnr_gap_sessions only on suppressed bars."""
    _, gapped = _gapped_df()
    result = compute_indicators(gapped)
    assert "vnr_gap_sessions" in result.columns
    flagged = result["vnr_gap_sessions"].dropna()
    assert len(flagged) == 1
    assert flagged.iloc[0] == 2
    assert "vnr_gap_sessions" in get_all_output_fields()


def test_vnr_no_gap_no_flag():
    """A contiguous business-day series carries no gap flags and no suppression."""
    full = _make_price_df(100)
    result = compute_indicators(full)
    assert result["vnr_gap_sessions"].isna().all()
    assert result["vnr"].iloc[10:].notna().all()


def test_vnr_regression_issue_559():
    """The observed IWDA.AS case: closes 124.23 -> 127.65 across a two-session
    gap (2026-08-03 missing) must not report the inflated 4.48σ figure.

    With a contiguous index the same closes score >4σ; with the real gapped
    dates the bar must be suppressed and flagged instead.
    """
    n = 80
    warmup_dates = pd.bdate_range(end="2026-07-31", periods=n)
    # Alternating ±0.6%-ish closes ending exactly at the observed 124.23.
    closes = [124.23 if (n - 1 - i) % 2 == 0 else 123.50 for i in range(n)]

    contiguous = pd.Series(
        closes + [127.65], index=list(warmup_dates) + [pd.Timestamp("2026-08-03")]
    )
    inflated = volatility_normalized_return(contiguous).iloc[-1]
    assert inflated > 4  # what the bug displayed (4.48 on the live data)

    gapped = pd.Series(
        closes + [127.65], index=list(warmup_dates) + [pd.Timestamp("2026-08-04")]
    )
    vnr = volatility_normalized_return(gapped)
    assert pd.isna(vnr.iloc[-1])

    df = pd.DataFrame({
        "open": gapped, "high": gapped, "low": gapped, "close": gapped,
        "volume": 1_000_000,
    })
    result = compute_indicators(df)
    assert result["vnr_gap_sessions"].iloc[-1] == 2
    snapshot = build_indicator_snapshot(result)
    assert snapshot["values"]["vnr"] is None
    assert snapshot["values"]["vnr_gap_sessions"] == 2
