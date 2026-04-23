import os
import sqlite3
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("repo root not found")


def load_schema(conn: sqlite3.Connection, repo_root: str) -> None:
    schema_path = os.path.join(repo_root, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _make_dt(hours: int) -> datetime:
    return datetime(2026, 1, 1, 8, 0, 0) + timedelta(hours=hours)


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.run.schedule_persistence import build_validated_schedule_payload
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
            ("B_MIX", "P001", "mix", 1, "2026-01-10", "normal", "yes", "pending"),
        )
        conn.execute(
            """
            INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_ZERO", "P001", "zero", 1, "2026-01-10", "normal", "yes", "scheduled"),
        )
        conn.executemany(
            """
            INSERT INTO BatchOperations
            (id, op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source, machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "B_MIX_10", "B_MIX", None, 10, "OT_A", "A", "internal", None, None, None, 1.0, 0.0, None, "completed"),
                (2, "B_MIX_20", "B_MIX", None, 20, "OT_B", "B", "internal", None, None, None, 1.0, 0.0, None, "pending"),
                (3, "B_ZERO_10", "B_ZERO", None, 10, "OT_C", "C", "internal", None, None, None, 1.0, 0.0, None, "skipped"),
            ],
        )
        conn.commit()

        svc = ScheduleService(conn, logger=None, op_logger=None)
        batches = {
            "B_MIX": svc.batch_repo.get("B_MIX"),
            "B_ZERO": svc.batch_repo.get("B_ZERO"),
        }
        reschedulable_operations = [svc.op_repo.get(2)]

        results = [
            SimpleNamespace(
                op_id=1,
                op_code="B_MIX_10",
                batch_id="B_MIX",
                seq=10,
                machine_id=None,
                operator_id=None,
                start_time=_make_dt(0),
                end_time=_make_dt(1),
                source="internal",
                op_type_name="A",
            ),
            SimpleNamespace(
                op_id=2,
                op_code="B_MIX_20",
                batch_id="B_MIX",
                seq=20,
                machine_id=None,
                operator_id=None,
                start_time=_make_dt(1),
                end_time=_make_dt(2),
                source="internal",
                op_type_name="B",
            ),
            SimpleNamespace(
                op_id=3,
                op_code="B_ZERO_10",
                batch_id="B_ZERO",
                seq=10,
                machine_id=None,
                operator_id=None,
                start_time=_make_dt(2),
                end_time=_make_dt(3),
                source="internal",
                op_type_name="C",
            ),
        ]
        summary = SimpleNamespace(
            success=True,
            total_ops=1,
            scheduled_ops=1,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        )
        rejected_out_of_scope = False
        try:
            build_validated_schedule_payload(results, allowed_op_ids={2})
        except ValidationError as exc:
            details = dict(getattr(exc, "details", {}) or {})
            rejected_out_of_scope = details.get("reason") == "out_of_scope_schedule_rows"
            assert details.get("count") == 2, details
            assert details.get("sample_op_ids") == [1, 3], details
            assert details.get("allowed_scope_kind") == "reschedulable_op_ids", details
        assert rejected_out_of_scope, "mixed scope results must be rejected instead of silent drop"

        validated_schedule_payload = build_validated_schedule_payload([results[1]], allowed_op_ids={2})

        persist_schedule(
            svc,
            cfg=SimpleNamespace(auto_assign_persist="no"),
            version=7,
            validated_schedule_payload=validated_schedule_payload,
            summary=summary,
            used_strategy=SimpleNamespace(value="priority_first"),
            used_params={},
            batches=batches,
            reschedulable_operations=reschedulable_operations,
            normalized_batch_ids=["B_MIX", "B_ZERO"],
            created_by="regression",
            simulate=False,
            frozen_op_ids=set(),
            result_status="success",
            result_summary_json="{}",
            result_summary_obj={"algo": {}},
            missing_internal_resource_op_ids=set(),
            overdue_items=[],
            time_cost_ms=0,
        )

        schedule_rows = conn.execute("SELECT op_id FROM Schedule WHERE version=? ORDER BY op_id", (7,)).fetchall()
        assert [int(r["op_id"]) for r in schedule_rows] == [2], [dict(r) for r in schedule_rows]

        op_status = {
            int(r["id"]): str(r["status"] or "").strip().lower()
            for r in conn.execute("SELECT id, status FROM BatchOperations ORDER BY id").fetchall()
        }
        assert op_status[1] == "completed", op_status
        assert op_status[2] == "scheduled", op_status
        assert op_status[3] == "skipped", op_status

        batch_status = {
            str(r["batch_id"]): str(r["status"] or "").strip().lower()
            for r in conn.execute("SELECT batch_id, status FROM Batches ORDER BY batch_id").fetchall()
        }
        assert batch_status["B_MIX"] == "scheduled", batch_status
        assert batch_status["B_ZERO"] == "scheduled", batch_status

        hist = conn.execute("SELECT version, result_status FROM ScheduleHistory WHERE version=?", (7,)).fetchone()
        assert hist is not None and int(hist["version"]) == 7 and str(hist["result_status"]) == "success"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print("OK")


if __name__ == "__main__":
    main()
