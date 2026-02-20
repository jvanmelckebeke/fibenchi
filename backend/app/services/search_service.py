"""Search business logic — DB-backed symbol directory with Yahoo fallback."""

from datetime import datetime, timezone

from sqlalchemy import or_, select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.symbol_directory import SymbolDirectory
from app.services.yahoo import search as yahoo_search

_MIN_LOCAL_RESULTS = 8


async def _query_local(db: AsyncSession, query: str, limit: int = 8) -> list[dict]:
    """Search the local symbol_directory table by prefix/substring."""
    pattern = f"%{query}%"
    stmt = (
        select(SymbolDirectory)
        .where(
            or_(
                sa_func.lower(SymbolDirectory.symbol).like(pattern),
                sa_func.lower(SymbolDirectory.name).like(pattern),
            )
        )
        .order_by(
            # Exact symbol match first, then prefix, then substring
            sa_func.lower(SymbolDirectory.symbol) != query,
            ~sa_func.lower(SymbolDirectory.symbol).startswith(query),
            SymbolDirectory.last_seen.desc(),
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "symbol": row.symbol,
            "name": row.name,
            "exchange": row.exchange,
            "type": row.type,
        }
        for row in result.scalars().all()
    ]


async def _upsert_symbols(db: AsyncSession, results: list[dict]) -> None:
    """Upsert Yahoo search results into the symbol_directory table."""
    if not results:
        return

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    rows = [
        {
            "symbol": r["symbol"],
            "name": r["name"],
            "exchange": r["exchange"],
            "type": r["type"],
            "last_seen": datetime.now(timezone.utc),
        }
        for r in results
    ]

    stmt = pg_insert(SymbolDirectory).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["symbol"],
        set_={
            "name": stmt.excluded.name,
            "exchange": stmt.excluded.exchange,
            "type": stmt.excluded.type,
            "last_seen": stmt.excluded.last_seen,
        },
    )
    await db.execute(stmt)
    await db.commit()


def _parse_yahoo_results(quotes: list[dict]) -> list[dict]:
    """Parse raw Yahoo search quotes into normalized dicts."""
    results = []
    for item in quotes:
        qt = item.get("quoteType", "")
        if qt not in ("EQUITY", "ETF"):
            continue
        results.append({
            "symbol": item.get("symbol", ""),
            "name": item.get("shortname") or item.get("longname") or "",
            "exchange": item.get("exchDisp") or item.get("exchange") or "",
            "type": "stock" if qt == "EQUITY" else "etf",
        })
        if len(results) >= 8:
            break
    return results


async def search_symbols(query: str, db: AsyncSession) -> list[dict]:
    """Search for ticker symbols, querying local DB first with Yahoo fallback."""
    q_lower = query.strip().lower()

    # Try local DB first
    local_results = await _query_local(db, q_lower)
    if len(local_results) >= _MIN_LOCAL_RESULTS:
        return local_results

    # Fall back to Yahoo Finance
    raw = await yahoo_search(q_lower, first_quote=False)
    yahoo_results = _parse_yahoo_results(raw.get("quotes", []))

    # Persist Yahoo results to the directory (fire-and-forget on error)
    if yahoo_results:
        try:
            await _upsert_symbols(db, yahoo_results)
        except Exception:
            await db.rollback()

    # If we got Yahoo results, return those (fresher); otherwise return whatever local had
    return yahoo_results if yahoo_results else local_results


async def search_local(query: str, db: AsyncSession) -> list[dict]:
    """Search only the local symbol_directory table (instant, no Yahoo)."""
    q_lower = query.strip().lower()
    return await _query_local(db, q_lower, limit=8)


async def search_yahoo(query: str, db: AsyncSession) -> list[dict]:
    """Search Yahoo Finance only, excluding symbols already in local results."""
    q_lower = query.strip().lower()

    # Get local symbols to exclude from Yahoo results
    local_results = await _query_local(db, q_lower, limit=20)
    local_symbols = {r["symbol"] for r in local_results}

    # Query Yahoo
    raw = await yahoo_search(q_lower, first_quote=False)
    yahoo_results = _parse_yahoo_results(raw.get("quotes", []))

    # Filter out duplicates already in local DB
    unique_yahoo = [r for r in yahoo_results if r["symbol"] not in local_symbols]

    # Persist new Yahoo results to the directory
    if unique_yahoo:
        try:
            await _upsert_symbols(db, unique_yahoo)
        except Exception:
            await db.rollback()

    return unique_yahoo
