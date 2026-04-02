import os
import sqlite3
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def load_schema(conn: sqlite3.Connection, repo_root: str) -> None:
    schema_path = os.path.join(repo_root, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _make_dt(hours: int) -> datetime:
    return datetime(2026, 1, 1, 8, 0, 0) + timedelta(hours=hours)


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
    from core.services.scheduler.schedule_persistence import persist_schedule
    from core.services.scheduler.schedule_service import ScheduleService

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    load_schema(conn, repo_root)

    try:
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P001", "测试零件", "yes"))
        conn.execute(
            """
            INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_FUSE", "P001", "保险丝批次", 1, "2026-01-10", "normal", "yes", "pending"),
        )
        conn.execute(
            """
            INSERT INTO BatchOperations
            (id, op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source, machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "B_FUSE_10", "B_FUSE", None, 10, "OT_A", "工序A", "internal", None, None, None, 1.0, 0.0, None, "pending"),
        )
        conn.commit()

        svc = ScheduleService(conn, logger=None, op_logger=OperationLogger(conn, logger=None))
        batch = svc.batch_repo.get("B_FUSE")
        op = svc.op_repo.get(1)
        if batch is None or op is None:
            raise RuntimeError("测试数据初始化失败")

        before = _snapshot(conn)
        try:
            payload: Dict[str, Any] = {
                "cfg": SimpleNamespace(auto_assign_persist="no"),
                "version": 9,
                "results": [
                    SimpleNamespace(
                        op_id=1,
                        op_code="B_FUSE_10",
                        batch_id="B_FUSE",
                        seq=10,
                        machine_id="MC001",
                        operator_id="OP001",
                        start_time=_make_dt(0),
                        end_time=_make_dt(1),
                        source="internal",
                        op_type_name="工序A",
                    )
                ],
                "summary": SimpleNamespace(total_ops=1, scheduled_ops=1, failed_ops=0),
                "used_strategy": SimpleNamespace(value="priority_first"),
                "used_params": {},
                "batches": {"B_FUSE": batch},
                "operations": [op],
                "reschedulable_operations": [op],
                "reschedulable_op_ids": {1},
                "normalized_batch_ids": ["B_FUSE"],
                "created_by": "regression",
                "has_actionable_schedule": False,
                "simulate": False,
                "frozen_op_ids": set(),
                "result_status": "success",
                "result_summary_json": "{}",
                "result_summary_obj": {"algo": {}},
                "missing_internal_resource_op_ids": set(),
                "overdue_items": [],
                "time_cost_ms": 0,
            }
            persist_schedule(svc, **payload)
            raise RuntimeError("持久化保险丝应拒绝 has_actionable_schedule=False")
        except ValidationError as exc:
            message = getattr(exc, "message", str(exc))
            assert "本次没有实际可执行排产任务" in message, f"保险丝提示异常：{message!r}"

        after = _snapshot(conn)
        assert before == after, f"保险丝拒绝后不应写入任何留痕或状态：before={before!r}, after={after!r}"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print("OK")


if __name__ == "__main__":
    main()
