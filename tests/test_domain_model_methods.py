from __future__ import annotations

import pytest

from core.models import BatchOperation, PartOperation, Schedule
from core.models.enums import BatchOperationStatus, LockStatus, PartOperationStatus, SourceType


def test_batch_operation_domain_predicates() -> None:
    op = BatchOperation(
        id=1,
        op_code="OP1",
        batch_id="B1",
        source=" EXTERNAL ",
        supplier_id=" S1 ",
        setup_hours=1.5,
        unit_hours=2.0,
        status=" SCHEDULED ",
    )

    assert op.is_external()
    assert not op.is_internal()
    assert op.has_supplier()
    assert op.is_scheduled()
    assert not op.is_completed()
    assert not op.is_processing()
    assert op.processing_hours() == 3.5


def test_batch_operation_status_predicates_cover_processing_and_defaults() -> None:
    op = BatchOperation(id=1, op_code="OP1", batch_id="B1")

    assert op.is_internal()
    assert not op.is_external()
    assert op.is_pending()
    assert not op.has_supplier()

    op.status = BatchOperationStatus.PROCESSING.value
    assert op.is_processing()

    op.status = BatchOperationStatus.COMPLETED.value
    assert op.is_completed()

    op.status = BatchOperationStatus.SKIPPED.value
    assert op.is_skipped()


@pytest.mark.parametrize("source", ["legacy", "unknown", "bad", "", "   ", None])
def test_batch_operation_unknown_source_is_not_internal_or_external(source: object) -> None:
    op = BatchOperation(id=1, op_code="OP1", batch_id="B1", source=source)  # type: ignore[arg-type]

    assert not op.is_external()
    assert not op.is_internal()


def test_part_operation_domain_predicates() -> None:
    op = PartOperation(
        id=1,
        part_no="P1",
        seq=10,
        source=SourceType.EXTERNAL.value,
        supplier_id="S1",
        ext_group_id="G1",
        setup_hours=0.5,
        unit_hours=1.25,
        status=PartOperationStatus.ACTIVE.value,
    )

    assert op.is_external()
    assert not op.is_internal()
    assert op.is_active()
    assert not op.is_deleted()
    assert op.has_supplier()
    assert op.has_external_group()
    assert op.processing_hours() == 1.75


def test_part_operation_defaults_are_internal_active() -> None:
    op = PartOperation(id=1, part_no="P1", seq=1)

    assert op.is_internal()
    assert not op.is_external()
    assert op.is_active()
    assert not op.is_deleted()
    assert not op.has_supplier()
    assert not op.has_external_group()

    op.status = " DELETED "
    assert op.is_deleted()


@pytest.mark.parametrize("source", ["legacy", "unknown", "bad", "", "   ", None])
def test_part_operation_unknown_source_is_not_internal_or_external(source: object) -> None:
    op = PartOperation(id=1, part_no="P1", seq=1, source=source)  # type: ignore[arg-type]

    assert not op.is_external()
    assert not op.is_internal()


def test_schedule_domain_predicates() -> None:
    schedule = Schedule(
        id=1,
        op_id=10,
        machine_id=" M1 ",
        operator_id=None,
        start_time="2026-05-01 08:00",
        end_time="2026-05-01 10:00",
        lock_status=" LOCKED ",
        version=1,
    )

    assert schedule.is_locked()
    assert not schedule.is_unlocked()
    assert schedule.has_machine()
    assert not schedule.has_operator()
    assert schedule.has_any_resource()

    schedule.lock_status = LockStatus.UNLOCKED.value
    schedule.machine_id = None
    schedule.operator_id = " O1 "
    assert schedule.is_unlocked()
    assert not schedule.has_machine()
    assert schedule.has_operator()
    assert schedule.has_any_resource()
