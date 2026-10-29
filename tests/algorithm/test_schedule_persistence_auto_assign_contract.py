"""共同排产 payload 校验与 Schedule 唯一索引迁移合同。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set

import pytest

from core.algorithm_contracts.types import ScheduleResult
from core.errors import ValidationError
from core.models.batch_operation import BatchOperation
from core.services.scheduler.run.schedule_payload_contract import (
    build_validated_schedule_payload,
)
from tests._support.algo_operations import make_batch_operation, make_schedule_result
from tests._support.paths import REPO_ROOT


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def _make_dt(hours: int) -> datetime:
    return datetime(2026, 1, 1, 8, 0, 0) + timedelta(hours=hours)


def _result(
    op_id: int,
    *,
    machine_id: Optional[str] = "MC_A",
    operator_id: Optional[str] = "OP_A",
    source: str = "internal",
    start_offset: int = 0,
    end_offset: int = 1,
) -> ScheduleResult:
    return make_schedule_result(
        op_id=op_id,
        op_code=f"B001_{op_id:02d}",
        batch_id="B001",
        seq=op_id,
        machine_id=machine_id,
        operator_id=operator_id,
        start_time=_make_dt(start_offset),
        end_time=_make_dt(end_offset),
        source=source,
        op_type_name="A",
    )


def _operations(sources: Dict[int, str]) -> List[BatchOperation]:
    return [
        make_batch_operation(id=op_id, op_code=f"B001_{op_id:02d}", batch_id="B001", seq=op_id, source=source)
        for op_id, source in sorted(sources.items())
    ]


def _no_point_evidence(row: Any) -> None:
    """这些工序都不是零工时工序：生产见证核对对它们给不出证据。"""
    return None


def _build_payload(results: List[Any], *, allowed_op_ids: Set[int], operations: List[BatchOperation]):
    # 与生产 workbench/run/input 同口径：工序来源表由本次全部工序派生，本次输入没有缺资源工序、排产没有报错。
    return build_validated_schedule_payload(
        results,
        allowed_op_ids=allowed_op_ids,
        operations=operations,
        operation_sources={op.id: op.source for op in operations},
        missing_internal_resource_op_ids=set(),
        schedule_errors=[],
        point_validator=_no_point_evidence,
    )


def _assert_validation_reason(results: List[Any], *, allowed_op_ids: Set[int], reason: str) -> Dict[str, Any]:
    operations = _operations({op_id: "internal" for op_id in allowed_op_ids})
    with pytest.raises(ValidationError) as exc_info:
        _build_payload(results, allowed_op_ids=allowed_op_ids, operations=operations)
    details = dict(getattr(exc_info.value, "details", {}) or {})
    assert details.get("reason") == reason, details
    return details


def test_schedule_payload_error_priority_and_no_actionable_details() -> None:
    invalid = _result(1, start_offset=1, end_offset=1)
    valid = _result(2, start_offset=2, end_offset=3)
    out_of_scope = _result(99, start_offset=3, end_offset=4)

    details = _assert_validation_reason(
        [invalid, valid, out_of_scope],
        allowed_op_ids={1, 2},
        reason="out_of_scope_schedule_rows",
    )
    assert details.get("sample_op_ids") == [99], details
    assert details.get("allowed_scope_kind") == "reschedulable_op_ids", details

    details = _assert_validation_reason(
        [invalid, valid],
        allowed_op_ids={1, 2},
        reason="invalid_schedule_rows",
    )
    assert details.get("invalid_schedule_row_count") == 1, details
    assert "start_time must be earlier than end_time" in "\n".join(details.get("validation_errors") or [])

    details = _assert_validation_reason(
        [_result(1, start_offset=1, end_offset=1), _result(2, start_offset=2, end_offset=2)],
        allowed_op_ids={1, 2},
        reason="no_actionable_schedule_rows",
    )
    assert len(details.get("validation_errors") or []) == 2, details


def test_schedule_payload_rejects_duplicate_op_id_before_persistence() -> None:
    details = _assert_validation_reason(
        [
            _result(1, machine_id="MC_A", start_offset=0, end_offset=1),
            _result(1, machine_id="MC_B", start_offset=2, end_offset=3),
        ],
        allowed_op_ids={1},
        reason="duplicate_schedule_rows",
    )

    assert details.get("sample_op_ids") == [1], details
    assert details.get("count") == 1, details


@pytest.mark.parametrize(
    "invalid_result, expected_text",
    [
        (_result(2, source="internal", machine_id=None, operator_id="OP_A"), "internal 工序必须有设备和人员"),
        (_result(2, source="internal", machine_id="MC_A", operator_id=None), "internal 工序必须有设备和人员"),
        (
            make_schedule_result(
                op_id=2,
                op_code="B001_02",
                batch_id="B001",
                seq=2,
                machine_id="MC_A",
                operator_id="OP_A",
                start_time="2026-01-01 08:00:00",
                end_time=_make_dt(1),
                source="internal",
                op_type_name="A",
            ),
            "start_time/end_time 必须是有效时间",
        ),
        (_result(2, source="legacy", machine_id="MC_A", operator_id="OP_A"), "source 必须是 internal 或 external"),
    ],
)
def test_schedule_payload_rejects_invalid_persist_rows_before_any_valid_save(invalid_result, expected_text) -> None:
    valid = _result(1, machine_id="MC_A", operator_id="OP_A", start_offset=0, end_offset=1)

    details = _assert_validation_reason(
        [valid, invalid_result],
        allowed_op_ids={1, 2},
        reason="invalid_schedule_rows",
    )

    assert expected_text in "\n".join(details.get("validation_errors") or []), details


def test_schedule_payload_rejects_result_source_that_disagrees_with_operation_source() -> None:
    valid = _result(1, machine_id="MC_A", operator_id="OP_A", source="internal")
    wrong_source = _result(2, machine_id="MC_A", operator_id="OP_A", source="external")
    operations = _operations({1: "internal", 2: "internal"})

    with pytest.raises(ValidationError) as exc_info:
        _build_payload([valid, wrong_source], allowed_op_ids={1, 2}, operations=operations)

    details = dict(getattr(exc_info.value, "details", {}) or {})
    assert details.get("reason") == "invalid_schedule_rows", details
    assert "source 与原工序不一致" in "\n".join(details.get("validation_errors") or []), details


def _seed_common(conn: sqlite3.Connection, rows: Iterable[tuple]) -> None:
    conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P001", "part", "yes"))
    conn.execute(
        """
        INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("B001", "P001", "part", 1, "2026-01-10", "normal", "yes", "pending"),
    )
    for machine_id in ("MC_A", "MC_B", "MC_C", "MC_D", "MC_KEEP"):
        conn.execute(
            "INSERT INTO Machines (machine_id, name, status) VALUES (?, ?, ?)",
            (machine_id, machine_id, "active"),
        )
    for operator_id in ("OP_A", "OP_B", "OP_C", "OP_D", "OP_KEEP"):
        conn.execute(
            "INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)",
            (operator_id, operator_id, "active"),
        )
    conn.executemany(
        """
        INSERT INTO BatchOperations
        (id, op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source, machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                op_id,
                f"B001_{op_id:02d}",
                "B001",
                None,
                op_id,
                "OT_A",
                "A",
                source,
                machine_id,
                operator_id,
                None,
                1.0,
                0.0,
                None,
                "pending",
            )
            for op_id, source, _label, machine_id, operator_id in rows
        ],
    )
    conn.commit()


def test_schedule_schema_rejects_duplicate_version_op_rows() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _load_schema(conn)
    try:
        _seed_common(conn, [(1, "internal", "missing", None, None)])
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "MC_A", "OP_A", "2026-01-01 08:00:00", "2026-01-01 09:00:00", "unlocked", 21),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (1, "MC_B", "OP_B", "2026-01-01 10:00:00", "2026-01-01 11:00:00", "unlocked", 21),
            )
        conn.execute(
            "INSERT INTO Schedule (op_id, machine_id, operator_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "MC_B", "OP_B", "2026-01-01 10:00:00", "2026-01-01 11:00:00", "unlocked", 22),
        )
    finally:
        conn.close()

