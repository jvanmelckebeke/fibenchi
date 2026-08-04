"""Yahoo quote ``market_state`` vocabulary as a trait table.

Yahoo reports one of six states per symbol (documented on
``app/schemas/quote.py``): ``PREPRE``/``PRE`` (before the open), ``REGULAR``
(session running), ``POST``/``POSTPOST`` (after-hours running / ended), and
``CLOSED``. Before this table existed, each consumer re-derived which states
count as "active" with its own inline set — six sites, five different
predicates. All predicates now come from here.

``phase`` speaks the same vocabulary as ``Venue.phase()``
(``app/services/market_calendar.py``), so a consumer can fall back from the
live per-symbol state to the venue's scheduled phase with no translation:
the live feed is the authority (it knows about halts), the schedule is the
backstop when the feed is absent.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketStateInfo:
    # Scheduled-phase equivalent — the join key to Venue.phase().
    phase: str  # "premarket" | "open" | "aftermarket" | "closed"
    # Quotes are worth polling in this state. Note POSTPOST ("after-hours has
    # ended") is kept active — the historical behavior of every consumer —
    # even though prices are settled by then; revisit deliberately, not as a
    # refactor side effect.
    active: bool
    # The current session's daily bar is still building, so the trailing bar
    # Yahoo returns is a live partial (see drop_unsettled_last_bar).
    session_forming: bool


MARKET_STATES: dict[str, MarketStateInfo] = {
    "PREPRE": MarketStateInfo(phase="premarket", active=True, session_forming=False),
    "PRE": MarketStateInfo(phase="premarket", active=True, session_forming=False),
    "REGULAR": MarketStateInfo(phase="open", active=True, session_forming=True),
    "POST": MarketStateInfo(phase="aftermarket", active=True, session_forming=False),
    "POSTPOST": MarketStateInfo(phase="closed", active=True, session_forming=False),
    "CLOSED": MarketStateInfo(phase="closed", active=False, session_forming=False),
}

# Unknown/missing states get the most conservative reading: nothing moving,
# nothing forming. Callers that want "unknown ≠ closed" semantics should test
# for None themselves before consulting traits.
_UNKNOWN = MarketStateInfo(phase="closed", active=False, session_forming=False)


def state_info(state: str | None) -> MarketStateInfo:
    """Traits for a raw market-state code (unknown → conservative defaults)."""
    if state is None:
        return _UNKNOWN
    return MARKET_STATES.get(state, _UNKNOWN)


def is_active(state: str | None) -> bool:
    return state_info(state).active


def any_active(states) -> bool:
    """Whether any of the given states counts as an active market."""
    return any(is_active(s) for s in states)


def is_session_forming(state: str | None) -> bool:
    return state_info(state).session_forming
