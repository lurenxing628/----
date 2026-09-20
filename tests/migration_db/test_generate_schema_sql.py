"""合同测试：schema.sql 是生成物——与 v4 起点 + 迁移链的导出结果逐字节一致，
运行期结构契约按 schema.sql 声明的表列集合派生比对，不再维护手写 needed 清单。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.migration_state import current_schema_contract_issues
from core.infrastructure.schema_declaration import declared_columns, declared_tables
from tests._support.paths import REPO_ROOT
from tools import generate_schema_sql as generator

SCHEMA_PATH = Path(REPO_ROOT) / "schema.sql"


def _committed() -> str:
    with open(SCHEMA_PATH, encoding="utf-8", newline="") as handle:
        return handle.read()


def test_committed_schema_sql_is_exactly_the_migration_chain_export() -> None:
    """等价于 python -m tools.generate_schema_sql --check。"""
    generated = generator.generate_schema_text()
    assert generated == _committed(), "schema.sql 与迁移链导出不一致：请运行 python -m tools.generate_schema_sql --write 后提交"


def test_generated_schema_has_fixed_header_idempotent_ddl_and_no_bookkeeping_objects() -> None:
    text = _committed()
    assert text.startswith(generator.HEADER + "PRAGMA foreign_keys = ON;\nCREATE TABLE IF NOT EXISTS SchemaVersion")
    assert "INSERT OR IGNORE INTO SchemaVersion (id, version) VALUES (1, 0);\n" in text
    assert "sqlite_sequence" not in text and "sqlite_autoindex" not in text
    statements = [line for line in text.splitlines() if line.startswith("CREATE ")]
    assert statements and all(" IF NOT EXISTS " in line for line in statements)
    seeds = [line for line in text.splitlines() if line.startswith("INSERT INTO ")]
    assert [line.split("(")[0] for line in seeds] == [
        "INSERT INTO WorkbenchPlanIdentityClock", "INSERT INTO WorkbenchExecutionLedgerClock"], "新库种子行来自 DDL 模块，放在全部 DDL 之后"
    assert text.rstrip("\n").endswith(seeds[-1])
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(text)
        conn.executescript(text)  # IF NOT EXISTS：重复执行不报错
        assert conn.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()[0] == 0
    finally:
        conn.close()


def test_cli_check_and_write_modes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(generator, "generate_schema_text", lambda **_kwargs: "-- generated\nCREATE TABLE IF NOT EXISTS T (id);\n")
    target = tmp_path / "schema.sql"
    target.write_text("-- stale\n", encoding="utf-8")
    assert generator.main(["--check", "--output", str(target)]) == 1
    assert "不一致" in capsys.readouterr().err
    assert generator.main(["--write", "--output", str(target)]) == 0
    assert target.read_bytes() == b"-- generated\nCREATE TABLE IF NOT EXISTS T (id);\n"
    assert generator.main(["--check", "--output", str(target)]) == 0


def test_declared_structure_is_parsed_by_sqlite_not_regex() -> None:
    text = "PRAGMA foreign_keys = ON;\ncreate table if not exists \"Odd Name\" (id INTEGER PRIMARY KEY, note TEXT);\nCREATE TABLE SchemaVersion (id INTEGER, version INTEGER);\n"
    assert declared_tables(text) == ["Odd Name"]
    assert declared_columns(text) == {"Odd Name": ["id", "note"], "SchemaVersion": ["id", "version"]}


def test_contract_issues_derive_from_declared_core_tables(schema_conn) -> None:
    assert current_schema_contract_issues(schema_conn) == []
    schema_conn.execute("DROP TABLE ResourceTeams")
    assert "missing_table: ResourceTeams" in current_schema_contract_issues(schema_conn)
    if sqlite3.sqlite_version_info >= (3, 35, 0):
        schema_conn.execute("ALTER TABLE MachineDowntimes DROP COLUMN reason_detail")
        assert "missing_column: MachineDowntimes.reason_detail" in current_schema_contract_issues(schema_conn)


def test_subsystem_owned_tables_are_reported_by_their_own_contract_only(schema_conn) -> None:
    schema_conn.execute("DROP TABLE WorkbenchRunCandidateTasks")
    issues = current_schema_contract_issues(schema_conn)
    assert any("WorkbenchRunCandidateTasks" in item for item in issues)
    assert "missing_table: WorkbenchRunCandidateTasks" not in issues, "子系统表由自己的 DDL 契约核对，不重复报"


def test_explicit_schema_text_overrides_repository_schema(schema_conn) -> None:
    custom = _committed() + "CREATE TABLE IF NOT EXISTS ExtraCoreTable (id INTEGER PRIMARY KEY, label TEXT);\n"
    assert current_schema_contract_issues(schema_conn, schema_sql=custom) == ["missing_table: ExtraCoreTable"]
