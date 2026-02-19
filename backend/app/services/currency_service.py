"""Currency lookup service with in-memory cache.

Provides O(1) lookups for raw Yahoo currency codes → (display_code, divisor).
The cache is populated from the currencies DB table at startup.
Unknown codes encountered at runtime are auto-inserted with divisor=1.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.currency import Currency

logger = logging.getLogger(__name__)

# Module-level cache: raw_code → (display_code, divisor)
_cache: dict[str, tuple[str, int]] = {}

# Safety-net subunit mappings (always merged into cache)
_SUBUNIT_CURRENCIES: dict[str, tuple[str, int]] = {
    "GBp": ("GBP", 100),
    "GBX": ("GBP", 100),
    "ILA": ("ILS", 100),
    "ZAc": ("ZAR", 100),
}


async def load_cache(db: AsyncSession) -> None:
    """Populate the in-memory cache from the currencies table."""
    result = await db.execute(select(Currency))
    rows = result.scalars().all()
    _cache.clear()
    for row in rows:
        _cache[row.code] = (row.display_code, row.divisor)
    # Merge subunit safety net (DB should have these, but just in case)
    for code, (display, divisor) in _SUBUNIT_CURRENCIES.items():
        _cache.setdefault(code, (display, divisor))
    logger.info("Currency cache loaded: %d entries", len(_cache))


def lookup(raw_code: str) -> tuple[str, int]:
    """Look up a raw Yahoo currency code. Returns (display_code, divisor).

    Falls back to (raw_code, 1) for unknown codes — safe default since
    most currencies don't need normalization.
    """
    return _cache.get(raw_code, (raw_code, 1))


async def ensure_currency(db: AsyncSession, raw_code: str) -> None:
    """Register an unknown currency code in the DB and cache.

    No-op if the code is already known.
    """
    if raw_code in _cache:
        return
    # Unknown code — insert with divisor=1 (display_code == raw_code)
    currency = Currency(code=raw_code, display_code=raw_code, divisor=1)
    db.add(currency)
    await db.flush()
    # Cache is updated eagerly (before the caller commits). This is safe because
    # the caller is responsible for committing the transaction — if it rolls back,
    # the stale cache entry merely maps to (raw_code, 1) which is the same
    # fallback that lookup() would return for an unknown code anyway.
    _cache[raw_code] = (raw_code, 1)
    logger.info("Auto-registered unknown currency: %s", raw_code)
