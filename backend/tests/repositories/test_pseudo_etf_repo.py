"""Tests for PseudoEtfRepository — CRUD, thesis, and annotation operations."""

import pytest
from datetime import date

from app.models.pseudo_etf import PseudoETF, PseudoEtfAnnotation, PseudoEtfThesis
from app.repositories.pseudo_etf_repo import PseudoEtfRepository

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _create_etf(db, name: str = "Quantum", **kwargs) -> PseudoETF:
    defaults = dict(base_date=date(2025, 1, 1), base_value=100.0)
    defaults.update(kwargs)
    repo = PseudoEtfRepository(db)
    return await repo.create(name=name, **defaults)


async def test_list_all_ordered(db):
    await _create_etf(db, "Bravo")
    await _create_etf(db, "Alpha")

    repo = PseudoEtfRepository(db)
    result = await repo.list_all()
    assert len(result) == 2
    assert result[0].name == "Alpha"
    assert result[1].name == "Bravo"


async def test_get_by_id_and_name(db):
    etf = await _create_etf(db, "Quantum")

    repo = PseudoEtfRepository(db)
    by_id = await repo.get_by_id(etf.id)
    assert by_id is not None
    assert by_id.name == "Quantum"

    by_name = await repo.get_by_name("Quantum")
    assert by_name is not None
    assert by_name.id == etf.id


async def test_get_by_name_not_found(db):
    repo = PseudoEtfRepository(db)
    result = await repo.get_by_name("Nonexistent")
    assert result is None


async def test_create_and_delete(db):
    etf = await _create_etf(db, "ToDelete")

    repo = PseudoEtfRepository(db)
    await repo.delete(etf)

    result = await repo.get_by_id(etf.id)
    assert result is None


async def test_get_thesis_none(db):
    etf = await _create_etf(db)

    repo = PseudoEtfRepository(db)
    result = await repo.get_thesis(etf.id)
    assert result is None


async def test_upsert_thesis_create_and_update(db):
    etf = await _create_etf(db)

    repo = PseudoEtfRepository(db)
    thesis = await repo.upsert_thesis(etf.id, "Version 1")
    assert thesis.content == "Version 1"
    assert thesis.pseudo_etf_id == etf.id

    # Update
    updated = await repo.upsert_thesis(etf.id, "Version 2")
    assert updated.content == "Version 2"
    assert updated.id == thesis.id  # same row


async def test_list_annotations_ordered(db):
    etf = await _create_etf(db)

    repo = PseudoEtfRepository(db)
    await repo.create_annotation(pseudo_etf_id=etf.id, date=date(2025, 3, 1), title="Later")
    await repo.create_annotation(pseudo_etf_id=etf.id, date=date(2025, 1, 1), title="Earlier")

    result = await repo.list_annotations(etf.id)
    assert len(result) == 2
    assert result[0].title == "Earlier"
    assert result[1].title == "Later"


async def test_create_annotation(db):
    etf = await _create_etf(db)

    repo = PseudoEtfRepository(db)
    annotation = await repo.create_annotation(
        pseudo_etf_id=etf.id, date=date(2025, 1, 15),
        title="Earnings", body="Beat estimates", color="#22c55e",
    )
    assert annotation.id is not None
    assert annotation.title == "Earnings"
    assert annotation.pseudo_etf_id == etf.id


async def test_get_annotation_by_id_and_etf(db):
    etf = await _create_etf(db)

    repo = PseudoEtfRepository(db)
    annotation = await repo.create_annotation(
        pseudo_etf_id=etf.id, date=date(2025, 1, 15), title="Event",
    )

    result = await repo.get_annotation(annotation.id, etf.id)
    assert result is not None
    assert result.title == "Event"

    # Wrong etf_id should return None
    wrong = await repo.get_annotation(annotation.id, 999)
    assert wrong is None


async def test_delete_annotation(db):
    etf = await _create_etf(db)

    repo = PseudoEtfRepository(db)
    annotation = await repo.create_annotation(
        pseudo_etf_id=etf.id, date=date(2025, 1, 15), title="ToDelete",
    )
    await repo.delete_annotation(annotation)

    result = await repo.get_annotation(annotation.id, etf.id)
    assert result is None
