"""Bars quoted in the wrong share basis, and what the frame can decide about them."""

import pandas as pd
import pytest

from app.services.yahoo.normalize import normalize_frame
from app.services.yahoo.normalize.basis import (
    DISPLACED_WINDOW_SESSIONS,
    MAX_DISPLACED_BARS,
    normalize_basis,
)
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
        "adjclose": closes,
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
    displaced: set[int],
    n_pre: int = 12,
    n_post: int = 3,
    ratio: float = RATIO,
    dividends: dict[int, float] | None = None,
) -> pd.DataFrame:
    """The frame Yahoo serves around a split it reports but half-applies.

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
    cash = None
    if dividends is not None:
        cash = [dividends.get(i, 0.0) for i in range(len(true))]
    return frame(closes, splits, cash)


def expected(n_pre: int = 12, n_post: int = 3, ratio: float = RATIO) -> list[float]:
    """That frame with every bar in one basis, before ``normalize_splits`` runs."""
    true = true_series(n_pre + n_post)
    return [t * ratio if i < n_pre else t for i, t in enumerate(true)]


class TestRequotingDisplacedBars:
    def test_an_isolated_bar_is_moved_onto_its_neighbours_basis(self):
        # The MNST shape: 48.5 between 96.8 and 97.2.
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
        out = normalize_basis(mixed({5}, dividends={5: 0.25}), "MNST")
        want = expected()[5]

        assert out["open"].iloc[5] == pytest.approx(want)
        assert out["high"].iloc[5] == pytest.approx(want * 1.01)
        assert out["low"].iloc[5] == pytest.approx(want * 0.99)
        assert out["adjclose"].iloc[5] == pytest.approx(want)
        # Cash per share is quoted in the basis of its own bar, so it rides
        # along or σ-Move divides two different units.
        assert out["dividends"].iloc[5] == pytest.approx(0.5)
        # Twice the price means half the share count for the same turnover.
        assert out["volume"].iloc[5] == pytest.approx(500_000)

    def test_a_reverse_split_frame_is_handled_the_same_way(self):
        out = normalize_basis(mixed({5}, ratio=0.1), "X")
        assert out["close"].tolist() == pytest.approx(expected(ratio=0.1))

    def test_running_twice_changes_nothing(self):
        once = normalize_basis(mixed({5}), "MNST")
        twice = normalize_basis(once, "MNST")
        assert twice["close"].tolist() == pytest.approx(once["close"].tolist())

    def test_a_frame_spanning_two_splits(self):
        # The older split's own step must not read as a break during the newer
        # split's pass, and the bar displaced behind both has to end up under
        # the product of the two.
        true = true_series(40)
        closes = [
            t * 4 if i < 20 else (t * 2 if i < 32 else t)
            for i, t in enumerate(true)
        ]
        closes[10] = true[10] * 2  # the provider applied only the older split
        splits = [0.0] * 40
        splits[20] = splits[32] = RATIO

        out = normalize_frame(frame(closes, splits), "X")
        assert out["close"].tolist() == pytest.approx(true)


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
        closes = expected()
        closes[5:12] = [c / 2 for c in closes[5:12]]
        df = frame(closes, [0.0] * 12 + [RATIO] + [0.0, 0.0])
        assert normalize_basis(df, "X") is df

    def test_a_matched_pair_outside_the_window_is_untouched(self):
        # A genuine halving and recovery far enough back is the artifact's
        # exact shape. Distance is the only thing separating them, so the scan
        # stops before it reaches this pair.
        closes = expected(n_pre=50)
        closes[5] = closes[5] / 2
        assert 5 < 50 - DISPLACED_WINDOW_SESSIONS
        df = frame(closes, [0.0] * 50 + [RATIO] + [0.0, 0.0])
        assert normalize_basis(df, "X") is df

    def test_a_group_at_the_frames_oldest_bar_is_untouched(self):
        # No bar before it, so no step into the group.
        df = mixed({0, 1})
        assert normalize_basis(df, "MNST") is df

    def test_a_group_longer_than_the_bound_is_left_alone(self):
        df = mixed(set(range(3, 4 + MAX_DISPLACED_BARS)), n_pre=24)
        assert normalize_basis(df, "MNST") is df

    def test_a_group_at_the_bound_is_still_repaired(self):
        out = normalize_basis(mixed(set(range(3, 3 + MAX_DISPLACED_BARS)), n_pre=24), "MNST")
        assert out["close"].tolist() == pytest.approx(expected(n_pre=24))

    def test_a_frame_too_short_to_have_a_quiet_median_refuses(self):
        # With four bars the mis-quote's own two steps are the median, so the
        # band swallows both readings and nothing is decidable.
        df = mixed({1}, n_pre=3, n_post=1)
        assert normalize_basis(df, "X") is df

    def test_an_empty_frame(self):
        df = frame([])
        assert normalize_basis(df, "X") is df


class TestWindowsAgree:
    def test_two_different_adjustment_draws_land_on_the_same_prices(self):
        first = normalize_frame(mixed({5}), "MNST")
        second = normalize_frame(mixed({3, 7, 8}), "MNST")

        assert first["close"].tolist() == pytest.approx(second["close"].tolist())
        assert first["close"].tolist() == pytest.approx(true_series(15))

    def test_a_window_starting_before_the_group_agrees(self):
        wide = normalize_frame(mixed({8}, n_pre=20), "MNST")
        narrow = normalize_frame(mixed({8}, n_pre=20).iloc[4:], "MNST")

        shared = wide.index.intersection(narrow.index)
        assert wide.loc[shared, "close"].tolist() == pytest.approx(
            narrow.loc[shared, "close"].tolist()
        )


class TestWindowsThatStillDisagree:
    """The two windows that lose a step, recorded with the numbers they store.

    Neither is a regression — both are what ``normalize_splits`` did on its own
    — but neither is answered here either, and the values are the same shape as
    the corruption that prompted this module.
    """

    def test_a_window_starting_inside_a_group_stores_quarter_priced_bars(self):
        df = mixed({5, 6, 7}, n_pre=12)

        assert normalize_frame(df, "MNST")["close"].tolist()[6:9] == pytest.approx(
            [48.6, 48.7, 48.8]
        )
        # Bars 6 and 7 keep the provider's already-adjusted price and are
        # halved a second time by the rebasing around them.
        inside = normalize_frame(df.iloc[6:], "MNST")
        assert inside["close"].tolist()[:3] == pytest.approx([24.3, 24.35, 48.8])

    def test_a_group_ending_on_the_bar_before_the_ex_date_stores_a_cliff(self):
        out = normalize_frame(mixed({11}, n_pre=12), "MNST")

        # The ex-date step is measured against an already-adjusted bar, reads
        # ~1, and the whole pre-split region stays in the old basis.
        assert out["close"].iloc[10] == pytest.approx(98.0)
        assert out["close"].iloc[11] == pytest.approx(49.1)
