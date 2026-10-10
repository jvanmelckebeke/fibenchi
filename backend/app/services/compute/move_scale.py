"""Each symbol's own distribution of window moves, as the board's move bars read it.

A bar's length is the share of the symbol's past moves over the same window
that were smaller in absolute size. The server can't place today's move on
that distribution itself, because the board measures the window against the
live price, so it ships the distribution as quantiles and the client places
the live move on them.

The samples mirror the board's reading: for every stored session in the
lookback, the percent change from the last close on or before the date one
window earlier. They overlap, so a lookback of 52 weeks holds about 250
samples for any window, not 52 independent ones.
"""

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from app.schemas.companion import MoveScale, MoveScales

#: Quantile levels shipped per window: 0, 5, ..., 100 percent.
QUANTILE_LEVELS = np.arange(0, 101, 5)


@dataclass(frozen=True)
class MoveWindow:
    #: Calendar days the board's window spans (board/color-scale.ts PCT_WINDOWS).
    days: int
    #: Calendar days of samples the full distribution uses.
    lookback_days: int
    #: Fewer calendar days of samples than this and the scale is withheld.
    min_lookback_days: int


MOVE_WINDOWS: dict[str, MoveWindow] = {
    "1wk": MoveWindow(days=7, lookback_days=364, min_lookback_days=182),
    "2wk": MoveWindow(days=14, lookback_days=364, min_lookback_days=182),
    "1mo": MoveWindow(days=30, lookback_days=730, min_lookback_days=364),
}

#: Calendar days of stored closes a full set of scales needs before the latest bar.
MOVE_SCALE_HISTORY_DAYS = max(w.lookback_days + w.days for w in MOVE_WINDOWS.values())


def move_scale(closes: pd.Series, window: MoveWindow) -> MoveScale | None:
    """Quantiles of ``|window return|`` in percent, or None on too little history.

    ``closes`` is indexed by session date, ascending, with no missing values.
    """
    if closes.empty:
        return None
    dates = np.asarray(closes.index, dtype="datetime64[D]")
    values = closes.to_numpy(dtype=float)
    latest = dates[-1]

    in_lookback = np.flatnonzero(dates >= latest - np.timedelta64(window.lookback_days, "D"))
    # The baseline for session i is the last close on or before i's date less
    # the window, the same rule windowPct applies to the live reading.
    base_idx = np.searchsorted(dates, dates[in_lookback] - np.timedelta64(window.days, "D"), side="right") - 1
    has_base = base_idx >= 0
    sample_idx = in_lookback[has_base]
    base_idx = base_idx[has_base]
    base = values[base_idx]
    usable = base != 0
    sample_idx = sample_idx[usable]
    if sample_idx.size == 0:
        return None

    lookback_days = int((latest - dates[sample_idx[0]]).astype(int))
    if lookback_days < window.min_lookback_days:
        return None

    moves = np.abs(values[sample_idx] / base[usable] - 1) * 100
    quantiles = np.percentile(moves, QUANTILE_LEVELS)
    return MoveScale(
        quantiles=[round(float(q), 4) for q in quantiles],
        samples=int(sample_idx.size),
        lookback_days=lookback_days,
    )


def move_scales(closes: pd.Series) -> MoveScales:
    """The scale for every board window."""
    return MoveScales(**{key: move_scale(closes, w) for key, w in MOVE_WINDOWS.items()})


def move_scale_history_start(today: date | None = None) -> date:
    """First date a full set of scales can read, with a week of slack for a stale latest bar."""
    return (today or date.today()) - timedelta(days=MOVE_SCALE_HISTORY_DAYS + 7)
