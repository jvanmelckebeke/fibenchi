"""Technical indicator computations on price data."""

import pandas as pd


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
