from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from app.services.compute.move_scale import MOVE_WINDOWS, move_scale, move_scales

LATEST = date(2026, 10, 9)


def _closes(n: int, start: float = 100.0, seed: int = 3) -> pd.Series:
    dates = [d.date() for d in pd.bdate_range(end=LATEST, periods=n)]
    rng = np.random.default_rng(seed)
    return pd.Series(start * np.cumprod(1 + rng.normal(0, 0.012, n)), index=dates)


def _reference(closes: pd.Series, days: int, lookback: int) -> list[float]:
    """The definition spelled out session by session."""
    moves = []
    for d, c in closes.items():
        if d < LATEST - timedelta(days=lookback):
            continue
        before = closes[closes.index <= d - timedelta(days=days)]
        if before.empty:
            continue
        moves.append(abs(c / before.iloc[-1] - 1) * 100)
    return [round(float(q), 4) for q in np.percentile(moves, np.arange(0, 101, 5))]


@pytest.mark.parametrize("key", ["1wk", "2wk", "1mo"])
def test_quantiles_match_the_definition_over_the_full_lookback(key):
    w = MOVE_WINDOWS[key]
    closes = _closes(600)
    scale = move_scale(closes, w)

    assert scale is not None
    assert scale.quantiles == _reference(closes, w.days, w.lookback_days)
    assert len(scale.quantiles) == 21
    assert scale.quantiles == sorted(scale.quantiles)
    # Every weekday in the lookback is a sample, and the earliest sits on its edge.
    assert scale.lookback_days > w.lookback_days - 3
    assert scale.samples == sum(1 for d in closes.index if d >= LATEST - timedelta(days=w.lookback_days))


def test_window_and_lookback_per_key():
    assert {k: (w.days, w.lookback_days, w.min_lookback_days) for k, w in MOVE_WINDOWS.items()} == {
        "1wk": (7, 364, 182),
        "2wk": (14, 364, 182),
        "1mo": (30, 730, 364),
    }


def test_weekend_window_start_takes_the_close_before_it():
    # A 7-day window from a Monday starts on a Monday; from a Sunday it would
    # take Friday. With weekday closes, every 1wk sample is a five-session move.
    closes = _closes(400)
    scale = move_scale(closes, MOVE_WINDOWS["1wk"])
    five_session = (closes / closes.shift(5) - 1).abs() * 100
    in_lookback = five_session[[d >= LATEST - timedelta(days=364) for d in closes.index]]
    expected = np.percentile(in_lookback, np.arange(0, 101, 5))
    assert scale.quantiles == [round(float(q), 4) for q in expected]


def test_short_history_uses_what_exists_above_the_threshold():
    # About 40 weeks of weekdays: 1wk and 2wk get a shorter scale, 1mo is withheld.
    closes = _closes(200)
    scales = move_scales(closes)

    first_sample = min(d for d in closes.index if d >= closes.index[0] + timedelta(days=7))
    assert scales.one_week.lookback_days == (LATEST - first_sample).days
    assert scales.one_week.lookback_days < 364
    assert scales.one_week.quantiles == _reference(closes, 7, 364)
    assert scales.two_weeks is not None
    assert scales.one_month is None


@pytest.mark.parametrize(
    ("key", "weeks", "present"),
    [("1wk", 26, True), ("1wk", 25, False), ("2wk", 26, True), ("2wk", 25, False), ("1mo", 52, True), ("1mo", 51, False)],
)
def test_threshold(key, weeks, present):
    w = MOVE_WINDOWS[key]
    # Calendar-daily closes so the span of samples is exact: the first sample
    # sits one window after the first close.
    span = weeks * 7
    n = span + w.days + 1
    dates = [LATEST - timedelta(days=n - 1 - i) for i in range(n)]
    closes = pd.Series(np.linspace(100, 120, n), index=dates)
    scale = move_scale(closes, w)
    assert (scale is not None) == present
    if present:
        assert scale.lookback_days == span


def test_empty_and_single_close_are_null():
    assert move_scale(pd.Series(dtype=float), MOVE_WINDOWS["1wk"]) is None
    assert move_scale(pd.Series([100.0], index=[LATEST]), MOVE_WINDOWS["1wk"]) is None


def test_flat_series_gives_equal_quantiles():
    dates = [d.date() for d in pd.bdate_range(end=LATEST, periods=300)]
    scale = move_scale(pd.Series(50.0, index=dates), MOVE_WINDOWS["2wk"])
    assert scale.quantiles == [0.0] * 21


def test_alternating_steps_tie_quantiles():
    # Calendar-daily closes stepping up 10% and back every seven days: every
    # 1wk sample spans exactly one step, so the quantiles hold two values.
    n = 400
    dates = [LATEST - timedelta(days=n - 1 - i) for i in range(n)]
    closes = pd.Series([100.0 * (1.1 if (i // 7) % 2 else 1.0) for i in range(n)], index=dates)
    scale = move_scale(closes, MOVE_WINDOWS["1wk"])
    assert set(scale.quantiles) == {round(100 / 11, 4), 10.0}
    assert scale.quantiles == sorted(scale.quantiles)
