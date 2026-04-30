from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pytest

from core.infrastructure.errors import ValidationError
from core.models import BatchOperation, PartOperation
from core.services.process.part_service import PartService
from core.services.scheduler.operation_edit_service import _ensure_internal_operation_editable


class _PartRepo:
    def get(self, part_no: str) -> object:
        return object()


class _PartOpRepo:
    def __init__(self, op: PartOperation) -> None:
        self._op = op

    def get(self, part_no: str, seq: int) -> PartOperation:
        return self._op

    def update(self, part_no: str, seq: int, values: Any) -> None:
        raise AssertionError("unknown source must be rejected before update")


class _TxManager:
    @contextmanager
    def transaction(self) -> Iterator[None]:
        raise AssertionError("unknown source must be rejected before transaction")
        yield


def test_part_service_update_internal_hours_rejects_unknown_source() -> None:
    svc = PartService.__new__(PartService)
    svc.part_repo = _PartRepo()
    svc.op_repo = _PartOpRepo(
        PartOperation(
            id=1,
            part_no="P1",
            seq=10,
            source="legacy",
        )
    )
    svc.tx_manager = _TxManager()

    with pytest.raises(ValidationError, match="只能编辑内部工序工时"):
        svc.update_internal_hours("P1", 10, 1.0, 2.0)


def test_operation_edit_rejects_unknown_batch_operation_source() -> None:
    op = BatchOperation(
        id=1,
        op_code="OP1",
        batch_id="B1",
        source="legacy",
    )

    with pytest.raises(ValidationError, match="只能编辑内部工序"):
        _ensure_internal_operation_editable(op, op_id=1)
