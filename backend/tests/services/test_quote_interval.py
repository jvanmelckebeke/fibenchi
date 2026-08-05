"""Tests for the SSE poll-interval selection (live states + schedule backstop)."""

from datetime import datetime, timezone

from app.services.quote_service import _poll_interval


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_live_regular_is_fast():
    assert _poll_interval({"REGULAR"}, ["AAPL"], _utc(2024, 4, 3, 15, 0)) == 15


def test_dead_feed_during_session_backstopped():
    """An empty quote batch mid-session must not fall to the 300s cadence."""
    assert _poll_interval(set(), ["AAPL"], _utc(2024, 4, 3, 15, 0)) == 15


def test_all_closed_is_slow():
    assert _poll_interval({"CLOSED"}, ["AAPL"], _utc(2024, 4, 6, 12, 0)) == 300


def test_sleep_clamped_to_next_bell():
    """Two minutes before the Amsterdam open, an all-closed stream sleeps ~2min,
    not the full 300s — it wakes at the bell."""
    interval = _poll_interval({"CLOSED"}, ["IWDA.AS"], _utc(2024, 4, 8, 6, 58))
    assert 15 <= interval <= 130


def test_live_state_can_speed_past_schedule():
    """A REGULAR quote on a scheduled-closed day (special session/halt lift)
    keeps the fast cadence — live is authoritative when present."""
    assert _poll_interval({"REGULAR"}, ["AAPL"], _utc(2024, 4, 6, 12, 0)) == 15


def test_explicit_closed_beats_schedule():
    """Yahoo confidently saying CLOSED during a scheduled session wins — a
    stale calendar must not pin fast polling on a day the venue is shut."""
    assert _poll_interval({"CLOSED"}, ["AAPL"], _utc(2024, 4, 3, 15, 0)) == 300


def test_overnight_states_idle():
    """With PREPRE/POSTPOST inactive (#568), an overnight feed slows fully
    (modulo the next-bell clamp on nearby opens)."""
    interval = _poll_interval({"PREPRE", "POSTPOST"}, ["AAPL"], _utc(2024, 4, 6, 12, 0))
    assert interval == 300
