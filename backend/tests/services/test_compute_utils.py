"""Tests for shared compute utility functions."""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest

from app.services.compute.utils import prices_to_df


def _make_price(d: date, open_: float, high: float, low: float, close: float, volume: int):
    """Create a mock PriceHistory object."""
    p = MagicMock()
    p.date = d
    p.open = open_
    p.high = high
    p.low = low
    p.close = close
    p.volume = volume
    return p


class TestPricesToDf:
    def test_converts_to_dataframe(self):
        prices = [
            _make_price(date(2025, 1, 2), 100.0, 105.0, 99.0, 102.0, 1_000_000),
            _make_price(date(2025, 1, 3), 102.0, 106.0, 101.0, 104.0, 1_200_000),
        ]
        df = prices_to_df(prices)

        assert isinstance(df, pd.DataFrame)
        assert df.index.name == "date"
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 2

    def test_values_correct(self):
        prices = [_make_price(date(2025, 1, 2), 100.0, 105.0, 99.0, 102.0, 1_000_000)]
        df = prices_to_df(prices)

        assert df.iloc[0]["open"] == 100.0
        assert df.iloc[0]["high"] == 105.0
        assert df.iloc[0]["low"] == 99.0
        assert df.iloc[0]["close"] == 102.0
        assert df.iloc[0]["volume"] == 1_000_000

    def test_date_as_index(self):
        prices = [
            _make_price(date(2025, 1, 2), 100.0, 105.0, 99.0, 102.0, 1_000_000),
            _make_price(date(2025, 1, 3), 102.0, 106.0, 101.0, 104.0, 1_200_000),
        ]
        df = prices_to_df(prices)

        assert df.index[0] == date(2025, 1, 2)
        assert df.index[1] == date(2025, 1, 3)

    def test_empty_prices(self):
        """Empty input raises KeyError due to missing 'date' column in set_index."""
        with pytest.raises(KeyError):
            prices_to_df([])

    def test_preserves_order(self):
        prices = [
            _make_price(date(2025, 1, 5), 110.0, 115.0, 109.0, 112.0, 800_000),
            _make_price(date(2025, 1, 2), 100.0, 105.0, 99.0, 102.0, 1_000_000),
        ]
        df = prices_to_df(prices)

        # Order should match input, not be sorted by date
        assert df.index[0] == date(2025, 1, 5)
        assert df.index[1] == date(2025, 1, 2)
