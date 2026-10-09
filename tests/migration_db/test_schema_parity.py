"""新建库与旧版本完整迁移所得结构一致。"""

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


def test_identical_schema_text_is_normalized_once_but_changed_ddl_is_not_reused(monkeypatch):
    from core.infrastructure import workbench_metadata_schema as schema

    original, calls = schema._strip_line_comments, []
    schema._normalized_sql.cache_clear()

    def strip(sql):
        calls.append(sql)
        return original(sql)

    monkeypatch.setattr(schema, "_strip_line_comments", strip)
    first = "CREATE TABLE sample (value TEXT DEFAULT '--keep') -- ignore\n;"
    changed = first.replace("'--keep'", "'--changed'")
    assert schema.canonical_sql(first) == schema.canonical_sql(first)
    assert schema.canonical_ddl_parts(first) == ["value TEXT DEFAULT '--keep'"]
    assert schema.canonical_sql(changed) != schema.canonical_sql(first)
    assert calls == [first, changed]


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
