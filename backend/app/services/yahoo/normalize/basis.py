"""Requote bars the provider sent in the wrong share basis, judged by neighbours.

``normalize_splits`` reads a single step — the one across the ex-date — and
applies its verdict to every bar before it. That holds only while those bars
agree with each other, and around a split Yahoo's do not: it serves a date
adjusted in one response and unadjusted in the next. Each fetch window then
upserts whatever basis its own frame decided, so overlapping jobs rewrite
overlapping subsets of a range run after run and the stored series ends up with
bars a full split factor off their neighbours. A re-fetch reproduces them.

**What this decides.** A group of bars that steps away from its neighbours by
the declared ratio and steps straight back on the far side is not a session
anyone traded; it is those bars quoted in the other basis, and two matched
steps say so without a re-fetch and without any record of what an earlier fetch
wrote. Like everything else in this package it is a pure function of the frame,
so it re-derives the same answer every time and stops firing on its own once
the provider settles.

**What it does not decide — and this is the whole of it.** A group needs a step
on *both* sides. A group running to either edge of the frame's pre-split region
has one step, which is what a genuine crash and a mis-quote share, so it is left
alone. That is a refusal to add a wrong answer, not a repair:

- A window whose oldest bars are mid-group loses the left step. The group stays
  displaced, ``normalize_splits`` rebases the region around it, and those bars
  end up a further factor out. ``price_heal`` fetches ``period="1mo"``, so a
  run three weeks after an ex-date reaches this.
- A group ending on the bar immediately *before* the ex-date loses the right
  step, because the right step is the split's own. ``normalize_splits`` then
  measures the ex-date against a bar in the other basis, reads ~1, and records
  the split as already applied — storing a full cliff. MNST's 2026-08-10 bar
  was exactly that draw.

Both are the same missing evidence, and answering them means teaching
``_confirmed_ratios`` to judge the ex-date step against a robust pre-split
level instead of the single bar before it. That is not this module's to do.
"""

import logging
import math
from bisect import bisect_left

import pandas as pd

from app.services.yahoo.normalize.splits import (
    SPLIT_COLUMN,
    rescale,
    separation_band,
)

logger = logging.getLogger(__name__)

# How long a displaced group may be, and how far before the ex-date it may sit.
#
# Both bound the same risk: two *unrelated* real moves of the split's size, one
# down and one up, are a matched pair too, and only distance separates them
# from the artifact. A heal re-fetch spans every bar we hold, so an unbounded
# scan offers ~1250 steps to pair across five years, against the single step
# ``normalize_splits`` weighs.
#
# MNST's churn ran 2026-07-30 to 2026-08-10, 8 sessions ending on the ex-date.
# The window has to clear that with room and stop well short of a year; 30
# sessions is ~4x the one run measured and ~40x fewer chances to pair than the
# unbounded scan. The group bound is tighter because the observed artifact is
# per-bar flip-flopping inside that window, not a solid fortnight.
DISPLACED_WINDOW_SESSIONS = 30
MAX_DISPLACED_BARS = 10


def _declared_ratios(df: pd.DataFrame) -> list[tuple[int, float]]:
    """``(position, ratio)`` for every split event the frame carries."""
    raw = pd.to_numeric(df[SPLIT_COLUMN], errors="coerce")
    return [
        (pos, float(value))
        for pos, value in enumerate(raw)
        if pd.notna(value) and value > 0 and not math.isclose(float(value), 1.0)
    ]


def _priced(closes: pd.Series) -> list[int]:
    """Positions the frame actually prices, oldest first."""
    return [
        pos for pos in range(len(closes))
        if pd.notna(closes.iat[pos]) and closes.iat[pos] > 0
    ]


def _breaks(
    closes: pd.Series,
    priced: list[int],
    band: float,
    ratio: float,
    ex_positions: set[int],
    ex_pos: int,
) -> list[tuple[int, float]]:
    """Steps that land on the ratio, as ``(index into priced, factor)``.

    A step qualifies when it is within ``band`` of the ratio *and* further than
    ``band`` from zero — the two-sided test ``_confirmed_ratios`` uses, so a
    frame whose own noise admits both readings yields nothing.

    Every ex-date step is skipped, not only this ratio's: in a frame spanning
    two splits the older one's step is otherwise a candidate here.
    """
    found: list[tuple[int, float]] = []
    last = bisect_left(priced, ex_pos)
    for k in range(max(1, last - DISPLACED_WINDOW_SESSIONS), last):
        if priced[k] in ex_positions:
            continue
        step = math.log(float(closes.iat[priced[k]]) / float(closes.iat[priced[k - 1]]))
        for factor in (ratio, 1.0 / ratio):
            if abs(step - math.log(factor)) <= band < abs(step):
                found.append((k, factor))
                break
    return found


def _displaced(
    breaks: list[tuple[int, float]], priced: list[int]
) -> list[tuple[list[int], float]]:
    """Groups that step away by a factor and step straight back.

    Both factors come from ``{ratio, 1/ratio}``, so "steps back" is the exact
    test that they are not the same one, and the drift a group accumulates
    while displaced never enters the decision.
    """
    runs: list[tuple[list[int], float]] = []
    j = 0
    while j + 1 < len(breaks):
        (start, factor), (end, back) = breaks[j], breaks[j + 1]
        if math.isclose(factor * back, 1.0) and end - start <= MAX_DISPLACED_BARS:
            runs.append((priced[start:end], factor))
            j += 2
        else:
            j += 1
    return runs


def normalize_basis(df: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
    """Move bars quoted in the wrong share basis onto the one their neighbours use.

    Returns ``df`` unchanged when the frame declares no split, which is nearly
    every frame, or when its bars already agree.
    """
    if df.empty or "close" not in df.columns or SPLIT_COLUMN not in df.columns:
        return df
    declared = _declared_ratios(df)
    if not declared:
        return df

    # Copied because the loop requotes bars in it as it goes, so a frame
    # spanning two splits weighs the second against bars the first repaired —
    # and ``pd.to_numeric`` hands back the frame's own column when it is
    # already numeric.
    closes = pd.to_numeric(df["close"], errors="coerce").astype(float).copy()
    band = separation_band(closes, pd.to_numeric(df[SPLIT_COLUMN], errors="coerce").fillna(0.0))
    divisor = pd.Series(1.0, index=range(len(df)))
    ex_positions = {pos for pos, _ in declared}

    for ex_pos, ratio in declared:
        priced = _priced(closes)
        for positions, factor in _displaced(
            _breaks(closes, priced, band, ratio, ex_positions, ex_pos), priced
        ):
            for pos in positions:
                divisor.iat[pos] *= factor
                closes.iat[pos] = float(closes.iat[pos]) / factor
            logger.info(
                "%s: %d bar(s) from %s sit %.4fx off their neighbours and step "
                "straight back; requoting them in the basis around them "
                "(split %s on %s, band %.4f)",
                symbol or "?", len(positions), df.index[positions[0]], factor,
                ratio, df.index[ex_pos], band,
            )

    if (divisor == 1.0).all():
        return df
    return rescale(df, divisor)
