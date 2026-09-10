"""Persistent workbench identity and command metadata; no business data rewrites."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

RESOURCE_TABLES: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "part": ("Parts", ("part_no",)),
    "op_type": ("OpTypes", ("op_type_id",)),
    "machine": ("Machines", ("machine_id",)),
    "operator": ("Operators", ("operator_id",)),
    "supplier": ("Suppliers", ("supplier_id",)),
    "material": ("Materials", ("material_id",)),
    "calendar": ("WorkCalendar", ("date",)),
    "operator_calendar": ("OperatorCalendar", ("operator_id", "date")),
    "batch": ("Batches", ("batch_id",)),
    "resource_team": ("ResourceTeams", ("team_id",)),
}
_ALTERNATE_KEYS = {"op_type": "name", "resource_team": "name"}

_TABLES = {
    "WorkbenchEntityRefs": """CREATE TABLE IF NOT EXISTS WorkbenchEntityRefs (
        ref TEXT PRIMARY KEY NOT NULL CHECK(length(ref) = 48 AND ref NOT GLOB '*[^0-9a-f]*'),
        kind TEXT NOT NULL,
        entity_key TEXT NOT NULL,
        alternate_key TEXT,
        revision INTEGER NOT NULL DEFAULT 1 CHECK(typeof(revision) = 'integer' AND revision > 0),
        active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
        created_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )""",
    "WorkbenchCommandReceipts": """CREATE TABLE IF NOT EXISTS WorkbenchCommandReceipts (
        request_key TEXT PRIMARY KEY NOT NULL CHECK(length(request_key) BETWEEN 16 AND 128),
        receipt_ref TEXT NOT NULL UNIQUE CHECK(length(receipt_ref) = 32 AND receipt_ref NOT GLOB '*[^0-9a-f]*'),
        action TEXT NOT NULL,
        context_ref TEXT NOT NULL,
        input_hash TEXT NOT NULL CHECK(length(input_hash) = 64 AND input_hash NOT GLOB '*[^0-9a-f]*'),
        outcome_json TEXT NOT NULL,
        committed_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )""",
}
_INDEXES = {
    "idx_workbench_refs_active_key": "CREATE UNIQUE INDEX IF NOT EXISTS idx_workbench_refs_active_key ON WorkbenchEntityRefs(kind, entity_key) WHERE active = 1",
    "idx_workbench_refs_kind": "CREATE INDEX IF NOT EXISTS idx_workbench_refs_kind ON WorkbenchEntityRefs(kind, active)",
    "idx_workbench_refs_alternate": "CREATE INDEX IF NOT EXISTS idx_workbench_refs_alternate ON WorkbenchEntityRefs(kind, alternate_key) WHERE active = 1",
    "idx_workbench_batch_materials_material": "CREATE INDEX IF NOT EXISTS idx_workbench_batch_materials_material ON BatchMaterials(material_id)",
}


def entity_key_sql(columns: Tuple[str, ...], prefix: str) -> str:
    parts = [f'CAST({prefix}."{column}" AS TEXT)' for column in columns]
    if len(parts) == 1:
        return parts[0]
    return " || ':' || ".join(f"replace(replace({part}, '%', '%25'), ':', '%3A')" for part in parts)


def entity_key(*values: str) -> str:
    if not values or any(not isinstance(value, str) for value in values):
        raise ValueError("实体内部标识必须是字符串。")
    # SQLite length(TEXT) stops at NUL; delimiter escaping agrees across encodings.
    return values[0] if len(values) == 1 else ":".join(value.replace("%", "%25").replace(":", "%3A") for value in values)


def _alternate_key_sql(kind: str, prefix: str) -> str:
    column = _ALTERNATE_KEYS.get(kind)
    return f'CAST({prefix}."{column}" AS TEXT)' if column else "NULL"


def identity_triggers(kind: str, table: str, columns: Tuple[str, ...], alternate_column: str = "", *,
                      alternate_columns: Tuple[str, ...] = (), split_conflicts: bool = False) -> Dict[str, str]:
    if alternate_column and alternate_columns:
        raise ValueError("身份备用键不能同时指定单列和复合列。")
    new, old = entity_key_sql(columns, "NEW"), entity_key_sql(columns, "OLD")
    alternate = (entity_key_sql(alternate_columns, "NEW") if alternate_columns else
                 f'CAST(NEW."{alternate_column}" AS TEXT)' if alternate_column else _alternate_key_sql(kind, "NEW"))
    conflict = f"entity_key = {new}"
    if alternate_column or alternate_columns or kind in _ALTERNATE_KEYS:
        conflict += f" OR alternate_key = {alternate}"
    stem = "wb_ref_" + kind
    result = {
        stem + "_insert": f"""CREATE TRIGGER IF NOT EXISTS {stem}_insert AFTER INSERT ON "{table}" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = '{kind}' AND active = 1 AND ({conflict});
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), '{kind}', {new}, {alternate});
        END""",
        stem + "_update": f"""CREATE TRIGGER IF NOT EXISTS {stem}_update AFTER UPDATE ON "{table}" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = '{kind}' AND active = 1 AND entity_key != {old} AND ({conflict});
            UPDATE WorkbenchEntityRefs SET entity_key = {new}, alternate_key = {alternate}, revision = revision + 1
                WHERE kind = '{kind}' AND entity_key = {old} AND active = 1;
        END""",
        stem + "_delete": f"""CREATE TRIGGER IF NOT EXISTS {stem}_delete AFTER DELETE ON "{table}" BEGIN
            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1
                WHERE kind = '{kind}' AND entity_key = {old} AND active = 1;
        END""",
    }
    if split_conflicts and (alternate_column or alternate_columns or kind in _ALTERNATE_KEYS):
        # Separate indexed lookups avoid scanning the whole kind for each OR match.
        predicates = [f"entity_key = {new}", f"alternate_key = {alternate}"]
        where = f"kind = '{kind}' AND active = 1"
        def retire(extra):
            return "\n".join(
                "            UPDATE WorkbenchEntityRefs SET active = 0, revision = revision + 1\n"
                f"                WHERE {where}{extra} AND {predicate};" for predicate in predicates)
        result[stem + "_insert"] = f"""CREATE TRIGGER IF NOT EXISTS {stem}_insert AFTER INSERT ON "{table}" BEGIN
{retire('')}
            INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
                VALUES(lower(hex(randomblob(24))), '{kind}', {new}, {alternate});
        END"""
        result[stem + "_update"] = f"""CREATE TRIGGER IF NOT EXISTS {stem}_update AFTER UPDATE ON "{table}" BEGIN
{retire(' AND entity_key != ' + old)}
            UPDATE WorkbenchEntityRefs SET entity_key = {new}, alternate_key = {alternate}, revision = revision + 1
                WHERE kind = '{kind}' AND entity_key = {old} AND active = 1;
        END"""
    return result


def metadata_objects() -> Dict[str, str]:
    objects = dict(_TABLES)
    objects.update(_INDEXES)
    for kind, (table, columns) in RESOURCE_TABLES.items():
        objects.update(identity_triggers(kind, table, columns))
    return objects


def install_metadata(conn) -> None:
    for sql in metadata_objects().values():
        conn.execute(sql)
    for kind, (table, columns) in RESOURCE_TABLES.items():
        key = entity_key_sql(columns, "source")
        alternate = _alternate_key_sql(kind, "source")
        if conn.execute(f'SELECT 1 FROM "{table}" AS source WHERE {key} IS NULL LIMIT 1').fetchone():
            raise RuntimeError(f"{table} 存在缺失的业务标识，不能安全建立永久引用；未修正原数据。")
        conn.execute(f"""INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
            SELECT lower(hex(randomblob(24))), ?, {key}, {alternate} FROM "{table}" AS source
            WHERE NOT EXISTS (SELECT 1 FROM WorkbenchEntityRefs AS existing
                WHERE existing.kind = ? AND existing.entity_key = {key} AND existing.active = 1)""", (kind, kind))


def _canonical_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\bIF\s+NOT\s+EXISTS\b", "", sql, flags=re.I)).strip().rstrip(";")


def workbench_metadata_contract_issues(conn) -> List[str]:
    actual = {row[0]: row[1] for row in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')"
    ).fetchall()}
    issues = []
    for name, sql in metadata_objects().items():
        if name not in actual:
            issues.append("missing_workbench_metadata: " + name)
        elif _canonical_sql(actual[name] or "") != _canonical_sql(sql):
            issues.append("bad_workbench_metadata: " + name)
    return issues
