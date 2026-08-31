"""Rebase a provider price frame onto the asset's current share basis.

A stock split makes two adjacent bars incomparable: MNST's 2026-08-11 2:1
split put 90.36 next to 45.53, and every indicator that reads a return, a
moving average or a band across that boundary computed on two different
units. The -49% pseudo-return squared into the EWMA variance pinned
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

**What the frame has to prove.** Those two readings sit ``log(r)`` apart, which
for a 5:4 split is 0.22 rather than 0.69 — close enough that a band wide enough
to recognise one recognises both. So the test is not "is the step near the
split?" but "can this frame tell the two apart?", and it is the asset's own
session-to-session noise that decides. Exactly one reading may fall inside a
band scaled from that noise; both or neither means undecidable, and the frame
is left alone. Idempotency cuts both ways — a wrong adjustment is re-derived
identically on every fetch and never heals — so refusing is the only safe
answer to a frame that cannot settle the question.
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

# Cash-per-share columns, rebased by the same divisor as the prices. A 1.00
# dividend paid before a 2:1 split is 0.50 per share in the current basis, and
# σ-Move divides it by a rebased close — leaving it in the old basis would
# hand the total-return numerator two different units.
CASH_COLUMNS = ("dividends",)

# How close the frame's step has to sit to a hypothesis to be said to match it,
# as a log-ratio distance — sized from the frame's own noise rather than fixed.
#
# There are two hypotheses on every ex-date: the provider left the frame
# unadjusted (step ~ 1/r) or it already adjusted (step ~ 1). They sit log(r)
# apart, so how far apart they are depends on the split. A fixed band sized for
# a 2:1 (0.69 apart) admits both hypotheses for a 5:4 (0.22 apart) and applies
# the divisor to a frame that was already in the new basis — a fabricated +25%
# step, below the heal's 1.4 detection threshold, permanent because the
# stateless design re-decides the same way on every fetch.
#
# So the question is not "is the step near the split?" but "can this frame tell
# the two apart?", and what limits that is how much the price moves on its own.
# The band is therefore NOISE_K times the frame's own median absolute log
# return, and a hypothesis is accepted only when it is the *only* one inside
# it. Both inside means the frame cannot distinguish them; neither inside means
# the step is something else entirely (the real -30% day a bare
# nearest-hypothesis rule would "correct" into +40%). Both outcomes leave the
# frame alone.
#
# NOISE_K = 3 covers an ordinary session comfortably. Measured over the book's
# 46,217 stored bars, per-asset median absolute log return runs 1.14% (median
# asset), 2.29% (p90), 5.4% (p99 and max) — so the band is ~3.4% for a typical
# name and ~16% for the most volatile one held.
#
# The floor matters for the other end: a series that barely moves (an ETC that
# stops repricing, anything gone stale) yields a band near zero, and then a
# single real 6% day sits "far" from both hypotheses and every split on that
# symbol becomes undecidable. 0.05 is above the p99 asset's typical session.
NOISE_K = 3.0
MIN_SEPARATION_BAND = 0.05

# A ratio is decidable when the hypotheses are more than two bands apart, i.e.
# ``log(r) > 2 * band``: above ~1.11:1 for a typical name, ~1.38:1 for the
# noisiest. Below that an unadjusted split and an ordinary down day are the
# same evidence, and no other signal rescues it — a 5:4 split moves share
# volume by 25% against daily volume noise several times that, and Yahoo's
# ``adjclose`` matched the unadjusted ``close`` right through MNST's split.
# Nor can the heal cover it: at SPLIT_STEP_FACTOR 1.4 the book yields 11
# candidates, at 1.2 it yields 81 and at 1.1 it yields 610, against a cap of
# 10 re-fetches per run. Sub-1.1 splits are outside what price evidence
# settles, and this module says so rather than guessing.

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
# currency rebasing and 7 real earnings moves, each of which costs one
# re-fetch once and is then remembered as unexplained.
#
# Lives here rather than in the heal job so "split-sized" has one definition.
SPLIT_STEP_FACTOR = 1.4

def _separation_band(closes: pd.Series, events: pd.Series) -> float:
    """How close a step has to sit to a hypothesis to be said to match it.

    The frame's own median absolute log return, scaled by ``NOISE_K`` — an
    estimate of how far this asset moves in an ordinary session, which is
    exactly what limits how well any step can be attributed. Median rather
    than stdev, and ex-date bars excluded, so the split's own step and a
    couple of earnings days cannot inflate the band that judges them.

    Falls back to the floor when the frame is too short to say anything.
    """
    log_returns = (closes / closes.shift(1)).apply(
        lambda v: math.log(v) if v and v > 0 else float("nan")
    )
    # Drop the ex-date steps themselves and their carry into the next bar.
    on_event = events > 0
    log_returns = log_returns.where(~(on_event | on_event.shift(-1, fill_value=False)))

    usable = log_returns.abs().dropna()
    if usable.empty:
        return MIN_SEPARATION_BAND
    return max(NOISE_K * float(usable.median()), MIN_SEPARATION_BAND)


def _confirmed_ratios(df: pd.DataFrame, symbol: str | None) -> pd.Series:
    """Per-bar split ratio, but only where the frame's own prices back it up.

    1.0 everywhere else, so the result composes by multiplication.

    "Back it up" means the frame distinguishes the two hypotheses — unadjusted
    (step ~ 1/r) and already adjusted (step ~ 1) — not merely that it is near
    one of them. Exactly one must fall inside the band; see
    :data:`MIN_SEPARATION_BAND`.
    """
    raw = pd.to_numeric(df[SPLIT_COLUMN], errors="coerce")
    closes = pd.to_numeric(df["close"], errors="coerce")
    ratios = pd.Series(1.0, index=range(len(df)))
    band = _separation_band(closes, raw.fillna(0.0))

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
        step = math.log(observed)
        # Distance to each hypothesis: the frame is unadjusted and we must
        # divide, or it is already adjusted and we must not.
        to_unadjusted = abs(step - math.log(1.0 / ratio))
        to_adjusted = abs(step)

        if to_unadjusted <= band < to_adjusted:
            ratios.iat[pos] = float(ratio)
            logger.info(
                "%s: split %s on %s corroborated (step %.4f, expected ~%.4f, "
                "band %.4f); rebasing the bars before it",
                symbol or "?", ratio, df.index[pos], observed, 1.0 / ratio, band,
            )
            continue

        if to_adjusted <= band < to_unadjusted:
            logger.debug(
                "%s: split %s on %s already applied by the provider (step %.4f, band %.4f)",
                symbol or "?", ratio, df.index[pos], observed, band,
            )
            continue

        # Neither hypothesis fits, or both do. Undecidable either way, and the
        # two are worth telling apart in the log: "both" is a split too small
        # for this frame's noise to resolve, "neither" is a step that no split
        # explains.
        both = to_unadjusted <= band and to_adjusted <= band
        level = logger.info if both else logger.warning
        level(
            "%s: split %s on %s %s (step %.4f, expected ~%.4f, band %.4f); "
            "leaving the frame alone",
            symbol or "?", ratio, df.index[pos],
            "is too small for this frame to resolve" if both else "is not corroborated",
            observed, 1.0 / ratio, band,
        )

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
    for col in (*PRICE_COLUMNS, *CASH_COLUMNS):
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
