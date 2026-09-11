"""Put the bars of one frame in one share basis before anything reads the step.

``normalize_splits`` reads a single step — the one across the ex-date — and
applies its verdict to every bar before it. That is only sound if the frame's
pre-split bars already agree with each other, and around a split Yahoo's do
not. It serves a date adjusted in one response and unadjusted in the next, so
a frame can arrive with isolated bars sitting a full split factor away from
their own neighbours.

Left alone that turns into the cross-frame failure, because each fetch window
covers a different set of dates and each upsert writes whatever basis its own
frame decided. MNST's stored series two weeks after its 2026-08-11 2:1 split
held 48.83, 24.10, 46.78, 47.09, 94.46, 47.08 on consecutive sessions — four
fabricated 2x steps, each of which σ-Move squares into the EWMA variance. Two
reads minutes apart returned different numbers for the same dates, because
background jobs were rewriting overlapping subsets of the range run after run.

**What the repair is.** A bar that is a split factor away from the bar before
it *and* a split factor back on the bar after it is not a session anyone
traded; it is one bar quoted in the other basis. That is decidable from the
frame alone, without a re-fetch and without any record of what a previous fetch
wrote, so this stays a pure function of the frame like everything else here.

**What it refuses.** Only a group bounded on *both* sides qualifies. A group
running to either edge of the pre-split region has one piece of evidence
instead of two, and a genuine crash of the same size is indistinguishable from
it — so those are left for the wide-window re-fetch in
``heal_split_discontinuities``. The step also has to land on the ratio the
provider itself declared, not merely be large: a real move within the noise
band of exactly log(2) days before a 2:1 split is far rarer than a move that is
merely big.
"""

import logging
import math

import pandas as pd

from app.services.yahoo.normalize.splits import (
    SPLIT_COLUMN,
    rescale,
    separation_band,
)

logger = logging.getLogger(__name__)

# How long a wrongly-based group may be before it is left to the re-fetch.
#
# The bound is what stops two *unrelated* moves of the split's size from being
# paired: a name that halves in March and doubles in June, then splits 2:1 in
# August, offers exactly the same two steps as a displaced group, and the only
# thing separating them is that the real pair sits months apart. The observed
# artifact is per-bar flip-flopping over days, so a fortnight of sessions is
# already generous.
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
    closes: pd.Series, priced: list[int], band: float, ratio: float, before: int
) -> list[tuple[int, float]]:
    """Steps that land on the declared ratio, as ``(index into priced, factor)``.

    A step counts only when it is near the ratio *and* too far from zero to be
    an ordinary session — the same two-sided test ``_confirmed_ratios`` uses, and
    for the same reason. A frame whose own noise is wide enough to admit both
    readings has not told us anything, and reading it either way would be a
    guess re-derived identically on every later fetch.

    Bounded by ``before`` — the ex-date's position — so neither end of a pair
    can be the split's own step, which belongs to ``normalize_splits``.
    """
    found: list[tuple[int, float]] = []
    for k in range(1, len(priced)):
        pos = priced[k]
        if pos >= before:
            break
        step = math.log(float(closes.iat[pos]) / float(closes.iat[priced[k - 1]]))
        for factor in (ratio, 1.0 / ratio):
            if abs(step - math.log(factor)) <= band < abs(step):
                found.append((k, factor))
                break
    return found


def _displaced(breaks: list[tuple[int, float]], priced: list[int]) -> list[tuple[list[int], float]]:
    """Groups of bars that step away by a factor and step straight back.

    Both factors come from ``{ratio, 1/ratio}``, so "steps back" is the exact
    test that they are not the same one — no second tolerance to choose, and
    the drift the group accumulates while displaced never enters the decision.
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

    # Copied: the loop below requotes bars as it decides them, so that later
    # groups are judged against repaired neighbours, and ``pd.to_numeric``
    # hands back the frame's own column when it is already numeric.
    closes = pd.to_numeric(df["close"], errors="coerce").astype(float).copy()
    band = separation_band(closes, pd.to_numeric(df[SPLIT_COLUMN], errors="coerce").fillna(0.0))
    divisor = pd.Series(1.0, index=range(len(df)))

    for ex_pos, ratio in declared:
        priced = _priced(closes)
        for positions, factor in _displaced(
            _breaks(closes, priced, band, ratio, ex_pos), priced
        ):
            for pos in positions:
                divisor.iat[pos] *= factor
                closes.iat[pos] = float(closes.iat[pos]) / factor
            logger.info(
                "%s: %d bar(s) from %s sit %.4fx off their neighbours and step "
                "straight back, which no session does; requoting them in the "
                "basis around them (split %s on %s, band %.4f)",
                symbol or "?", len(positions), df.index[positions[0]], factor,
                ratio, df.index[ex_pos], band,
            )

    if (divisor == 1.0).all():
        return df
    return rescale(df, divisor)
