"""Background-task registry.

Jobs declare themselves with the :func:`background_task` decorator (same
pattern as ``INDICATOR_REGISTRY``); the app's lifespan schedules whatever is
registered instead of hand-wiring each ``scheduler.add_job`` call.

A task's trigger is either a ready APScheduler trigger or a zero-arg factory
resolved at scheduling time. A factory may return ``None`` to disable just
that task (after logging why) — this is the seam that fixes the old
``main.py`` behaviour where one malformed ``REFRESH_CRON`` silently skipped
*every* background job.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from apscheduler.triggers.base import BaseTrigger

logger = logging.getLogger(__name__)

TriggerFactory = Callable[[], "BaseTrigger | None"]


@dataclass(frozen=True)
class BackgroundTask:
    """One scheduled job: its scheduler id, coroutine function, and trigger."""

    id: str
    func: Callable[[], Awaitable[None]]
    trigger: BaseTrigger | TriggerFactory

    def resolve_trigger(self) -> BaseTrigger | None:
        """The trigger to schedule with, or None when the task is disabled
        (the factory is expected to have logged the reason)."""
        if isinstance(self.trigger, BaseTrigger):
            return self.trigger
        return self.trigger()


_REGISTRY: dict[str, BackgroundTask] = {}


def background_task(id: str, trigger: BaseTrigger | TriggerFactory):
    """Register the decorated coroutine function as a scheduled job.

    Stackable: the same function may be registered under several ids with
    different triggers (the primary + supplemental price refreshes do this).
    """

    def decorator(func: Callable[[], Awaitable[None]]):
        if id in _REGISTRY:
            raise ValueError(f"Duplicate background task id: {id!r}")
        _REGISTRY[id] = BackgroundTask(id=id, func=func, trigger=trigger)
        return func

    return decorator


def all_tasks() -> list[BackgroundTask]:
    """Every registered task, in registration order."""
    return list(_REGISTRY.values())
