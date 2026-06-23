"""Thesis aggregate performance — pure computation (no I/O).

The headline number for a thesis is the equal-weight mean return of its member
tickers **since the thesis was opened**. Anchoring to the open date (rather than
"today") is the point: it tells you whether the thesis is working since you
formed it, not how the tickers look right now.
"""

from datetime import date
from typing import cast

import pandas as pd


def aggregate_return_pct(member_closes: list[list[float]]) -> float | None:
    """Equal-weight mean return since the open, in percent (2 dp).

    Each element is one member's close prices on/after the thesis open date,
    ordered by date. Per-member return = ``last / first - 1`` where ``first`` is
    the close on (or nearest after) the open date. Members with no prices, or a
    zero/missing opening close, are excluded. Returns ``None`` when no member
    contributes a return (e.g. an empty thesis or no price data since the open).
    """
    returns: list[float] = []
    for closes in member_closes:
        if not closes:
            continue
        first = closes[0]
        if not first:
            continue
        returns.append(closes[-1] / first - 1.0)
    if not returns:
        return None
    return round(sum(returns) / len(returns) * 100.0, 2)


def _downsample(points: list[tuple], max_points: int) -> list[tuple]:
    """Evenly thin ``points`` to at most ``max_points``, always keeping the last."""
    n = len(points)
    if max_points <= 1 or n <= max_points:
        return points
    step = (n - 1) / (max_points - 1)
    idxs = sorted({round(i * step) for i in range(max_points)})
    idxs[-1] = n - 1  # guarantee the final point survives the rounding
    return [points[i] for i in idxs]


def aggregate_return_series(
    closes_by_member: list[list[tuple[date, float]]],
    *,
    max_points: int = 60,
) -> list[dict]:
    """Equal-weight performance curve since the open, in percent.

    The daily counterpart to :func:`aggregate_return_pct`: instead of one headline
    number it returns the whole curve, for a sparkline. Each member is normalised
    to its own opening close (``close / first - 1``); on a given date the value is
    the equal-weight mean across members that have started — a member contributes
    from its first available close, carried forward over gaps. Members with no
    prices or a zero/missing open are excluded.

    ``closes_by_member`` is one ``(date, close)`` list per member, ascending by
    date (same assumption as the aggregate). Returns ``[]`` when no member
    contributes. The curve is downsampled to ``max_points`` (last always kept) to
    keep the payload small.
    """
    columns: list[pd.Series] = []
    for closes in closes_by_member:
        if not closes:
            continue
        first = closes[0][1]
        if not first:
            continue
        idx = pd.DatetimeIndex([d for d, _ in closes])
        columns.append(pd.Series([c / first - 1.0 for _, c in closes], index=idx))
    if not columns:
        return []

    # Outer-join members on date and carry each forward over gaps. Leading NaN
    # (before a member's first print) is preserved, so a member only counts once
    # it has started; mean(axis=1) skips NaN → equal weight across the started set.
    aligned = pd.concat(columns, axis=1).sort_index().ffill()
    mean = cast("pd.Series", aligned.mean(axis=1)).dropna()
    if mean.empty:
        return []

    points = [(ts, round(val * 100.0, 2)) for ts, val in mean.items()]
    return [
        {"date": ts.date().isoformat(), "pct": pct}
        for ts, pct in _downsample(points, max_points)
    ]
