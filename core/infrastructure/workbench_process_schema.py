"""Template row identities only; installation never rewrites process facts."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .workbench_metadata_schema import (
    _canonical_sql,
    entity_key_sql,
    identity_triggers,
    workbench_metadata_contract_issues,
)

PROCESS_ENTITY_TABLES: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "template_operation": ("PartOperations", ("id",)),
    "template_external_group": ("ExternalGroups", ("group_id",)),
}
_ALTERNATE_COLUMNS = {"template_operation": ("part_no", "seq")}


def process_objects(*, legacy=False) -> Dict[str, str]:
    objects = {}
    for kind, (table, columns) in PROCESS_ENTITY_TABLES.items():
        objects.update(identity_triggers(
            kind, table, columns, alternate_columns=_ALTERNATE_COLUMNS.get(kind, ()), split_conflicts=not legacy,
        ))
    return objects


def optimize_process_identity_triggers(conn) -> None:
    """Upgrade only the exact known v22 DDL, without reallocating any identity."""
    if not conn.in_transaction:
        raise RuntimeError("Process identity trigger upgrade requires a caller transaction.")
    current, legacy = process_objects(), process_objects(legacy=True)
    actual = {row[0]: row[1] for row in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'")}
    for name, sql in current.items():
        if name not in actual or _canonical_sql(actual[name]) not in (_canonical_sql(sql), _canonical_sql(legacy[name])):
            raise RuntimeError("Cannot replace missing or unrecognized process identity trigger: " + name)
    for name, sql in current.items():
        if _canonical_sql(actual[name]) != _canonical_sql(sql):
            conn.execute('DROP TRIGGER "' + name + '"')
            conn.execute(sql)


def _source_contract_issues(conn) -> List[str]:
    issues = []
    for kind, (table, columns) in PROCESS_ENTITY_TABLES.items():
        info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        names = {row[1] for row in info}
        required = columns + _ALTERNATE_COLUMNS.get(kind, ())
        issues.extend("missing_workbench_process_source: " + table + "." + column
                      for column in required if column not in names)
        primary = tuple(row[1] for row in sorted(info, key=lambda row: row[5]) if row[5])
        if primary != columns:
            issues.append("bad_workbench_process_primary_key: " + table)
    return issues


def workbench_process_contract_issues(conn) -> List[str]:
    """Read-only structural check; missing identities are never allocated here."""
    actual = {row[0]: row[1] for row in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')"
    ).fetchall()}
    issues = _source_contract_issues(conn)
    for name, sql in process_objects().items():
        if name not in actual:
            issues.append("missing_workbench_process: " + name)
        elif _canonical_sql(actual[name] or "") != _canonical_sql(sql):
            issues.append("bad_workbench_process: " + name)
    return issues


def install_process(conn) -> None:
    """Install/backfill within the caller's transaction; reject damaged objects."""
    issues = workbench_metadata_contract_issues(conn) + [
        issue for issue in workbench_process_contract_issues(conn)
        if not issue.startswith("missing_workbench_process: ")
    ]
    if issues:
        raise RuntimeError("Cannot install workbench process identities: " + "; ".join(issues))
    for table, columns in PROCESS_ENTITY_TABLES.values():
        key = entity_key_sql(columns, "source")
        if conn.execute(f'SELECT 1 FROM "{table}" AS source WHERE {key} IS NULL LIMIT 1').fetchone():
            raise RuntimeError(f"{table} has a missing primary key; process identities were not installed.")
    for sql in process_objects().values():
        conn.execute(sql)
    for kind, (table, columns) in PROCESS_ENTITY_TABLES.items():
        key = entity_key_sql(columns, "source")
        alternate_columns = _ALTERNATE_COLUMNS.get(kind, ())
        alternate = entity_key_sql(alternate_columns, "source") if alternate_columns else "NULL"
        conn.execute(f"""INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, alternate_key)
            SELECT lower(hex(randomblob(24))), ?, {key}, {alternate} FROM "{table}" AS source
            WHERE NOT EXISTS (SELECT 1 FROM WorkbenchEntityRefs AS existing
                WHERE existing.kind = ? AND existing.entity_key = {key} AND existing.active = 1)""", (kind, kind))
