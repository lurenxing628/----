"""合同测试：新库路径与迁移链路径的整库结构对账。

路径 A：空库 ← schema.sql（ensure_schema 的新库路径）。
路径 B：空库 ← tests/migration_db/fixtures/schema-v4.sql（冻结起点）← 逐版迁移到 CURRENT_SCHEMA_VERSION。
两条路径得到的库，按表、列（名/类型/NOT NULL/默认值/主键）、外键、索引（唯一性/列序/部分索引）、
CHECK 约束、触发器、视图逐项比较，任一差异即失败并逐项列出。列的物理顺序不比较：SQLite 的
ALTER TABLE ADD COLUMN 只能追加，Machines/Operators/ScheduleAdjustmentScenario 三张表在迁移链上的
列序天然与 schema.sql 不同，按列名访问不受影响。修法方向固定为“补迁移让 B 追上 A”，
不允许删 A 的对象来凑齐（见 docs/dev/roadmaps/foundation-boundary-governance §4.4）。
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.infrastructure.database import CURRENT_SCHEMA_VERSION, ensure_schema, get_connection
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"
ORIGIN_V4_PATH = Path(__file__).parent / "fixtures" / "schema-v4.sql"
ORIGIN_VERSION = 4

_WS_RE = re.compile(r"\s+")
_IF_NOT_EXISTS_RE = re.compile(r"\bIF\s+NOT\s+EXISTS\b", re.IGNORECASE)
_CHECK_RE = re.compile(r"\bCHECK\s*\(", re.IGNORECASE)


def _normalize_sql(sql: Any) -> str:
    text = str(sql or "")
    text = _IF_NOT_EXISTS_RE.sub("", text)
    text = text.replace('"', "").replace("`", "").replace("[", "").replace("]", "")
    text = _WS_RE.sub(" ", text).strip().rstrip(";").strip()
    return text


def _normalize_default(value: Any) -> str:
    if value is None:
        return "<none>"
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = "'" + text[1:-1] + "'"
    return text.upper() if text.upper() in ("CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME", "NULL") else text


def _extract_checks(create_sql: str) -> List[str]:
    """从 CREATE TABLE 文本里抽出所有 CHECK(...) 子句（按括号配平），规范化后排序。"""
    text = _normalize_sql(create_sql)
    checks: List[str] = []
    for match in _CHECK_RE.finditer(text):
        start = match.end()
        depth = 1
        index = start
        while index < len(text) and depth > 0:
            if text[index] == "(":
                depth += 1
            elif text[index] == ")":
                depth -= 1
            index += 1
        checks.append(_WS_RE.sub(" ", text[start:index - 1]).strip().upper())
    return sorted(checks)


def _user_tables(conn: sqlite3.Connection) -> List[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(row[0]) for row in rows]


def _table_facets(conn: sqlite3.Connection, table: str) -> Dict[str, Any]:
    quoted = '"' + table.replace('"', '""') + '"'
    columns = [
        (str(row[1]), str(row[2] or "").upper(), int(row[3]), _normalize_default(row[4]), int(row[5]))
        for row in conn.execute(f"PRAGMA table_info({quoted})").fetchall()
    ]
    foreign_keys = sorted(
        (str(row[2]), str(row[3]), str(row[4] or ""), str(row[5] or "").upper(), str(row[6] or "").upper())
        for row in conn.execute(f"PRAGMA foreign_key_list({quoted})").fetchall()
    )
    indexes: Dict[str, Tuple[Any, ...]] = {}
    for row in conn.execute(f"PRAGMA index_list({quoted})").fetchall():
        index_name, unique, origin, partial = str(row[1]), int(row[2]), str(row[3]), int(row[4])
        if origin == "pk":
            continue
        index_columns = tuple(str(col[2]) for col in conn.execute(f'PRAGMA index_info("{index_name}")').fetchall())
        if origin == "c":
            sql_row = conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (index_name,)).fetchone()
            key = index_name
            definition = _normalize_sql(sql_row[0] if sql_row else "")
        else:
            key = f"<auto-{origin}>:" + ",".join(index_columns)
            definition = ""
        indexes[key] = (unique, index_columns, partial, definition)
    create_row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return {
        "columns": columns,
        "foreign_keys": foreign_keys,
        "indexes": indexes,
        "checks": _extract_checks(str(create_row[0]) if create_row else ""),
    }


def _objects(conn: sqlite3.Connection, kind: str) -> Dict[str, str]:
    rows = conn.execute("SELECT name, sql FROM sqlite_master WHERE type=? ORDER BY name", (kind,)).fetchall()
    return {str(row[0]): _normalize_sql(row[1]) for row in rows}


def snapshot_structure(conn: sqlite3.Connection) -> Dict[str, Any]:
    return {
        "tables": {name: _table_facets(conn, name) for name in _user_tables(conn)},
        "triggers": _objects(conn, "trigger"),
        "views": _objects(conn, "view"),
    }


def diff_structures(fresh: Dict[str, Any], migrated: Dict[str, Any]) -> List[str]:
    diffs: List[str] = []
    fresh_tables, migrated_tables = fresh["tables"], migrated["tables"]
    for name in sorted(set(fresh_tables) - set(migrated_tables)):
        diffs.append(f"表 {name}：新库有、迁移链没有（缺迁移）")
    for name in sorted(set(migrated_tables) - set(fresh_tables)):
        diffs.append(f"表 {name}：迁移链有、新库没有（schema.sql 漏表）")
    for name in sorted(set(fresh_tables) & set(migrated_tables)):
        left, right = fresh_tables[name], migrated_tables[name]
        left_cols = {col[0]: col for col in left["columns"]}
        right_cols = {col[0]: col for col in right["columns"]}
        for col in sorted(set(left_cols) - set(right_cols)):
            diffs.append(f"表 {name} 列 {col}：新库有、迁移链没有")
        for col in sorted(set(right_cols) - set(left_cols)):
            diffs.append(f"表 {name} 列 {col}：迁移链有、新库没有")
        for col in sorted(set(left_cols) & set(right_cols)):
            if left_cols[col] != right_cols[col]:
                diffs.append(f"表 {name} 列 {col}：定义不同 新库={left_cols[col]} 迁移链={right_cols[col]}")
        if left["foreign_keys"] != right["foreign_keys"]:
            diffs.append(f"表 {name}：外键不同 新库={left['foreign_keys']} 迁移链={right['foreign_keys']}")
        for key in sorted(set(left["indexes"]) - set(right["indexes"])):
            diffs.append(f"表 {name} 索引 {key}：新库有、迁移链没有")
        for key in sorted(set(right["indexes"]) - set(left["indexes"])):
            diffs.append(f"表 {name} 索引 {key}：迁移链有、新库没有")
        for key in sorted(set(left["indexes"]) & set(right["indexes"])):
            if left["indexes"][key] != right["indexes"][key]:
                diffs.append(f"表 {name} 索引 {key}：定义不同 新库={left['indexes'][key]} 迁移链={right['indexes'][key]}")
        if left["checks"] != right["checks"]:
            diffs.append(f"表 {name}：CHECK 约束不同 新库={left['checks']} 迁移链={right['checks']}")
    for kind in ("triggers", "views"):
        left_objs, right_objs = fresh[kind], migrated[kind]
        for name in sorted(set(left_objs) - set(right_objs)):
            diffs.append(f"{kind[:-1]} {name}：新库有、迁移链没有")
        for name in sorted(set(right_objs) - set(left_objs)):
            diffs.append(f"{kind[:-1]} {name}：迁移链有、新库没有")
        for name in sorted(set(left_objs) & set(right_objs)):
            if left_objs[name] != right_objs[name]:
                diffs.append(f"{kind[:-1]} {name}：定义不同\n    新库={left_objs[name]}\n    迁移链={right_objs[name]}")
    return diffs


def build_fresh_database(tmp_path: Path) -> Path:
    db_path = tmp_path / "fresh.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "fresh_backups"))
    return db_path


def build_migrated_database(tmp_path: Path) -> Path:
    db_path = tmp_path / "migrated.db"
    conn = get_connection(str(db_path))
    try:
        conn.executescript(ORIGIN_V4_PATH.read_text(encoding="utf-8"))
        conn.executescript(
            f"DELETE FROM SchemaVersion; INSERT INTO SchemaVersion (id, version) VALUES (1, {ORIGIN_VERSION});"
        )
        conn.commit()
    finally:
        conn.close()
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "migrated_backups"))
    return db_path


def _version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()[0])


def test_fresh_schema_matches_v4_origin_migrated_to_current(tmp_path: Path) -> None:
    fresh_path = build_fresh_database(tmp_path)
    migrated_path = build_migrated_database(tmp_path)
    fresh_conn = get_connection(str(fresh_path))
    migrated_conn = get_connection(str(migrated_path))
    try:
        assert _version(fresh_conn) == CURRENT_SCHEMA_VERSION
        assert _version(migrated_conn) == CURRENT_SCHEMA_VERSION
        diffs = diff_structures(snapshot_structure(fresh_conn), snapshot_structure(migrated_conn))
    finally:
        fresh_conn.close()
        migrated_conn.close()
    assert not diffs, (
        f"schema.sql 新库与 v{ORIGIN_VERSION} 起点迁移到 v{CURRENT_SCHEMA_VERSION} 的库结构不一致，共 {len(diffs)} 项：\n"
        + "\n".join(f"  - {item}" for item in diffs)
    )


def test_diff_structures_reports_each_facet() -> None:
    left = {
        "tables": {
            "A": {"columns": [("id", "INTEGER", 1, "<none>", 1), ("x", "TEXT", 0, "'a'", 0)], "foreign_keys": [],
                  "indexes": {"idx_a": (0, ("x",), 0, "CREATE INDEX idx_a ON A(x)")}, "checks": ["X IN ('A')"]},
            "OnlyFresh": {"columns": [], "foreign_keys": [], "indexes": {}, "checks": []},
        },
        "triggers": {"trg": "CREATE TRIGGER trg ..."},
        "views": {},
    }
    right = {
        "tables": {
            "A": {"columns": [("id", "INTEGER", 1, "<none>", 1), ("x", "TEXT", 1, "'a'", 0)], "foreign_keys": [],
                  "indexes": {}, "checks": []},
            "OnlyMigrated": {"columns": [], "foreign_keys": [], "indexes": {}, "checks": []},
        },
        "triggers": {},
        "views": {},
    }
    diffs = diff_structures(left, right)
    assert any("OnlyFresh" in item and "缺迁移" in item for item in diffs)
    assert any("OnlyMigrated" in item and "漏表" in item for item in diffs)
    assert any("列 x：定义不同" in item for item in diffs)
    assert any("索引 idx_a：新库有" in item for item in diffs)
    assert any("CHECK 约束不同" in item for item in diffs)
    assert any("trigger trg：新库有" in item for item in diffs)
