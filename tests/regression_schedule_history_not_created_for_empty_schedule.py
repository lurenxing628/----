import os
import sqlite3
import sys


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


def _snapshot(conn: sqlite3.Connection) -> dict:
    from data.repositories import ScheduleHistoryRepository

    batch_row = conn.execute("SELECT status FROM Batches WHERE batch_id=?", ("B_EMPTY",)).fetchone()
    op_rows = conn.execute("SELECT id, status FROM BatchOperations WHERE batch_id=? ORDER BY id", ("B_EMPTY",)).fetchall()
    return {
        "history_count": int(conn.execute("SELECT COUNT(1) AS cnt FROM ScheduleHistory").fetchone()["cnt"] or 0),
        "latest_version": int(ScheduleHistoryRepository(conn, logger=None).get_latest_version()),
        "schedule_count": int(conn.execute("SELECT COUNT(1) AS cnt FROM Schedule").fetchone()["cnt"] or 0),
        "log_count": int(conn.execute("SELECT COUNT(1) AS cnt FROM OperationLogs").fetchone()["cnt"] or 0),
        "version_seq_count": int(conn.execute("SELECT COUNT(1) AS cnt FROM ScheduleVersionSeq").fetchone()["cnt"] or 0),
        "batch_status": str(batch_row["status"] or "").strip().lower() if batch_row else "",
        "op_statuses": {
            int(row["id"]): str(row["status"] or "").strip().lower()
            for row in op_rows
        },
    }


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.errors import ValidationError
    from core.infrastructure.logging import OperationLogger
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
            ("B_EMPTY", "P001", "空执行批次", 1, "2026-01-10", "normal", "yes", "pending"),
        )
        conn.executemany(
            """
            INSERT INTO BatchOperations
            (id, op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source, machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "B_EMPTY_10", "B_EMPTY", None, 10, "OT_A", "工序A", "internal", None, None, None, 1.0, 0.0, None, "completed"),
                (2, "B_EMPTY_20", "B_EMPTY", None, 20, "OT_B", "工序B", "external", None, None, None, 0.0, 0.0, 2.0, "skipped"),
            ],
        )
        conn.commit()

        svc = ScheduleService(conn, logger=None, op_logger=OperationLogger(conn, logger=None))
        before = _snapshot(conn)

        try:
            svc.run_schedule(
                batch_ids=["B_EMPTY"],
                start_dt="2026-01-01 08:00:00",
                simulate=False,
                enforce_ready=True,
            )
            raise RuntimeError("空执行场景应抛出 ValidationError")
        except ValidationError as exc:
            message = getattr(exc, "message", str(exc))
            assert "所选批次没有可重排工序，本次未执行排产。" in message, f"空执行提示异常：{message!r}"

        after = _snapshot(conn)
        assert before == after, f"空执行前后数据库快照不应变化：before={before!r}, after={after!r}"
        assert after["latest_version"] == 0, f"空执行不应推进最新版本号：{after!r}"
        assert after["history_count"] == 0, f"空执行不应写入 ScheduleHistory：{after!r}"
        assert after["schedule_count"] == 0, f"空执行不应写入 Schedule：{after!r}"
        assert after["log_count"] == 0, f"空执行不应写入排产操作日志：{after!r}"
        assert after["version_seq_count"] == 0, f"空执行不应占用版本号序列：{after!r}"
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print("OK")


if __name__ == "__main__":
    main()
