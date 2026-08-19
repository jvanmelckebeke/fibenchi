"""Split normalization: rebasing a frame onto the current share basis (#648)."""

import pandas as pd
import pytest

from app.services.compute.splits import SPLIT_STEP_FACTOR, normalize_splits


def frame(closes: list[float], splits: list[float] | None = None) -> pd.DataFrame:
    """A minimal daily frame: closes, matching OHLC, volume, split events."""
    dates = pd.date_range("2026-01-01", periods=len(closes), freq="D").date
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": [1_000_000] * len(closes),
            "splits": splits if splits is not None else [0.0] * len(closes),
        },
        index=pd.Index(dates, name="date"),
    )


class TestUnadjustedFrames:
    def test_rebases_pre_split_bars_and_leaves_the_rest(self):
        # The MNST shape: a clean 2:1 step the provider reported but never applied.
        df = frame([94.4, 90.4, 45.5, 46.0], splits=[0, 0, 2.0, 0])
        out = normalize_splits(df, "MNST")

        assert list(out["close"].round(2)) == [47.20, 45.20, 45.50, 46.00]
        assert list(out["open"].round(2)) == [47.20, 45.20, 45.50, 46.00]
        # High/low ride along, or the bar stops containing its own close.
        assert out["high"].iloc[0] == pytest.approx(94.4 * 1.01 / 2)
        assert out["low"].iloc[0] == pytest.approx(94.4 * 0.99 / 2)

    def test_volume_moves_the_other_way(self):
        # Twice the shares outstanding means the old session's share count has
        # to double to stay comparable with today's.
        out = normalize_splits(frame([90.0, 45.0], splits=[0, 2.0]), "X")
        assert list(out["volume"]) == [2_000_000, 1_000_000]

    def test_reverse_split_scales_up(self):
        # 1:10 reverse: ratio 0.1, so the pre-split bars multiply by 10.
        df = frame([2.0, 2.1, 21.0, 20.5], splits=[0, 0, 0.1, 0])
        out = normalize_splits(df, "X")
        assert list(out["close"].round(2)) == [20.0, 21.0, 21.0, 20.5]

    def test_several_splits_compose(self):
        # The oldest bar is behind both, so it carries the product.
        df = frame([80.0, 40.0, 41.0, 20.5], splits=[0, 2.0, 0, 2.0])
        out = normalize_splits(df, "X")
        assert list(out["close"].round(2)) == [20.0, 20.0, 20.5, 20.5]


class TestFramesThatMustBeLeftAlone:
    def test_already_adjusted_frame_is_untouched(self):
        # Yahoo eventually applies the split itself. The event stays in the
        # response, so the only thing separating this from the case above is
        # that the prices are already continuous.
        df = frame([47.2, 45.2, 45.5, 46.0], splits=[0, 0, 2.0, 0])
        assert normalize_splits(df, "MNST") is df

    def test_running_twice_changes_nothing(self):
        # The property the whole design rests on: no record is kept of what was
        # applied, so a second pass must reach the same answer on its own.
        df = frame([94.4, 90.4, 45.5, 46.0], splits=[0, 0, 2.0, 0])
        once = normalize_splits(df, "MNST")
        twice = normalize_splits(once, "MNST")
        assert list(twice["close"]) == list(once["close"])
        assert list(twice["volume"]) == list(once["volume"])

    def test_uncorroborated_split_is_refused(self):
        # The event says 2:1 but the prices barely moved. Applying it would
        # manufacture a +100% day. Leave it and let the vol guard withhold.
        df = frame([90.0, 89.0, 88.0, 87.0], splits=[0, 0, 2.0, 0])
        assert normalize_splits(df, "X") is df

    def test_a_real_crash_on_an_ex_date_is_refused(self):
        # -30% is far from both 0.5 and 1.0. Nearest-hypothesis would call it a
        # split and "correct" it into +40%; the tolerance band refuses instead.
        df = frame([90.0, 63.0], splits=[0, 2.0])
        assert normalize_splits(df, "X") is df

    def test_split_on_the_first_bar_has_no_evidence(self):
        df = frame([45.5, 46.0], splits=[2.0, 0])
        assert normalize_splits(df, "X") is df

    def test_a_real_crash_with_no_split_event_is_untouched(self):
        # OKLO's -54% SPAC reprice, 2024-05-10. Split-sized, and real.
        df = frame([18.23, 8.45])
        assert normalize_splits(df, "OKLO") is df

    def test_frame_without_a_splits_column_is_untouched(self):
        # yahooquery omits the column for symbols Yahoo reports no splits for,
        # which is most of them.
        df = frame([10.0, 11.0]).drop(columns=["splits"])
        assert normalize_splits(df, "X") is df

    def test_empty_frame(self):
        df = frame([])
        assert normalize_splits(df, "X") is df


class TestStepFactor:
    def test_sits_between_the_smallest_split_and_the_largest_real_move(self):
        # Both bounds are measured, not chosen. A 3:2 split steps by 1.5x, so
        # anything at or above that never gets examined. The largest genuine
        # single-session moves in the book are IBM 2026-07-14 and MDA.TO
        # 2025-09-08, both 0.75, both confirmed split-free against the
        # provider; the threshold has to clear them or the heal spends every
        # run re-fetching ordinary earnings days.
        smallest_split_step = 1.5  # 3:2
        largest_real_move = 1 / 0.75
        assert largest_real_move < SPLIT_STEP_FACTOR < smallest_split_step
