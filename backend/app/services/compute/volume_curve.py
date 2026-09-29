"""Fit a venue's intraday volume profile from 5-minute bars.

Pure computation over frames, no I/O — :mod:`app.services.volume_curve_service`
fetches, persists and serves.

The output answers one question: *by this point in a regular session, what
fraction of the day's volume has normally traded?* RVOL divides by it so a
mid-morning reading is comparable to a full day's, and to the next symbol's on
a venue three hours ahead.
"""

import logging
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)

#: Buckets the session is divided into. 40 is 2.5% of a session — about 13
#: minutes of a European equity day, fine enough to separate the opening cross
#: from the rest of the first half hour, coarse enough that one bucket still
#: holds two or three 5-minute bars to average over.
CURVE_BUCKETS = 40

#: Symbol-sessions a venue's curve must be fitted over before it is used. Below
#: this the median is drawn through a handful of days, and one earnings morning
#: on a thin venue moves it more than the auction structure does.
MIN_CURVE_SAMPLES = 20


def _session_curve(volumes: pd.Series, open_at: datetime, close_at: datetime) -> list[float] | None:
    """Cumulative volume fraction at each bucket boundary for one session.

    Returns ``CURVE_BUCKETS`` values, the last of which is 1.0, or None when
    the session is unusable: no volume, or bars covering so little of it that
    the early buckets would be fitted on nothing.
    """
    span = (close_at - open_at).total_seconds()
    if span <= 0:
        return None
    total = float(volumes.sum())
    if total <= 0:
        return None

    cumulative = [0.0] * CURVE_BUCKETS
    for ts, vol in volumes.items():
        progress = (pd.Timestamp(ts).to_pydatetime() - open_at).total_seconds() / span
        if progress < 0 or progress > 1:
            continue  # auction print outside the regular session
        # A bar's volume is credited to the bucket its close falls in, so the
        # curve reads "traded by the end of bucket b" rather than "some time
        # around b".
        bucket = min(CURVE_BUCKETS - 1, int(progress * CURVE_BUCKETS))
        cumulative[bucket] += float(vol)

    running = 0.0
    out: list[float] = []
    for bucket_volume in cumulative:
        running += bucket_volume
        out.append(running / total)

    # A session Yahoo returned only the tail of would fit a curve that is flat
    # at zero all morning and then vertical — worse than no curve, because it
    # makes every early reading enormous.
    if out[CURVE_BUCKETS // 2] <= 0:
        return None
    return out


def fit_curve(sessions: list[tuple[pd.Series, datetime, datetime]]) -> tuple[list[float], int] | None:
    """Median cumulative-volume curve across sessions, plus the sample count.

    Median rather than mean: one symbol's earnings morning front-loads its
    whole day, and a mean lets that single session bend the venue's curve for
    everyone on it.
    """
    curves = [c for c in (_session_curve(*s) for s in sessions) if c is not None]
    if not curves:
        return None

    frame = pd.DataFrame(curves)
    median = frame.median(axis=0).tolist()

    # The median of monotone curves is monotone, but floating-point summation
    # and the final normalisation are not guaranteed to leave it so. Clamp
    # rather than trust: a curve that dips backwards makes RVOL jump.
    fitted: list[float] = []
    running = 0.0
    for value in median:
        running = max(running, min(1.0, float(value)))
        fitted.append(running)
    fitted[-1] = 1.0
    return fitted, len(curves)


def pace_at(curve: list[float], progress: float) -> float | None:
    """Evaluate a fitted curve at ``progress`` (0 at the open, 1 at the close).

    Linearly interpolated between bucket boundaries, with 0 at the open. None
    outside the session — the caller has no live volume to normalise then
    anyway, and extrapolating a curve past its ends invents numbers.
    """
    if not curve or progress < 0 or progress > 1:
        return None
    if progress >= 1:
        return 1.0

    position = progress * len(curve)
    index = int(position)
    lower = curve[index - 1] if index > 0 else 0.0
    upper = curve[index]
    return lower + (upper - lower) * (position - index)
