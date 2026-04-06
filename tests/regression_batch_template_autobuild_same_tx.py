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
    with open(os.path.join(repo_root, "schema.sql"), "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.errors import AppError, ErrorCode
    from core.services.scheduler.batch_service import BatchService

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        load_schema(conn, repo_root)
        conn.execute(
            "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
            ("OT_IN", "数铣", "internal"),
        )
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            ("P_AUTO_TX", "自动补建件", "5数铣10数铣", "no", None),
        )
        conn.execute(
            """
            INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, ready_date, status, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("DUMMY_TX", "P_AUTO_TX", "自动补建件", 1, None, "normal", "no", None, "pending", "占位批次"),
        )
        conn.execute(
            """
            INSERT INTO BatchOperations
            (op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source, machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_AUTO_TX_05", "DUMMY_TX", None, 5, "OT_IN", "数铣", "internal", None, None, None, 0, 0, None, "pending"),
        )
        conn.commit()

        svc = BatchService(conn, logger=None, op_logger=None)
        try:
            svc.create_batch_from_template(
                batch_id="B_AUTO_TX",
                part_no="P_AUTO_TX",
                quantity=1,
                priority="normal",
                ready_status="yes",
            )
        except AppError as e:
            assert e.code == ErrorCode.DUPLICATE_ENTRY, f"期望触发 BatchOperations.op_code 唯一约束：{e.code!r}"
        else:
            raise AssertionError("期望通过工序编码冲突触发整体回滚，但实际未失败")

        batch_row = conn.execute("SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", ("B_AUTO_TX",)).fetchone()
        assert batch_row is not None and int(batch_row["cnt"] or 0) == 0, (
            f"失败后不应残留批次头：{dict(batch_row) if batch_row else None!r}"
        )

        batch_op_row = conn.execute("SELECT COUNT(1) AS cnt FROM BatchOperations WHERE batch_id=?", ("B_AUTO_TX",)).fetchone()
        assert batch_op_row is not None and int(batch_op_row["cnt"] or 0) == 0, (
            f"失败后不应残留批次工序：{dict(batch_op_row) if batch_op_row else None!r}"
        )

        template_row = conn.execute("SELECT COUNT(1) AS cnt FROM PartOperations WHERE part_no=?", ("P_AUTO_TX",)).fetchone()
        assert template_row is not None and int(template_row["cnt"] or 0) == 0, (
            f"失败后不应残留自动补建模板：{dict(template_row) if template_row else None!r}"
        )

        part_row = conn.execute("SELECT route_parsed FROM Parts WHERE part_no=?", ("P_AUTO_TX",)).fetchone()
        if part_row is None or str(part_row["route_parsed"] or "").strip() != "no":
            raise RuntimeError(f"失败后 route_parsed 不应被提前写成 yes：{dict(part_row) if part_row else None!r}")

        print("OK")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
