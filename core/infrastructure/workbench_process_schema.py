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
_UPDATE_COLUMNS: Dict[str, Tuple[str, ...]] = {
    "template_operation": (
        "id", "part_no", "seq", "op_type_id", "op_type_name", "source", "supplier_id",
        "ext_days", "ext_group_id", "setup_hours", "unit_hours", "status", "created_at",
    ),
}
_INDEXES = {
    "idx_part_operations_ext_group": "CREATE INDEX IF NOT EXISTS idx_part_operations_ext_group ON PartOperations(ext_group_id)",
    "idx_part_operations_part_status": "CREATE INDEX IF NOT EXISTS idx_part_operations_part_status ON PartOperations(part_no, status)",
}


def process_objects() -> Dict[str, str]:
    objects = dict(_INDEXES)
    for kind, (table, columns) in PROCESS_ENTITY_TABLES.items():
        objects.update(identity_triggers(
            kind, table, columns,
            alternate_columns=_ALTERNATE_COLUMNS.get(kind, ()),
            update_columns=_UPDATE_COLUMNS.get(kind, ()),
        ))
    return objects


def workbench_process_contract_issues(structure: SchemaStructure) -> List[str]:
    """Read-only structural check; missing identities are never allocated here."""
    actual = structure.sql
    issues = []
    for name, sql in process_objects().items():
        if name not in actual:
            issues.append("missing_workbench_process: " + name)
        elif canonical_sql(actual[name]) != canonical_sql(sql):
            issues.append("bad_workbench_process: " + name)
    return issues
