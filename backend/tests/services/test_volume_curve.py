"""Fitting and evaluating a venue's intraday volume curve."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.services.compute.volume_curve import (
    CURVE_BUCKETS,
    fit_curve,
    pace_at,
)

OPEN = datetime(2026, 9, 18, 7, 0, tzinfo=timezone.utc)   # 09:00 Oslo
CLOSE = datetime(2026, 9, 18, 14, 25, tzinfo=timezone.utc)  # 16:25 Oslo


def session(volumes: list[int], open_at: datetime = OPEN, close_at: datetime = CLOSE):
    """One session's bars, spread evenly across the trading day."""
    span = (close_at - open_at) / len(volumes)
    index = [open_at + span * i for i in range(len(volumes))]
    return pd.Series(volumes, index=pd.DatetimeIndex(index)), open_at, close_at


def five_minute_session(open_at: datetime, close_at: datetime, volume: int = 100):
    """Bars every five *clock* minutes — so a short session has fewer of them."""
    bars = int((close_at - open_at).total_seconds() // 300)
    index = [open_at + timedelta(minutes=5 * i) for i in range(bars)]
    return pd.Series([volume] * bars, index=pd.DatetimeIndex(index)), open_at, close_at


def test_flat_volume_fits_a_straight_line():
    curve, samples = fit_curve([session([100] * 40)])
    assert samples == 1
    assert curve[-1] == 1.0
    assert curve[19] == pytest.approx(0.5, abs=0.03)


def test_front_loaded_session_reads_above_the_clock():
    """The opening auction is the whole reason a flat elapsed-time assumption
    is wrong: by 10% of the session, well over 10% has traded."""
    volumes = [1000] * 4 + [100] * 36
    curve, _ = fit_curve([session(volumes)])
    assert curve[3] > 0.4
    assert pace_at(curve, 0.1) > 0.4


def test_curve_is_monotone_and_ends_at_one():
    curve, _ = fit_curve([session([5, 900, 3, 700, 2] * 8)])
    assert curve == sorted(curve)
    assert curve[-1] == 1.0
    assert len(curve) == CURVE_BUCKETS


def test_median_ignores_one_symbol_s_earnings_morning():
    """A single session that traded its whole day in the first ten minutes must
    not bend the venue's curve for everyone on it."""
    normal = [session([100] * 40) for _ in range(8)]
    spike = session([10_000] * 2 + [1] * 38)
    curve, samples = fit_curve(normal + [spike])
    assert samples == 9
    assert curve[1] < 0.15


def test_half_day_folds_into_the_same_curve():
    """Buckets are session progress, not clock minutes. Both sessions below run
    at a steady five-minute cadence; the short one simply has fewer bars. Bucket
    on absolute minutes instead and its curve reaches 1.0 half way along and
    then flatlines, which would read as a venue that stops trading at lunch."""
    full, _ = fit_curve([five_minute_session(OPEN, CLOSE)])
    half, _ = fit_curve([five_minute_session(OPEN, OPEN + (CLOSE - OPEN) / 2)])
    assert half == pytest.approx(full, abs=0.03)


def test_session_with_no_volume_is_not_fitted():
    assert fit_curve([session([0] * 40)]) is None


def test_session_yahoo_only_returned_the_tail_of_is_rejected():
    """A frame starting after lunch would fit a curve flat at zero all morning
    and vertical after it — every early reading would read enormous."""
    afternoon_only, _, _ = five_minute_session(OPEN + (CLOSE - OPEN) * 0.7, CLOSE)
    assert fit_curve([(afternoon_only, OPEN, CLOSE)]) is None


def test_no_usable_sessions_yields_no_curve():
    assert fit_curve([]) is None


class TestPaceAt:
    def test_interpolates_between_buckets(self):
        curve = [(i + 1) / CURVE_BUCKETS for i in range(CURVE_BUCKETS)]
        assert pace_at(curve, 0.5) == pytest.approx(0.5, abs=0.001)

    def test_is_zero_at_the_open_not_the_first_bucket_s_value(self):
        curve = [0.4] + [0.4 + 0.6 * (i + 1) / (CURVE_BUCKETS - 1) for i in range(CURVE_BUCKETS - 1)]
        assert pace_at(curve, 0.0) == pytest.approx(0.0)

    def test_is_one_at_the_close(self):
        curve = [(i + 1) / CURVE_BUCKETS for i in range(CURVE_BUCKETS)]
        assert pace_at(curve, 1.0) == 1.0

    def test_refuses_to_extrapolate_outside_the_session(self):
        curve = [(i + 1) / CURVE_BUCKETS for i in range(CURVE_BUCKETS)]
        assert pace_at(curve, -0.1) is None
        assert pace_at(curve, 1.5) is None

    def test_no_curve_is_no_answer(self):
        assert pace_at([], 0.5) is None
