"""Tests for Yahoo Finance currency detection and OHLCV normalization."""

from unittest.mock import MagicMock, PropertyMock, patch

import pandas as pd
import pytest

from app.services.yahoo import (
    EXCHANGE_CURRENCY_MAP,
    currency_from_suffix,
    _normalize_ohlcv_df,
)


class TestCurrencyFromSuffix:
    """Tests for currency_from_suffix exchange-suffix-to-currency mapping."""

    def test_kospi_returns_krw(self):
        assert currency_from_suffix("006260.KS") == "KRW"

    def test_kosdaq_returns_krw(self):
        assert currency_from_suffix("035420.KQ") == "KRW"

    def test_tokyo_returns_jpy(self):
        assert currency_from_suffix("7203.T") == "JPY"

    def test_hong_kong_returns_hkd(self):
        assert currency_from_suffix("0700.HK") == "HKD"

    def test_xetra_returns_eur(self):
        assert currency_from_suffix("VWCE.DE") == "EUR"

    def test_london_returns_gbp(self):
        assert currency_from_suffix("HSBA.L") == "GBP"

    def test_toronto_returns_cad(self):
        assert currency_from_suffix("RY.TO") == "CAD"

    def test_australia_returns_aud(self):
        assert currency_from_suffix("CBA.AX") == "AUD"

    def test_india_nse_returns_inr(self):
        assert currency_from_suffix("RELIANCE.NS") == "INR"

    def test_india_bse_returns_inr(self):
        assert currency_from_suffix("RELIANCE.BO") == "INR"

    def test_shanghai_returns_cny(self):
        assert currency_from_suffix("600519.SS") == "CNY"

    def test_swiss_returns_chf(self):
        assert currency_from_suffix("NESN.SW") == "CHF"

    def test_copenhagen_returns_dkk(self):
        assert currency_from_suffix("NOVO-B.CO") == "DKK"

    def test_oslo_returns_nok(self):
        assert currency_from_suffix("EQNR.OL") == "NOK"

    def test_stockholm_returns_sek(self):
        assert currency_from_suffix("VOLV-B.ST") == "SEK"

    def test_no_suffix_returns_none(self):
        assert currency_from_suffix("AAPL") is None

    def test_unknown_suffix_returns_none(self):
        assert currency_from_suffix("FOO.ZZ") is None

    def test_case_insensitive_suffix(self):
        """Suffix lookup handles case variations (e.g. '.ks' vs '.KS')."""
        assert currency_from_suffix("006260.ks") == "KRW"

    def test_all_map_entries_are_iso_4217_length(self):
        """All currency codes in the exchange map are 3 characters (ISO 4217)."""
        for suffix, currency in EXCHANGE_CURRENCY_MAP.items():
            assert len(currency) == 3, f"{suffix} maps to non-ISO code: {currency}"
            assert currency == currency.upper(), f"{suffix} maps to non-uppercase: {currency}"


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
