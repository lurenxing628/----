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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.process.external_group_service import ExternalGroupService

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    load_schema(conn, repo_root)

    # 准备最小数据：Parts + PartOperations + ExternalGroups
    conn.execute(
        "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?,?,?,?)",
        ("P001", "零件", "", "yes"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P001", 10, "外协A", "external", None, 2.0, "G001", 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P001", 11, "外协B", "external", None, 1.0, "G001", 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id, remark)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("G001", "P001", 10, 11, "separate", None, None, None),
    )
    conn.commit()

    svc = ExternalGroupService(conn)

    # 关键：merge_mode 大小写混用时仍应被接受
    g = svc.set_merge_mode(group_id="G001", merge_mode="MERGED", total_days=3)
    assert g.merge_mode == "merged", f"merge_mode 未规范化：{g.merge_mode!r}"
    assert float(g.total_days or 0) == 3.0, f"total_days 写入异常：{g.total_days!r}"

    row = conn.execute("SELECT merge_mode, total_days FROM ExternalGroups WHERE group_id='G001'").fetchone()
    assert row["merge_mode"] == "merged", f"ExternalGroups.merge_mode 未落库为 merged：{row['merge_mode']!r}"
    assert float(row["total_days"] or 0) == 3.0, f"ExternalGroups.total_days 落库异常：{row['total_days']!r}"

    # merged 模式：组内工序 ext_days 必须被清空（置 NULL）
    rows = conn.execute("SELECT seq, ext_days FROM PartOperations WHERE part_no='P001' ORDER BY seq ASC").fetchall()
    for r in rows:
        assert r["ext_days"] is None, f"merged 模式下 ext_days 应为 NULL：seq={r['seq']} ext_days={r['ext_days']!r}"

    print("OK")


if __name__ == "__main__":
    main()

