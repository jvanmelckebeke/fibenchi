"""Tests for the startup/cron cache warmup helpers in app.main."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.main import warm_all_group_caches

pytestmark = pytest.mark.asyncio(loop_scope="function")


def _make_group(gid: int, name: str = "G"):
    g = MagicMock()
    g.id = gid
    g.name = name
    return g


@patch("app.main.compute_and_cache_indicators", new_callable=AsyncMock)
@patch("app.main.async_session")
@patch("app.repositories.group_repo.GroupRepository")
async def test_warm_all_group_caches_iterates_every_group(
    MockGroupRepo, mock_async_session, mock_compute,
):
    """Pre-warm should call compute_and_cache_indicators once per group."""
    groups = [_make_group(1, "Watchlist"), _make_group(2, "Hotlist"), _make_group(3, "Crypto")]
    MockGroupRepo.return_value.list_all = AsyncMock(return_value=groups)

    mock_async_session.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_compute.return_value = {"AAPL": {}}  # non-empty snapshot

    warmed = await warm_all_group_caches()

    assert warmed == 3
    assert mock_compute.await_count == 3
    called_group_ids = [call.kwargs["group_id"] for call in mock_compute.call_args_list]
    assert called_group_ids == [1, 2, 3]


@patch("app.main.compute_and_cache_indicators", new_callable=AsyncMock)
@patch("app.main.async_session")
@patch("app.repositories.group_repo.GroupRepository")
async def test_warm_all_group_caches_continues_on_per_group_failure(
    MockGroupRepo, mock_async_session, mock_compute,
):
    """A failure on one group must not stop the loop."""
    groups = [_make_group(1), _make_group(2), _make_group(3)]
    MockGroupRepo.return_value.list_all = AsyncMock(return_value=groups)

    mock_async_session.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_compute.side_effect = [{"A": {}}, RuntimeError("boom"), {"C": {}}]

    warmed = await warm_all_group_caches()

    # Two succeeded, one raised
    assert warmed == 2
    assert mock_compute.await_count == 3


@patch("app.main.compute_and_cache_indicators", new_callable=AsyncMock)
@patch("app.main.async_session")
@patch("app.repositories.group_repo.GroupRepository")
async def test_warm_all_group_caches_handles_no_groups(
    MockGroupRepo, mock_async_session, mock_compute,
):
    MockGroupRepo.return_value.list_all = AsyncMock(return_value=[])

    mock_async_session.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_async_session.return_value.__aexit__ = AsyncMock(return_value=False)

    warmed = await warm_all_group_caches()

    assert warmed == 0
    mock_compute.assert_not_awaited()
