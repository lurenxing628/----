"""schema.sql 生成器：手写源只有 DDL 模块与迁移链，schema.sql 是它们的导出物。

做法：把冻结的 tests/migration_db/fixtures/schema-v4.sql 装进临时库，写入 SchemaVersion=4，
走生产的 ensure_schema 迁移到 CURRENT_SCHEMA_VERSION，再按 sqlite_master 的创建顺序导出全部 DDL。
输出 = 固定头（生成说明、PRAGMA foreign_keys、SchemaVersion 表与版本 0 初始行）+ 逐条 CREATE ... IF NOT EXISTS
       + 末尾的新库种子行（各 DDL 模块声明的 *_initialization_sql，目前是两张时钟表的单例行）。

用法：
    python -m tools.generate_schema_sql --check    # 与已提交的 schema.sql 逐字节比较，不等退出码 1
    python -m tools.generate_schema_sql --write    # 重新生成并覆盖 schema.sql
"""

from __future__ import annotations

import argparse
import difflib
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection  # noqa: E402
from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_initialization_sql  # noqa: E402
from core.infrastructure.workbench_plan_identity_schema import plan_identity_initialization_sql  # noqa: E402

DEFAULT_ORIGIN = REPO_ROOT / "tests" / "migration_db" / "fixtures" / "schema-v4.sql"
DEFAULT_OUTPUT = REPO_ROOT / "schema.sql"
ORIGIN_VERSION = 4
HEADER = (
    "-- 本文件由 python -m tools.generate_schema_sql --write 生成：手写源是 core/infrastructure 的 DDL 模块与迁移链，请勿手改。\n"
    "-- 校验：python -m tools.generate_schema_sql --check；门禁合同见 tests/migration_db/test_generate_schema_sql.py。\n"
)
# 新库种子行：由拥有该表的 DDL 模块声明，放在全部 DDL 之后执行（引用的表此时都已存在，时钟表上没有触发器）。
SEED_STATEMENT_SOURCES = (plan_identity_initialization_sql, execution_ledger_initialization_sql)
_IF_NOT_EXISTS_PREFIXES = (
    ("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS "),
    ("CREATE UNIQUE INDEX ", "CREATE UNIQUE INDEX IF NOT EXISTS "),
    ("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS "),
    ("CREATE TRIGGER ", "CREATE TRIGGER IF NOT EXISTS "),
    ("CREATE VIEW ", "CREATE VIEW IF NOT EXISTS "),
)


def build_migrated_database(work_dir: Path, *, origin: Path = DEFAULT_ORIGIN, schema_path: Optional[Path] = None) -> Path:
    """v4 起点 + 生产迁移链 → CURRENT_SCHEMA_VERSION 的库文件。schema_path 只用于迁移器的缺表提示文案。"""
    db_path = work_dir / "generated.db"
    conn = get_connection(str(db_path))
    try:
        conn.executescript(origin.read_text(encoding="utf-8"))
        conn.executescript(
            f"DELETE FROM SchemaVersion; INSERT INTO SchemaVersion (id, version) VALUES (1, {ORIGIN_VERSION});"
        )
        conn.commit()
    finally:
        conn.close()
    hint = schema_path if schema_path is not None and schema_path.exists() else origin
    ensure_schema(str(db_path), schema_path=str(hint), backup_dir=str(work_dir / "backups"))
    return db_path


def _with_if_not_exists(sql: str) -> str:
    text = sql.strip()
    for prefix, replacement in _IF_NOT_EXISTS_PREFIXES:
        if text[: len(prefix)].upper() == prefix:
            return replacement + text[len(prefix):]
    raise ValueError("无法识别的 DDL 语句：" + text[:80])


def render_schema_sql(db_path: Path) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY rowid").fetchall()
        version = int(conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()[0])
    finally:
        conn.close()
    if version != CURRENT_SCHEMA_VERSION:
        raise RuntimeError(f"迁移链停在 v{version}，与 CURRENT_SCHEMA_VERSION={CURRENT_SCHEMA_VERSION} 不一致，拒绝生成")
    version_ddl = [sql for _kind, name, sql in rows if name == "SchemaVersion"]
    if len(version_ddl) != 1:
        raise RuntimeError("迁移后的库缺少唯一的 SchemaVersion 表定义")
    parts: List[str] = [HEADER, "PRAGMA foreign_keys = ON;\n", _with_if_not_exists(version_ddl[0]) + ";\n",
                        "INSERT OR IGNORE INTO SchemaVersion (id, version) VALUES (1, 0);\n"]
    for _kind, name, sql in rows:
        if name == "SchemaVersion" or str(name).startswith("sqlite_"):
            continue
        parts.append(_with_if_not_exists(sql) + ";\n")
    for source in SEED_STATEMENT_SOURCES:
        parts.append(source().strip() + "\n")
    return "".join(parts)


def generate_schema_text(*, origin: Path = DEFAULT_ORIGIN, schema_path: Optional[Path] = DEFAULT_OUTPUT) -> str:
    with tempfile.TemporaryDirectory(prefix="aps-schema-gen-") as tmp:
        return render_schema_sql(build_migrated_database(Path(tmp), origin=origin, schema_path=schema_path))


def _read(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="从 v4 起点 + 迁移链生成 schema.sql，或校验已提交文件是否与生成结果一致")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="逐字节比较生成结果与 --output 文件，不等退出码 1")
    mode.add_argument("--write", action="store_true", help="生成并覆盖 --output 文件")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="schema.sql 路径（默认仓库根）")
    parser.add_argument("--origin", default=str(DEFAULT_ORIGIN), help="冻结起点 schema-v4.sql 路径")
    args = parser.parse_args(list(argv) if argv is not None else None)
    output, origin = Path(args.output), Path(args.origin)
    generated = generate_schema_text(origin=origin, schema_path=output)
    if args.write:
        with open(output, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(generated)
        print(f"[generate-schema-sql] 已写入 {output}（{generated.count(chr(10))} 行，v{CURRENT_SCHEMA_VERSION}）")
        return 0
    committed = _read(output)
    if committed == generated:
        print(f"[generate-schema-sql] {output} 与迁移链导出结果一致（v{CURRENT_SCHEMA_VERSION}）")
        return 0
    diff = list(difflib.unified_diff((committed or "").splitlines(), generated.splitlines(),
                                     fromfile=str(output), tofile="generated", lineterm="", n=2))
    print(f"[generate-schema-sql] {output} 与迁移链导出结果不一致；请运行 --write 后提交。差异（前 60 行）：", file=sys.stderr)
    for line in diff[:60]:
        print("  " + line, file=sys.stderr)
    if len(diff) > 60:
        print(f"  ... 其余 {len(diff) - 60} 行略", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
