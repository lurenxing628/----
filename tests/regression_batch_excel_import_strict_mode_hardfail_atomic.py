import os
import sqlite3
import sys
from types import SimpleNamespace


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
    from core.services.common.excel_service import ImportMode, ImportPreviewRow, RowStatus
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
        preview_rows = [
            ImportPreviewRow(
                row_num=2,
                status=RowStatus.NEW,
                data={
                    "批次号": "B_STRICT_IMPORT",
                    "图号": "P_ROUTE",
                    "数量": 1,
                    "交期": "2026-06-01",
                    "优先级": "normal",
                    "齐套": "yes",
                    "齐套日期": None,
                    "备注": "strict-mode-hardfail",
                },
                message="将新增",
            )
        ]

        try:
            svc.import_from_preview_rows(
                preview_rows=preview_rows,
                mode=ImportMode.OVERWRITE,
                parts_cache={"P_ROUTE": SimpleNamespace(part_name="路线件")},
                auto_generate_ops=True,
                strict_mode=True,
                existing_ids=set(),
            )
        except BusinessError as e:
            assert e.code == ErrorCode.ROUTE_PARSE_ERROR, f"strict_mode Excel 导入应返回 ROUTE_PARSE_ERROR：{e.code!r}"
        else:
            raise AssertionError("strict_mode=True 且模板补建需要 fallback 时，Excel 导入应硬失败")

        batch_row = conn.execute("SELECT COUNT(1) AS cnt FROM Batches WHERE batch_id=?", ("B_STRICT_IMPORT",)).fetchone()
        assert batch_row is not None and int(batch_row["cnt"] or 0) == 0, (
            f"strict_mode 失败后不应残留 Batches：{dict(batch_row) if batch_row else None!r}"
        )

        op_row = conn.execute("SELECT COUNT(1) AS cnt FROM BatchOperations WHERE batch_id=?", ("B_STRICT_IMPORT",)).fetchone()
        assert op_row is not None and int(op_row["cnt"] or 0) == 0, (
            f"strict_mode 失败后不应残留 BatchOperations：{dict(op_row) if op_row else None!r}"
        )

        print("OK")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
