"""Technical indicator computations on price data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from app.services.yahoo import batch_fetch_currencies, batch_fetch_history
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
        output = defn.func(closes, **defn.params)

        if isinstance(output, pd.Series):
            # Single-output indicator (e.g. rsi, sma)
            result[defn.output_fields[0]] = output
        elif isinstance(output, dict) and defn.result_mapping:
            # Multi-output indicator (e.g. macd, bollinger_bands)
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

    histories = batch_fetch_history(symbols, period="3mo")
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
