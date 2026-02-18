"""Tests for Yahoo Finance currency normalization (subunit → main currency)."""

import pandas as pd
import pytest

from app.services.yahoo import normalize_currency, _normalize_ohlcv_df


class TestNormalizeCurrency:
    def test_gbp_pence_lowercase_p(self):
        code, divisor = normalize_currency("GBp")
        assert code == "GBP"
        assert divisor == 100

    def test_gbx(self):
        code, divisor = normalize_currency("GBX")
        assert code == "GBP"
        assert divisor == 100

    def test_israeli_agorot(self):
        code, divisor = normalize_currency("ILA")
        assert code == "ILS"
        assert divisor == 100

    def test_south_african_cents(self):
        code, divisor = normalize_currency("ZAc")
        assert code == "ZAR"
        assert divisor == 100

    def test_usd_unchanged(self):
        code, divisor = normalize_currency("USD")
        assert code == "USD"
        assert divisor == 1

    def test_eur_unchanged(self):
        code, divisor = normalize_currency("EUR")
        assert code == "EUR"
        assert divisor == 1

    def test_gbp_already_normalized(self):
        code, divisor = normalize_currency("GBP")
        assert code == "GBP"
        assert divisor == 1

    def test_unknown_currency_passthrough(self):
        code, divisor = normalize_currency("XYZ")
        assert code == "XYZ"
        assert divisor == 1


class TestNormalizeOhlcvDf:
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            "open": [3200.0, 3250.0],
            "high": [3300.0, 3350.0],
            "low": [3100.0, 3150.0],
            "close": [3250.0, 3300.0],
            "volume": [1_000_000, 1_200_000],
        })

    def test_divisor_1_returns_same(self, sample_df):
        result = _normalize_ohlcv_df(sample_df, 1)
        assert result is sample_df  # no copy needed

    def test_pence_to_pounds(self, sample_df):
        result = _normalize_ohlcv_df(sample_df, 100)
        assert result["open"].tolist() == [32.0, 32.5]
        assert result["high"].tolist() == [33.0, 33.5]
        assert result["low"].tolist() == [31.0, 31.5]
        assert result["close"].tolist() == [32.5, 33.0]

    def test_volume_unchanged(self, sample_df):
        result = _normalize_ohlcv_df(sample_df, 100)
        assert result["volume"].tolist() == [1_000_000, 1_200_000]

    def test_does_not_mutate_original(self, sample_df):
        original_open = sample_df["open"].tolist()
        _normalize_ohlcv_df(sample_df, 100)
        assert sample_df["open"].tolist() == original_open

    def test_handles_adjclose(self):
        df = pd.DataFrame({
            "open": [3200.0],
            "high": [3300.0],
            "low": [3100.0],
            "close": [3250.0],
            "adjclose": [3250.0],
            "volume": [1_000_000],
        })
        result = _normalize_ohlcv_df(df, 100)
        assert result["adjclose"].tolist() == [32.5]
        assert result["volume"].tolist() == [1_000_000]
