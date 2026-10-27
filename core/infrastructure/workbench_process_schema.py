"""Template row identities only."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .schema_structure import SchemaStructure
from .workbench_metadata_schema import canonical_sql, identity_triggers

PROCESS_ENTITY_TABLES: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "template_operation": ("PartOperations", ("id",)),
    "template_external_group": ("ExternalGroups", ("group_id",)),
}
_ALTERNATE_COLUMNS = {"template_operation": ("part_no", "seq")}


def process_objects() -> Dict[str, str]:
    objects = {}
    for kind, (table, columns) in PROCESS_ENTITY_TABLES.items():
        objects.update(identity_triggers(
            kind, table, columns, alternate_columns=_ALTERNATE_COLUMNS.get(kind, ()), split_conflicts=True,
        ))
    return objects


def _source_contract_issues(*, structure: SchemaStructure) -> List[str]:
    issues = []
    for kind, (table, columns) in PROCESS_ENTITY_TABLES.items():
        info = structure.table_info(table)
        names = {row[1] for row in info}
        required = columns + _ALTERNATE_COLUMNS.get(kind, ())
        issues.extend("missing_workbench_process_source: " + table + "." + column
                      for column in required if column not in names)
        primary = tuple(row[1] for row in sorted(info, key=lambda row: row[5]) if row[5])
        if primary != columns:
            issues.append("bad_workbench_process_primary_key: " + table)
    return issues


def workbench_process_contract_issues(conn, *, structure=None) -> List[str]:
    """Read-only structural check; missing identities are never allocated here."""
    structure = structure if structure is not None else SchemaStructure(conn)
    actual = structure.sql
    issues = _source_contract_issues(structure=structure)
    for name, sql in process_objects().items():
        if name not in actual:
            issues.append("missing_workbench_process: " + name)
        elif canonical_sql(actual[name]) != canonical_sql(sql):
            issues.append("bad_workbench_process: " + name)
    return issues
