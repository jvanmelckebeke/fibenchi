"""Tests for the market-state trait table.

The table replaced five inline predicates over Yahoo's six-value market_state
vocabulary; these tests pin the traits to the historical behavior of those
sites so the consolidation stays a pure refactor.
"""

from app.services.market_state import (
    MARKET_STATES,
    any_active,
    is_active,
    is_session_forming,
    state_info,
)


def test_covers_canonical_states():
    """Exactly the six states Yahoo emits (documented on schemas/quote.py)."""
    assert set(MARKET_STATES) == {"PREPRE", "PRE", "REGULAR", "POST", "POSTPOST", "CLOSED"}


def test_active_states_are_the_trading_ones():
    """Only states in which something can actually trade count as active.

    PREPRE (overnight — lasts all night for European venues) and POSTPOST
    (after-hours ended) are deliberately inactive so the SSE stream and
    intraday gates idle instead of polling settled prices.
    """
    active = {s for s, info in MARKET_STATES.items() if info.active}
    assert active == {"REGULAR", "PRE", "POST"}


def test_only_regular_forms_a_session():
    """price_sync's _ACTIVE_SESSION_STATES was {REGULAR}."""
    forming = {s for s, info in MARKET_STATES.items() if info.session_forming}
    assert forming == {"REGULAR"}
    assert is_session_forming("REGULAR") is True
    assert is_session_forming("POST") is False


def test_settled_states_read_as_closed_phase():
    """Prices are settled in CLOSED, POSTPOST, and the overnight PREPRE —
    the stale-price pulse must not fire in any of them."""
    closed = {s for s, info in MARKET_STATES.items() if info.phase == "closed"}
    assert closed == {"CLOSED", "POSTPOST", "PREPRE"}


def test_phase_speaks_venue_vocabulary():
    """phase is the join key to Venue.phase() — same four values."""
    assert {info.phase for info in MARKET_STATES.values()} <= {
        "premarket", "open", "aftermarket", "closed",
    }


def test_unknown_states_are_conservative():
    for state in (None, "POSTMARKET", ""):
        info = state_info(state)
        assert info.active is False
        assert info.session_forming is False
        assert info.phase == "closed"
    assert is_active("NONSENSE") is False


def test_any_active():
    assert any_active({"CLOSED", "POST"}) is True
    assert any_active({"CLOSED"}) is False
    # The overnight pair alone must not keep pollers awake.
    assert any_active({"PREPRE", "POSTPOST"}) is False
    assert any_active(set()) is False
