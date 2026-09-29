"""Companion-app config contract — the single source of truth.

This Pydantic model is the SoT for the mobile companion (jvanmelckebeke/fibenchi-app).
Its JSON Schema (see ``scripts/export_companion_schema.py``) is the input to the
app's Zod codegen, so the contract cannot drift between Fibenchi and the app.

Shape is normalized: groups reference symbols, and ``tickers`` holds each symbol's
metadata once (a symbol commonly lives in several groups via the M:N group_assets).

Serialized camelCase (alias generator) for the TypeScript consumer; constructed
with snake_case field names internally (populate_by_name).
"""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.asset import AssetType

#: Current contract version. Bump on any breaking shape change; the app gates on it.
CONFIG_VERSION = 1


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ConfigTicker(_CamelModel):
    """Metadata for a single tracked symbol (defined once across all groups)."""

    name: str = Field(description="Display name")
    type: AssetType = Field(description="Asset type: stock, etf, or index")
    currency: str = Field(default="USD", description="ISO 4217 display code (normalized, e.g. GBp -> GBP)")
    tags: list[str] = Field(default_factory=list, description="Tag names attached to this symbol")


class ConfigGroup(_CamelModel):
    """A user group as ordered symbol references."""

    name: str = Field(description="Group name")
    icon: str | None = Field(default=None, description="Lucide icon name")
    is_default: bool = Field(description="Whether this is the protected default group (Watchlist)")
    position: int = Field(description="Display order (0 = first)")
    symbols: list[str] = Field(default_factory=list, description="Ticker symbols in this group, in order")


class CompanionConfig(_CamelModel):
    """The full config bundle the companion app pulls and caches."""

    version: Literal[1] = Field(description="Contract version the app gates on (always sent; required so the app's gate can't be bypassed by an absent field)")
    generated_at: datetime.datetime = Field(description="When this bundle was produced (UTC)")
    groups: list[ConfigGroup] = Field(default_factory=list, description="User groups, ordered")
    tickers: dict[str, ConfigTicker] = Field(default_factory=dict, description="symbol -> metadata")
    tags: dict[str, str] = Field(default_factory=dict, description="tag name -> hex colour")


#: Current calendar-contract version. Deliberately independent of
#: ``CONFIG_VERSION``: the calendar changes about once a year and the group
#: config whenever a group is touched, so the app fetches and caches the two
#: bundles separately and a change to one must not invalidate the other.
CALENDAR_VERSION = 1


class CalendarWindow(_CamelModel):
    """The date range the calendar body covers, inclusive on both ends."""

    from_: datetime.date = Field(alias="from", description="First date covered (inclusive)")
    to: datetime.date = Field(description="Last date covered (inclusive)")


class HalfDay(_CamelModel):
    """A session that closes before its usual time."""

    date: datetime.date = Field(description="Session date")
    close: datetime.time = Field(description="Closing time in the venue's local timezone")


class VenueCalendar(_CamelModel):
    """One venue's trading week, holidays, and half-days over the window.

    Together the first three fields describe the window exactly: a date in it
    is a session iff it appears in ``extraSessions``, or its weekday is in
    ``tradingDays`` and it is not in ``closures``.
    """

    timezone: str = Field(description="IANA timezone of the venue's local clock")
    trading_days: list[int] = Field(
        description="Weekdays the venue currently trades, ISO numbering (1 = Monday .. 7 = Sunday). "
        "Read from the venue's recent sessions, so do not assume Mon-Fri: some venues trade a "
        "different week, and a venue can change its week mid-window (see extraSessions)"
    )
    closures: list[datetime.date] = Field(
        description="Dates in the window that fall on a tradingDays weekday but had no session"
    )
    extra_sessions: list[datetime.date] = Field(
        description="Sessions in the window on a weekday outside tradingDays — normally empty, "
        "non-empty when the venue changed its trading week during the window"
    )
    half_days: list[HalfDay] = Field(description="Sessions in the window that close early")


class CompanionCalendar(_CamelModel):
    """The venue-calendar bundle the companion app pulls and caches."""

    version: Literal[1] = Field(description="Calendar contract version the app gates on (separate from config's)")
    generated_at: datetime.datetime = Field(description="When this bundle was produced (UTC)")
    window: CalendarWindow = Field(description="Date range the closures and half-days cover")
    venues: dict[str, VenueCalendar] = Field(
        description="exchange_calendars name -> calendar. A venue whose calendar can't be built is "
        "absent rather than guessed at"
    )
    symbols: dict[str, str | None] = Field(
        description="symbol -> exchange_calendars name, null when the ticker maps to no modelled venue. "
        "Always the full tracked book, even when the venues map is filtered, since this is the only "
        "place the mapping is published. A name here may be absent from venues (filtered out, or its "
        "calendar failed to build) — fall back to the calendar-less approximation for those symbols"
    )
