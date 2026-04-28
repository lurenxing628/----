from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Set

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.schedule_persistence import build_validated_schedule_payload, persist_schedule
from core.services.scheduler.schedule_service import ScheduleService

REPO_ROOT = Path(__file__).resolve().parents[1]


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
) -> SimpleNamespace:
    return SimpleNamespace(
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


def _assert_validation_reason(results: List[Any], *, allowed_op_ids: Set[int], reason: str) -> Dict[str, Any]:
    with pytest.raises(ValidationError) as exc_info:
        build_validated_schedule_payload(results, allowed_op_ids=allowed_op_ids)
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


def _base_persist_kwargs(
    svc: ScheduleService,
    *,
    cfg: Any,
    version: int,
    payload: Any,
    operations: List[Any],
    simulate: bool,
    missing_internal_resource_op_ids: Set[int],
    result_status: str = "success",
) -> Dict[str, Any]:
    return {
        "cfg": cfg,
        "version": version,
        "validated_schedule_payload": payload,
        "summary": SimpleNamespace(total_ops=len(operations), scheduled_ops=len(payload.scheduled_op_ids), failed_ops=0),
        "used_strategy": SimpleNamespace(value="priority_first"),
        "used_params": {},
        "batches": {"B001": svc.batch_repo.get("B001")},
        "reschedulable_operations": operations,
        "normalized_batch_ids": ["B001"],
        "created_by": "regression",
        "simulate": simulate,
        "frozen_op_ids": set(),
        "result_status": result_status,
        "result_summary_json": "{}",
        "result_summary_obj": {"algo": {}},
        "missing_internal_resource_op_ids": missing_internal_resource_op_ids,
        "overdue_items": [],
        "time_cost_ms": 0,
    }


def _resource_snapshot(conn: sqlite3.Connection) -> Dict[int, Dict[str, str]]:
    rows = conn.execute("SELECT id, status, machine_id, operator_id FROM BatchOperations ORDER BY id").fetchall()
    return {
        int(row["id"]): {
            "status": str(row["status"] or ""),
            "machine_id": str(row["machine_id"] or ""),
            "operator_id": str(row["operator_id"] or ""),
        }
        for row in rows
    }


def test_simulate_keeps_real_status_and_auto_assign_resources_unchanged() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _load_schema(conn)
    try:
        _seed_common(conn, [(1, "internal", "missing", None, None)])
        svc = ScheduleService(conn, logger=None, op_logger=None)
        operations = [svc.op_repo.get(1)]
        payload = build_validated_schedule_payload([_result(1, machine_id="MC_A", operator_id="OP_A")], allowed_op_ids={1})

        persist_schedule(
            svc,
            **_base_persist_kwargs(
                svc,
                cfg=SimpleNamespace(auto_assign_persist="yes"),
                version=11,
                payload=payload,
                operations=operations,
                simulate=True,
                missing_internal_resource_op_ids={1},
                result_status="simulated",
            ),
        )

        snap = _resource_snapshot(conn)
        assert snap[1] == {"status": "pending", "machine_id": "", "operator_id": ""}
        assert int(conn.execute("SELECT COUNT(1) AS cnt FROM Schedule WHERE version=11").fetchone()["cnt"] or 0) == 1
        hist = conn.execute("SELECT result_status FROM ScheduleHistory WHERE version=11").fetchone()
        assert hist is not None and hist["result_status"] == "simulated"
    finally:
        conn.close()


def test_auto_assign_persist_no_keeps_resources_empty_but_updates_status() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _load_schema(conn)
    try:
        _seed_common(conn, [(1, "internal", "missing", None, None)])
        svc = ScheduleService(conn, logger=None, op_logger=None)
        operations = [svc.op_repo.get(1)]
        payload = build_validated_schedule_payload([_result(1, machine_id="MC_A", operator_id="OP_A")], allowed_op_ids={1})

        persist_schedule(
            svc,
            **_base_persist_kwargs(
                svc,
                cfg=SimpleNamespace(auto_assign_persist="no"),
                version=12,
                payload=payload,
                operations=operations,
                simulate=False,
                missing_internal_resource_op_ids={1},
            ),
        )

        snap = _resource_snapshot(conn)
        assert snap[1] == {"status": "scheduled", "machine_id": "", "operator_id": ""}
    finally:
        conn.close()


def test_auto_assign_persist_only_fills_internal_missing_fields_without_overwrite() -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    _load_schema(conn)
    try:
        _seed_common(
            conn,
            [
                (1, "internal", "missing_both", None, None),
                (2, "internal", "missing_operator", "MC_KEEP", None),
                (3, "internal", "missing_machine", None, "OP_KEEP"),
                (4, "external", "external_missing", None, None),
                (5, "internal", "not_in_missing_set", None, None),
            ],
        )
        svc = ScheduleService(conn, logger=None, op_logger=None)
        operations = [svc.op_repo.get(op_id) for op_id in range(1, 6)]
        results = [
            _result(1, machine_id="MC_A", operator_id="OP_A"),
            _result(2, machine_id="MC_B", operator_id="OP_B"),
            _result(3, machine_id="MC_C", operator_id="OP_C"),
            _result(4, machine_id="MC_D", operator_id="OP_D", source="external"),
            _result(5, machine_id="MC_A", operator_id="OP_A"),
        ]
        payload = build_validated_schedule_payload(results, allowed_op_ids={1, 2, 3, 4, 5})

        persist_schedule(
            svc,
            **_base_persist_kwargs(
                svc,
                cfg=SimpleNamespace(auto_assign_persist="yes"),
                version=13,
                payload=payload,
                operations=operations,
                simulate=False,
                missing_internal_resource_op_ids={1, 2, 3},
            ),
        )

        snap = _resource_snapshot(conn)
        assert snap[1] == {"status": "scheduled", "machine_id": "MC_A", "operator_id": "OP_A"}
        assert snap[2] == {"status": "scheduled", "machine_id": "MC_KEEP", "operator_id": "OP_B"}
        assert snap[3] == {"status": "scheduled", "machine_id": "MC_C", "operator_id": "OP_KEEP"}
        assert snap[4] == {"status": "scheduled", "machine_id": "", "operator_id": ""}
        assert snap[5] == {"status": "scheduled", "machine_id": "", "operator_id": ""}
    finally:
        conn.close()
