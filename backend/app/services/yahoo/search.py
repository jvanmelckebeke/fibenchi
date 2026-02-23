"""Yahoo Finance symbol search."""

from yahooquery import search as _yq_search

from app.utils import async_threadable


@async_threadable
def search(query: str, **kwargs) -> dict:
    """Search Yahoo Finance for ticker symbols."""
    return _yq_search(query, **kwargs)
