"""Euronext symbol provider — fetches stock listings from Euronext's public CSV export."""

import csv
import io
import logging

import httpx

from app.services.symbol_providers.base import SymbolEntry, SymbolProvider

logger = logging.getLogger(__name__)

EURONEXT_CSV_URL = (
    "https://live.euronext.com/en/pd_es/data/stocks/download"
    "?mics=dm_all_stock&initialLetter=&fe_type=csv&fe_decimal_separator=.&fe_date_format=d%2Fm%2FY"
)

# Maps Euronext market display names to Yahoo Finance ticker suffixes.
MARKET_SUFFIX: dict[str, str] = {
    "Euronext Amsterdam": ".AS",
    "Euronext Brussels": ".BR",
    "Euronext Paris": ".PA",
    "Oslo Børs": ".OL",
    "Euronext Milan": ".MI",
    "Euronext Lisbon": ".LS",
    "Euronext Dublin": ".IR",
    # Growth / Access / Expand sub-markets inherit parent suffix
    "Euronext Growth Paris": ".PA",
    "Euronext Access Paris": ".PA",
    "Euronext Growth Milan": ".MI",
    "Euronext Growth Oslo": ".OL",
    "Euronext Expand Oslo": ".OL",
    "Euronext Growth Brussels": ".BR",
    "Euronext Access Brussels": ".BR",
    "Euronext Growth Dublin": ".IR",
    "Euronext Access Dublin": ".IR",
    "Euronext Growth Lisbon": ".LS",
    "Euronext Access Lisbon": ".LS",
}

# Markets to always skip (cross-listed international stocks, not native Euronext)
SKIP_MARKETS = {"Euronext Global Equity Market", "Trading After Hours", "EuroTLX", "Euronext Expert Market"}

# Canonical market key → display names that belong to it.
# Used to filter by user-selected markets.
MARKET_GROUPS: dict[str, list[str]] = {
    "amsterdam": ["Euronext Amsterdam"],
    "brussels": ["Euronext Brussels", "Euronext Growth Brussels", "Euronext Access Brussels"],
    "paris": ["Euronext Paris", "Euronext Growth Paris", "Euronext Access Paris"],
    "oslo": ["Oslo Børs", "Euronext Growth Oslo", "Euronext Expand Oslo"],
    "milan": ["Euronext Milan", "Euronext Growth Milan"],
    "lisbon": ["Euronext Lisbon", "Euronext Growth Lisbon", "Euronext Access Lisbon"],
    "dublin": ["Euronext Dublin", "Euronext Growth Dublin", "Euronext Access Dublin"],
}

_AVAILABLE_MARKETS = [
    {"key": "amsterdam", "label": "Euronext Amsterdam"},
    {"key": "brussels", "label": "Euronext Brussels"},
    {"key": "paris", "label": "Euronext Paris"},
    {"key": "oslo", "label": "Oslo Børs"},
    {"key": "milan", "label": "Euronext Milan"},
    {"key": "lisbon", "label": "Euronext Lisbon"},
    {"key": "dublin", "label": "Euronext Dublin"},
]


def _resolve_market(raw_market: str | None) -> tuple[str | None, str | None]:
    """Resolve a raw CSV market string to (suffix, canonical_key).

    For multi-market listings like "Euronext Brussels, Amsterdam",
    uses the first listed market.
    """
    if not raw_market:
        return None, None
    raw = raw_market.strip().strip('"')

    if raw in SKIP_MARKETS:
        return None, None

    # Direct match
    if raw in MARKET_SUFFIX:
        suffix = MARKET_SUFFIX[raw]
        # Find canonical key
        for key, members in MARKET_GROUPS.items():
            if raw in members:
                return suffix, key
        return suffix, None

    # Multi-market listing: "Euronext Brussels, Amsterdam" → try "Euronext Brussels"
    if "," in raw:
        first_part = raw.split(",")[0].strip()
        if first_part in MARKET_SUFFIX:
            suffix = MARKET_SUFFIX[first_part]
            for key, members in MARKET_GROUPS.items():
                if first_part in members:
                    return suffix, key
            return suffix, None

    return None, None


class EuronextProvider(SymbolProvider):
    """Fetches stock listings from Euronext's public CSV export."""

    async def fetch_symbols(self, config: dict) -> list[SymbolEntry]:
        enabled_markets: set[str] = set(config.get("markets", []))

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(config.get("url", EURONEXT_CSV_URL))
            resp.raise_for_status()

        # CSV starts with BOM + 4 header/info rows before data
        text = resp.text.lstrip("\ufeff")
        lines = text.splitlines()

        # Find the actual header row (contains "Name;ISIN;Symbol;...")
        header_idx = 0
        for i, line in enumerate(lines):
            if line.startswith("Name;") or line.startswith('"Name"'):
                header_idx = i
                break

        data_lines = lines[header_idx:]  # header + data rows
        reader = csv.DictReader(io.StringIO("\n".join(data_lines)), delimiter=";")

        results: list[SymbolEntry] = []
        for row in reader:
            raw_market = row.get("Market", "")
            suffix, market_key = _resolve_market(raw_market)

            if suffix is None:
                continue

            # Filter by enabled markets if any are specified
            if enabled_markets and market_key not in enabled_markets:
                continue

            raw_symbol = row.get("Symbol", "").strip().strip('"')
            raw_name = row.get("Name", "").strip().strip('"')
            raw_currency = row.get("Currency", "").strip().strip('"')

            if not raw_symbol or not raw_name:
                continue

            yahoo_symbol = f"{raw_symbol}{suffix}"

            results.append(SymbolEntry(
                symbol=yahoo_symbol,
                name=raw_name,
                exchange=raw_market.strip().strip('"'),
                currency=raw_currency,
                type="stock",
            ))

        logger.info("Euronext provider fetched %d symbols (markets=%s)", len(results), enabled_markets or "all")
        return results

    @staticmethod
    def available_markets() -> list[dict]:
        return list(_AVAILABLE_MARKETS)
