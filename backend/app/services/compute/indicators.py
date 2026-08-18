"""Technical indicator computations on price data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable

import numpy as np
import pandas as pd

from app.domain import AssetRef
from app.schemas.price import IndicatorSnapshotBase, SymbolIndicatorSnapshot
from app.services.price_providers import get_price_provider


def safe_round(value, decimals: int = 2) -> float | None:
    """Round a value if it is finite, otherwise return None."""
    if pd.notna(value) and np.isfinite(value):
        return round(value, decimals)
    return None


def rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    """RSI (Relative Strength Index). >70 overbought, <30 oversold."""
    delta = closes.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def sma(data: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return data.rolling(window=period).mean()


def ema(data: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return data.ewm(span=period, adjust=False).mean()


def bollinger_bands(
    closes: pd.Series, period: int = 20, std_dev: float = 2.0
) -> dict[str, pd.Series]:
    """Bollinger Bands: middle (SMA), upper (SMA + 2*std), lower (SMA - 2*std)."""
    middle = sma(closes, period)
    rolling_std = closes.rolling(window=period).std()
    upper = middle + (rolling_std * std_dev)
    lower = middle - (rolling_std * std_dev)
    return {"upper": upper, "middle": middle, "lower": lower}


def macd(closes: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, pd.Series]:
    """MACD line, signal line, and histogram."""
    macd_line = ema(closes, fast) - ema(closes, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def _wilder_smooth(data: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing method (equivalent to EWM with alpha=1/period).

    First value is a simple sum over the initial `period` rows,
    then subsequent values use: prev_smooth - (prev_smooth / period) + current.
    """
    return data.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def _true_range(df: pd.DataFrame) -> pd.Series:
    """True Range: max(High-Low, |High-PrevClose|, |Low-PrevClose|)."""
    prev_close = df["close"].shift(1)
    hl = df["high"] - df["low"]
    hc = (df["high"] - prev_close).abs()
    lc = (df["low"] - prev_close).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range using Wilder's smoothing.

    ATR measures volatility in price terms — useful for stop-loss
    placement, position sizing, and breakout confirmation.
    """
    tr = _true_range(df)
    return _wilder_smooth(tr, period)


# RiskMetrics daily decay; shared by the vnr indicator and its live forecast.
VNR_LAMBDA = 0.94

# Floor on the vol forecast, as a fraction of the asset's *own* long-run vol.
# The EWMA is a pure function of recent returns, so a series that stops moving
# decays it toward zero and the next real move divides by almost nothing. A
# global floor can't work — instruments legitimately differ in vol by orders of
# magnitude — so the floor is scaled per asset by its expanding return stdev.
#
# 0.15 was measured, not guessed. Swept against every tracked asset's stored
# history (77 series, ~350 bars each) and a synthetic 1.2%/day name gone flat
# for 120 sessions before a +3% day:
#
#   frac   real bars moved >0.05σ   synthetic σ-move
#   0.00                        0              92.7
#   0.10                        0              32.7
#   0.15                        0              21.8
#   0.25                       40              13.1
#
# 0.15 is the largest floor that changes *no* real observed bar while still
# cutting the pathological case ~4x. 0.25 looked tidier on the synthetic but
# clipped genuine quiet regimes — it cut a real RR.L +3.8% day from 2.50σ to
# 1.99σ, which is precisely the reading vnr exists to produce.
#
# Note this bounds the pathology rather than eliminating it: a floored σ still
# reports ~22σ for a series that has not moved in 120 sessions, because "low
# recent vol" and "not repricing at all" differ only in degree and one fraction
# cannot separate them. Detecting a degenerate flat run and withholding the
# score outright is the honest complement, and is deliberately left out of
# scope here — it reintroduces a blank, which is a display policy decision.
VNR_SIGMA_FLOOR_FRAC = 0.15
# Don't floor until the long-run estimate has enough observations to mean
# anything; below this the EWMA is the better of two weak estimates.
VNR_SIGMA_FLOOR_MIN_OBS = 20


def session_gap_days(index: pd.Index, session_dates: set[date] | None = None) -> pd.Series:
    """Sessions elapsed between each bar and the previous stored bar.

    1 means the bars are adjacent sessions; >1 means at least one session
    between them has no stored bar — a hole in the series.

    With ``session_dates`` (the venue's actual trading sessions covering the
    index range, from ``AssetRef(...).venue``) the count is exact: holidays
    are simply not sessions, so only genuine feed holes exceed 1. Without it,
    business days (Mon–Fri) approximate sessions, and an exchange holiday is
    indistinguishable from a hole — callers must treat >1 conservatively
    ("this is not a verified single-session step") rather than as proof of a
    data error.

    The first bar — and every bar of a non-date index (synthetic test series) —
    is NaN, meaning "no gap information": comparisons like ``gaps > 1`` are
    False there, so such rows are treated as contiguous.
    """
    gaps = pd.Series(np.nan, index=index)
    if len(index) < 2:
        return gaps
    if not isinstance(index[0], (date, datetime, np.datetime64)):
        return gaps
    d = pd.DatetimeIndex(index).values.astype("datetime64[D]")
    if session_dates:
        # Exact mode: count venue sessions in (prev, cur] for each bar pair.
        sessions = np.array(sorted(session_dates), dtype="datetime64[D]")
        counts = np.searchsorted(sessions, d, side="right")
        steps = counts[1:] - counts[:-1]
        # 0 means the calendar doesn't know this bar's date as a session even
        # though a bar exists — calendar and data disagree, so trust the data
        # and treat the step as contiguous rather than suppress on bad info.
        gaps.iloc[1:] = np.where(steps == 0, 1, steps)
    else:
        gaps.iloc[1:] = np.busday_count(d[:-1], d[1:])
    return gaps


def _ewma_daily_vol(
    closes: pd.Series,
    lam: float,
    gaps: pd.Series | None = None,
    sigma_floor_frac: float = VNR_SIGMA_FLOOR_FRAC,
    sigma_floor_min_obs: int = VNR_SIGMA_FLOOR_MIN_OBS,
) -> pd.Series:
    """Forward EWMA volatility forecast (RiskMetrics zero-mean).

    Returns the sqrt of the EWMA variance built from returns *through each bar*
    — i.e. the volatility with which to normalize the *next* bar's return. The
    forecast is floored at ``VNR_SIGMA_FLOOR_FRAC`` of the asset's expanding
    return stdev (see below); a fully flat series floors at zero and becomes
    NaN, which still guards the division. This is the un-shifted
    counterpart of the ``sigma_forecast`` inside :func:`volatility_normalized_return`;
    the value at the last bar is the forecast for the in-progress day, which the
    live snapshot uses to score today's move before its bar is written.

    ``gaps`` (a :func:`session_gap_days` series) excludes gap-spanning returns
    from the variance: a return across an N-session hole is √N-inflated, and
    squaring it into the EWMA (λ=0.94 → ~11-day half-life) would overstate σ
    for weeks after the gap — *understating* every subsequent σ-move. Dropped
    (not zeroed) returns leave the variance carried across the gap; with
    ``ignore_na=False`` the skipped position still ages the older observations,
    approximating one extra decay step for the missing stretch.

    Floor: the EWMA is a pure function of *recent* returns, so a series that
    goes quiet — a suspended ticker, an ETC that stops repricing, anything gone
    stale in a group that isn't pruned — decays it smoothly toward zero, and the
    first real move divides by almost nothing. Guarding only exact zero (which
    floating point rarely reaches) never caught this. The forecast is therefore
    floored at a fraction of the asset's own long-run vol, estimated by an
    *expanding* stdev so no future return leaks into a historical bar's
    denominator. Below ``VNR_SIGMA_FLOOR_MIN_OBS`` observations the estimate is
    NaN and no floor applies.
    """
    returns = closes.pct_change()
    if gaps is not None:
        returns = returns.where(~(gaps > 1))
    # RiskMetrics zero-mean EWMA variance: sigma^2_t = lam*sigma^2_{t-1} + (1-lam)*r^2_{t-1}
    ewma_var = (returns**2).ewm(alpha=1 - lam, adjust=False, ignore_na=False).mean()
    sigma = np.sqrt(ewma_var)
    floor = returns.expanding(min_periods=sigma_floor_min_obs).std() * sigma_floor_frac
    # `floor > sigma` is False wherever floor is NaN, so early bars keep sigma.
    sigma = sigma.where(~(floor > sigma), floor)
    return sigma.replace(0, float("nan"))


def volatility_normalized_return(
    closes: pd.Series,
    lam: float = VNR_LAMBDA,
    gaps: pd.Series | None = None,
    sigma_floor_frac: float = VNR_SIGMA_FLOOR_FRAC,
    sigma_floor_min_obs: int = VNR_SIGMA_FLOOR_MIN_OBS,
) -> pd.Series:
    """Volatility-normalized daily return — a "sigma move" / return z-score.

    Expresses each day's close-to-close return in units of the asset's own
    recent volatility, so moves become comparable across assets regardless of
    how volatile each one usually is: a +3% day in a calm name can be a bigger
    event (larger sigma move) than a +6% day in a high-beta name. A value of
    +2.0 means "today's up-move was twice the size recent volatility predicted".

    Volatility is a RiskMetrics-style zero-mean EWMA forecast built from returns
    through the *previous* day (``shift(1)``), so a large move does not deflate
    its own score. ``lam`` is the EWMA decay (RiskMetrics daily default 0.94);
    a larger lam means longer memory. Unlike a fixed rolling window, the EWMA
    has no hard edge, so an old shock decays smoothly instead of dropping out
    abruptly and stepping the score ("ghosting").

    Gap guard: ``pct_change`` is positional, so when a session is missing from
    the stored series the "daily" return actually spans several sessions while
    the denominator stays a one-day forecast — inflating the score by ~√N for
    an N-session hole (issue #559). Bars whose previous stored bar is more than
    one session back are therefore NaN'd rather than reported: the honest
    statement is "this is not a verified single-day return", not a fabricated
    single-day figure. ``gaps`` is a precomputed :func:`session_gap_days`
    series (``compute_indicators`` passes a venue-calendar-exact one); when
    omitted, the business-day fallback is derived from the index, in which
    case exchange holidays trip the guard too and conservatively blank the
    bar after a holiday.
    """
    if gaps is None:
        gaps = session_gap_days(closes.index)
    returns = closes.pct_change()
    # Forecast vol from data through the previous day; guard flat series (0 -> NaN).
    # The forecast gets the same gap series so gap-spanning returns can't
    # contaminate the denominator either (they would understate later σ-moves).
    sigma_forecast = _ewma_daily_vol(
        closes, lam, gaps, sigma_floor_frac, sigma_floor_min_obs,
    ).shift(1)
    return (returns / sigma_forecast).where(~(gaps > 1))


def adx(df: pd.DataFrame, period: int = 14) -> dict[str, pd.Series]:
    """Average Directional Index with +DI and -DI using Wilder's smoothing.

    ADX measures trend strength (0-100):
      >25 = trending, 20-25 = weak/forming, <20 = range-bound.
    +DI/-DI indicate trend direction.
    """
    high = df["high"]
    low = df["low"]

    # Directional movement
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(0.0, index=df.index)
    minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up_move > down_move) & (up_move > 0)] = up_move
    minus_dm[(down_move > up_move) & (down_move > 0)] = down_move

    atr_series = atr(df, period)

    # Smoothed directional indicators
    plus_di = 100 * _wilder_smooth(plus_dm, period) / atr_series
    minus_di = 100 * _wilder_smooth(minus_dm, period) / atr_series

    # Directional index and smoothed ADX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx_series = _wilder_smooth(dx, period)

    return {"adx": adx_series, "plus_di": plus_di, "minus_di": minus_di}


def choppiness_index(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Choppiness Index — measures whether the market is trending or ranging.

    CHOP = 100 × LOG10(SUM(TR, period) / (HH(period) - LL(period))) / LOG10(period)

    Values 0-100: >61 = choppy/ranging, <38 = trending. Direction-agnostic.
    """
    tr = _true_range(df)
    tr_sum = tr.rolling(window=period).sum()
    hh = df["high"].rolling(window=period).max()
    ll = df["low"].rolling(window=period).min()
    hl_range = hh - ll
    # Avoid log(0) / division by zero — replace zero ranges with NaN
    hl_range = hl_range.replace(0, float("nan"))
    return 100 * np.log10(tr_sum / hl_range) / np.log10(period)


def normalized_force_index(
    df: pd.DataFrame, ema_period: int = 13, short_vol: int = 20, long_vol: int = 200,
) -> dict[str, pd.Series]:
    """Normalized Elder's Force Index — EFI divided by average volume.

    Short NEFI = EMA(13) of EFI / SMA(Volume, 20)  — responsive, entry timing
    Long NEFI  = EMA(13) of EFI / SMA(Volume, 200) — smooth, trend confirmation

    Normalizes force to price-change scale so values are comparable across
    assets regardless of their absolute volume levels.
    """
    efi = (df["close"] - df["close"].shift(1)) * df["volume"]

    avg_vol_short = df["volume"].rolling(window=short_vol).mean().replace(0, float("nan"))
    avg_vol_long = df["volume"].rolling(window=long_vol).mean().replace(0, float("nan"))

    nefi_short = ema(efi / avg_vol_short, ema_period)
    nefi_long = ema(efi / avg_vol_long, ema_period)

    return {"nefi_short": nefi_short, "nefi_long": nefi_long}


def chaikin_money_flow(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Chaikin Money Flow — volume-weighted buying/selling pressure.

    MF_Multiplier = ((Close - Low) - (High - Close)) / (High - Low)
    MF_Volume = MF_Multiplier × Volume
    CMF(period) = SUM(MF_Volume, period) / SUM(Volume, period)

    Ranges -1 to +1. Positive = buying pressure, negative = selling pressure.
    """
    hl_range = df["high"] - df["low"]
    # Avoid division by zero for doji bars (high == low)
    hl_range = hl_range.replace(0, float("nan"))
    mf_multiplier = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl_range
    mf_volume = mf_multiplier * df["volume"]
    return mf_volume.rolling(window=period).sum() / df["volume"].rolling(window=period).sum()


def force_index(df: pd.DataFrame, ema_period: int = 13) -> dict[str, pd.Series]:
    """Elder's Force Index — per-bar price-volume conviction.

    Raw: (Close - Previous Close) × Volume
    Smoothed: 13-period EMA of raw Force Index

    Positive = bullish force, negative = bearish force.
    Big move + low force = suspect; big move + high force = conviction.
    """
    raw = (df["close"] - df["close"].shift(1)) * df["volume"]
    smoothed = ema(raw, ema_period)
    return {"force_raw": raw, "force_ema": smoothed}


def volume_stats(df: pd.DataFrame, period: int = 20) -> dict[str, pd.Series]:
    """Volume and average volume (SMA of volume)."""
    return {"volume": df["volume"], "avg_volume": df["volume"].rolling(window=period).mean()}


def relative_volume(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Relative Volume (RVOL) — a session's volume vs its recent normal.

    RVOL = volume / SMA(volume over the *prior* ``period`` sessions).

    Puts volume on a cross-asset scale: 1.0 is an average day, >1.5 elevated,
    >2 unusually heavy (news / breakout / capitulation), <0.5 quiet. The
    baseline is shifted by one bar so the current session is excluded from its
    own average — a volume spike therefore doesn't inflate the reference it is
    measured against. A flat/zero baseline becomes NaN to guard the division.

    Note: this is the daily-over-N-days RVOL. An intraday "volume so far vs
    average volume at this time of day" measure would need minute bars the
    daily pipeline doesn't carry.
    """
    baseline = df["volume"].shift(1).rolling(window=period).mean().replace(0, float("nan"))
    return df["volume"] / baseline


def bb_position(close: float, upper: float, middle: float, lower: float) -> str:
    """Classify where price sits relative to Bollinger Bands."""
    if close > upper:
        return "above"
    elif close > middle:
        return "upper"
    elif close > lower:
        return "lower"
    else:
        return "below"


# ---------------------------------------------------------------------------
# Indicator registry
# ---------------------------------------------------------------------------

def _macd_snapshot_derived(row: pd.Series) -> dict:
    """Derive MACD signal direction from latest row."""
    if pd.notna(row["macd"]) and pd.notna(row["macd_signal"]):
        return {"macd_signal_dir": "bullish" if row["macd"] > row["macd_signal"] else "bearish"}
    return {"macd_signal_dir": None}


def _bb_snapshot_derived(row: pd.Series) -> dict:
    """Derive Bollinger Band position from latest row."""
    if pd.notna(row["bb_upper"]) and pd.notna(row["bb_middle"]) and pd.notna(row["bb_lower"]):
        return {"bb_position": bb_position(row["close"], row["bb_upper"], row["bb_middle"], row["bb_lower"])}
    return {"bb_position": None}


def _atr_post_compute(result: pd.DataFrame) -> None:
    """Compute ATR% (ATR / close × 100) per bar after ATR is computed."""
    result["atr_pct"] = result["atr"] / result["close"] * 100


def _atr_snapshot_derived(row: pd.Series) -> dict:
    """Derive ATR% (ATR as percentage of close price) from latest row."""
    atr_val = row.get("atr")
    close_val = row.get("close")
    if pd.notna(atr_val) and pd.notna(close_val) and close_val != 0:
        return {"atr_pct": round(float(atr_val) / float(close_val) * 100, 2)}
    return {"atr_pct": None}


def _adx_snapshot_derived(row: pd.Series) -> dict:
    """Derive ADX trend strength classification from latest row."""
    if pd.notna(row["adx"]):
        val = row["adx"]
        if val > 25:
            return {"adx_trend": "strong"}
        elif val >= 20:
            return {"adx_trend": "weak"}
        else:
            return {"adx_trend": "absent"}
    return {"adx_trend": None}


def _nefi_snapshot_derived(row: pd.Series) -> dict:
    """Derive NEFI signal from short/long crossover."""
    short = row.get("nefi_short")
    long_ = row.get("nefi_long")
    if pd.notna(short) and pd.notna(long_):
        return {"nefi_signal": "bullish" if short > long_ else "bearish"}
    return {"nefi_signal": None}


def _cmf_snapshot_derived(row: pd.Series) -> dict:
    """Derive CMF signal from latest row."""
    if pd.notna(row.get("cmf")):
        return {"cmf_signal": "buying" if row["cmf"] > 0 else "selling"}
    return {"cmf_signal": None}


def _rvol_snapshot_derived(row: pd.Series) -> dict:
    """Derive a qualitative relative-volume state from the latest row."""
    val = row.get("rvol")
    if pd.notna(val):
        if val >= 2:
            return {"rvol_state": "high"}
        elif val >= 1.5:
            return {"rvol_state": "elevated"}
        elif val < 0.5:
            return {"rvol_state": "quiet"}
        return {"rvol_state": "normal"}
    return {"rvol_state": None}


def _chop_snapshot_derived(row: pd.Series) -> dict:
    """Derive choppiness state from latest row."""
    if pd.notna(row.get("chop")):
        val = row["chop"]
        if val > 61:
            return {"chop_state": "choppy"}
        elif val < 38:
            return {"chop_state": "trending"}
        else:
            return {"chop_state": "neutral"}
    return {"chop_state": None}


@dataclass(frozen=True)
class IndicatorDef:
    """Declarative definition of a technical indicator."""

    func: Callable
    params: dict = field(default_factory=dict)
    output_fields: list[str] = field(default_factory=list)
    result_mapping: dict[str, str] | None = None  # func result key → DataFrame column name
    decimals: int = 2
    warmup_periods: int = 0
    snapshot_derived: Callable[[pd.Series], dict] | None = None
    uses_ohlc: bool = False  # When True, func receives the full DataFrame instead of just closes
    # Per-field decimal overrides (field → decimals). Falls back to `decimals` if absent.
    field_decimals: dict[str, int] = field(default_factory=dict)
    # Post-compute callback: receives the result DataFrame and adds derived columns.
    post_compute: Callable[[pd.DataFrame], None] | None = None
    # When True, func receives the precomputed session-gap series as `gaps=`.
    needs_gaps: bool = False


INDICATOR_REGISTRY: dict[str, IndicatorDef] = {
    "rsi": IndicatorDef(
        func=rsi,
        params={"period": 14},
        output_fields=["rsi", "rsi_delta", "rsi_delta_sigma"],
        decimals=2,
        warmup_periods=14,
        field_decimals={"rsi_delta": 1, "rsi_delta_sigma": 1},
    ),
    "sma_20": IndicatorDef(
        func=sma,
        params={"period": 20},
        output_fields=["sma_20"],
        decimals=4,
        warmup_periods=20,
    ),
    "sma_50": IndicatorDef(
        func=sma,
        params={"period": 50},
        output_fields=["sma_50"],
        decimals=4,
        warmup_periods=50,
    ),
    "bb": IndicatorDef(
        func=bollinger_bands,
        params={"period": 20, "std_dev": 2.0},
        output_fields=["bb_upper", "bb_middle", "bb_lower"],
        result_mapping={"upper": "bb_upper", "middle": "bb_middle", "lower": "bb_lower"},
        decimals=4,
        warmup_periods=20,
        snapshot_derived=_bb_snapshot_derived,
    ),
    "macd": IndicatorDef(
        func=macd,
        params={"fast": 12, "slow": 26, "signal": 9},
        output_fields=[
            "macd", "macd_signal", "macd_hist",
            "macd_hist_delta", "macd_hist_delta_sigma",
            "macd_delta", "macd_delta_sigma",
        ],
        result_mapping={"macd": "macd", "signal": "macd_signal", "histogram": "macd_hist"},
        decimals=4,
        warmup_periods=35,
        snapshot_derived=_macd_snapshot_derived,
        field_decimals={
            "macd_hist_delta": 2, "macd_hist_delta_sigma": 1,
            "macd_delta": 2, "macd_delta_sigma": 1,
        },
    ),
    "atr": IndicatorDef(
        func=atr,
        params={"period": 14},
        output_fields=["atr", "atr_pct"],
        decimals=4,
        warmup_periods=14,
        uses_ohlc=True,
        snapshot_derived=_atr_snapshot_derived,
        field_decimals={"atr_pct": 2},
        post_compute=_atr_post_compute,
    ),
    "adx": IndicatorDef(
        func=adx,
        params={"period": 14},
        output_fields=["adx", "plus_di", "minus_di"],
        result_mapping={"adx": "adx", "plus_di": "plus_di", "minus_di": "minus_di"},
        decimals=2,
        warmup_periods=28,
        snapshot_derived=_adx_snapshot_derived,
        uses_ohlc=True,
    ),
    "volume": IndicatorDef(
        func=volume_stats,
        params={"period": 20},
        output_fields=["volume", "avg_volume"],
        result_mapping={"volume": "volume", "avg_volume": "avg_volume"},
        decimals=0,
        warmup_periods=20,
        uses_ohlc=True,
    ),
    "rvol": IndicatorDef(
        func=relative_volume,
        params={"period": 20},
        output_fields=["rvol"],
        decimals=2,
        # 20-session baseline + 1 shifted bar before the first finite value.
        warmup_periods=21,
        uses_ohlc=True,
        snapshot_derived=_rvol_snapshot_derived,
    ),
    "nefi": IndicatorDef(
        func=normalized_force_index,
        params={"ema_period": 13, "short_vol": 20, "long_vol": 200},
        output_fields=["nefi_short", "nefi_long"],
        result_mapping={"nefi_short": "nefi_short", "nefi_long": "nefi_long"},
        decimals=2,
        warmup_periods=200,
        uses_ohlc=True,
        snapshot_derived=_nefi_snapshot_derived,
    ),
    "cmf": IndicatorDef(
        func=chaikin_money_flow,
        params={"period": 20},
        output_fields=["cmf"],
        decimals=3,
        warmup_periods=20,
        uses_ohlc=True,
        snapshot_derived=_cmf_snapshot_derived,
    ),
    "chop": IndicatorDef(
        func=choppiness_index,
        params={"period": 14},
        output_fields=["chop"],
        decimals=1,
        warmup_periods=14,
        uses_ohlc=True,
        snapshot_derived=_chop_snapshot_derived,
    ),
    "vnr": IndicatorDef(
        func=volatility_normalized_return,
        params={
            "lam": VNR_LAMBDA,
            "sigma_floor_frac": VNR_SIGMA_FLOOR_FRAC,
            "sigma_floor_min_obs": VNR_SIGMA_FLOOR_MIN_OBS,
        },
        # vnr_sigma and vnr_gap_sessions are gap-aware companions set directly
        # by compute_indicators, which owns the session-gap series.
        output_fields=["vnr", "vnr_sigma", "vnr_gap_sessions"],
        decimals=2,
        warmup_periods=60,
        field_decimals={"vnr_sigma": 6, "vnr_gap_sessions": 0},
        needs_gaps=True,
    ),
}


def get_all_output_fields() -> list[str]:
    """Return all output field names from the registry."""
    fields: list[str] = []
    for defn in INDICATOR_REGISTRY.values():
        fields.extend(defn.output_fields)
    return fields


def get_max_warmup_periods() -> int:
    """Return the maximum warmup periods across all registered indicators."""
    return max((d.warmup_periods for d in INDICATOR_REGISTRY.values()), default=0)


def _batch_history_period() -> str:
    """Smallest canonical fetch period whose calendar span covers WARMUP_DAYS.

    The batch snapshot path fetches by provider period string, so the period
    must cover the registry's largest warmup (NEFI's 200-bar volume baseline —
    a shorter fetch leaves nefi_long/nefi_signal permanently null).
    """
    from app.constants import PERIOD_DAYS, WARMUP_DAYS

    for period, days in sorted(PERIOD_DAYS.items(), key=lambda kv: kv[1]):
        if days >= WARMUP_DAYS:
            return period
    return max(PERIOD_DAYS, key=lambda p: PERIOD_DAYS[p])


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------


def build_indicator_snapshot(indicators: pd.DataFrame) -> IndicatorSnapshotBase:
    """Build the latest-values snapshot from a computed indicators DataFrame.

    Returns close, change_pct, and all registry indicator fields (with derived
    fields) in ``values``. Insufficient history yields an all-default snapshot.
    """
    if indicators.empty or len(indicators) < 2:
        return IndicatorSnapshotBase(bars=len(indicators))

    latest = indicators.iloc[-1]
    prev_close = indicators.iloc[-2]["close"]

    change_pct = None
    # A gap-flagged latest bar means the previous *row* is not the previous
    # *session* — the difference would be a multi-session move mislabelled as
    # a 1-day change (schema documents change_pct as daily). Leave it None,
    # matching the suppressed σ-Move beside it.
    latest_is_gap = pd.notna(latest.get("vnr_gap_sessions"))
    if prev_close and prev_close != 0 and not latest_is_gap:
        change_pct = round((latest["close"] - prev_close) / prev_close * 100, 2)

    # Collect all indicator values from registry
    values: dict[str, float | str | None] = {}
    for defn in INDICATOR_REGISTRY.values():
        for col in defn.output_fields:
            decimals = defn.field_decimals.get(col, defn.decimals)
            values[col] = safe_round(latest[col], decimals)
        if defn.snapshot_derived:
            values.update(defn.snapshot_derived(latest))

    last_dt = indicators.index[-1]
    as_of = last_dt.date() if hasattr(last_dt, "date") else last_dt

    return IndicatorSnapshotBase(
        close=round(latest["close"], 2),
        as_of=as_of if isinstance(as_of, date) else None,
        change_pct=change_pct,
        bars=len(indicators),
        values=values,
    )


def _get_delta_fields() -> list[str]:
    """Return indicator fields that have corresponding *_delta output fields in the registry."""
    delta_fields: list[str] = []
    for defn in INDICATOR_REGISTRY.values():
        for col in defn.output_fields:
            if f"{col}_delta" in defn.output_fields:
                delta_fields.append(col)
    return delta_fields


def _compute_deltas(result: pd.DataFrame, window: int = 20, gaps: pd.Series | None = None) -> None:
    """Add daily deltas and outlier sigma flags for selected indicator fields.

    For each target field:
      - {field}_delta = day-over-day difference
      - {field}_delta_sigma = |Δ| expressed in rolling σ units, only when
        the absolute delta exceeds mean + 2σ of the rolling window (else NaN).

    ``gaps`` (a :func:`session_gap_days` series) blanks the delta on bars whose
    previous stored bar is more than one session back — ``diff()`` there is a
    multi-session move, which would both earn a fake outlier badge and inflate
    the rolling σ baseline (suppressing genuine outliers for the next
    ``window`` bars). The NaN also makes the rolling stats undersized for the
    affected windows (``min_periods=window``), so no flag fires on bad data.
    """
    for field_name in _get_delta_fields():
        if field_name not in result.columns:
            continue
        series = result[field_name]
        delta = series.diff()
        if gaps is not None:
            delta = delta.where(~(gaps > 1))
        result[f"{field_name}_delta"] = delta

        abs_delta = delta.abs()
        rolling_mean = abs_delta.rolling(window=window, min_periods=window).mean()
        rolling_std = abs_delta.rolling(window=window, min_periods=window).std()

        sigma = (abs_delta - rolling_mean) / rolling_std
        # Only keep sigma when |Δ| exceeds the 2σ threshold
        result[f"{field_name}_delta_sigma"] = sigma.where(
            abs_delta > rolling_mean + 2 * rolling_std
        )


def compute_indicators(
    df: pd.DataFrame, session_dates: set[date] | None = None,
) -> pd.DataFrame:
    """Compute all indicators and return a DataFrame with indicator columns.

    Input df must have a 'close' column (and 'high'/'low' for some indicators).
    Iterates the INDICATOR_REGISTRY to compute each indicator.

    ``session_dates`` — the venue's trading sessions covering the index range
    (from ``AssetRef(...).venue``) — makes the σ-Move gap guard exact:
    holidays are recognized as non-sessions instead of tripping the
    business-day fallback (issue #559).
    """
    closes = df["close"]

    # One gap series shared by the vnr guard and the vnr_gap_sessions flag.
    gap_series = session_gap_days(df.index, session_dates)

    result = pd.DataFrame(index=df.index)
    result["close"] = closes

    for defn in INDICATOR_REGISTRY.values():
        # OHLC indicators (ATR, ADX) receive the full DataFrame;
        # close-only indicators receive just the close Series.
        input_data = df if defn.uses_ohlc else closes
        kwargs = {**defn.params, "gaps": gap_series} if defn.needs_gaps else defn.params
        output = defn.func(input_data, **kwargs)

        if isinstance(output, pd.Series):
            # Single-output indicator (e.g. rsi, sma, atr)
            result[defn.output_fields[0]] = output
        elif isinstance(output, dict) and defn.result_mapping:
            # Multi-output indicator (e.g. macd, bollinger_bands, adx)
            for func_key, col_name in defn.result_mapping.items():
                result[col_name] = output[func_key]

        if defn.post_compute:
            defn.post_compute(result)

    # σ-Move companions, both gap-aware. vnr_sigma is the forward vol forecast
    # the UI divides a live intraday return by (see _ewma_daily_vol — the gap
    # series keeps hole-spanning returns out of the variance). vnr_gap_sessions
    # flags the bars the gap guard suppressed with the gap width, so the UI can
    # explain the blank (NaN everywhere else → None in responses).
    result["vnr_sigma"] = _ewma_daily_vol(closes, VNR_LAMBDA, gap_series)
    result["vnr_gap_sessions"] = gap_series.where(gap_series > 1)

    _compute_deltas(result, gaps=gap_series)

    return result


async def compute_batch_indicator_snapshots(
    symbols: list[str],
) -> list[SymbolIndicatorSnapshot]:
    """Compute indicator snapshots for multiple symbols in batch.

    Fetches enough history to cover indicator warmup (see
    :func:`_batch_history_period`) and currencies via the configured price
    provider, then computes indicators and builds snapshots for each symbol.

    Returns one :class:`SymbolIndicatorSnapshot` per symbol; symbols without
    usable history get a default snapshot carrying just symbol/currency.
    """
    if not symbols:
        return []

    provider = get_price_provider()
    histories = await provider.batch_fetch_history(symbols, period=_batch_history_period())
    currencies = await provider.batch_fetch_currencies(symbols)

    results: list[SymbolIndicatorSnapshot] = []
    for sym in symbols:
        currency = currencies.get(sym, "USD")
        df = histories.get(sym)
        if df is None or df.empty or len(df) < 2:
            results.append(SymbolIndicatorSnapshot(
                symbol=sym, currency=currency, bars=0 if df is None else len(df),
            ))
            continue

        venue = AssetRef(sym).venue
        sessions = venue.session_dates_for_index(df.index) if venue else None
        snapshot = build_indicator_snapshot(compute_indicators(df, session_dates=sessions))
        results.append(SymbolIndicatorSnapshot(
            symbol=sym, currency=currency, close=snapshot.close,
            change_pct=snapshot.change_pct, bars=snapshot.bars, values=snapshot.values,
        ))

    # Fundamentals are merged from cache by the caller (non-blocking).
    # See fundamentals_cache.merge_fundamentals_into_batch().

    return results
