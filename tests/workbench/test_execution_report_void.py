"""Withdrawal changes effective facts once, while preserving every original row."""

import sqlite3

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain, input_fingerprint
from core.services.workbench.execution.production_report import WorkbenchProductionReportService
from core.services.workbench.run.worker import WorkbenchRunWorker
from data.repositories.workbench_execution_report_repo import WorkbenchExecutionReportRepository
from tests.workbench.execution_ledger_support import END, START, all_rows
from tests.workbench.execution_ledger_support import ledger_case as ledger_fixture
from tests.workbench.field_workspace_support import BASE, FieldAPI
from tests.workbench.run_candidate_adoption_support import INTENT
from tests.workbench.run_candidate_adoption_support import preview as candidate_preview
from tests.workbench.run_candidate_adoption_support import service as candidate_adoption
from tests.workbench.run_candidate_support import candidate_case as candidate_fixture
from tests.workbench.scheduler_execution_ledger_support import read_facts
from tests.workbench.test_execution_dependency_regressions import (
    adopt,
    create,
    merged_external_route,
    report_plan,
    task,
    values,
)


def report(case, values=None):
    return case.command("create", case.task(1, case.op_id), values or case.values(4))["data"]["rows"][0]


def intent(row):
    return {"original_revision_ref": row["revision_ref"], "reason": "误记了其他工序的产出", "declared_operator": "现场班长"}


def test_preview_is_select_only_and_void_preserves_original_history(ledger_case):
    case = ledger_case
    case.install()
    row = report(case)
    case.command("correct", row["report_ref"], {**intent(row), "completed_quantity": 5})
    original = case.ledger.get_report(row["report_ref"])
    payload = {**intent(row), "original_revision_ref": original.revision_ref}
    before = all_rows(case.conn)
    case.conn.execute("PRAGMA query_only=ON")
    preview = case.writer.preview("report_void", row["report_ref"], payload)
    assert preview["can_confirm"] and preview["before"]["known_completed_quantity"] == 5
    assert preview["after"]["known_completed_quantity"] == 0 and preview["after"]["execution_state"] == "unreported"
    assert all_rows(case.conn) == before
    case.conn.execute("PRAGMA query_only=OFF")
    saved = case.command("report_void", row["report_ref"], payload)
    after = all_rows(case.conn)
    assert saved["data"]["state"] == "voided" and saved["data"]["refresh_required"]
    assert {name for name in before if before[name] != after[name]} == {
        "WorkbenchProductionReportVoids", "WorkbenchExecutionLedgerClock", "WorkbenchCommandReceipts"}
    projected = case.ledger.get_task(case.task(1, case.op_id))
    assert projected.reports == [] and projected.remaining_quantity == 10
    audit = projected.voided_reports[0]
    assert audit["report"]["correction_history"] == original.correction_history
    assert audit["void_fact"]["reason"] == payload["reason"] and audit["void_fact"]["declared_operator"] == "现场班长"
    assert audit["void_fact"]["receipt_ref"] == saved["receipt_ref"]
    assert case.ledger.get_report(row["report_ref"]).revision_ref == original.revision_ref


def test_zero_output_is_real_execution_until_explicitly_voided(ledger_case):
    case = ledger_case
    case.install()
    row = report(case, {"completed_quantity": 0, "effective_processing_hours": 0})
    assert case.ledger.get_task(case.task(1, case.op_id)).execution_state == "started"
    case.command("report_void", row["report_ref"], intent(row))
    assert case.ledger.get_task(case.task(1, case.op_id)).execution_state == "unreported"


def test_void_one_of_many_keeps_other_report_and_scheduler_intervals(ledger_case):
    case = ledger_case
    case.install()
    first = report(case)
    second = report(case, case.values(3, actual_start="2026-09-09T10:00:00", actual_end="2026-09-09T12:00:00"))
    case.command("report_void", first["report_ref"], intent(first))
    p = case.ledger.get_task(case.task(1, case.op_id))
    assert p.known_completed_quantity == 3 and p.remaining_quantity == 7 and p.execution_state == "partial"
    assert [row.report_ref for row in p.reports] == [second["report_ref"]]
    fact = read_facts(case.conn)[case.op_id]
    assert fact.remaining_quantity == 7 and len(fact.execution_effective_intervals) == 1
    assert fact.execution_effective_intervals[0][0].isoformat() == "2026-09-09T10:00:00"


def test_repeat_void_replays_before_actor_token_and_new_key_is_unchanged(ledger_case):
    case = ledger_case
    case.install()
    row = report(case)
    saved = case.command("report_void", row["report_ref"], intent(row), key="void-original-request-0001")
    def unavailable(*_):
        raise AssertionError("committed replay must not read a new actor or context")
    restarted = WorkbenchProductionReportService(case.conn, actor_provider=unavailable)
    replay = restarted.execute("report_void", row["report_ref"], intent(row), request_key="void-original-request-0001", validate_context=unavailable)
    assert replay == {**saved, "replayed": True}
    again = case.command("report_void", row["report_ref"], intent(row))
    assert again["result"] == "unchanged" and again["data"]["void_fact_ref"] == saved["data"]["void_fact_ref"]
    assert case.conn.execute("SELECT count(*) FROM WorkbenchProductionReportVoids").fetchone()[0] == 1


def test_old_revision_and_stale_operation_snapshot_cannot_void(ledger_case):
    case = ledger_case
    case.install()
    row = report(case)
    preview = case.writer.preview("report_void", row["report_ref"], intent(row))
    report(case, case.values(1))
    before = all_rows(case.conn)
    def validate(ref, action, snapshot):
        assert ref == row["report_ref"] and action == "report_void"
        if input_fingerprint(snapshot) != input_fingerprint(preview["snapshot"]):
            raise WorkbenchCommandRejected("context_stale", "changed")
    with pytest.raises(WorkbenchCommandRejected, match="changed"):
        case.command("report_void", row["report_ref"], intent(row), validate_context=validate)
    assert all_rows(case.conn) == before
    case.command("correct", row["report_ref"], {**intent(row), "remark": "新记录"})
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("report_void", row["report_ref"], intent(row))
    assert error.value.code == "context_stale"


@pytest.mark.parametrize("quantity", [4, 10])
def test_downstream_started_blocks_even_if_parent_was_only_partial(ledger_case, quantity):
    case = ledger_case
    successor = case.op("NEXT", seq=2)
    case.plan(2, [case.op_id, successor])
    case.install()
    row = case.command("create", case.task(2, case.op_id), case.values(quantity))["data"]["rows"][0]
    case.command("create", case.task(2, successor), {"actual_start": END, "completed_quantity": 0})
    before = all_rows(case.conn)
    preview = case.writer.preview("report_void", row["report_ref"], intent(row))
    assert not preview["can_confirm"] and preview["downstream_impacts"]
    assert all(item["operation_label"].startswith("2 ") for item in preview["downstream_impacts"])
    with pytest.raises(WorkbenchCommandRejected):
        case.command("report_void", row["report_ref"], intent(row))
    assert all_rows(case.conn) == before


def test_new_adopted_plan_protects_its_execution_basis(ledger_case):
    case = ledger_case
    case.install()
    row = report(case)
    case.plan(2, [case.op_id])
    preview = case.writer.preview("report_void", row["report_ref"], intent(row))
    assert not preview["can_confirm"]
    assert "adopted_execution_basis_changed" in {item["code"] for item in preview["downstream_impacts"]}


def test_old_actual_start_survives_voiding_new_report(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.install()
    row = report(case)
    original = all_rows(case.conn)["OperationExecutionEvents"]
    case.command("report_void", row["report_ref"], intent(row))
    projection = case.ledger.get_task(case.task(1, case.op_id))
    assert projection.execution_state == "started" and projection.first_actual_start == START
    assert all_rows(case.conn)["OperationExecutionEvents"] == original


def test_void_failure_rolls_back_fact_clock_and_receipt(ledger_case, monkeypatch):
    case = ledger_case
    case.install()
    row = report(case)
    original = WorkbenchExecutionReportRepository.append_void
    def fail(self, fact, *, request_key):
        original(self, fact, request_key=request_key)
        raise RuntimeError("injected after append")
    monkeypatch.setattr(WorkbenchExecutionReportRepository, "append_void", fail)
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandUncertain):
        case.command("report_void", row["report_ref"], intent(row))
    assert all_rows(case.conn) == before


def test_voided_history_cannot_be_corrected_reimported_or_replaced(ledger_case):
    case = ledger_case
    case.install()
    row = report(case)
    case.command("report_void", row["report_ref"], intent(row))
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.command("correct", row["report_ref"], {**intent(row), "completed_quantity": 2})
    assert error.value.code == "report_voided"
    with pytest.raises(WorkbenchCommandRejected) as error:
        report(case, {**case.values(2), "source": "excel", "report_no": row["report_no"]})
    assert error.value.code == "report_voided"
    for sql in ("DELETE FROM WorkbenchProductionReportVoids", "UPDATE WorkbenchProductionReportVoids SET reason='changed'",
                "INSERT OR REPLACE INTO WorkbenchProductionReportVoids SELECT * FROM WorkbenchProductionReportVoids"):
        with pytest.raises(sqlite3.IntegrityError):
            case.conn.execute(sql)
        case.conn.rollback()
    assert all_rows(case.conn) == before


def test_voided_legacy_supplement_can_be_replaced_by_one_new_effective_report(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=10)
    case.install()
    task = case.task(1, case.op_id)
    legacy_ref = case.ledger.get_task(task).legacy_facts[-1]["legacy_fact_ref"]
    api = FieldAPI(case)
    first = api.create(case.values(10, legacy_fact_ref=legacy_ref, reason="核对历史完工"))["data"]["rows"][0]
    original_reports = all_rows(case.conn)["WorkbenchProductionReports"]
    checked = api.client.post(BASE + "/reports/" + first["report_ref"] + "/void-preview", json={"input": intent(first)})
    preview = checked.get_json()["data"]
    assert checked.status_code == 200 and preview["can_confirm"]
    withdrawn = api.client.post(BASE + "/reports/" + first["report_ref"] + "/void", json=api.body(preview["write_context"], intent(first)))
    assert withdrawn.status_code == 200
    second = api.create(case.values(10, legacy_fact_ref=legacy_ref, reason="重新核对原始工时", effective_processing_hours=1))["data"]["rows"][0]
    projection = case.ledger.get_task(task)
    assert projection.known_completed_quantity == 10 and projection.data_quality == "complete"
    assert [row.report_ref for row in projection.reports] == [second["report_ref"]]
    assert projection.reports[0].effective_processing_hours == 1
    assert projection.voided_reports[0]["report"]["report_ref"] == first["report_ref"]
    assert all_rows(case.conn)["WorkbenchProductionReports"][:1] == original_reports
    before = all_rows(case.conn)
    with pytest.raises(WorkbenchCommandRejected):
        report(case, case.values(10, legacy_fact_ref=legacy_ref, reason="不能重复累计"))
    assert all_rows(case.conn) == before
    # The DB enforces the same effective-only rule even for a lower-level writer.
    with pytest.raises(sqlite3.IntegrityError, match="active report"):
        case.conn.execute("""INSERT INTO WorkbenchProductionReports SELECT ?,?,operation_ref,
            recorded_against_task_ref,recorded_against_plan_ref,source,legacy_fact_ref,recorded_at
            FROM WorkbenchProductionReports WHERE report_ref=?""", ("f" * 48, "duplicate-active", second["report_ref"]))
    case.conn.rollback()
    assert all_rows(case.conn) == before


def test_batch_cannot_create_two_effective_supplements_after_legacy_report_void(ledger_case):
    case = ledger_case
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=10)
    case.install()
    task = case.task(1, case.op_id)
    legacy_ref = case.ledger.get_task(task).legacy_facts[-1]["legacy_fact_ref"]
    first = report(case, case.values(10, legacy_fact_ref=legacy_ref, reason="核对历史完工"))
    case.command("report_void", first["report_ref"], intent(first))
    before = all_rows(case.conn)
    items = [{"action": "create", "ref": task, "payload": case.values(10, legacy_fact_ref=legacy_ref,
        reason="文件重新补齐", source="excel", report_no=number)} for number in ("renewed-1", "renewed-2")]
    with pytest.raises(WorkbenchCommandRejected):
        case.writer.execute_batch(items, context_ref=case.plan_ref(1), request_key="legacy-double-supplement-001",
                                  validate_context=lambda *_: None)
    assert all_rows(case.conn) == before


def test_missing_void_table_never_reactivates_archived_reports(ledger_case):
    case = ledger_case
    case.install()
    row = report(case)
    case.command("report_void", row["report_ref"], intent(row))
    case.conn.execute("DROP TABLE WorkbenchProductionReportVoids")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        case.ledger.get_task(case.task(1, case.op_id))
    assert error.value.code == "execution_ledger_unavailable"


def _completed_merged_reports(case, piece, *, downstream=False):
    members = merged_external_route(case, piece)
    successor = case.operation(seq=4, piece_id="unit-A" if piece else None) if downstream else None
    case.conn.commit()
    version = adopt(case)
    report_plan(case, version, {case.op_id})
    api = FieldAPI(case)
    for operation in members:
        payload = values(case, "2026-09-09T10:00:00", "2026-09-10T10:00:00", 1 if piece else 3)
        payload.update(actual_machine_ref=None, actual_operator_ref=None)
        assert create(api, version, operation, payload).status_code == 200
    if successor is not None:
        assert create(api, version, successor,
            values(case, "2026-09-10T10:00:00", "2026-09-10T11:00:00", 1 if piece else 3)).status_code == 200
    return api, version, members, successor


def _merged_change(api, version, operation, action, piece):
    row = task(api, version, operation)["execution"]["reports"][0]
    payload = {"original_revision_ref": row["revision_ref"], "reason": "原始报工数量核对"}
    if action == "correct":
        payload["completed_quantity"] = 0 if piece else 2
        return api.client.post(BASE + "/reports/" + row["report_ref"] + "/correct", json=api.body(row["write_context"], payload))
    checked = api.client.post(BASE + "/reports/" + row["report_ref"] + "/void-preview", json={"input": payload})
    preview = checked.get_json()["data"]
    assert checked.status_code == 200
    if not preview["can_confirm"]:
        return checked
    return api.client.post(BASE + "/reports/" + row["report_ref"] + "/void", json=api.body(preview["write_context"], payload))


@pytest.mark.parametrize("piece", [False, True])
@pytest.mark.parametrize("member", [0, 1])
@pytest.mark.parametrize("action", ["report_void", "correct"])
def test_merged_cycle_peer_does_not_block_report_withdrawal_or_quantity_correction(candidate_case, piece, member, action):
    case = candidate_case
    api, version, members, _ = _completed_merged_reports(case, piece)
    other = task(api, version, members[1 - member])["execution"]
    before_reports = all_rows(case.conn)["WorkbenchProductionReports"]
    response = _merged_change(api, version, members[member], action, piece)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["result"] == "committed", response.get_json()
    changed = task(api, version, members[member])["execution"]
    assert changed["execution_state"] == ("unreported" if action == "report_void" else "partial")
    assert changed["known_completed_quantity"] == (0 if action == "report_void" or piece else 2)
    peer = task(api, version, members[1 - member])["execution"]
    assert peer["execution_state"] == "complete" and peer["known_completed_quantity"] == other["known_completed_quantity"]
    assert peer["reports"][0]["revision_ref"] == other["reports"][0]["revision_ref"]
    assert all_rows(case.conn)["WorkbenchProductionReports"] == before_reports


@pytest.mark.parametrize("piece", [False, True])
@pytest.mark.parametrize("action", ["report_void", "correct"])
def test_merged_cycle_report_change_still_protects_real_successor_outside_group(candidate_case, piece, action):
    case = candidate_case
    api, version, members, successor = _completed_merged_reports(case, piece, downstream=True)
    successor_ref = task(api, version, successor)["operation_ref"]
    peer_ref = task(api, version, members[1])["operation_ref"]
    before = all_rows(case.conn)
    response = _merged_change(api, version, members[0], action, piece)
    body = response.get_json()
    if action == "report_void":
        assert response.status_code == 200 and body["data"]["can_confirm"] is False
        impacts = body["data"]["downstream_impacts"]
    else:
        assert response.status_code == 409 and body["committed"] is False
        row = task(api, version, members[0])["execution"]["reports"][0]
        with pytest.raises(WorkbenchCommandRejected) as error:
            case.writer.preview("correct", row["report_ref"], {"original_revision_ref": row["revision_ref"],
                "reason": "核对原始数量", "completed_quantity": 0 if piece else 2})
        impacts = error.value.conflicts
    assert successor_ref in {item["operation_ref"] for item in impacts}
    assert peer_ref not in {item["operation_ref"] for item in impacts}
    assert all_rows(case.conn) == before


@pytest.mark.parametrize("piece", [False, True])
def test_merged_cycle_peer_exemption_keeps_formally_adopted_report_dependency(candidate_case, piece):
    case = candidate_case
    api, _, members, _ = _completed_merged_reports(case, piece)
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    accepted = case.accept(key="merged-report-second-run-001", settings=case.settings("B1", "B2"))
    computed = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert computed["state"] == "complete" and computed["candidates"]
    candidate = computed["candidates"][0]["candidate_ref"]
    adopted = candidate_adoption(case.conn).adopt(candidate, candidate_preview(case, candidate),
        "merged-report-adopt-dependency-001", INTENT)
    version = adopted["data"]["official_plan"]["version"]
    before = all_rows(case.conn)
    response = _merged_change(api, version, members[0], "report_void", piece)
    body = response.get_json()
    assert response.status_code == 200 and body["data"]["can_confirm"] is False
    assert "adopted_completion_required" in {item["code"] for item in body["data"]["downstream_impacts"]}
    assert all_rows(case.conn) == before
