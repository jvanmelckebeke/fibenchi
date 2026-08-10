"""Yahoo quote ``market_state`` vocabulary as a trait table.

Yahoo reports one of six states per symbol (documented on
``app/schemas/quote.py``): ``PREPRE``/``PRE`` (before the open), ``REGULAR``
(session running), ``POST``/``POSTPOST`` (after-hours running / ended), and
``CLOSED``. Before this table existed, each consumer re-derived which states
count as "active" with its own inline set — six sites, five different
predicates. All predicates now come from here.

``phase`` speaks the same vocabulary as ``Venue.phase()``
(``app/services/market_calendar``), so a consumer can fall back from the
live per-symbol state to the venue's scheduled phase with no translation:
the live feed is the authority (it knows about halts), the schedule is the
backstop when the feed is absent.
"""

from dataclasses import dataclass

from app.domain.phases import Phase


@dataclass(frozen=True)
class MarketStateInfo:
    # Scheduled-phase equivalent — the join key to Venue.phase().
    phase: Phase
    # Quotes are worth polling in this state. PREPRE ("overnight, pre-market
    # hasn't started") and POSTPOST ("after-hours has ended") are NOT active:
    # nothing trades in either, and for European venues PREPRE lasts the whole
    # night — polling fast there only burned API calls. (They historically
    # counted as active; changed deliberately, see PR #568.)
    active: bool
    # The current session's daily bar is still building, so the trailing bar
    # Yahoo returns is a live partial (see drop_unsettled_last_bar).
    session_forming: bool


MARKET_STATES: dict[str, MarketStateInfo] = {
    "PREPRE": MarketStateInfo(phase=Phase.CLOSED, active=False, session_forming=False),
    "PRE": MarketStateInfo(phase=Phase.PREMARKET, active=True, session_forming=False),
    "REGULAR": MarketStateInfo(phase=Phase.OPEN, active=True, session_forming=True),
    "POST": MarketStateInfo(phase=Phase.AFTERMARKET, active=True, session_forming=False),
    "POSTPOST": MarketStateInfo(phase=Phase.CLOSED, active=False, session_forming=False),
    "CLOSED": MarketStateInfo(phase=Phase.CLOSED, active=False, session_forming=False),
}

# Unknown/missing states get the most conservative reading: nothing moving,
# nothing forming. Callers that want "unknown ≠ closed" semantics should test
# for None themselves before consulting traits.
_UNKNOWN = MarketStateInfo(phase=Phase.CLOSED, active=False, session_forming=False)


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
