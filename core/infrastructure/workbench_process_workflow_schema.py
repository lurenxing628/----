"""Explicit process confirmations; installation never infers business facts."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .schema_structure import SchemaStructure, schema_objects
from .workbench_metadata_schema import schema_contract_matches, workbench_metadata_contract_issues
from .workbench_process_schema import workbench_process_contract_issues
from .workbench_resource_schema import workbench_resource_contract_issues

WORKFLOW_TABLES = ("WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations")


def _confirmation_columns(prefix: str, *, optional: bool, legacy: bool) -> Tuple[str, str]:
    signature, stamp, person = (prefix + name for name in ("signature", "confirmed_at", "confirmed_by"))
    valid = (f"typeof({signature}) = 'text' AND length({signature}) = 64 "
             f"AND {signature} NOT GLOB '*[^0-9a-f]*' AND typeof({stamp}) = 'text' AND length({stamp}) > 0")
    declaration = f"{signature} TEXT, {stamp} TEXT, {person} TEXT"
    missing = f"{signature} IS NULL AND {stamp} IS NULL AND {person} IS NULL"
    if not legacy:
        content = prefix + "content_json"
        valid = (f"((typeof({content}) = 'text' AND length({content}) > 0) OR "
                 f"(typeof({signature}) = 'text' AND length({signature}) = 64 "
                 f"AND {signature} NOT GLOB '*[^0-9a-f]*')) "
                 f"AND typeof({stamp}) = 'text' AND length({stamp}) > 0")
        declaration += f", {content} TEXT"
        missing += f" AND {content} IS NULL"
    if optional:
        valid = f"({missing}) OR ({valid})"
    return (declaration,
            f"CHECK({valid}), CHECK({person} IS NULL OR (typeof({person}) = 'text' AND length(trim({person})) > 0))")


def workflow_objects(*, legacy: bool = False) -> Dict[str, str]:
    columns, checks = [], []
    for stage in ("route", "source", "hours"):
        declaration, constraints = _confirmation_columns(stage + "_", optional=True, legacy=legacy)
        columns.append(declaration)
        checks.append(constraints)
    declaration, constraints = _confirmation_columns("", optional=False, legacy=legacy)
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


def workbench_process_workflow_contract_issues(conn, *, structure=None, allow_legacy=True) -> List[str]:
    """Read-only exact contract check, including legal but incorrect DDL."""
    actual = schema_objects(conn, structure=structure)
    legacy = workflow_objects(legacy=True)
    return [("missing_workbench_process_workflow: " if name not in actual else "bad_workbench_process_workflow: ") + name
            for name, sql in workflow_objects().items()
            if name not in actual or not schema_contract_matches(
                conn, actual[name] or "", sql, legacy[name], allow_legacy=allow_legacy)]


def install_process_workflow(conn) -> None:
    """Install empty metadata tables inside the migration owner's transaction."""
    if not conn.in_transaction:
        raise RuntimeError("Process workflow installation requires a caller transaction.")
    structure = SchemaStructure(conn)
    objects = workflow_objects()
    workflow_issues = workbench_process_workflow_contract_issues(conn, structure=structure)
    missing = [issue for issue in workflow_issues if issue.startswith("missing_workbench_process_workflow: ")]
    if missing and len(missing) != len(objects):
        raise RuntimeError("Cannot install partial process workflow storage: " + "; ".join(workflow_issues))
    issues = (workbench_metadata_contract_issues(conn, structure=structure) + workbench_resource_contract_issues(conn, structure=structure)
              + workbench_process_contract_issues(conn, structure=structure) + [
                  issue for issue in workflow_issues
                  if not issue.startswith("missing_workbench_process_workflow: ")])
    if issues:
        raise RuntimeError("Cannot install process workflow: " + "; ".join(issues))
    for sql in objects.values():
        conn.execute(sql)
