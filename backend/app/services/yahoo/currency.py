"""Currency resolution and OHLCV normalization for Yahoo Finance data."""

import pandas as pd

from app.services.currency_service import lookup as currency_lookup

# Fallback mapping from Yahoo Finance exchange suffixes to ISO 4217 currency codes.
# Used when ticker.price doesn't return currency data for a symbol.
EXCHANGE_CURRENCY_MAP: dict[str, str] = {
    # Asia-Pacific
    ".KS": "KRW",   # Korea (KOSPI)
    ".KQ": "KRW",   # Korea (KOSDAQ)
    ".T": "JPY",    # Tokyo
    ".HK": "HKD",   # Hong Kong
    ".SS": "CNY",   # Shanghai
    ".SZ": "CNY",   # Shenzhen
    ".TW": "TWD",   # Taiwan (TWSE)
    ".TWO": "TWD",  # Taiwan (OTC)
    ".SI": "SGD",   # Singapore
    ".AX": "AUD",   # Australia (ASX)
    ".NZ": "NZD",   # New Zealand
    ".NS": "INR",   # India (NSE)
    ".BO": "INR",   # India (BSE)
    ".JK": "IDR",   # Jakarta
    ".BK": "THB",   # Bangkok
    # Europe
    ".L": "GBP",    # London
    ".IL": "GBP",   # London (IOB)
    ".PA": "EUR",   # Paris
    ".DE": "EUR",   # XETRA (Germany)
    ".F": "EUR",    # Frankfurt
    ".MI": "EUR",   # Milan
    ".MC": "EUR",   # Madrid
    ".AS": "EUR",   # Amsterdam
    ".BR": "EUR",   # Brussels
    ".LS": "EUR",   # Lisbon
    ".HE": "EUR",   # Helsinki
    ".AT": "EUR",   # Athens
    ".VI": "EUR",   # Vienna
    ".IR": "EUR",   # Dublin
    ".OL": "NOK",   # Oslo
    ".ST": "SEK",   # Stockholm
    ".CO": "DKK",   # Copenhagen
    ".IC": "ISK",   # Iceland
    ".WA": "PLN",   # Warsaw
    ".PR": "CZK",   # Prague
    ".BD": "HUF",   # Budapest
    ".SW": "CHF",   # Swiss Exchange
    ".IS": "TRY",   # Istanbul
    # Middle East & Africa
    ".TA": "ILS",   # Tel Aviv
    ".SR": "SAR",   # Saudi (Tadawul)
    ".QA": "QAR",   # Qatar
    ".JO": "ZAR",   # Johannesburg
    # Americas
    ".TO": "CAD",   # Toronto (TSX)
    ".V": "CAD",    # TSX Venture
    ".SA": "BRL",   # Sao Paulo
    ".MX": "MXN",   # Mexico
    ".SN": "CLP",   # Santiago
    ".BA": "ARS",   # Buenos Aires
}


def currency_from_suffix(symbol: str) -> str | None:
    """Derive currency from a Yahoo Finance exchange suffix (e.g. '.KS' -> 'KRW').

    Returns None if the symbol has no recognized suffix.
    """
    dot = symbol.rfind(".")
    if dot == -1:
        return None
    suffix = symbol[dot:]
    return EXCHANGE_CURRENCY_MAP.get(suffix.upper()) or EXCHANGE_CURRENCY_MAP.get(suffix)


def resolve_currency(info: dict, symbol: str) -> tuple[str, int]:
    """Resolve display currency and subunit divisor from Yahoo price info.

    Applies the standard fallback chain:
      1. Extract raw currency from the price info dict
      2. Look it up in the currency cache (handles subunits like GBp -> GBP/100)
      3. Fall back to exchange-suffix mapping
      4. Default to ("USD", 1)

    Returns (display_code, divisor).
    """
    raw = info.get("currency") if isinstance(info, dict) else None
    if raw:
        return currency_lookup(raw)
    suffix_currency = currency_from_suffix(symbol)
    if suffix_currency:
        return (suffix_currency, 1)
    return ("USD", 1)


def _normalize_ohlcv_df(df: pd.DataFrame, divisor: int) -> pd.DataFrame:
    """Divide OHLCV price columns by divisor. Volume is left unchanged."""
    if divisor == 1:
        return df
    price_cols = [c for c in ("open", "high", "low", "close", "adjclose") if c in df.columns]
    df = df.copy()
    df[price_cols] = df[price_cols] / divisor
    return df
