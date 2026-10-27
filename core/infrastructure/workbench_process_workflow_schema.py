"""Explicit process confirmations schema and contract validation."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .schema_structure import schema_objects
from .workbench_metadata_schema import canonical_sql

WORKFLOW_TABLES = ("WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations")


def _confirmation_columns(prefix: str, *, optional: bool) -> Tuple[str, str]:
    stamp, person, content = (prefix + name for name in ("confirmed_at", "confirmed_by", "content_json"))
    declaration = f"{stamp} TEXT, {person} TEXT, {content} TEXT"
    missing = f"{stamp} IS NULL AND {person} IS NULL AND {content} IS NULL"
    valid = f"typeof({content}) = 'text' AND length({content}) > 0 AND typeof({stamp}) = 'text' AND length({stamp}) > 0"
    if optional:
        valid = f"({missing}) OR ({valid})"
    return (declaration,
            f"CHECK({valid}), CHECK({person} IS NULL OR (typeof({person}) = 'text' AND length(trim({person})) > 0))")


def workflow_objects() -> Dict[str, str]:
    columns, checks = [], []
    for stage in ("route", "source", "hours"):
        declaration, constraints = _confirmation_columns(stage + "_", optional=True)
        columns.append(declaration)
        checks.append(constraints)
    declaration, constraints = _confirmation_columns("", optional=False)
    return {
        WORKFLOW_TABLES[0]: """CREATE TABLE IF NOT EXISTS WorkbenchProcessWorkflow (
        part_ref TEXT PRIMARY KEY NOT NULL REFERENCES WorkbenchEntityRefs(ref),
        """ + ",\n        ".join(columns + checks) + "\n    )",
        WORKFLOW_TABLES[1]: """CREATE TABLE IF NOT EXISTS WorkbenchProcessOperationConfirmations (
        part_ref TEXT NOT NULL REFERENCES WorkbenchProcessWorkflow(part_ref),
        operation_ref TEXT NOT NULL REFERENCES WorkbenchEntityRefs(ref),
        stage TEXT NOT NULL CHECK(stage IN ('source', 'hours')),
        """ + declaration + ",\n        " + constraints + """,
        PRIMARY KEY(part_ref, operation_ref, stage)
    )""",
        "idx_wb_process_confirmation_operation": "CREATE INDEX IF NOT EXISTS idx_wb_process_confirmation_operation ON WorkbenchProcessOperationConfirmations(operation_ref)",
    }


def workbench_process_workflow_contract_issues(conn, *, structure=None) -> List[str]:
    """Read-only exact contract check, including legal but incorrect DDL."""
    actual = schema_objects(conn, structure=structure)
    return [("missing_workbench_process_workflow: " if name not in actual else "bad_workbench_process_workflow: ") + name
            for name, sql in workflow_objects().items()
            if name not in actual or canonical_sql(actual[name]) != canonical_sql(sql)]
