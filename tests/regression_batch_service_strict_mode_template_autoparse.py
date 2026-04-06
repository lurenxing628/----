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

    from core.infrastructure.errors import BusinessError, ErrorCode
    from core.services.scheduler.batch_service import BatchService

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        load_schema(conn, repo_root)
        conn.execute(
            "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
            ("OT_EXT", "表处理", "external"),
        )
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed, remark) VALUES (?, ?, ?, ?, ?)",
            ("P_ROUTE", "路线件", "10表处理", "no", None),
        )
        conn.commit()

        svc = BatchService(conn, logger=None, op_logger=None)
        try:
            svc.create_batch_from_template(
                batch_id="B_STRICT",
                part_no="P_ROUTE",
                quantity=1,
                priority="normal",
                ready_status="yes",
                strict_mode=True,
            )
        except BusinessError as e:
            assert e.code == ErrorCode.ROUTE_PARSE_ERROR, f"strict_mode 建批应返回 ROUTE_PARSE_ERROR：{e.code!r}"
        else:
            raise AssertionError("strict_mode=True 时自动补建模板应因缺供应商映射失败")

        row = conn.execute("SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", ("B_STRICT",)).fetchone()
        assert row is not None and int(row["cnt"] or 0) == 0, f"strict_mode 失败后不应残留 Batches：{dict(row) if row else None!r}"

        print("OK")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
