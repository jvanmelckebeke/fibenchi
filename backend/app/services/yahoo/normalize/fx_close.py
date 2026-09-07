"""Recover the session close Yahoo's FX daily bars don't carry.

A settled ``=X`` bar reports ``close`` within a pip or two of its own
``open``, so candles are bodyless and every close-based indicator runs on a
series of opens, a session stale. The real close is the next bar's open: in a
market that trades around the clock the two are the same number, which
BTC-USD confirms where both are correct — ``|close - next_open| / (high-low)``
is 0.001 over 731 bars.

Which kinds of instrument get this is ``BY_KIND``'s call in the package
``__init__``, not this module's.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# How small a frame's median candle body has to be before its closes are read
# as opens in disguise.
#
# Two measured populations, 2y of daily bars. FX medians run 0.000-0.016 with
# p90 at 0.056 (8 pairs, 4,128 bars). Everything else sits an order of
# magnitude up: AAPL 0.433, IWDA.AS 0.433, 7203.T 0.500 — and so do the two
# continuous markets that would otherwise be the suspects, crypto and futures
# (BTC-USD 0.430, GC=F 0.645, CL=F 0.452, ES=F 0.468). The defect is
# FX-shaped, not "24-hour market"-shaped. This sits ~6x above one population
# and ~4x below the other; a frame landing between them is one neither
# reading explains and is left alone.
#
# Testing the frame rather than trusting the ticker is what makes this
# self-correcting: the day Yahoo publishes a real FX close, bodies cross the
# ceiling and this stops firing without anyone noticing it had to.
FX_BODY_CEILING = 0.10

# Below this many bars with a non-zero range, a median body says nothing — a
# handful of quiet sessions would read as the defect.
MIN_BODY_SAMPLE = 5


def _reads_as_opens(df: pd.DataFrame) -> bool:
    """Whether this frame's closes are indistinguishable from its opens."""
    high = pd.to_numeric(df["high"], errors="coerce")
    low = pd.to_numeric(df["low"], errors="coerce")
    span = (high - low).where(lambda s: s > 0)
    body = (pd.to_numeric(df["close"], errors="coerce")
            - pd.to_numeric(df["open"], errors="coerce")).abs() / span
    usable = body.dropna()
    if len(usable) < MIN_BODY_SAMPLE:
        return False
    return float(usable.median()) <= FX_BODY_CEILING


def recover_fx_close(df: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
    """Rewrite a frame's closes as the following bar's open.

    Returns ``df`` unchanged when its bodies show it already carries real
    closes. The trailing bar has no successor and keeps the provider's value,
    which is the right one while it is still forming — Yahoo tracks the live
    price there.
    """
    if df.empty or not {"open", "high", "low", "close"} <= set(df.columns):
        return df
    if not _reads_as_opens(df):
        return df

    out = df.copy()
    close = pd.to_numeric(out["close"], errors="coerce")
    recovered = pd.to_numeric(out["open"], errors="coerce").shift(-1).fillna(close)

    # The recovered close lands outside the bar's own high/low on 25.5% of FX
    # bars, where Yahoo's daily window ends before the next one opens. Widening
    # the range beats the obvious alternative of clamping the close into it:
    # against a close rebuilt from hourly bars, clamping loses at every
    # percentile (median error 0.020% vs 0.016%, p90 0.168% vs 0.104%). It also
    # keeps a candle from printing a body outside its own wick.
    out["close"] = recovered
    out["high"] = pd.to_numeric(out["high"], errors="coerce").combine(recovered, max)
    out["low"] = pd.to_numeric(out["low"], errors="coerce").combine(recovered, min)

    logger.info(
        "%s: recovered %d close(s) from the following bar's open",
        symbol or "?", len(out) - 1,
    )
    return out
