"""Tests for AnnotationRepository — query methods against real SQLite DB."""

from datetime import date

import pytest

from app.models import Annotation, Asset, AssetType
from app.repositories.annotation_repo import AnnotationRepository
from tests.helpers import create_test_asset as _create_asset

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_list_by_asset_returns_correct_annotations_ordered_by_date(db):
    asset = await _create_asset(db, "AAPL")
    other = await _create_asset(db, "MSFT")

    repo = AnnotationRepository(db)
    await repo.create(asset_id=asset.id, date=date(2024, 3, 15), title="Later", color="#ff0000")
    await repo.create(asset_id=asset.id, date=date(2024, 1, 10), title="Earlier", color="#00ff00")
    await repo.create(asset_id=other.id, date=date(2024, 2, 1), title="Other asset", color="#0000ff")

    result = await repo.list_by_asset(asset.id)
    assert len(result) == 2
    assert result[0].title == "Earlier"
    assert result[1].title == "Later"
    assert result[0].date < result[1].date


async def test_list_by_asset_returns_empty_when_no_annotations(db):
    asset = await _create_asset(db, "AAPL")
    repo = AnnotationRepository(db)

    result = await repo.list_by_asset(asset.id)
    assert result == []


async def test_get_by_id_and_asset_finds_existing(db):
    asset = await _create_asset(db, "AAPL")
    repo = AnnotationRepository(db)

    created = await repo.create(
        asset_id=asset.id, date=date(2024, 5, 1), title="Earnings", color="#3b82f6",
    )

    result = await repo.get_by_id_and_asset(created.id, asset.id)
    assert result is not None
    assert result.id == created.id
    assert result.title == "Earnings"


async def test_get_by_id_and_asset_returns_none_when_wrong_asset(db):
    asset_a = await _create_asset(db, "AAPL")
    asset_b = await _create_asset(db, "MSFT")
    repo = AnnotationRepository(db)

    created = await repo.create(
        asset_id=asset_a.id, date=date(2024, 5, 1), title="Earnings", color="#3b82f6",
    )

    result = await repo.get_by_id_and_asset(created.id, asset_b.id)
    assert result is None


async def test_create_sets_all_fields(db):
    asset = await _create_asset(db, "AAPL")
    repo = AnnotationRepository(db)

    annotation = await repo.create(
        asset_id=asset.id,
        date=date(2024, 6, 15),
        title="Dividend",
        body="Quarterly dividend payout",
        color="#10b981",
    )

    assert annotation.id is not None
    assert annotation.asset_id == asset.id
    assert annotation.date == date(2024, 6, 15)
    assert annotation.title == "Dividend"
    assert annotation.body == "Quarterly dividend payout"
    assert annotation.color == "#10b981"


async def test_delete_removes_the_row(db):
    asset = await _create_asset(db, "AAPL")
    repo = AnnotationRepository(db)

    annotation = await repo.create(
        asset_id=asset.id, date=date(2024, 7, 1), title="Remove me", color="#ef4444",
    )
    annotation_id = annotation.id

    await repo.delete(annotation)

    result = await repo.get_by_id_and_asset(annotation_id, asset.id)
    assert result is None
