from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SymbolEntry:
    """A single symbol fetched from an exchange data source."""

    symbol: str  # Yahoo-compatible symbol (e.g. "AALB.AS")
    name: str
    exchange: str  # Display name (e.g. "Euronext Amsterdam")
    currency: str
    type: str = "stock"  # "stock" or "etf"


class SymbolProvider(ABC):
    """Abstract base for exchange symbol list providers."""

    @abstractmethod
    async def fetch_symbols(self, config: dict) -> list[SymbolEntry]:
        """Fetch symbol listings from the data source.

        Args:
            config: Provider-specific configuration (e.g. which sub-markets to include).

        Returns:
            List of SymbolEntry objects ready for upsert into symbol_directory.
        """

    @staticmethod
    @abstractmethod
    def available_markets() -> list[dict]:
        """Return the list of selectable sub-markets for the UI.

        Each dict has: {"key": "amsterdam", "label": "Euronext Amsterdam"}
        """
