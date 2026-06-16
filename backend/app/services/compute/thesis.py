"""Thesis aggregate performance — pure computation (no I/O).

The headline number for a thesis is the equal-weight mean return of its member
tickers **since the thesis was opened**. Anchoring to the open date (rather than
"today") is the point: it tells you whether the thesis is working since you
formed it, not how the tickers look right now.
"""


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
