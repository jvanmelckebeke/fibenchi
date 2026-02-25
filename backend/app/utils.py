"""Shared utilities."""

from __future__ import annotations

import asyncio
import threading
import time
from functools import wraps
from typing import Awaitable, Callable, ParamSpec, TypeVar

_P = ParamSpec("_P")
_R = TypeVar("_R")


def async_threadable(fn: Callable[_P, _R]) -> Callable[_P, Awaitable[_R]]:
    """Decorator that wraps a sync function to run in a thread via asyncio.to_thread.

    The decorated function becomes async. Callers simply ``await func(...)``
    instead of ``await asyncio.to_thread(func, ...)``.
    """

    @wraps(fn)
    async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        return await asyncio.to_thread(fn, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


class TTLCache:
    """Simple in-memory cache with per-entry TTL expiration.

    Stores entries as (value, timestamp) tuples. Expired entries are
    lazily evicted on access.

    Parameters:
        default_ttl: Default time-to-live in seconds for new entries.
        max_size: Maximum number of entries. Oldest entry is evicted when full.
                  0 means unlimited.
        thread_safe: When True, all operations are protected by a threading.Lock.
                     Enable this for caches accessed from multiple threads (e.g. via
                     asyncio.to_thread). Async-only caches (single event loop) can
                     leave this False to avoid unnecessary locking overhead.
    """

    def __init__(
        self, default_ttl: float, max_size: int = 0, *, thread_safe: bool = False
    ):
        self._data: dict = {}
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._lock: threading.Lock | None = threading.Lock() if thread_safe else None

    def get_value(self, key):
        """Return cached value if present and not expired, else None."""
        if self._lock is not None:
            with self._lock:
                return self._get_value_unlocked(key)
        return self._get_value_unlocked(key)

    def _get_value_unlocked(self, key):
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
        if self._lock is not None:
            with self._lock:
                self._set_value_unlocked(key, value)
        else:
            self._set_value_unlocked(key, value)

    def _set_value_unlocked(self, key, value) -> None:
        if self.max_size and len(self._data) >= self.max_size and key not in self._data:
            oldest = min(self._data, key=lambda k: self._data[k][1])
            del self._data[oldest]
        self._data[key] = (value, time.monotonic())

    def clear(self) -> None:
        """Remove all entries."""
        if self._lock is not None:
            with self._lock:
                self._data.clear()
        else:
            self._data.clear()

    def __len__(self) -> int:
        return len(self._data)
