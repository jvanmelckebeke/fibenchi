"""Technical indicator computations on price data."""

from __future__ import annotations

import pandas as pd

from app.services.yahoo import batch_fetch_currencies, batch_fetch_history


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


def build_indicator_snapshot(indicators: pd.DataFrame) -> dict:
    """Build a dict of latest indicator values from a computed indicators DataFrame.

    Returns fields common to both HoldingIndicatorResponse and
    ConstituentIndicatorResponse: close, change_pct, rsi, sma_20, sma_50,
    macd/signal/hist/dir, bb_upper/middle/lower/position.
    """
    if indicators.empty or len(indicators) < 2:
        return {}

    latest = indicators.iloc[-1]
    prev_close = indicators.iloc[-2]["close"]

    change_pct = None
    if prev_close and prev_close != 0:
        change_pct = round((latest["close"] - prev_close) / prev_close * 100, 2)

    macd_dir = None
    if pd.notna(latest["macd"]) and pd.notna(latest["macd_signal"]):
        macd_dir = "bullish" if latest["macd"] > latest["macd_signal"] else "bearish"

    bb_pos = None
    if pd.notna(latest["bb_upper"]) and pd.notna(latest["bb_middle"]) and pd.notna(latest["bb_lower"]):
        bb_pos = bb_position(latest["close"], latest["bb_upper"], latest["bb_middle"], latest["bb_lower"])

    return {
        "close": round(latest["close"], 2),
        "change_pct": change_pct,
        "rsi": safe_round(latest["rsi"], 2),
        "sma_20": safe_round(latest["sma_20"], 2),
        "sma_50": safe_round(latest["sma_50"], 2),
        "macd": safe_round(latest["macd"], 4),
        "macd_signal": safe_round(latest["macd_signal"], 4),
        "macd_hist": safe_round(latest["macd_hist"], 4),
        "macd_signal_dir": macd_dir,
        "bb_upper": safe_round(latest["bb_upper"], 2),
        "bb_middle": safe_round(latest["bb_middle"], 2),
        "bb_lower": safe_round(latest["bb_lower"], 2),
        "bb_position": bb_pos,
    }


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all indicators and return a DataFrame with indicator columns.

    Input df must have a 'close' column (and 'high'/'low' for some indicators).
    """
    closes = df["close"]
    macd_data = macd(closes)
    bb_data = bollinger_bands(closes)

    result = pd.DataFrame(index=df.index)
    result["close"] = closes
    result["rsi"] = rsi(closes)
    result["sma_20"] = sma(closes, 20)
    result["sma_50"] = sma(closes, 50)
    result["bb_upper"] = bb_data["upper"]
    result["bb_middle"] = bb_data["middle"]
    result["bb_lower"] = bb_data["lower"]
    result["macd"] = macd_data["macd"]
    result["macd_signal"] = macd_data["signal"]
    result["macd_hist"] = macd_data["histogram"]

    return result


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
