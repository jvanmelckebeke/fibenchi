"""Shared utilities."""

from __future__ import annotations

import asyncio
import time
from functools import wraps
from typing import Hashable, TypeVar


def async_threadable(fn):
    """Decorator that wraps a sync function to run in a thread via asyncio.to_thread.

    The decorated function becomes async. Callers simply ``await func(...)``
    instead of ``await asyncio.to_thread(func, ...)``.
    """

    @wraps(fn)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(fn, *args, **kwargs)

    return wrapper

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class TTLCache:
    """Simple in-memory cache with per-entry TTL expiration.

    Stores entries as (value, timestamp) tuples. Expired entries are
    lazily evicted on access.

    Parameters:
        default_ttl: Default time-to-live in seconds for new entries.
        max_size: Maximum number of entries. Oldest entry is evicted when full.
                  0 means unlimited.
    """

    def __init__(self, default_ttl: float, max_size: int = 0):
        self._data: dict = {}
        self.default_ttl = default_ttl
        self.max_size = max_size

    def get_value(self, key):
        """Return cached value if present and not expired, else None."""
        entry = self._data.get(key)
        if entry is None:
            return None
        value, ts = entry
        if time.monotonic() - ts > self.default_ttl:
            del self._data[key]
            return None
        return value

    def set_value(self, key, value) -> None:
        """Store a value with the default TTL. Evicts oldest if at capacity."""
        if self.max_size and len(self._data) >= self.max_size and key not in self._data:
            oldest = min(self._data, key=lambda k: self._data[k][1])
            del self._data[oldest]
        self._data[key] = (value, time.monotonic())

    def clear(self) -> None:
        """Remove all entries."""
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)
