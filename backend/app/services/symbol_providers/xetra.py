"""Xetra symbol provider — fetches stock + ETF listings from Deutsche Börse's public CSV."""

import csv
import io
import logging

import httpx

from app.services.symbol_providers.base import SymbolEntry, SymbolProvider

logger = logging.getLogger(__name__)

XETRA_URL = (
    "https://www.cashmarket.deutsche-boerse.com/resource/blob/1528"
    "/57f4f5c50d1901ec167614242a2ffd7a/data/t7-xetr-allTradableInstruments.csv"
)

# Instrument Type values we care about (skip ETN, ETC, warrants, bonds, etc.)
_ALLOWED_TYPES = {"CS", "ETF"}

# Map Xetra Instrument Type → our canonical type string
_TYPE_MAP = {"CS": "stock", "ETF": "etf"}


class XetraProvider(SymbolProvider):
    """Fetches stock + ETF listings from Deutsche Börse Xetra's public CSV."""

    async def fetch_symbols(self, config: dict) -> list[SymbolEntry]:
        url = config.get("url", XETRA_URL)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        results = _parse_csv(resp.text)

        logger.info(
            "Xetra provider fetched %d symbols (%d stocks, %d ETFs)",
            len(results),
            sum(1 for r in results if r.type == "stock"),
            sum(1 for r in results if r.type == "etf"),
        )
        return results

    @staticmethod
    def available_markets() -> list[dict]:
        return [{"key": "xetra", "label": "Xetra (Deutsche Börse)"}]


def _parse_csv(raw_text: str) -> list[SymbolEntry]:
    """Parse Xetra's all-tradable-instruments CSV into SymbolEntry objects."""
    text = raw_text.lstrip("\ufeff")
    lines = text.splitlines()

    # Skip metadata lines (e.g. "Market:;XETR", "Date Last Update:;...") to find the header
    header_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("Product Status"):
            header_idx = i
            break

    data_lines = lines[header_idx:]
    reader = csv.DictReader(io.StringIO("\n".join(data_lines)), delimiter=";")

    results: list[SymbolEntry] = []
    seen: set[str] = set()

    for row in reader:
        product_status = row.get("Product Status", "").strip()
        instrument_status = row.get("Instrument Status", "").strip()
        if product_status != "Active" or instrument_status != "Active":
            continue

        instrument_type = row.get("Instrument Type", "").strip()
        if instrument_type not in _ALLOWED_TYPES:
            continue

        mnemonic = row.get("Mnemonic", "").strip()
        name = row.get("Instrument", "").strip()
        currency = row.get("Currency", "").strip()

        if not mnemonic or not name:
            continue

        yahoo_symbol = f"{mnemonic}.DE"

        # Skip duplicates (same mnemonic can appear multiple times with different configs)
        if yahoo_symbol in seen:
            continue
        seen.add(yahoo_symbol)

        results.append(SymbolEntry(
            symbol=yahoo_symbol,
            name=name,
            exchange="Xetra",
            currency=currency,
            type=_TYPE_MAP[instrument_type],
        ))

    return results
