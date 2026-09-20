"""对照资料存档解码：存档行按存档自身的列序解码，列序不同但定义相同的历史存档不能被静默错位。"""

import pytest

from core.infrastructure.workbench_execution_ledger_schema import execution_ledger_objects
from core.infrastructure.workbench_metadata_schema import canonical_ddl_parts
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.candidate_baseline import _report_revisions

NAME = "WorkbenchProductionReportRevisions"
KNOWN = execution_ledger_objects()[NAME]


def _rotated_ddl():
    parts = canonical_ddl_parts(KNOWN)
    columns = [part for part in parts if not part.split("(")[0].split(" ")[0].upper() in ("UNIQUE", "FOREIGN", "PRIMARY", "CHECK")]
    constraints = [part for part in parts if part not in columns]
    rotated = columns[3:] + columns[:3]
    return "CREATE TABLE " + NAME + "(" + ",".join(rotated + constraints) + ")", [part.split(" ", 1)[0] for part in rotated]


def _archive(ddl, rows):
    return {"schema": [["table", NAME, NAME, ddl]], "tables": {NAME: rows}}


def test_rows_decode_by_the_archived_column_order():
    ddl, order = _rotated_ddl()
    assert order[0] != "revision_ref", "夹具必须真的把列序转了"
    values = {"revision_ref": "r" * 48, "report_ref": "p" * 48, "sequence": 1, "previous_revision_ref": None,
              "action": "create", "values_json": "{}", "reason": "why", "local_operator": "op",
              "declared_operator": "op", "recorded_at": "2026-09-20T08:00:00", "request_key": "req-1"}
    decoded = _report_revisions(_archive(ddl, [[values[column] for column in order]]))
    assert decoded == [values]


def test_definition_drift_and_row_width_drift_are_rejected():
    ddl, order = _rotated_ddl()
    with pytest.raises(WorkbenchCommandRejected) as exc_info:
        _report_revisions(_archive(ddl.replace("reason TEXT NOT NULL", "reason TEXT"), [[None] * len(order)]))
    assert exc_info.value.code == "candidate_baseline_invalid"
    with pytest.raises(WorkbenchCommandRejected):
        _report_revisions(_archive(ddl, [[None] * (len(order) - 1)]))
