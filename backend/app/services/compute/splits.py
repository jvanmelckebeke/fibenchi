"""Rebase a provider price frame onto the asset's current share basis.

A stock split makes two adjacent bars incomparable: MNST's 2026-08-11 2:1
split put 90.36 next to 45.53, and every indicator that reads a return, a
moving average or a band across that boundary computed on two different units
(#648). The -49% pseudo-return squared into the EWMA variance pinned
``vnr_sigma`` at 10.7% daily against a true ~1.5%, so a genuine +4.09% day
scored 0.37σ and ranked near the *bottom* of a σ-ranked scan.

Yahoo reports the event and declines to act on it. Eight days after the MNST
split, ``range=6mo&interval=1d`` still returned ``close=90.36`` *and*
``adjclose=90.36`` for 2026-08-07, so switching to the adjusted column fixes
nothing and we have to apply the factor ourselves.

**Why this is a pure function of the frame and keeps no record of what it
did.** The obvious design is a table of applied splits, consulted so a re-fetch
can't double-adjust. That invariant cannot hold: such a ledger makes a claim
about stored rows, and the next upsert overwrites those rows with whatever
basis the provider felt like sending. Yahoo served MNST's 2026-08-10 bar
already-adjusted (45.715), then ``null``, then unadjusted (91.43) inside nine
days — its adjustment state is not stable in either direction. So the ledger
would buy fake idempotency at the cost of a migration.

Running on the raw frame every fetch is idempotent by construction instead,
because the evidence and the decision live in the same frame: a 2:1 split means
the frame's own step across the ex-date is either ~0.5 (nobody adjusted, so we
do) or ~1.0 (already adjusted, so we don't). No stored state can go stale, and
the day Yahoo finally adjusts its history, this stops adjusting with it.
"""

import logging
import math

import pandas as pd

logger = logging.getLogger(__name__)

# yahooquery joins the chart endpoint's split events onto the frame, carrying
# numerator/denominator on the ex-date bar and 0.0 elsewhere. Yahoo returns
# ``events`` whether or not it is asked to, so neither fetch path has to pass
# the parameter.
#
# The column is absent entirely for a symbol Yahoo reports no splits for, which
# is most of them, so its absence says nothing and is not worth a log line. The
# canary for "yahooquery stopped emitting this" is
# ``heal_split_discontinuities``: it warns on a split-sized step that survives
# a full re-fetch, which is evidence rather than inference.
SPLIT_COLUMN = "splits"

PRICE_COLUMNS = ("open", "high", "low", "close", "adjclose")

# How far the frame's own step across an ex-date may sit from the split ratio
# and still corroborate it, as an absolute log-ratio distance (~28%).
#
# The two hypotheses are far apart — for a 2:1 split the step is either 0.5 or
# 1.0, 0.69 apart in log space — so this band separates them with room to
# spare while still refusing an ambiguous middle. Refusing matters: a bare
# nearest-hypothesis rule would read a real -30% day as a 2:1 split and
# "correct" it into +40%. Anything this cannot corroborate is left alone, and
# the volatility model's own guard is what keeps the uncorrected step from
# being scored.
SPLIT_CORROBORATION_LOG_TOL = 0.25

# A bar-to-bar step large enough to be worth asking the provider about, as a
# factor in either direction. Used only by ``heal_split_discontinuities`` to
# decide where to *look*; the corroboration band above is what decides whether
# anything is actually applied, so a loose value here costs a wasted re-fetch
# and can never cause a wrong adjustment.
#
# Bounded from both sides by measurement over 44,457 stored bars. It has to sit
# below 1.5 or a 3:2 split is never examined, and comfortably above the largest
# genuine single-session moves in the book — IBM's 2026-07-14 fall from 290.23
# to 217.07 and MDA.TO's 2025-09-08 fall from 44.01 to 32.99, both 0.75 and
# both confirmed against the provider as real, split-free sessions. 1.4 leaves
# ~7% of headroom on the split side and ~30% on the ordinary-move side.
#
# At this value the current book yields 9 candidates: MNST's split, RR.L's
# currency rebasing (#654) and 7 real earnings moves, each of which costs one
# re-fetch once and is then remembered as unexplained.
#
# Lives here rather than in the heal job so "split-sized" has one definition.
SPLIT_STEP_FACTOR = 1.4

def _confirmed_ratios(df: pd.DataFrame, symbol: str | None) -> pd.Series:
    """Per-bar split ratio, but only where the frame's own prices back it up.

    1.0 everywhere else, so the result composes by multiplication.
    """
    raw = pd.to_numeric(df[SPLIT_COLUMN], errors="coerce")
    closes = pd.to_numeric(df["close"], errors="coerce")
    ratios = pd.Series(1.0, index=range(len(df)))

    for pos in range(len(df)):
        ratio = raw.iat[pos]
        if not (ratio > 0) or math.isclose(ratio, 1.0):
            continue

        here = closes.iat[pos]
        earlier = closes.iloc[:pos].dropna()
        earlier = earlier[earlier > 0]
        if pd.isna(here) or here <= 0 or earlier.empty:
            # The ex-date bar opens the frame, or the prices around it are
            # unusable. Adjusting on the event alone would be adjusting blind.
            logger.info(
                "%s: split %s on %s has no usable predecessor in this frame; leaving it alone",
                symbol or "?", ratio, df.index[pos],
            )
            continue

        observed = here / earlier.iat[-1]
        drift = abs(math.log(observed) - math.log(1.0 / ratio))
        if drift > SPLIT_CORROBORATION_LOG_TOL:
            level = logger.warning if abs(math.log(observed)) > 0.1 else logger.debug
            level(
                "%s: split %s on %s not corroborated (step %.4f, expected ~%.4f); "
                "treating the frame as already adjusted",
                symbol or "?", ratio, df.index[pos], observed, 1.0 / ratio,
            )
            continue

        ratios.iat[pos] = float(ratio)

    return ratios


def _divisor(ratios: pd.Series) -> pd.Series:
    """Cumulative factor separating each bar from the frame's newest basis.

    A bar must be divided by every split that took effect *after* it, so the
    ex-date bar itself is excluded — it is already in the new basis. Reversing,
    shifting one position and running a cumulative product does that in one
    pass, and composes correctly when a frame spans several splits.
    """
    return ratios[::-1].shift(1).fillna(1.0).cumprod()[::-1]


def normalize_splits(df: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
    """Rescale pre-split bars so the whole frame is in the current share basis.

    Returns ``df`` unchanged when there is nothing to do, which is the usual
    case. Prices are divided by the cumulative factor and volume multiplied by
    it, so a pre-split bar becomes what that session would have printed had the
    split always applied.
    """
    if df.empty or "close" not in df.columns or SPLIT_COLUMN not in df.columns:
        return df

    divisor = _divisor(_confirmed_ratios(df, symbol))
    if (divisor == 1.0).all():
        return df

    out = df.copy()
    factor = divisor.to_numpy()
    for col in PRICE_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce") / factor
    if "volume" in out.columns:
        out["volume"] = pd.to_numeric(out["volume"], errors="coerce") * factor

    adjusted = int((divisor != 1.0).sum())
    logger.info(
        "%s: rebased %d pre-split bar(s) onto the current share basis (factor %.4f)",
        symbol or "?", adjusted, float(divisor.iloc[0]),
    )
    return out
