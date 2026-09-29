"""The provider-frame pipeline: which steps a symbol's kind earns it (#670)."""

import pandas as pd
import pytest

from app.domain.instrument import AssetKind
from app.services.yahoo.normalize import (
    BY_KIND,
    UNIVERSAL,
    normalize_frame,
    normalize_splits,
    recover_fx_close,
    steps_for,
)
from tests.helpers import daily_date_index


class TestDispatch:
    def test_every_symbol_gets_the_universal_steps(self):
        for symbol in ("AAPL", "JPY=X", "BTC-USD", "GC=F", "^GSPC", "IWDA.AS"):
            assert normalize_splits in steps_for(symbol)

    def test_only_fx_gets_the_close_recovery(self):
        assert recover_fx_close in steps_for("JPY=X")
        for symbol in ("AAPL", "BTC-USD", "GC=F", "^GSPC", "IWDA.AS", "MSFT"):
            assert recover_fx_close not in steps_for(symbol)

    def test_universal_steps_come_first(self):
        steps = steps_for("EURUSD=X")
        assert steps[: len(UNIVERSAL)] == UNIVERSAL

    def test_an_unclassifiable_symbol_still_gets_the_universal_steps(self):
        assert steps_for(None) == UNIVERSAL
        assert steps_for("") == UNIVERSAL

    def test_no_kind_specific_step_is_also_a_universal_one(self):
        # A step in both lists would run twice on the kind that names it.
        for steps in BY_KIND.values():
            assert not set(steps) & set(UNIVERSAL)

    def test_registry_is_keyed_by_the_enum_not_by_strings(self):
        assert all(isinstance(k, AssetKind) for k in BY_KIND)


def _fx_frame() -> pd.DataFrame:
    opens = [158.9, 155.6, 156.0, 155.3, 154.4, 154.9]
    return pd.DataFrame(
        {
            "open": opens,
            "high": [o * 1.01 for o in opens],
            "low": [o * 0.99 for o in opens],
            "close": opens,
            "volume": [0] * len(opens),
        },
        index=daily_date_index(len(opens)),
    )


class TestPipeline:
    def test_fx_frame_comes_out_with_recovered_closes(self):
        out = normalize_frame(_fx_frame(), "JPY=X")
        assert list(out["close"])[:-1] == [155.6, 156.0, 155.3, 154.4, 154.9]

    def test_the_same_frame_under_an_equity_symbol_is_untouched(self):
        # The one assertion that proves the kind gate is the registry's and
        # not a test buried inside the FX step.
        df = _fx_frame()
        assert normalize_frame(df, "AAPL")["close"].equals(df["close"])

    def test_a_frame_with_no_quirk_to_fix_is_returned_as_is(self):
        df = _fx_frame()
        df["close"] = [o * 1.008 for o in df["open"]]
        assert normalize_frame(df, "JPY=X") is df

    def test_symbol_is_optional(self):
        df = _fx_frame()
        assert normalize_frame(df)["close"].equals(df["close"])

    def test_steps_take_the_frame_and_symbol_and_return_a_frame(self):
        df = _fx_frame()
        for step in (*UNIVERSAL, *(s for v in BY_KIND.values() for s in v)):
            assert isinstance(step(df, "JPY=X"), pd.DataFrame)

    def test_empty_frame_survives_every_step(self):
        assert normalize_frame(pd.DataFrame(), "JPY=X").empty


@pytest.mark.parametrize("symbol", ["JPY=X", "AAPL"])
def test_pipeline_is_idempotent_on_a_reissued_provider_frame(symbol):
    # Every fetch re-runs on the raw frame, so the same frame twice has to
    # give the same answer twice.
    df = _fx_frame()
    assert normalize_frame(df, symbol).equals(normalize_frame(df.copy(), symbol))
