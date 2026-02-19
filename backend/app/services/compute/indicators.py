"""Technical indicator computations on price data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from app.services.yahoo import _batch_fetch_history_sync, batch_fetch_currencies
from app.utils import async_threadable


def safe_round(value, decimals: int = 2) -> float | None:
    """Round a value if it is not NaN/None, otherwise return None."""
    if pd.notna(value):
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


INDICATOR_REGISTRY: dict[str, IndicatorDef] = {
    "rsi": IndicatorDef(
        func=rsi,
        params={"period": 14},
        output_fields=["rsi"],
        decimals=2,
        warmup_periods=14,
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
        output_fields=["macd", "macd_signal", "macd_hist"],
        result_mapping={"macd": "macd", "signal": "macd_signal", "histogram": "macd_hist"},
        decimals=4,
        warmup_periods=35,
        snapshot_derived=_macd_snapshot_derived,
    ),
    "atr": IndicatorDef(
        func=atr,
        params={"period": 14},
        output_fields=["atr"],
        decimals=4,
        warmup_periods=14,
        uses_ohlc=True,
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


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------


def build_indicator_snapshot(indicators: pd.DataFrame) -> dict:
    """Build a dict of latest indicator values from a computed indicators DataFrame.

    Returns close, change_pct, and all registry indicator fields (with derived fields).
    """
    if indicators.empty or len(indicators) < 2:
        return {}

    latest = indicators.iloc[-1]
    prev_close = indicators.iloc[-2]["close"]

    change_pct = None
    if prev_close and prev_close != 0:
        change_pct = round((latest["close"] - prev_close) / prev_close * 100, 2)

    result: dict = {
        "close": round(latest["close"], 2),
        "change_pct": change_pct,
    }

    # Collect all indicator values from registry
    values: dict[str, float | None] = {}
    for defn in INDICATOR_REGISTRY.values():
        for col in defn.output_fields:
            values[col] = safe_round(latest[col], defn.decimals)
        if defn.snapshot_derived:
            values.update(defn.snapshot_derived(latest))

    result["values"] = values
    return result


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all indicators and return a DataFrame with indicator columns.

    Input df must have a 'close' column (and 'high'/'low' for some indicators).
    Iterates the INDICATOR_REGISTRY to compute each indicator.
    """
    closes = df["close"]

    result = pd.DataFrame(index=df.index)
    result["close"] = closes

    for defn in INDICATOR_REGISTRY.values():
        # OHLC indicators (ATR, ADX) receive the full DataFrame;
        # close-only indicators receive just the close Series.
        input_data = df if defn.uses_ohlc else closes
        output = defn.func(input_data, **defn.params)

        if isinstance(output, pd.Series):
            # Single-output indicator (e.g. rsi, sma, atr)
            result[defn.output_fields[0]] = output
        elif isinstance(output, dict) and defn.result_mapping:
            # Multi-output indicator (e.g. macd, bollinger_bands, adx)
            for func_key, col_name in defn.result_mapping.items():
                result[col_name] = output[func_key]

    return result


@async_threadable
def compute_batch_indicator_snapshots(
    symbols: list[str],
) -> list[dict]:
    """Compute indicator snapshots for multiple symbols in batch.

    Fetches ~3 months of history and currencies via Yahoo Finance, then
    computes indicators and builds snapshots for each symbol.

    Returns a list of dicts (one per symbol) with keys:
    symbol, currency, and all build_indicator_snapshot fields.
    """
    if not symbols:
        return []

    histories = _batch_fetch_history_sync(symbols, period="3mo")
    currencies = batch_fetch_currencies(symbols)

    results = []
    for sym in symbols:
        currency = currencies.get(sym, "USD")
        df = histories.get(sym)
        if df is None or df.empty or len(df) < 2:
            results.append({"symbol": sym, "currency": currency})
            continue

        snapshot = build_indicator_snapshot(compute_indicators(df))
        results.append({"symbol": sym, "currency": currency, **snapshot})

    return results
