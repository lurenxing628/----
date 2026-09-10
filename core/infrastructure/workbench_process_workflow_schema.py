"""Explicit process confirmations; installation never infers business facts."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .workbench_metadata_schema import _canonical_sql, workbench_metadata_contract_issues
from .workbench_process_schema import workbench_process_contract_issues
from .workbench_resource_schema import workbench_resource_contract_issues

WORKFLOW_TABLES = ("WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations")


def _confirmation_columns(prefix: str, *, optional: bool) -> Tuple[str, str]:
    signature, stamp, person = (prefix + name for name in ("signature", "confirmed_at", "confirmed_by"))
    valid = (f"typeof({signature}) = 'text' AND length({signature}) = 64 "
             f"AND {signature} NOT GLOB '*[^0-9a-f]*' AND typeof({stamp}) = 'text' AND length({stamp}) > 0")
    if optional:
        valid = f"({signature} IS NULL AND {stamp} IS NULL AND {person} IS NULL) OR ({valid})"
    return (f"{signature} TEXT, {stamp} TEXT, {person} TEXT",
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


def workbench_process_workflow_contract_issues(conn) -> List[str]:
    """Read-only exact contract check, including legal but incorrect DDL."""
    actual = {row[0]: row[1] for row in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')"
    )}
    return [("missing_workbench_process_workflow: " if name not in actual else "bad_workbench_process_workflow: ") + name
            for name, sql in workflow_objects().items()
            if name not in actual or _canonical_sql(actual[name] or "") != _canonical_sql(sql)]


def install_process_workflow(conn) -> None:
    """Install empty metadata tables inside the migration owner's transaction."""
    if not conn.in_transaction:
        raise RuntimeError("Process workflow installation requires a caller transaction.")
    workflow_issues = workbench_process_workflow_contract_issues(conn)
    missing = [issue for issue in workflow_issues if issue.startswith("missing_workbench_process_workflow: ")]
    if missing and len(missing) != len(workflow_objects()):
        raise RuntimeError("Cannot install partial process workflow storage: " + "; ".join(workflow_issues))
    issues = (workbench_metadata_contract_issues(conn) + workbench_resource_contract_issues(conn)
              + workbench_process_contract_issues(conn) + [
                  issue for issue in workflow_issues
                  if not issue.startswith("missing_workbench_process_workflow: ")])
    if issues:
        raise RuntimeError("Cannot install process workflow: " + "; ".join(issues))
    for sql in workflow_objects().values():
        conn.execute(sql)
