from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pytest

from core.infrastructure.errors import ValidationError
from core.models import BatchOperation, PartOperation
from core.services.process.deletion_validator import (
    DeletionValidator,
    ValidationResult,
)
from core.services.process.deletion_validator import (
    Operation as DeleteOp,
)
from core.services.process.part_service import PartService
from core.services.process.route_parser import ParsedOperation, ParseResult, ParseStatus
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


class _RejectingCreateRepo:
    def create(self, values: Any) -> None:
        raise AssertionError("unknown source must be rejected before persistence")


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


def test_part_service_save_template_rejects_unknown_parsed_operation_source() -> None:
    svc = PartService.__new__(PartService)
    svc.op_repo = _RejectingCreateRepo()
    svc.group_repo = _RejectingCreateRepo()
    parse_result = ParseResult(
        status=ParseStatus.SUCCESS,
        operations=[
            ParsedOperation(
                seq=10,
                op_type_name="旧来源工序",
                source="legacy",
            )
        ],
        external_groups=[],
        warnings=[],
        errors=[],
        stats={"total": 1, "internal": 0, "external": 0, "unknown": 1},
        original_input="10旧来源工序",
        normalized_input="10旧来源工序",
    )

    with pytest.raises(ValidationError, match="来源无效"):
        svc._save_template_no_tx(part_no="P1", parse_result=parse_result)


def test_deletion_validator_rejects_unknown_source_in_active_operations() -> None:
    validator = DeletionValidator()
    ops = [
        DeleteOp(seq=1, source="external"),
        DeleteOp(seq=2, source="legacy"),
    ]

    result = validator.can_delete(ops, to_delete=[1])

    assert result.result == ValidationResult.DENIED
    assert result.can_delete is False
    assert result.affected_ops == [2]
    assert "来源无效" in result.message
    assert validator.get_deletion_groups(ops) == []
