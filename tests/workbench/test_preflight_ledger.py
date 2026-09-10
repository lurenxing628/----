"""Integration with AJ's actual installed unique ExecutionProjection service."""

import pytest

from core.services.workbench.preflight import PreflightService
from tests.workbench.execution_ledger_support import START
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture
from tests.workbench.identity_metadata_support import insert_row
from tests.workbench.preflight_support import read_only_snapshot, snapshot


def evaluate(case):
    value = {"batch_refs": [case.ref("batch", "B1")], "start_date": "2026-09-09", "end_date": "2026-09-10",
             "ready_check": True, "missing_resource_policy": "auto_assign", "completed_policy": "preserve_actuals"}
    with read_only_snapshot(case.conn):
        data, _ = PreflightService(case.conn).evaluate(value)
    assert data["execution_projection_source"] == "execution_ledger"
    assert "execution_ledger_unavailable" not in {row["code"] for row in data["run_blocked_reasons"]}
    assert data["run_blocked"] is True
    return data


@pytest.mark.parametrize("quantity,expected,remaining", [(0, "partial", 10), (4, "partial", 6), (10, "complete", 0), (None, "partial", None)])
def test_installed_report_values_are_not_reaggregated(ledger_case, quantity, expected, remaining):
    case = ledger_case
    case.install()
    case.command("create", case.task(1, case.op_id), case.values(quantity))
    row = evaluate(case)["tasks"][0]
    assert row["status"] == "protected" and row["execution"]["execution_state"] == expected
    assert row["execution"]["remaining_quantity"] == remaining
    assert row["execution"]["known_completed_quantity"] == (quantity or 0)


def test_installed_started_unknown_does_not_unlock(ledger_case):
    case = ledger_case
    case.install()
    case.command("create", case.task(1, case.op_id), {"actual_start": START})
    data = evaluate(case)
    row = data["tasks"][0]
    assert row["status"] == "protected" and row["execution"]["execution_state"] == "started"
    assert row["execution"]["remaining_quantity"] is None and row["execution"]["unknown_record_count"] == 1
    assert any(row["code"] == "execution_review_required" for row in data["blockers"])


def test_installed_legacy_finish_survives_unknown_quantity(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish")
    case.install()
    row = evaluate(case)["tasks"][0]
    assert row["status"] == "protected" and row["execution"]["execution_state"] == "complete"
    assert row["execution"]["completion_basis"] == "legacy_finish_event"
    assert row["execution"]["data_quality"] == "legacy_incomplete"
    assert row["execution"]["remaining_quantity"] is None


@pytest.mark.parametrize("damage", ["finish_without_start", "broken_previous_revision"])
def test_installed_invalid_legacy_sequence_never_unlocks_successor(ledger_case, damage):
    case = ledger_case
    if damage == "broken_previous_revision":
        case.event(case.op_id, "start")
    event_id = case.event(case.op_id, "finish")
    if damage == "broken_previous_revision":
        case.conn.execute("UPDATE OperationExecutionEvents SET previous_state_revision='wrong' WHERE id=?", (event_id,))
    successor = case.op("OP2", seq=2)
    case.plan(2, [case.op_id, successor])
    case.install()
    assert case.conn.execute("SELECT count(*) FROM WorkbenchExecutionLegacyFacts WHERE recorded_against_task_ref IS NULL").fetchone()[0] == 0
    data = evaluate(case)
    first, second = data["tasks"]
    assert first["status"] == "protected" and second["status"] == "skipped"
    assert first["execution"]["execution_state"] == "unreported"
    assert first["execution"]["data_quality"] == "invalid"
    assert first["execution"]["confirmed_finish"] is None and first["execution"]["remaining_quantity"] is None
    assert "invalid_legacy_sequence" in {row["code"] for row in first["issues"]}
    assert "execution_review_required" in {row["code"] for row in data["blockers"]}
    assert data["eligible_tasks"] == 0


def test_installed_ambiguous_old_schedule_is_not_bound_to_replacement_or_latest(ledger_case):
    case = ledger_case
    original = dict(case.conn.execute("SELECT * FROM Schedule WHERE version=1 AND op_id=?", (case.op_id,)).fetchone())
    case.conn.execute("DELETE FROM Schedule WHERE id=?", (original["id"],))
    insert_row(case.conn, "Schedule", original)
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish")
    successor = case.op("OP2", seq=2)
    case.plan(2, [case.op_id, successor])
    assert case.conn.execute("""SELECT count(*) FROM WorkbenchPlanSourceRefs
        WHERE kind='schedule_row' AND source_key=? AND version=1""", (str(original["id"]),)).fetchone()[0] == 2
    case.install()
    bindings = case.conn.execute("""SELECT operation_ref, recorded_against_task_ref, recorded_against_plan_ref
        FROM WorkbenchExecutionLegacyFacts ORDER BY id""").fetchall()
    assert [tuple(row) for row in bindings] == [(None, None, None)] * 2
    data = evaluate(case)
    first, second = data["tasks"]
    assert first["status"] == "blocked" and second["status"] == "skipped"
    assert first["execution"]["execution_state"] == "unreported" and first["execution"]["data_quality"] == "invalid"
    assert first["execution"]["confirmed_finish"] is None and first["execution"]["remaining_quantity"] is None
    assert "legacy_identity_unresolved" in {row["code"] for row in first["issues"]}
    assert second["issues"][-1]["related_operation_ref"] == first["operation_ref"]
    assert data["counts"]["blocked_tasks"] == 1 and data["eligible_tasks"] == 0
    assert case.conn.execute("SELECT count(*) FROM WorkbenchProductionReports").fetchone()[0] == 0


@pytest.mark.parametrize("change", ["DELETE FROM OperationExecutionEvents WHERE event_type='finish'",
    "UPDATE OperationExecutionEvents SET event_time='2026-09-09T11:00:00',quantity_done=1 WHERE event_type='finish'"])
def test_installed_archived_unknown_finish_survives_source_drift(ledger_case, change):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish")
    case.install()
    archived = snapshot(case.conn)["WorkbenchExecutionLegacyFacts"]
    case.conn.execute(change)
    case.conn.commit()
    row = evaluate(case)["tasks"][0]
    assert row["status"] == "protected" and row["execution"]["execution_state"] == "complete"
    assert row["execution"]["completion_basis"] == "legacy_finish_event"
    assert row["execution"]["confirmed_finish"] == "2026-09-09T10:00:00"
    assert row["execution"]["remaining_quantity"] is None
    assert "legacy_source_changed" in {item["code"] for item in row["issues"]}
    assert snapshot(case.conn)["WorkbenchExecutionLegacyFacts"] == archived


def test_installed_piece_completion_does_not_use_batch_target(ledger_case):
    case = ledger_case
    piece = case.op("PIECE", piece="unit-1")
    case.plan(2, [piece])
    case.install()
    case.command("create", case.task(2, piece), case.values(1))
    row = next(row for row in evaluate(case)["tasks"] if row["piece_id"] == "unit-1")
    assert row["execution"]["execution_state"] == "complete" and row["execution"]["remaining_quantity"] == 0


def test_installed_preflight_never_constructs_legacy_operation_model(ledger_case, monkeypatch):
    from core.models.batch_operation import BatchOperation

    case = ledger_case
    case.install()
    case.conn.execute("UPDATE BatchOperations SET setup_hours=NULL")
    case.conn.commit()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("preflight must not normalize NULL through BatchOperation.from_row")

    monkeypatch.setattr(BatchOperation, "from_row", classmethod(forbidden))
    data = evaluate(case)
    assert data["counts"]["blocked_tasks"] == 1 and data["counts"]["ready_tasks"] == 0
