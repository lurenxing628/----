import os
import sqlite3
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _has_column(conn: sqlite3.Connection, table: str, col: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    for r in rows:
        name = r["name"] if isinstance(r, sqlite3.Row) else r[1]
        if str(name) == str(col):
            return True
    return False


def main():
    """
    回归目标：
    - 旧库缺少 OperatorMachine.skill_level / OperatorMachine.is_primary 时，
      ensure_schema() 必须能自动补齐字段，避免业务代码查询时报错：
        SELECT operator_id, machine_id, skill_level, is_primary FROM OperatorMachine

    复现设计：
    - 人工创建一个“旧 OperatorMachine 表”（仅 operator_id/machine_id）
    - 插入 1 条数据
    - 调用 ensure_schema()（应触发迁移补列与默认值回填）
    - 断言两列存在，且查询不报错、值为默认值 normal/no
    """

    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_operator_machine_cols_")
    test_db = os.path.join(tmpdir, "aps_operator_machine_cols.db")

    # 1) 构造旧库：OperatorMachine 缺列
    conn0 = sqlite3.connect(test_db)
    try:
        conn0.execute("PRAGMA foreign_keys = OFF;")
        conn0.execute(
            """
            CREATE TABLE OperatorMachine (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                operator_id TEXT NOT NULL,
                machine_id  TEXT NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn0.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC_A1"))
        conn0.commit()

        assert not _has_column(conn0, "OperatorMachine", "skill_level")
        assert not _has_column(conn0, "OperatorMachine", "is_primary")
    finally:
        try:
            conn0.close()
        except Exception:
            pass

    # 2) 执行 schema 确保/迁移：应自动补列
    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))

    conn = get_connection(test_db)
    try:
        assert _has_column(conn, "OperatorMachine", "skill_level"), "迁移失败：未补齐 OperatorMachine.skill_level"
        assert _has_column(conn, "OperatorMachine", "is_primary"), "迁移失败：未补齐 OperatorMachine.is_primary"

        rows = conn.execute(
            "SELECT operator_id, machine_id, skill_level, is_primary FROM OperatorMachine ORDER BY operator_id, machine_id"
        ).fetchall()
        assert len(rows) == 1, f"预期 1 条 OperatorMachine 记录，实际 {len(rows)}"

        r = rows[0]
        assert (r["operator_id"] or "").strip() == "OP001"
        assert (r["machine_id"] or "").strip() == "MC_A1"
        assert (r["skill_level"] or "").strip() == "normal", f"预期默认 skill_level='normal'，实际 {r['skill_level']!r}"
        assert (r["is_primary"] or "").strip() == "no", f"预期默认 is_primary='no'，实际 {r['is_primary']!r}"

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

