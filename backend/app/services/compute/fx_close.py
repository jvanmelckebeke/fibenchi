"""Recover the session close that FX daily bars don't carry.

Yahoo's settled daily bar for an ``=X`` pair reports ``close`` within a pip or
two of its own ``open``. Measured over 2y of bars for eight pairs (JPY=X,
EURUSD=X, GBPUSD=X, EURJPY=X, AUDUSD=X, USDCHF=X, EURGBP=X, MXN=X, 4,128 bars):
median body ``|close-open| / (high-low)`` is 0.000-0.016 and p90 is 0.056. The
same measure over the instruments Fibenchi actually holds sits at 0.43-0.50
(AAPL 0.433, IWDA.AS 0.433, 7203.T 0.500), and the two continuous markets that
are the closest analogue to FX — crypto and futures — sit there too (BTC-USD
0.430, GC=F 0.645, CL=F 0.452, ES=F 0.468). So the defect is FX-shaped, not
"continuous market"-shaped, and nothing else needs this.

Stored verbatim, that makes every close-based reading — MACD, RSI, the moving
averages, σ-Move — run on a series of *opens*, i.e. one session stale, and
leaves candles as hairline bodies under full-height wicks.

**Where the real close comes from.** In a market that trades around the clock,
the next bar's open *is* this bar's close. The check on that claim is BTC-USD,
where both numbers are correct: ``|close - next_open| / (high-low)`` is 0.001
over 731 bars. So the shift is not an approximation FX forces on us; it is what
the two quantities mean in a continuous market.

Against a close reconstructed from ``interval="1h"`` bars over 1y and six
pairs, the shift cuts the median error from 0.238% to 0.016% and p90 from
0.673% to 0.104%. The residual is Yahoo's daily window ending before the next
one starts, mostly across a weekend.

**Why the close is not clamped into the provider's high/low.** It lands outside
them on 25.5% of bars (p75 of the excursion is 0.006 of the range, p99 is 1.26
ranges), so clamping is a real choice rather than a formality — and it is the
worse one, losing on every percentile against the same hourly truth (median
0.020% vs 0.016%, p90 0.168% vs 0.104%). The range is widened to contain the
recovered close instead, which also keeps a candle from printing a body outside
its own wick.

**Why this re-decides from the frame every fetch rather than recording what it
did.** Same reasoning as ``normalize_splits``: the evidence and the decision
live in the same frame, so no stored state can go stale, and the day Yahoo
starts publishing a real FX close the body test stops matching and this stops
firing on its own.
"""

import logging

import pandas as pd

from app.domain.instrument import classify

logger = logging.getLogger(__name__)

# How small a frame's median candle body has to be before its closes are read
# as opens in disguise. The two populations measured in the module docstring
# are 0.016 (worst FX) and 0.430 (healthiest non-FX), so this sits ~6x above
# one and ~4x below the other; anything in between is a frame neither reading
# explains, which is left alone.
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


def normalize_fx_close(df: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
    """Rewrite an FX frame's closes as the next bar's open.

    Returns ``df`` unchanged for anything that isn't an ``=X`` pair, and for an
    FX frame whose bodies show it already carries real closes. The trailing bar
    has no successor and keeps the provider's value — which is the right one
    while it is still forming, since Yahoo tracks the live price there.
    """
    if df.empty or not classify(symbol or "").kind.is_fx:
        return df
    if not {"open", "high", "low", "close"} <= set(df.columns):
        return df
    if not _reads_as_opens(df):
        return df

    out = df.copy()
    opens = pd.to_numeric(out["open"], errors="coerce")
    close = pd.to_numeric(out["close"], errors="coerce")
    recovered = opens.shift(-1).fillna(close)

    out["close"] = recovered
    out["high"] = pd.to_numeric(out["high"], errors="coerce").combine(recovered, max)
    out["low"] = pd.to_numeric(out["low"], errors="coerce").combine(recovered, min)

    logger.info(
        "%s: recovered %d FX close(s) from the following bar's open",
        symbol or "?", len(out) - 1,
    )
    return out
