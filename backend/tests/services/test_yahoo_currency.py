"""Tests for Yahoo Finance currency normalization and detection."""

from unittest.mock import MagicMock, PropertyMock, patch

import pandas as pd
import pytest

from app.services.yahoo import (
    EXCHANGE_CURRENCY_MAP,
    _currency_from_suffix,
    _extract_currency,
    _normalize_ohlcv_df,
    normalize_currency,
)


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


class TestCurrencyFromSuffix:
    """Tests for _currency_from_suffix exchange-suffix-to-currency mapping."""

    def test_kospi_returns_krw(self):
        assert _currency_from_suffix("006260.KS") == "KRW"

    def test_kosdaq_returns_krw(self):
        assert _currency_from_suffix("035420.KQ") == "KRW"

    def test_tokyo_returns_jpy(self):
        assert _currency_from_suffix("7203.T") == "JPY"

    def test_hong_kong_returns_hkd(self):
        assert _currency_from_suffix("0700.HK") == "HKD"

    def test_xetra_returns_eur(self):
        assert _currency_from_suffix("VWCE.DE") == "EUR"

    def test_london_returns_gbp(self):
        assert _currency_from_suffix("HSBA.L") == "GBP"

    def test_toronto_returns_cad(self):
        assert _currency_from_suffix("RY.TO") == "CAD"

    def test_australia_returns_aud(self):
        assert _currency_from_suffix("CBA.AX") == "AUD"

    def test_india_nse_returns_inr(self):
        assert _currency_from_suffix("RELIANCE.NS") == "INR"

    def test_india_bse_returns_inr(self):
        assert _currency_from_suffix("RELIANCE.BO") == "INR"

    def test_shanghai_returns_cny(self):
        assert _currency_from_suffix("600519.SS") == "CNY"

    def test_swiss_returns_chf(self):
        assert _currency_from_suffix("NESN.SW") == "CHF"

    def test_copenhagen_returns_dkk(self):
        assert _currency_from_suffix("NOVO-B.CO") == "DKK"

    def test_oslo_returns_nok(self):
        assert _currency_from_suffix("EQNR.OL") == "NOK"

    def test_stockholm_returns_sek(self):
        assert _currency_from_suffix("VOLV-B.ST") == "SEK"

    def test_no_suffix_returns_none(self):
        assert _currency_from_suffix("AAPL") is None

    def test_unknown_suffix_returns_none(self):
        assert _currency_from_suffix("FOO.ZZ") is None

    def test_case_insensitive_suffix(self):
        """Suffix lookup handles case variations (e.g. '.ks' vs '.KS')."""
        assert _currency_from_suffix("006260.ks") == "KRW"

    def test_all_map_entries_are_iso_4217_length(self):
        """All currency codes in the exchange map are 3 characters (ISO 4217)."""
        for suffix, currency in EXCHANGE_CURRENCY_MAP.items():
            assert len(currency) == 3, f"{suffix} maps to non-ISO code: {currency}"
            assert currency == currency.upper(), f"{suffix} maps to non-uppercase: {currency}"


class TestExtractCurrency:
    """Tests for _extract_currency which tries multiple Yahoo data sources."""

    def _make_ticker(self, price_data=None, detail_data=None):
        """Create a mock Ticker with configurable price and summary_detail."""
        ticker = MagicMock()
        type(ticker).price = PropertyMock(return_value=price_data or {})
        type(ticker).summary_detail = PropertyMock(return_value=detail_data or {})
        return ticker

    def test_extracts_from_price_data(self):
        """Primary path: currency from ticker.price."""
        ticker = self._make_ticker(
            price_data={"006260.KS": {"currency": "KRW", "regularMarketPrice": 50000}},
        )
        currency, divisor = _extract_currency(ticker, "006260.KS")
        assert currency == "KRW"
        assert divisor == 1

    def test_normalizes_subunit_from_price_data(self):
        """Subunit currency (GBp) from ticker.price is normalized to GBP."""
        ticker = self._make_ticker(
            price_data={"HSBA.L": {"currency": "GBp"}},
        )
        currency, divisor = _extract_currency(ticker, "HSBA.L")
        assert currency == "GBP"
        assert divisor == 100

    def test_falls_back_to_summary_detail(self):
        """When ticker.price has no currency, try ticker.summary_detail."""
        ticker = self._make_ticker(
            price_data={"006260.KS": "No data found"},  # error string, not dict
            detail_data={"006260.KS": {"currency": "KRW"}},
        )
        currency, divisor = _extract_currency(ticker, "006260.KS")
        assert currency == "KRW"
        assert divisor == 1

    def test_falls_back_to_suffix_when_both_fail(self):
        """When both Yahoo data sources fail, use exchange suffix mapping."""
        ticker = self._make_ticker(
            price_data={"006260.KS": "No data found"},
            detail_data={"006260.KS": "No data found"},
        )
        currency, divisor = _extract_currency(ticker, "006260.KS")
        assert currency == "KRW"
        assert divisor == 1

    def test_defaults_to_usd_when_all_fail(self):
        """When all sources fail and there's no recognized suffix, default to USD."""
        ticker = self._make_ticker(
            price_data={"UNKNOWN": "error"},
            detail_data={"UNKNOWN": "error"},
        )
        currency, divisor = _extract_currency(ticker, "UNKNOWN")
        assert currency == "USD"
        assert divisor == 1

    def test_price_data_missing_currency_key(self):
        """When ticker.price returns a dict but without 'currency' key, try fallback."""
        ticker = self._make_ticker(
            price_data={"006260.KS": {"regularMarketPrice": 50000}},  # no currency key
            detail_data={"006260.KS": {"currency": "KRW"}},
        )
        currency, divisor = _extract_currency(ticker, "006260.KS")
        assert currency == "KRW"
        assert divisor == 1

    def test_price_data_none_currency(self):
        """When ticker.price has currency=None, try fallback."""
        ticker = self._make_ticker(
            price_data={"006260.KS": {"currency": None}},
            detail_data={"006260.KS": {"currency": "KRW"}},
        )
        currency, divisor = _extract_currency(ticker, "006260.KS")
        assert currency == "KRW"
        assert divisor == 1

    def test_summary_detail_normalizes_subunit(self):
        """Subunit from summary_detail is also normalized."""
        ticker = self._make_ticker(
            price_data={"HSBA.L": "error"},
            detail_data={"HSBA.L": {"currency": "GBp"}},
        )
        currency, divisor = _extract_currency(ticker, "HSBA.L")
        assert currency == "GBP"
        assert divisor == 100

    def test_empty_price_data_dict(self):
        """Empty dict from ticker.price triggers fallback."""
        ticker = self._make_ticker(
            price_data={},
            detail_data={"AAPL": {"currency": "USD"}},
        )
        currency, divisor = _extract_currency(ticker, "AAPL")
        assert currency == "USD"
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
