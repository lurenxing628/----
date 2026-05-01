from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.services.scheduler.schedule_service as schedule_service_mod
from core.infrastructure.errors import ValidationError
from core.services.common.build_outcome import BuildOutcome
from core.services.scheduler.run.schedule_optimizer import OptimizationOutcome
from core.services.scheduler.schedule_service import ScheduleService

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()


def _message(exc: ValidationError) -> str:
    return getattr(exc, "message", str(exc))


def test_schedule_service_rejects_no_actionable_schedule_rows(monkeypatch) -> None:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        _load_schema(conn)
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P001", "测试件", "yes"))
        conn.execute(
            "INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("B_NOACT", "P001", "测试件", 1, "2026-03-10", "normal", "yes", "pending"),
        )
        cur = conn.execute(
            """
            INSERT INTO BatchOperations
            (op_code, batch_id, piece_id, seq, op_type_name, source, machine_id, operator_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_NOACT_10", "B_NOACT", "P1", 10, "工序A", "internal", None, None, 1.0, 0.0, "pending"),
        )
        assert cur.lastrowid is not None
        op_id = int(cur.lastrowid)
        conn.commit()

        def _stub_build_algo_operations(_svc, ops, *, strict_mode=False, return_outcome=False):
            items = []
            for op in ops:
                assert op.id is not None
                op_id_value = int(op.id)
                items.append(
                    SimpleNamespace(
                        id=op_id_value,
                        op_code=op.op_code,
                        batch_id=op.batch_id,
                        seq=int(op.seq or 0),
                        source=op.source,
                        machine_id=op.machine_id,
                        operator_id=op.operator_id,
                        supplier_id=getattr(op, "supplier_id", None),
                        op_type_name=getattr(op, "op_type_name", None),
                    )
                )
            if return_outcome:
                return BuildOutcome(items)
            return items

        monkeypatch.setattr(schedule_service_mod, "build_algo_operations", _stub_build_algo_operations)
        monkeypatch.setattr(schedule_service_mod, "build_freeze_window_seed", lambda *_args, **_kwargs: (set(), [], []))
        monkeypatch.setattr(schedule_service_mod, "load_machine_downtimes", lambda *_args, **_kwargs: {})
        monkeypatch.setattr(schedule_service_mod, "build_resource_pool", lambda *_args, **_kwargs: ({}, []))
        monkeypatch.setattr(
            schedule_service_mod,
            "extend_downtime_map_for_resource_pool",
            lambda *_args, **kwargs: kwargs.get("downtime_map") or {},
        )

        def _stub_optimize_schedule(**_kwargs):
            return OptimizationOutcome(
                results=[
                    SimpleNamespace(
                        op_id=op_id,
                        op_code="B_NOACT_10",
                        batch_id="B_NOACT",
                        seq=10,
                        machine_id="MC001",
                        operator_id="OP001",
                        start_time=None,
                        end_time=None,
                        source="internal",
                        op_type_name="工序A",
                    )
                ],
                summary=SimpleNamespace(success=True, total_ops=1, scheduled_ops=1, failed_ops=0, warnings=[], errors=[], duration_seconds=0.1),
                used_strategy=SimpleNamespace(value="priority_first"),
                used_params={},
                metrics=None,
                best_score=None,
                best_order=[],
                attempts=[],
                improvement_trace=[],
                algo_mode="greedy",
                objective_name="min_overdue",
                algo_stats={},
                time_budget_seconds=1,
            )

        monkeypatch.setattr(schedule_service_mod, "optimize_schedule", _stub_optimize_schedule)

        svc = ScheduleService(conn, logger=None, op_logger=None)
        with pytest.raises(ValidationError) as exc_info:
            svc.run_schedule(batch_ids=["B_NOACT"], start_dt="2026-03-02 08:00:00", simulate=False, enforce_ready=True)

        assert "有效可落库排程行" in _message(exc_info.value)
        details = getattr(exc_info.value, "details", None) or {}
        assert details.get("reason") == "no_actionable_schedule_rows"
        assert details.get("missing_internal_resource_count") == 1
        missing_ops = list(details.get("missing_internal_resource_ops") or [])
        assert missing_ops, details
        assert missing_ops[0]["batch_id"] == "B_NOACT"
        assert missing_ops[0]["seq"] == 10
        assert missing_ops[0]["op_type_name"] == "工序A"
        assert missing_ops[0]["missing_fields"] == ["设备", "人员"]
        assert "B_NOACT / 工序10 / 工序A 缺设备、人员" in str(details.get("user_message") or "")

        schedule_count = int(conn.execute("SELECT COUNT(1) AS cnt FROM Schedule").fetchone()["cnt"] or 0)
        history_count = int(conn.execute("SELECT COUNT(1) AS cnt FROM ScheduleHistory").fetchone()["cnt"] or 0)
        version_seq_count = int(conn.execute("SELECT COUNT(1) AS cnt FROM ScheduleVersionSeq").fetchone()["cnt"] or 0)
        batch_status = conn.execute("SELECT status FROM Batches WHERE batch_id='B_NOACT'").fetchone()["status"]
        op_status = conn.execute("SELECT status FROM BatchOperations WHERE id=?", (op_id,)).fetchone()["status"]
        assert schedule_count == 0
        assert history_count == 0
        assert str(batch_status or "").strip().lower() == "pending"
        assert str(op_status or "").strip().lower() == "pending"
        assert version_seq_count == 0
    finally:
        conn.close()
