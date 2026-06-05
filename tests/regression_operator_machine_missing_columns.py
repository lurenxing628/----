"""回归测试：残缺旧库仅有缺列的 OperatorMachine 表（无 skill_level/is_primary 且缺其它整表）时，ensure_schema() 必须抛 MigrationContractError 快速失败，不得用当前 schema.sql 静默补成“看起来可用”的新库，原有数据保持原样。"""

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
    - 残缺旧库只有 OperatorMachine 一张业务表、缺少其它整表时，
      ensure_schema() 必须 fail-fast，不能用当前 schema.sql 静默补成“看起来可用”的新库。

    复现设计：
    - 人工创建一个“旧 OperatorMachine 表”（仅 operator_id/machine_id）
    - 插入 1 条数据
    - 调用 ensure_schema()
    - 断言抛出 MigrationContractError，且真实库仍未补出 skill_level/is_primary
    """

    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import MigrationContractError, ensure_schema, get_connection

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

    # 2) 执行 schema 确保/迁移：残缺整库应直接失败，不能静默补齐
    try:
        ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    except MigrationContractError as exc:
        message = str(exc)
        assert "不受支持的残缺结构" in message, message
        assert "不会用当前 schema.sql 静默补齐缺失整表" in message, message
    else:
        raise AssertionError("只有 OperatorMachine 的残缺旧库不应被静默补成当前结构")

    conn = get_connection(test_db)
    try:
        assert not _has_column(conn, "OperatorMachine", "skill_level"), "fail-fast 后不应补齐 skill_level"
        assert not _has_column(conn, "OperatorMachine", "is_primary"), "fail-fast 后不应补齐 is_primary"

        rows = conn.execute("SELECT operator_id, machine_id FROM OperatorMachine ORDER BY operator_id, machine_id").fetchall()
        assert len(rows) == 1, f"预期 1 条 OperatorMachine 记录，实际 {len(rows)}"

        r = rows[0]
        assert (r["operator_id"] or "").strip() == "OP001"
        assert (r["machine_id"] or "").strip() == "MC_A1"

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
