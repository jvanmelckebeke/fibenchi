"""FX close recovery: reading the session close off the next bar's open (#670)."""

import pandas as pd
import pytest

from app.services.compute.fx_close import (
    FX_BODY_CEILING,
    MIN_BODY_SAMPLE,
    normalize_fx_close,
)
from tests.helpers import daily_date_index


def frame(opens: list[float], closes: list[float] | None = None) -> pd.DataFrame:
    """A daily frame whose closes default to its opens — the defect's shape.

    High/low straddle the *pair* of opens either side of each bar, so the
    genuine intraday travel is inside the range the way Yahoo reports it.
    """
    closes = list(opens) if closes is None else closes
    nxt = opens[1:] + [opens[-1]]
    return pd.DataFrame(
        {
            "open": opens,
            "high": [max(o, n) * 1.002 for o, n in zip(opens, nxt)],
            "low": [min(o, n) * 0.998 for o, n in zip(opens, nxt)],
            "close": closes,
            "volume": [0] * len(opens),
        },
        index=daily_date_index(len(opens)),
    )


DEFECTIVE = [158.9, 155.6, 156.0, 155.3, 154.4, 154.9]


class TestRecovery:
    def test_close_becomes_the_next_bar_open(self):
        out = normalize_fx_close(frame(DEFECTIVE), "JPY=X")
        assert list(out["close"])[:-1] == DEFECTIVE[1:]

    def test_trailing_bar_keeps_the_provider_close(self):
        # It has no successor, and while it is still forming Yahoo tracks the
        # live price there — which is the one close it gets right.
        df = frame(DEFECTIVE)
        df.loc[df.index[-1], "close"] = 153.1
        out = normalize_fx_close(df, "JPY=X")
        assert out["close"].iloc[-1] == pytest.approx(153.1)

    def test_range_widens_to_contain_the_recovered_close(self):
        # A gap between Yahoo's daily window and the next open leaves the true
        # close outside the bar's own high/low.
        df = frame(DEFECTIVE)
        df.loc[df.index[0], ["high", "low"]] = [159.0, 158.5]
        out = normalize_fx_close(df, "JPY=X")
        assert out["close"].iloc[0] == pytest.approx(155.6)
        assert out["low"].iloc[0] == pytest.approx(155.6)
        assert out["high"].iloc[0] == pytest.approx(159.0)

    def test_open_high_low_of_a_contained_bar_are_untouched(self):
        df = frame(DEFECTIVE)
        out = normalize_fx_close(df, "JPY=X")
        assert list(out["open"]) == list(df["open"])
        assert out["high"].iloc[1] == pytest.approx(df["high"].iloc[1])
        assert out["low"].iloc[1] == pytest.approx(df["low"].iloc[1])

    def test_rerunning_on_the_same_provider_frame_is_stable(self):
        df = frame(DEFECTIVE)
        assert normalize_fx_close(df, "JPY=X").equals(
            normalize_fx_close(df.copy(), "JPY=X")
        )


class TestGating:
    @pytest.mark.parametrize("symbol", ["AAPL", "BTC-USD", "GC=F", "^GSPC", "IWDA.AS"])
    def test_only_fx_shapes_are_touched(self, symbol):
        # Futures and crypto are continuous too, and measure clean — 0.43-0.65
        # median body against FX's 0.00-0.02.
        df = frame(DEFECTIVE)
        assert normalize_fx_close(df, symbol) is df

    def test_missing_symbol_is_not_fx(self):
        df = frame(DEFECTIVE)
        assert normalize_fx_close(df, None) is df

    def test_a_frame_with_real_bodies_is_left_alone(self):
        # The day Yahoo starts publishing a real FX close, this stops firing.
        df = frame(DEFECTIVE, closes=[155.7, 156.1, 155.4, 154.5, 155.0, 153.1])
        assert normalize_fx_close(df, "JPY=X") is df

    def test_a_frame_too_short_to_judge_is_left_alone(self):
        df = frame(DEFECTIVE[:MIN_BODY_SAMPLE - 1])
        assert normalize_fx_close(df, "JPY=X") is df

    def test_empty_frame(self):
        df = pd.DataFrame()
        assert normalize_fx_close(df, "JPY=X") is df

    def test_frame_without_ohlc_columns(self):
        df = pd.DataFrame({"close": [1.0, 2.0]})
        assert normalize_fx_close(df, "JPY=X") is df

    def test_zero_range_bars_do_not_count_toward_the_sample(self):
        # A flat bar has no body to measure; enough of them and the frame
        # can't say whether its closes are opens.
        df = frame(DEFECTIVE)
        for i in range(len(df) - MIN_BODY_SAMPLE + 1):
            df.loc[df.index[i], ["high", "low"]] = [100.0, 100.0]
        assert normalize_fx_close(df, "JPY=X") is df

    def test_body_ceiling_is_the_boundary(self):
        # Bodies just under the ceiling read as the defect; just over, they don't.
        span = 1.0
        for factor, repaired in ((FX_BODY_CEILING / 2, True), (FX_BODY_CEILING * 2, False)):
            opens = [100.0 + i for i in range(6)]
            df = pd.DataFrame(
                {
                    "open": opens,
                    "high": [o + span / 2 for o in opens],
                    "low": [o - span / 2 for o in opens],
                    "close": [o + span * factor for o in opens],
                    "volume": [0] * len(opens),
                },
                index=daily_date_index(len(opens)),
            )
            out = normalize_fx_close(df, "EURUSD=X")
            assert (out is not df) is repaired
