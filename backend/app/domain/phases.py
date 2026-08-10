"""App-owned trading-time vocabularies: :class:`Phase` and :class:`Session`.

Two closed-world enums this codebase owns (unlike Yahoo's open-world
``market_state`` codes, which stay raw strings interpreted by the
``market_state`` trait table):

- ``Phase`` — what a venue is scheduled to be doing at an instant. Spoken
  by ``Venue.phase()`` and ``MarketStateInfo.phase`` (the join key between
  the live feed and the schedule).
- ``Session`` — the 3-value bucket an intraday bar is stored/served under
  (``IntradayPrice.session``, the SSE ``intraday`` event, the frontend's
  session-colored chart segments).

Both are ``StrEnum``: members compare equal to their raw strings, so DB
values, JSON payloads, and string-based tests are unaffected.
"""

from enum import StrEnum


class Phase(StrEnum):
    PREMARKET = "premarket"
    OPEN = "open"
    AFTERMARKET = "aftermarket"
    CLOSED = "closed"


class Session(StrEnum):
    PRE = "pre"
    REGULAR = "regular"
    POST = "post"


# CLOSED deliberately has no session: bars printed while a venue is closed
# (auction/late prints) are filed to the nearer session boundary by
# ``_classify_session`` rather than mapped mechanically.
PHASE_TO_SESSION: dict[Phase, Session] = {
    Phase.PREMARKET: Session.PRE,
    Phase.OPEN: Session.REGULAR,
    Phase.AFTERMARKET: Session.POST,
}
