"""Two-connection adoption races, rollback and no visible half-applied imports."""


import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandUncertain
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from tests.workbench.process_commands_support import hours_input, run_stage
from tests.workbench.process_quota_protection_support import (
    file_apply,
    file_preview,
    snapshot,
)
from tests.workbench.process_quota_protection_support import locked_quota_case as _locked  # noqa: F401
from tests.workbench.process_quota_protection_support import quota_case as _quota  # noqa: F401
from tests.workbench.template_lineage_support import ledger_fixture as _ledger  # noqa: F401
from tests.workbench.template_lineage_support import lineage_case as _lineage  # noqa: F401


def test_savepoint_failure_does_not_lose_outer_work_and_outer_rollback_keeps_locks(locked_quota_case):
    case = locked_quota_case
    rows, _ = file_preview(case.conn, {"sequence": 1, "unit_hours": 99}, {"sequence": 2, "unit_hours": 8})
    before = snapshot(case.conn)
    with pytest.raises(RuntimeError, match="receipt failed"):
        with TransactionManager(case.conn).transaction(begin_immediate=True):
            result, _ = file_apply(case.conn, rows)
            assert [row["result"] for row in result] == ["skipped", "committed"]
            raise RuntimeError("receipt failed")
    assert snapshot(case.conn) == before


def test_stage_receipt_failure_rolls_back_hours_and_confirmation(locked_quota_case):
    case = locked_quota_case
    payload = hours_input(case.conn, "P1")
    payload["operations"][0]["setup_hours"] = 9
    payload["operations"][1]["unit_hours"] = 8
    case.conn.execute("""CREATE TEMP TRIGGER cw_fail_receipt BEFORE INSERT ON WorkbenchCommandReceipts
        BEGIN SELECT RAISE(ABORT,'CW receipt failed'); END""")
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        run_stage(case.conn, "hours_confirm", payload,
                  identity=WorkbenchProcessQueryService(case.conn).resolve(case.ref("part", "P1")))
    assert snapshot(case.conn) == before


