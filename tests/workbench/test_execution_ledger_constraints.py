"""Corrections must not silently revoke successor or adopted execution constraints."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.execution_ledger_support import END, all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture


def test_reopen_without_downstream_is_explicit_and_historical(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    row = case.command("create", task, case.values(10))["data"]["rows"][0]
    case.command("correct", row["report_ref"], {"completed_quantity": 5, "original_revision_ref": row["revision_ref"], "reason": "Counter overcount"})
    projection = case.ledger.get_task(task)
    assert projection.execution_state == "partial" and projection.confirmed_finish is None
    assert projection.reports[0].correction_history[0]["after"]["completed_quantity"] == 10


@pytest.mark.parametrize("with_actual", [False, True])
def test_reopen_refuses_downstream_adopted_or_produced(ledger_case, with_actual):
    case = ledger_case
    successor = case.op("OP2", seq=2)
    case.plan(2, [case.op_id, successor], start=END, end="2026-09-09T12:00:00")
    case.install()
    task = case.task(2, case.op_id)
    row = case.command("create", task, case.values(10))["data"]["rows"][0]
    if with_actual:
        case.command("create", case.task(2, successor), case.values(1, actual_start=END, actual_end="2026-09-09T12:00:00"))
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("correct", row["report_ref"], {"completed_quantity": 5, "original_revision_ref": row["revision_ref"], "reason": "Counter correction"})
    assert any(item["code"] == "downstream_requires_completion" for item in error.value.conflicts)
    assert all_rows(case.conn) == before


def test_finish_delay_conflict_and_reason_only_remains_allowed(ledger_case):
    case = ledger_case
    successor = case.op("OP2", seq=2)
    case.plan(2, [case.op_id, successor], start=END, end="2026-09-09T12:00:00")
    case.install()
    task = case.task(2, case.op_id)
    row = case.command("create", task, case.values(10))["data"]["rows"][0]
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("correct", row["report_ref"], {"actual_end": "2026-09-09T11:00:00", "original_revision_ref": row["revision_ref"], "reason": "Finish correction"})
    assert any(item["code"] == "downstream_time_conflict" for item in error.value.conflicts)
    case.command("correct", row["report_ref"], {"remark": "Verified", "original_revision_ref": row["revision_ref"], "reason": "Remark only"})


def test_new_adoption_protects_original_quantity_even_without_successor(ledger_case):
    case = ledger_case
    case.install()
    row = case.command("create", case.task(1, case.op_id), case.values(4))["data"]["rows"][0]
    case.plan(2, [case.op_id])
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("correct", row["report_ref"], {"completed_quantity": 2, "original_revision_ref": row["revision_ref"], "reason": "Would change remaining"})
    assert any(item["code"] == "adopted_execution_basis_changed" for item in error.value.conflicts)
    assert all_rows(case.conn) == before


def test_actual_resource_relations_are_not_inferred_from_labels(ledger_case):
    case = ledger_case
    case.install()
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Operator')")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected):
        case.command("create", case.task(1, case.op_id), case.values(1, actual_operator_ref=case.ref("operator", "O2")))
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O2','M1')")
    case.conn.commit()
    case.command("create", case.task(1, case.op_id), case.values(1, actual_operator_ref=case.ref("operator", "O2")))
    assert case.ledger.get_task(case.task(1, case.op_id)).reports[0].actual_operator_ref == case.ref("operator", "O2")
