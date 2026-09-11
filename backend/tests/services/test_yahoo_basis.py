"""Bars quoted in the wrong share basis, and making every window agree (#665)."""

import pandas as pd
import pytest

from app.services.yahoo.normalize import normalize_frame
from app.services.yahoo.normalize.basis import MAX_DISPLACED_BARS, normalize_basis
from tests.helpers import daily_date_index

RATIO = 2.0


def frame(
    closes: list[float],
    splits: list[float] | None = None,
    dividends: list[float] | None = None,
) -> pd.DataFrame:
    """A minimal daily frame: closes, matching OHLC, volume, split events."""
    data = {
        "open": closes,
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "close": closes,
        "volume": [1_000_000] * len(closes),
        "splits": splits if splits is not None else [0.0] * len(closes),
    }
    if dividends is not None:
        data["dividends"] = dividends
    return pd.DataFrame(data, index=daily_date_index(len(closes)))


def true_series(n: int) -> list[float]:
    """A quiet ~0.2%/session series, in the current share basis throughout."""
    return [48.0 + 0.1 * i for i in range(n)]


def mixed(
    displaced: set[int], n_pre: int = 12, n_post: int = 3, ratio: float = RATIO
) -> pd.DataFrame:
    """The frame Yahoo actually serves around a split it reports but half-applies.

    Pre-split bars come back unadjusted, except the ones in ``displaced``, which
    it has already rebased. Which ones those are changes from response to
    response, which is the whole problem.
    """
    true = true_series(n_pre + n_post)
    closes = [
        (t if i in displaced else t * ratio) if i < n_pre else t
        for i, t in enumerate(true)
    ]
    splits = [0.0] * len(true)
    splits[n_pre] = ratio
    return frame(closes, splits)


def expected(n_pre: int = 12, n_post: int = 3, ratio: float = RATIO) -> list[float]:
    """What that frame looks like once every bar is in one basis, pre-rebase."""
    true = true_series(n_pre + n_post)
    return [t * ratio if i < n_pre else t for i, t in enumerate(true)]


class TestRequotingDisplacedBars:
    def test_an_isolated_bar_is_moved_onto_its_neighbours_basis(self):
        # The MNST shape: 48.5 sitting between 96.8 and 97.2 is not a session
        # anyone traded, it is one bar quoted in the other basis.
        out = normalize_basis(mixed({5}), "MNST")
        assert out["close"].tolist() == pytest.approx(expected())

    def test_a_contiguous_group_is_moved_together(self):
        # What an overlapping fetch writes: a window's worth of bars, not one.
        out = normalize_basis(mixed({4, 5, 6}), "MNST")
        assert out["close"].tolist() == pytest.approx(expected())

    def test_several_separate_groups_in_one_frame(self):
        out = normalize_basis(mixed({3, 6, 7, 10}), "MNST")
        assert out["close"].tolist() == pytest.approx(expected())

    def test_the_whole_bar_moves_not_just_the_close(self):
        out = normalize_basis(mixed({5}), "MNST")
        assert out["open"].iloc[5] == pytest.approx(expected()[5])
        assert out["high"].iloc[5] == pytest.approx(expected()[5] * 1.01)
        assert out["low"].iloc[5] == pytest.approx(expected()[5] * 0.99)
        # Twice the price means half the share count for the same turnover.
        assert out["volume"].iloc[5] == pytest.approx(500_000)

    def test_a_reverse_split_frame_is_handled_the_same_way(self):
        out = normalize_basis(mixed({5}, ratio=0.1), "X")
        assert out["close"].tolist() == pytest.approx(expected(ratio=0.1))

    def test_running_twice_changes_nothing(self):
        once = normalize_basis(mixed({5}), "MNST")
        twice = normalize_basis(once, "MNST")
        assert twice["close"].tolist() == pytest.approx(once["close"].tolist())


class TestFramesThatMustBeLeftAlone:
    def test_a_frame_the_provider_kept_consistent_is_untouched(self):
        df = mixed(set())
        assert normalize_basis(df, "MNST") is df

    def test_a_frame_with_no_split_event_is_untouched(self):
        df = frame(true_series(10))
        assert normalize_basis(df, "X") is df

    def test_a_frame_without_a_splits_column_is_untouched(self):
        df = mixed({5}).drop(columns=["splits"])
        assert normalize_basis(df, "MNST") is df

    def test_a_real_move_that_never_steps_back_is_untouched(self):
        # A genuine halving inside the pre-split window offers one step, not a
        # matched pair. One step is what a crash and a mis-quote share, so it
        # decides nothing and the bars stay as the provider sent them.
        closes = expected()
        closes[5:12] = [c / 2 for c in closes[5:12]]
        df = frame(closes, [0.0] * 5 + [0.0] * 7 + [RATIO] + [0.0, 0.0])
        assert normalize_basis(df, "X") is df

    def test_a_group_running_to_the_ex_date_is_left_to_the_refetch(self):
        # The last pre-split bar has the split's own step on its far side, and
        # that step is exactly what ``normalize_splits`` has to read. Claiming
        # it here would be deciding the split twice on one piece of evidence.
        df = mixed({11})
        assert normalize_basis(df, "MNST") is df

    def test_a_group_longer_than_the_bound_is_left_alone(self):
        displaced = set(range(3, 4 + MAX_DISPLACED_BARS))
        df = mixed(displaced, n_pre=24)
        assert normalize_basis(df, "MNST") is df

    def test_a_group_at_the_bound_is_still_repaired(self):
        displaced = set(range(3, 3 + MAX_DISPLACED_BARS))
        out = normalize_basis(mixed(displaced, n_pre=24), "MNST")
        assert out["close"].tolist() == pytest.approx(expected(n_pre=24))

    def test_a_frame_too_short_to_have_a_quiet_median_refuses(self):
        # With four bars the mis-quote's own two steps *are* the median, so the
        # noise band swallows both readings and nothing is decidable. Refusing
        # is the only safe answer: a wrong requote would be re-derived
        # identically on every later fetch.
        df = mixed({1}, n_pre=3, n_post=1)
        assert normalize_basis(df, "X") is df

    def test_an_empty_frame(self):
        df = frame([])
        assert normalize_basis(df, "X") is df


class TestWindowsAgree:
    """The acceptance criterion: what gets stored for a date cannot depend on
    which window happened to fetch it, or on which bars Yahoo rebased that time.
    """

    def test_two_different_adjustment_draws_land_on_the_same_prices(self):
        first = normalize_frame(mixed({5}), "MNST")
        second = normalize_frame(mixed({3, 7, 8}), "MNST")

        assert first["close"].tolist() == pytest.approx(second["close"].tolist())
        assert first["close"].tolist() == pytest.approx(true_series(15))

    def test_a_shorter_window_over_the_same_dates_agrees_too(self):
        wide = normalize_frame(mixed({5}, n_pre=20), "MNST")
        narrow = normalize_frame(mixed({5}, n_pre=20).iloc[4:], "MNST")

        shared = wide.index.intersection(narrow.index)
        assert wide.loc[shared, "close"].tolist() == pytest.approx(
            narrow.loc[shared, "close"].tolist()
        )
