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
    from core.services.process.part_service import PartService

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        load_schema(conn, repo_root)
        conn.execute(
            "INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)",
            ("OT_EXT", "表处理", "external"),
        )
        conn.commit()

        svc = PartService(conn, logger=None, op_logger=None)

        try:
            svc.create(part_no="P_STRICT", part_name="严格件", route_raw="10表处理", strict_mode=True)
        except BusinessError as e:
            assert e.code == ErrorCode.ROUTE_PARSE_ERROR, f"严格创建应返回 ROUTE_PARSE_ERROR：{e.code!r}"
        else:
            raise AssertionError("strict_mode=True 时应因缺供应商映射而拒绝创建")

        row = conn.execute("SELECT COUNT(1) AS cnt FROM Parts WHERE part_no=?", ("P_STRICT",)).fetchone()
        assert row is not None and int(row["cnt"] or 0) == 0, f"strict_mode 失败后不应残留 Parts：{dict(row) if row else None!r}"

        op_row = conn.execute("SELECT COUNT(1) AS cnt FROM PartOperations WHERE part_no=?", ("P_STRICT",)).fetchone()
        assert op_row is not None and int(op_row["cnt"] or 0) == 0, f"strict_mode 失败后不应残留 PartOperations：{dict(op_row) if op_row else None!r}"

        print("OK")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
