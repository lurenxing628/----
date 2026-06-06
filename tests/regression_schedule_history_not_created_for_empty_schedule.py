"""回归测试：当所选批次只含 completed/skipped 工序、没有可重排工序时，ScheduleService.run_schedule 须抛 ValidationError(「所选批次没有可重排工序，本次未执行排产。」)且数据库快照前后完全不变——不写 ScheduleHistory/Schedule/排产日志、不推进 latest_version、不占用 ScheduleVersionSeq。"""

import sqlite3


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


def test_schedule_history_not_created_for_empty_schedule(schema_conn) -> None:

    from core.infrastructure.errors import ValidationError
    from core.infrastructure.logging import OperationLogger
    from core.services.scheduler.schedule_service import ScheduleService

    conn = schema_conn

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


