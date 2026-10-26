"""Real preflight API read-only, field, scope, execution and token contracts."""


import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.preflight_support import checked, payload
from tests.workbench.preflight_support import pf as pf_fixture  # noqa: F401
from tests.workbench.preflight_support import pf_legacy_schema as pf_legacy_fixture  # noqa: F401
from tests.workbench.run_candidate_support import candidate_case as candidate_fixture  # noqa: F401
from web.routes.workbench.preflight import evaluate_preflight_input_prepared


@pytest.mark.parametrize("fixture_name,source", [("pf", "execution_ledger"), ("pf_legacy_schema", "legacy_guard_only")])
def test_read_only_zero_hours_and_unavailable_worker(request, fixture_name, source, monkeypatch):
    import json
    import sqlite3
    from collections import Counter

    from core.models.content import same
    from data.repositories.workbench_preflight_facts_repo import WorkbenchPreflightFactsRepository
    from web.public_token_registry import resolve_public_token
    from web.routes.workbench.preflight import INPUT_SCOPE

    pf = request.getfixturevalue(fixture_name)
    pf.conn.execute("UPDATE Batches SET due_date='2026-9-9',ready_date='' WHERE batch_id='PF-0000'")
    pf.conn.commit()
    from core.infrastructure.database import get_connection
    from core.services.workbench.facts.production_capture import (
        NON_INPUT_RECEIPT_ACTIONS,
        ProductionFactsCapture,
        non_input_row,
    )

    native = get_connection(":memory:")
    try:
        pf.conn.backup(native)
        native.execute("BEGIN")
        previous = native.execute("SELECT due_date,ready_date FROM Batches WHERE batch_id='PF-0000'").fetchone()
        capture = ProductionFactsCapture(native)
        business = next(row for row in capture.business_table("Batches") if row["batch_id"] == "PF-0000")
        raw = next(row for row in capture.table("Batches") if row["batch_id"] == "PF-0000")
        assert business["due_date"] == previous[0] and previous[0].isoformat() == "2026-09-09"
        assert business["ready_date"] is previous[1] is None
        assert raw["due_date"] == "2026-9-9"
        saved = next(row for row in capture.archive(named=True)["tables"]["Batches"] if row["batch_id"] == "PF-0000")
        assert saved["due_date"] == "2026-9-9"
        assert raw["ready_date"] == saved["ready_date"] == ""
    finally:
        native.close()
    receipts = sqlite3.connect(":memory:")
    try:
        receipts.execute("CREATE TABLE WorkbenchCommandReceipts(request_key TEXT,action,outcome_json)")
        actions = (*NON_INPUT_RECEIPT_ACTIONS, "trial.save", "dashboard.transition", "TRIAL.save",
                   None, sqlite3.Binary(b"trial.save"), 7, "execution.report_correct", "unknown", "unchanged")
        originals = [(str(index), action, '{"result":"unchanged"}' if action == "unchanged"
                      else "not-json" if action == "unknown" else '{"result":"committed"}')
                     for index, action in enumerate(actions)]
        receipts.executemany("INSERT INTO WorkbenchCommandReceipts VALUES (?,?,?)", originals)
        originals = WorkbenchPreflightFactsRepository(receipts).capture_table("WorkbenchCommandReceipts")[1]
        statements = []
        receipts.set_trace_callback(statements.append)
        capture = ProductionFactsCapture(receipts)
        actual = capture.archive(named=True)["tables"]["WorkbenchCommandReceipts"]
        columns = capture.columns["WorkbenchCommandReceipts"]
        expected = [dict(zip(columns, row)) for row in originals
                    if not non_input_row("WorkbenchCommandReceipts", row, columns)]
        assert same(actual, expected)
        assert len(capture.table("WorkbenchCommandReceipts")) == len(originals) - 4
        sql = [statement for statement in statements if statement.startswith("SELECT")
               and 'FROM "WorkbenchCommandReceipts"' in statement]
        assert len(sql) == 1 and "typeof(\"action\")='text'" in sql[0]
        assert "COLLATE BINARY IN" in sql[0] and '"action" GLOB' in sql[0]
        assert len(WorkbenchPreflightFactsRepository(receipts).capture_table(
            "WorkbenchCommandReceipts")[1]) == len(originals)
    finally:
        receipts.close()
    table_reads = Counter()
    capture_table = WorkbenchPreflightFactsRepository.capture_table

    def captured(repo, name):
        table_reads[name] += 1
        return capture_table(repo, name)

    monkeypatch.setattr(WorkbenchPreflightFactsRepository, "capture_table", captured)
    data = checked(pf)
    first_reads = dict(table_reads)
    assert {"Batches", "BatchOperations"} <= set(first_reads)
    assert set(first_reads.values()) == {1}
    table_reads.clear()
    repeated = checked(pf)
    assert dict(table_reads) == first_reads
    assert repeated["input_ref"] != data["input_ref"]
    with pf.application.app_context():
        first_binding = resolve_public_token(INPUT_SCOPE, data["input_ref"],
            message="Preflight input is unavailable", field="input_ref")
        repeated_binding = resolve_public_token(INPUT_SCOPE, repeated["input_ref"],
            message="Preflight input is unavailable", field="input_ref")
    assert repeated_binding["fingerprint"] == first_binding["fingerprint"]
    from core.services.workbench.facts.schema_compat import project_facts

    archive = json.loads(first_binding["fingerprint"])
    legacy = {"schema": archive["schema"], "tables": archive["tables"]}
    assert archive["version"] == "production-facts-v2" and archive["columns"]
    assert same(project_facts(archive), project_facts(legacy))
    assert data["counts"]["ready_tasks"] == 1
    assert data["counts"]["blocked_tasks"] == 0
    assert data["calendar_check"] == "not_evaluated"
    assert data["effective_start"] == "2026-09-09T00:00:00"
    assert data["effective_end_exclusive"] == "2026-09-10T00:00:00"
    assert data["write_context"]["capabilities"]["scheduling.run"] is False
    assert data["write_context"]["write_token"] is None
    reasons = {row["code"] for row in data["run_blocked_reasons"]}
    assert data["run_blocked"] is True and "schedule_not_computed" in reasons
    assert data["execution_projection_source"] == source
    assert ("execution_ledger_unavailable" in reasons) == (source == "legacy_guard_only")


_RECEIPT = ("INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_hash,outcome_json) "
            "VALUES ('preflight-receipt-0001','" + "c" * 32 + "','{}','context','" + "d" * 64 + "','{{\"result\":\"{}\"}}')")


@pytest.mark.parametrize("change,stale", [(_RECEIPT.format("dashboard.transition", "committed"), False), (_RECEIPT.format("calendar.defaults", "committed"), True)])
def test_input_ref_uses_the_run_worker_facts_scope(pf, change, stale):
    # 检查到开始之间：日志、自动维护时钟、看板处置、试调和“无改动”回执排产都不读，和排产计算同一口径，不算现场变化；
    # 其他已提交的回执仍保守地算变化。
    data = checked(pf)
    pf.conn.execute(change)
    pf.conn.commit()
    with pf.application.app_context():
        pf.conn.execute("BEGIN")
        try:
            if stale:
                with pytest.raises(WorkbenchCommandRejected, match="有变化"):
                    evaluate_preflight_input_prepared(pf.conn, data["input_ref"])
            else:
                assert evaluate_preflight_input_prepared(pf.conn, data["input_ref"]).data["normalized_input"] == payload(pf)
        finally:
            pf.conn.rollback()


@pytest.mark.parametrize("piece_id", [None, "piece-A"])
def test_unreported_stored_skipped_is_shared_by_preflight_input_and_partial_candidate(candidate_case, piece_id):
    from core.services.workbench.run.preflight import PreflightService
    from tests.workbench.run_candidate_adoption_support import service
    from tests.workbench.run_candidate_support import api, compute, read

    case = candidate_case
    if piece_id is not None:
        case.conn.execute("UPDATE Batches SET quantity=1 WHERE batch_id='B1'")
    skipped = case.operation(seq=2, piece_id=piece_id)
    case.operation(seq=3, piece_id=piece_id)
    case.conn.execute("UPDATE BatchOperations SET status='skipped' WHERE id=?", (skipped,))
    case.conn.commit()
    data, _fingerprint = PreflightService(case.conn).evaluate(case.settings())
    assert data["counts"]["ready_tasks"] == 1
    assert data["counts"]["skipped_tasks"] == 2
    assert data["blockers"] == []
    assert "skipped_not_adoptable" in {item["code"] for item in data["warnings"]}
    row = next(row for row in data["tasks"] if row["sequence"] == 2)
    assert row["status"] == "skipped"
    assert {item["code"] for item in row["issues"]} == {"operation_skipped"}
    downstream = next(row for row in data["tasks"] if row["sequence"] == 3)
    assert downstream["status"] == "skipped"
    assert {item["code"] for item in downstream["issues"]} == {"predecessor_excluded"}
    _run_ref, candidates = compute(case)
    assert candidates
    client, _statements = api(case)
    summary = read(client, "/candidates/" + candidates[0])["data"]["candidate"]
    assert summary["status"] == "partial" and summary["task_count"] == 1
    denied = service(case.conn).preview(candidates[0])
    assert denied["validation"]["can_adopt"] is False
    assert denied["validation"]["issues"][0]["code"] == "candidate_incomplete"
    assert case.conn.execute("SELECT COUNT(*) FROM Schedule").fetchone()[0] == 0


def test_corrupt_official_schedule_time_in_hold_window_blocks_strict_freeze(candidate_case):
    from core.errors import ValidationError
    from core.services.workbench.run.preflight import PreflightService
    from tests.workbench.run_compute_support import prepare_run_input

    case = candidate_case
    case.conn.execute("INSERT INTO ScheduleHistory(version,strategy) VALUES (1,'greedy')")
    case.conn.execute(
        "INSERT INTO Schedule(op_id,machine_id,operator_id,start_time,end_time,version) VALUES (?,'M1','O1','bad','2026-09-09 09:00:00',1)",
        (case.op_id,),
    )
    case.conn.commit()
    settings = case.settings(hold_window={"start": "2026-09-09T08:00", "end": "2026-09-09T12:00"})
    data, _fingerprint = PreflightService(case.conn).evaluate(settings)
    assert "freeze_window_unavailable" in {item["code"] for item in data["blockers"]}
    with pytest.raises(ValidationError) as exc:
        prepare_run_input(case.conn, settings, case.projections())
    assert exc.value.field == "freeze_window"


def test_unexpected_preflight_failure_logs_the_request_ref_shown_to_the_user(pf, monkeypatch, caplog):
    """排产检查的未预期错误：日志记下的编号就是用户看到的「下方编号」，原始异常留在日志里。"""
    import logging

    from core.services.workbench.run.preflight import PreflightService

    def broken(service, value):
        raise RuntimeError("preflight evaluation broke")

    monkeypatch.setattr(PreflightService, "evaluate", broken)
    with caplog.at_level(logging.ERROR):
        response = pf.post("/api/workbench/v1/scheduling/preflight", json=payload(pf))
    assert response.status_code == 500, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    result = response.get_json()
    error = result["error"]
    assert result["committed"] is False
    assert (error["code"], error["message"]) == ("storage_failure", "排产检查没有完成，没有生成这次排产，也没有改动任何业务数据。"
                                                 "请刷新重试；仍不行请联系维护人员，并告知下方编号。")
    record, = [item for item in caplog.records if item.getMessage().startswith("只读排产前检查失败")]
    assert record.getMessage() == "只读排产前检查失败 request_ref=" + error["request_ref"]
    assert isinstance(record.exc_info[1], RuntimeError)
