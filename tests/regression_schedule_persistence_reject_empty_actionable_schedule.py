"""回归测试：排产持久化遇到空的 validated payload 必须当安全熔断，persist_schedule 抛 reason=no_actionable_schedule_rows 的 ValidationError 且不在 Schedule/History/日志/批次状态留下任何痕迹；raise_no_actionable_schedule_error 优先用根因错误而非缺资源提示，并屏蔽含 Traceback/路径/口令的不安全自动派工错误，工时不合法时仍给「批次工序补充页补齐」提示。"""

import os
import sqlite3
import sys
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from tests._support.paths import REPO_ROOT_STR


def find_repo_root() -> str:
    return REPO_ROOT_STR


def load_schema(conn: sqlite3.Connection, repo_root: str) -> None:
    schema_path = os.path.join(repo_root, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _snapshot(conn: sqlite3.Connection) -> dict:
    batch_row = conn.execute("SELECT status FROM Batches WHERE batch_id=?", ("B_FUSE",)).fetchone()
    op_row = conn.execute("SELECT status FROM BatchOperations WHERE id=?", (1,)).fetchone()
    return {
        "schedule_count": int(conn.execute("SELECT COUNT(1) AS cnt FROM Schedule").fetchone()["cnt"] or 0),
        "history_count": int(conn.execute("SELECT COUNT(1) AS cnt FROM ScheduleHistory").fetchone()["cnt"] or 0),
        "log_count": int(conn.execute("SELECT COUNT(1) AS cnt FROM OperationLogs").fetchone()["cnt"] or 0),
        "batch_status": str(batch_row["status"] or "").strip().lower() if batch_row else "",
        "op_status": str(op_row["status"] or "").strip().lower() if op_row else "",
    }


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.errors import ValidationError
    from core.infrastructure.logging import OperationLogger
    from core.services.scheduler.run.schedule_persistence import ValidatedSchedulePayload
    from core.services.scheduler.schedule_persistence import persist_schedule
    from core.services.scheduler.schedule_service import ScheduleService

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    load_schema(conn, repo_root)

    try:
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P001", "part", "yes"))
        conn.execute(
            """
            INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_FUSE", "P001", "fuse", 1, "2026-01-10", "normal", "yes", "pending"),
        )
        conn.execute(
            """
            INSERT INTO BatchOperations
            (id, op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source, machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "B_FUSE_10", "B_FUSE", None, 10, "OT_A", "A", "internal", None, None, None, 1.0, 0.0, None, "pending"),
        )
        conn.commit()

        svc = ScheduleService(conn, logger=None, op_logger=OperationLogger(conn, logger=None))
        batch = svc.batch_repo.get("B_FUSE")
        op = svc.op_repo.get(1)
        if batch is None or op is None:
            raise RuntimeError("test fixture init failed")

        before = _snapshot(conn)
        try:
            payload: Dict[str, Any] = {
                "cfg": SimpleNamespace(auto_assign_persist="no"),
                "version": 9,
                "validated_schedule_payload": ValidatedSchedulePayload(
                    schedule_rows=[],
                    scheduled_op_ids=set(),
                    assigned_by_op_id={},
                ),
                "summary": SimpleNamespace(total_ops=1, scheduled_ops=0, failed_ops=1),
                "used_strategy": SimpleNamespace(value="priority_first"),
                "used_params": {},
                "batches": {"B_FUSE": batch},
                "reschedulable_operations": [op],
                "normalized_batch_ids": ["B_FUSE"],
                "created_by": "regression",
                "simulate": False,
                "frozen_op_ids": set(),
                "result_status": "failed",
                "result_summary_json": "{}",
                "result_summary_obj": {"algo": {}},
                "missing_internal_resource_op_ids": set(),
                "overdue_items": [],
                "time_cost_ms": 0,
            }
            persist_schedule(svc, **payload)
            raise RuntimeError("persist_schedule must reject empty validated payload")
        except ValidationError as exc:
            details = getattr(exc, "details", None) or {}
            assert details.get("reason") == "no_actionable_schedule_rows", details

        after = _snapshot(conn)
        assert before == after, f"persist safety fuse must not leave any traces: before={before!r}, after={after!r}"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print("OK")


@pytest.mark.parametrize(
    ("root_error", "expected_public_text"),
    [
        (
            "自动派工没有找到可用的设备和人员组合：工序 OP10。请检查设备工种、人员可操作设备和资源可用时间后再排产。",
            "自动派工没有找到可用的设备和人员组合：工序 OP10。请检查设备工种、人员可操作设备和资源可用时间后再排产",
        ),
        (
            "自动派工资料不完整，本次无法自动补齐设备和人员：工序 OP10",
            "自动派工资料不完整，本次无法自动补齐设备和人员：工序 OP10",
        ),
        (
            "自制工序缺少自动派工所需工种信息，无法自动分配：工序 OP10",
            "自制工序缺少自动派工所需工种信息，无法自动分配：工序 OP10",
        ),
        ("工时不合法：工序 OP10", "工时不合法：工序 OP10"),
        (
            "批次 B-1 的工序 OP-10（顺序 1，工种 数车，图号 P-1，零件 测试件）自动派工资料不完整，请检查设备工种和人员可操作设备后再排产。",
            "批次 B-1 的工序 OP-10（顺序 1，工种 数车，图号 P-1，零件 测试件）自动派工资料不完整，请检查设备工种和人员可操作设备后再排产",
        ),
        (
            "批次 B-1 的工序 OP-10（顺序 1，工种 数车。精加工，图号 P-1，零件 测试件）自动派工资料不完整，请检查设备工种和人员可操作设备后再排产。",
            "批次 B-1 的工序 OP-10（顺序 1，工种 数车。精加工，图号 P-1，零件 测试件）自动派工资料不完整，请检查设备工种和人员可操作设备后再排产",
        ),
    ],
)
def test_no_actionable_schedule_prefers_root_error_over_missing_resource_hint(
    root_error: str,
    expected_public_text: str,
) -> None:
    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.run.schedule_persistence_errors import raise_no_actionable_schedule_error

    op = SimpleNamespace(
        id=1,
        batch_id="B_AUTO",
        seq=10,
        op_type_name="数车",
        machine_id="",
        operator_id="",
    )

    with pytest.raises(ValidationError) as exc_info:
        raise_no_actionable_schedule_error(
            [root_error],
            operations=[op],
            missing_internal_resource_op_ids={1},
        )

    details = exc_info.value.details or {}
    assert details.get("reason") == "no_actionable_schedule_rows"
    assert details.get("missing_internal_resource_count") == 1
    assert expected_public_text in str(details.get("user_message") or "")
    assert "批次工序补充页补齐" not in str(details.get("user_message") or "")


def test_non_auto_assign_invalid_hours_error_keeps_missing_resource_hint() -> None:
    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.run.schedule_persistence_errors import raise_no_actionable_schedule_error

    op = SimpleNamespace(
        id=1,
        batch_id="B_AUTO",
        seq=10,
        op_type_name="数车",
        machine_id="",
        operator_id="",
    )

    with pytest.raises(ValidationError) as exc_info:
        raise_no_actionable_schedule_error(
            ["工时不合法：工序 OP10 工时字段不合法：setup_hours='abc'"],
            operations=[op],
            missing_internal_resource_op_ids={1},
        )

    message = str((exc_info.value.details or {}).get("user_message") or "")
    assert "批次工序补充页补齐" in message
    assert "工时不合法" not in message


def test_auto_assign_failed_op_ids_from_errors_accepts_sgs_public_message_format_with_batch() -> None:
    from core.services.scheduler.run.auto_assign_resource_errors import auto_assign_failed_op_ids_from_errors

    operations = [
        SimpleNamespace(id=11, batch_id="B-1", op_code="OP-10"),
        SimpleNamespace(id=12, batch_id="B-2", op_code="OP-10"),
        SimpleNamespace(id=13, batch_id="B-1", op_code="OP-101"),
    ]
    errors = [
        "批次 B-1 的工序 OP-10（顺序 1，工种 数车，图号 P-1，零件 测试件）自动派工资料不完整，请检查设备工种和人员可操作设备后再排产。",
    ]

    assert auto_assign_failed_op_ids_from_errors(errors=errors, operations=operations) == {11}


def test_sgs_auto_assign_failed_op_ids_from_errors_does_not_guess_when_batch_misses() -> None:
    from core.services.scheduler.run.auto_assign_resource_errors import auto_assign_failed_op_ids_from_errors

    operations = [
        SimpleNamespace(id=12, batch_id="B-2", op_code="OP-10"),
    ]
    errors = [
        "批次 B-1 的工序 OP-10（顺序 1，工种 数车，图号 P-1，零件 测试件）自动派工资料不完整，请检查设备工种和人员可操作设备后再排产。",
    ]

    assert auto_assign_failed_op_ids_from_errors(errors=errors, operations=operations) == set()


def test_auto_assign_failed_op_ids_from_errors_accepts_sgs_public_sequence_format() -> None:
    from core.services.scheduler.run.auto_assign_resource_errors import auto_assign_failed_op_ids_from_errors

    operations = [
        SimpleNamespace(id=21, batch_id="B-1", op_code="", seq=1),
        SimpleNamespace(id=22, batch_id="B-2", op_code="", seq=1),
    ]
    errors = [
        "批次 B-1 的工序顺序 1（工种 数车，图号 P-1，零件 测试件）自动派工资料不完整，请检查设备工种和人员可操作设备后再排产。",
    ]

    assert auto_assign_failed_op_ids_from_errors(errors=errors, operations=operations) == {21}


def test_legacy_auto_assign_failed_op_ids_from_errors_does_not_guess_duplicate_op_codes() -> None:
    from core.services.scheduler.run.auto_assign_resource_errors import auto_assign_failed_op_ids_from_errors

    operations = [
        SimpleNamespace(id=11, batch_id="B-1", op_code="OP-10"),
        SimpleNamespace(id=12, batch_id="B-2", op_code="OP-10"),
    ]

    assert (
        auto_assign_failed_op_ids_from_errors(
            errors=["自动派工资料不完整，本次无法自动补齐设备和人员：工序 OP-10"],
            operations=operations,
        )
        == set()
    )


def test_no_actionable_schedule_does_not_expose_unsafe_auto_assign_root_error() -> None:
    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.run.schedule_persistence_errors import raise_no_actionable_schedule_error

    root_error = (
        "自动派工资料不完整，本次无法自动补齐设备和人员：工序 "
        "OP10 Traceback sqlite password /Users/private/aps.db"
    )
    op = SimpleNamespace(
        id=1,
        batch_id="B_AUTO",
        seq=10,
        op_type_name="数车",
        machine_id="",
        operator_id="",
    )

    with pytest.raises(ValidationError) as exc_info:
        raise_no_actionable_schedule_error(
            [root_error],
            operations=[op],
            missing_internal_resource_op_ids={1},
        )

    details = exc_info.value.details or {}
    user_message = str(details.get("user_message") or "")
    assert details.get("reason") == "no_actionable_schedule_rows"
    assert details.get("validation_errors") == [root_error]
    assert details.get("missing_internal_resource_count") == 1
    assert not user_message
    assert "批次工序补充页补齐" not in user_message
    assert "Traceback" not in user_message
    assert "sqlite" not in user_message
    assert "password" not in user_message
    assert "/Users/private" not in user_message


def test_no_actionable_schedule_uses_later_safe_auto_assign_error_after_unsafe_one() -> None:
    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.run.schedule_persistence_errors import raise_no_actionable_schedule_error

    unsafe_error = (
        "自动派工资料不完整，本次无法自动补齐设备和人员：工序 "
        "OP10 Traceback sqlite password /Users/private/aps.db"
    )
    safe_error = "自动派工资料不完整，本次无法自动补齐设备和人员：工序 OP11"

    with pytest.raises(ValidationError) as exc_info:
        raise_no_actionable_schedule_error(
            [unsafe_error, safe_error],
            operations=[
                SimpleNamespace(
                    id=1,
                    batch_id="B_AUTO",
                    seq=10,
                    op_type_name="数车",
                    machine_id="",
                    operator_id="",
                )
            ],
            missing_internal_resource_op_ids={1},
        )

    details = exc_info.value.details or {}
    user_message = str(details.get("user_message") or "")
    assert safe_error in user_message
    assert "批次工序补充页补齐" not in user_message
    assert "Traceback" not in user_message
    assert "sqlite" not in user_message
    assert "password" not in user_message
    assert "/Users/private" not in user_message


def test_empty_payload_uses_schedule_errors_for_no_actionable_message() -> None:
    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.run.schedule_payload_contract import build_validated_schedule_payload

    op = SimpleNamespace(
        id=1,
        batch_id="B_AUTO",
        seq=10,
        op_code="OP10",
        op_type_name="数车",
        machine_id="",
        operator_id="",
        source="internal",
    )

    with pytest.raises(ValidationError) as exc_info:
        build_validated_schedule_payload(
            [],
            allowed_op_ids={1},
            operations=[op],
            missing_internal_resource_op_ids={1},
            schedule_errors=["自动派工资料不完整，本次无法自动补齐设备和人员：工序 OP10"],
        )

    message = str((exc_info.value.details or {}).get("user_message") or "")
    assert "自动派工资料不完整" in message
    assert "批次工序补充页补齐" not in message


if __name__ == "__main__":
    main()
