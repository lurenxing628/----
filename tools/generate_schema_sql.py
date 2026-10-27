"""schema.sql 生成器：手写源只有 core/infrastructure 的 DDL 模块，schema.sql 是它们的导出物。

做法：在临时库中创建 SchemaVersion 表，依次执行 core_objects() 与各子系统 *_schema.py 的 DDL，
写入新库种子行并将 SchemaVersion 设为 CURRENT_SCHEMA_VERSION，通过 ensure_current_schema_contract
自检后，按 sqlite_master 的创建顺序导出全部 DDL。

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
from typing import Callable, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.infrastructure.batch_external_context_schema import objects as batch_external_context_objects  # noqa: E402
from core.infrastructure.calendar_periods_schema import objects as calendar_periods_objects  # noqa: E402
from core.infrastructure.core_schema import core_objects  # noqa: E402
from core.infrastructure.database import CURRENT_SCHEMA_VERSION, get_connection  # noqa: E402
from core.infrastructure.efficiency_indexes_schema import ADDED as efficiency_indexes  # noqa: E402
from core.infrastructure.machine_capabilities_schema import objects as machine_capabilities_objects  # noqa: E402
from core.infrastructure.material_stages_schema import objects as material_stages_objects  # noqa: E402
from core.infrastructure.migration_state import ensure_current_schema_contract  # noqa: E402
from core.infrastructure.single_pass_indexes_schema import ADDED as single_pass_indexes  # noqa: E402
from core.infrastructure.workbench_calibration_adoption_schema import (  # noqa: E402
    objects as calibration_adoption_objects,
)
from core.infrastructure.workbench_dashboard_external_schema import (  # noqa: E402
    workbench_dashboard_external_objects,
)
from core.infrastructure.workbench_dashboard_schema import workbench_dashboard_objects  # noqa: E402
from core.infrastructure.workbench_execution_ledger_schema import (  # noqa: E402
    execution_ledger_initialization_sql,
    execution_ledger_objects,
)
from core.infrastructure.workbench_execution_void_schema import execution_void_objects  # noqa: E402
from core.infrastructure.workbench_lineage_lookup_schema import lineage_lookup_objects  # noqa: E402
from core.infrastructure.workbench_metadata_schema import metadata_objects  # noqa: E402
from core.infrastructure.workbench_outsourcing_schema import workbench_outsourcing_objects  # noqa: E402
from core.infrastructure.workbench_outsourcing_source_schema import (  # noqa: E402
    workbench_outsourcing_source_objects,
)
from core.infrastructure.workbench_plan_identity_schema import (  # noqa: E402
    plan_identity_initialization_sql,
    plan_identity_objects,
)
from core.infrastructure.workbench_plan_identity_write_guard import (  # noqa: E402
    plan_identity_write_guard_objects,
)
from core.infrastructure.workbench_process_schema import process_objects  # noqa: E402
from core.infrastructure.workbench_process_workflow_schema import workflow_objects  # noqa: E402
from core.infrastructure.workbench_resource_schema import resource_objects  # noqa: E402
from core.infrastructure.workbench_run_read_model_schema import objects as run_read_model_objects  # noqa: E402
from core.infrastructure.workbench_run_schema import workbench_run_objects  # noqa: E402
from core.infrastructure.workbench_template_lineage_schema import template_lineage_objects  # noqa: E402
from core.infrastructure.workbench_trial_schema import workbench_trial_objects  # noqa: E402

DEFAULT_OUTPUT = REPO_ROOT / "schema.sql"
HEADER = (
    "-- 本文件由 python -m tools.generate_schema_sql --write 生成：手写源是 core/infrastructure 的 DDL 模块，请勿手改。\n"
    "-- 校验：python -m tools.generate_schema_sql --check。\n"
)
SCHEMA_VERSION_DDL = """CREATE TABLE SchemaVersion (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    version     INTEGER NOT NULL,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
)"""
DDL_SOURCES: Tuple[Callable[[], Dict[str, str]], ...] = (
    core_objects,
    metadata_objects,
    resource_objects,
    process_objects,
    workflow_objects,
    plan_identity_objects,
    plan_identity_write_guard_objects,
    execution_ledger_objects,
    execution_void_objects,
    workbench_run_objects,
    run_read_model_objects,
    template_lineage_objects,
    lineage_lookup_objects,
    workbench_trial_objects,
    calibration_adoption_objects,
    workbench_dashboard_objects,
    workbench_outsourcing_objects,
    workbench_dashboard_external_objects,
    workbench_outsourcing_source_objects,
    batch_external_context_objects,
    calendar_periods_objects,
    machine_capabilities_objects,
    material_stages_objects,
    lambda: single_pass_indexes,
    lambda: efficiency_indexes,
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


def _with_if_not_exists(sql: str) -> str:
    text = sql.strip()
    for prefix, replacement in _IF_NOT_EXISTS_PREFIXES:
        if text[: len(prefix)].upper() == prefix:
            return replacement + text[len(prefix):]
    raise ValueError("无法识别的 DDL 语句：" + text[:80])


def build_baseline_database(work_dir: Path) -> Path:
    """直接由 DDL 模块构建 CURRENT_SCHEMA_VERSION 基线库。"""
    db_path = work_dir / "generated.db"
    conn = get_connection(str(db_path))
    try:
        conn.execute(SCHEMA_VERSION_DDL)
        conn.execute("INSERT INTO SchemaVersion (id, version) VALUES (1, ?)", (CURRENT_SCHEMA_VERSION,))
        for source in DDL_SOURCES:
            for sql in source().values():
                conn.execute(sql)
        for seed in SEED_STATEMENT_SOURCES:
            conn.execute(seed())
        conn.commit()
    finally:
        conn.close()
    return db_path


def render_schema_sql(db_path: Path) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY rowid").fetchall()
        version = int(conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()[0])
    finally:
        conn.close()
    if version != CURRENT_SCHEMA_VERSION:
        raise RuntimeError(f"基线库版本 v{version} 与 CURRENT_SCHEMA_VERSION={CURRENT_SCHEMA_VERSION} 不一致，拒绝生成")
    version_ddl = [sql for _kind, name, sql in rows if name == "SchemaVersion"]
    if len(version_ddl) != 1:
        raise RuntimeError("基线库缺少唯一的 SchemaVersion 表定义")
    parts: List[str] = [HEADER, "PRAGMA foreign_keys = ON;\n", _with_if_not_exists(version_ddl[0]) + ";\n",
                        "INSERT OR IGNORE INTO SchemaVersion (id, version) VALUES (1, 0);\n"]
    for _kind, name, sql in rows:
        if name == "SchemaVersion" or str(name).startswith("sqlite_"):
            continue
        parts.append(_with_if_not_exists(sql) + ";\n")
    for source in SEED_STATEMENT_SOURCES:
        parts.append(source().strip() + "\n")
    rendered = "".join(parts)
    check_conn = get_connection(str(db_path))
    try:
        ensure_current_schema_contract(
            check_conn, schema_version=CURRENT_SCHEMA_VERSION, schema_sql=rendered, full_data=True
        )
    finally:
        check_conn.close()
    return rendered


def generate_schema_text() -> str:
    with tempfile.TemporaryDirectory(prefix="aps-schema-gen-") as tmp:
        return render_schema_sql(build_baseline_database(Path(tmp)))


def _read(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    with open(path, encoding="utf-8", newline="") as handle:
        return handle.read()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="从 DDL 模块生成 schema.sql，或校验已提交文件是否与生成结果一致")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="逐字节比较生成结果与 --output 文件，不等退出码 1")
    mode.add_argument("--write", action="store_true", help="生成并覆盖 --output 文件")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="schema.sql 路径（默认仓库根）")
    args = parser.parse_args(list(argv) if argv is not None else None)
    output = Path(args.output)
    generated = generate_schema_text()
    if args.write:
        with open(output, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(generated)
        print(f"[generate-schema-sql] 已写入 {output}（{generated.count(chr(10))} 行，v{CURRENT_SCHEMA_VERSION}）")
        return 0
    committed = _read(output)
    if committed == generated:
        print(f"[generate-schema-sql] {output} 与 DDL 模块导出结果一致（v{CURRENT_SCHEMA_VERSION}）")
        return 0
    diff = list(difflib.unified_diff((committed or "").splitlines(), generated.splitlines(),
                                     fromfile=str(output), tofile="generated", lineterm="", n=2))
    print(f"[generate-schema-sql] {output} 与 DDL 模块导出结果不一致；请运行 --write 后提交。差异（前 60 行）：", file=sys.stderr)
    for line in diff[:60]:
        print("  " + line, file=sys.stderr)
    if len(diff) > 60:
        print(f"  ... 其余 {len(diff) - 60} 行略", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
