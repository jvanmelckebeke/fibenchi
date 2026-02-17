"""Unit tests for annotation_service — tests service logic with mocked repos."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.annotation_service import (
    create_annotation,
    delete_annotation,
    list_annotations,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")


@patch("app.services.annotation_service.AnnotationRepository")
async def test_list_annotations_delegates_to_repo(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    expected = [MagicMock(), MagicMock()]
    mock_repo.list_by_asset = AsyncMock(return_value=expected)

    result = await list_annotations(db, asset_id=42)

    MockRepo.assert_called_once_with(db)
    mock_repo.list_by_asset.assert_awaited_once_with(42)
    assert result == expected


@patch("app.services.annotation_service.AnnotationRepository")
async def test_create_annotation_passes_asset_id_and_kwargs(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    new_annotation = MagicMock()
    mock_repo.create = AsyncMock(return_value=new_annotation)

    result = await create_annotation(db, asset_id=7, date="2025-06-01", title="Earnings")

    MockRepo.assert_called_once_with(db)
    mock_repo.create.assert_awaited_once_with(
        asset_id=7, date="2025-06-01", title="Earnings"
    )
    assert result == new_annotation


@patch("app.services.annotation_service.AnnotationRepository")
async def test_delete_annotation_raises_404_when_not_found(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    mock_repo.get_by_id_and_asset = AsyncMock(return_value=None)

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await delete_annotation(db, annotation_id=99, asset_id=7)
    assert exc_info.value.status_code == 404


@patch("app.services.annotation_service.AnnotationRepository")
async def test_delete_annotation_calls_delete_when_found(MockRepo):
    db = AsyncMock()
    mock_repo = MockRepo.return_value
    annotation = MagicMock()
    mock_repo.get_by_id_and_asset = AsyncMock(return_value=annotation)
    mock_repo.delete = AsyncMock()

    await delete_annotation(db, annotation_id=5, asset_id=7)

    mock_repo.get_by_id_and_asset.assert_awaited_once_with(5, 7)
    mock_repo.delete.assert_awaited_once_with(annotation)
