"""Real preflight API read-only, field, scope, execution and token contracts."""

from datetime import date, datetime

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.run.preflight_facts import PreflightFacts
from tests.workbench.preflight_support import BASE, checked, payload, ref_for
from tests.workbench.preflight_support import pf as pf_fixture  # noqa: F401
from tests.workbench.run_candidate_support import candidate_case as candidate_fixture  # noqa: F401
from tests.workbench.run_jobs_support import RUN_NOW
from tests.workbench.run_jobs_support import job_case as job_case_fixture  # noqa: F401
from tests.workbench.run_jobs_support import service as run_service
from web.routes.workbench.preflight import evaluate_preflight_input_prepared
from web.runtime_host import install_wall_clock


def test_read_only_zero_hours_and_unavailable_worker(pf, monkeypatch):
    import json
    from collections import Counter

    from data.repositories.workbench_preflight_facts_repo import WorkbenchPreflightFactsRepository
    from web.public_token_registry import resolve_public_token
    from web.routes.workbench.preflight import INPUT_SCOPE

    pf.conn.execute("UPDATE Batches SET due_date='2026-09-09',ready_date='' WHERE batch_id='PF-0000'")
    pf.conn.commit()
    from core.infrastructure.database import get_connection
    from core.models.content import content_text
    from core.services.workbench.facts.production_capture import (
        ProductionFactsCapture,
        table_rows,
        validate_production_archive,
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
        assert raw["due_date"] == "2026-09-09"
        batch_ref = next(
            row["ref"]
            for row in capture.table("WorkbenchEntityRefs")
            if row["kind"] == "batch" and row["entity_key"] == "PF-0000" and row["active"] == 1
        )
        scoped = json.loads(content_text(capture.scoped_archive([batch_ref])))
        assert set(scoped) == {"columns", "tables", "revisions"}
        saved = table_rows(scoped, "Batches")
        assert [row["batch_id"] for row in saved] == ["PF-0000"]
        assert saved[0]["due_date"] == "2026-09-09"
        assert raw["ready_date"] == saved[0]["ready_date"] == ""
        validate_production_archive(scoped)
        assert capture.matches_admitted(scoped)
        with pytest.raises(ValueError, match="Corrupt production facts archive"):
            validate_production_archive({key: value for key, value in scoped.items() if key != "columns"})
        recorded = capture.revisions_record()
        assert capture.matches_recorded(recorded)
        with pytest.raises(ValueError, match="Corrupt production facts archive"):
            capture.matches_recorded({"revisions": {}})
    finally:
        native.close()
    table_reads = Counter()
    capture_table = WorkbenchPreflightFactsRepository.capture_table

    def captured(repo, name):
        table_reads[name] += 1
        return capture_table(repo, name)

    monkeypatch.setattr(WorkbenchPreflightFactsRepository, "capture_table", captured)
    data = checked(pf)
    # 提交时可以不带物料齐套规则：规范后的输入和回执的生效配置都按整批齐套记下。
    assert "material_strategy" not in payload(pf)
    assert data["normalized_input"]["material_strategy"] == data["effective_config"]["material_strategy"] == "strict"
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
    fingerprint = json.loads(first_binding["fingerprint"])
    assert fingerprint[0] == "preflight-v2" and isinstance(fingerprint[1], dict)
    assert data["counts"]["ready_tasks"] == 1
    assert data["counts"]["blocked_tasks"] == 0
    assert data["calendar_check"] == "not_evaluated"
    assert data["effective_start"] == "2026-09-09T00:00:00"
    assert data["effective_end_exclusive"] == "2026-09-10T00:00:00"
    assert data["write_context"]["capabilities"]["scheduling.run"] is False
    assert data["write_context"]["write_token"] is None
    reasons = {row["code"] for row in data["run_blocked_reasons"]}
    assert data["run_blocked"] is True and "schedule_not_computed" in reasons
    assert "execution_projection_source" not in data and "execution_ledger_unavailable" not in reasons
    staged = checked(pf, material_strategy="stage")
    assert staged["normalized_input"]["material_strategy"] == staged["effective_config"]["material_strategy"] == "stage"


def test_unpadded_stored_due_date_is_rejected_at_scheduling_admission_like_delivery(job_case):
    from core.services.workbench.facts.delivery_projection import parse_stored_due_date

    # 存量不补零的交期：排产准入与交付读取同一口径判为日期无效，不会一边排上、一边报交期无效。
    job_case.conn.execute("UPDATE Batches SET due_date='2026-9-9' WHERE batch_id='B1'")
    job_case.conn.commit()
    preview = run_service(job_case.conn).preview(job_case.preflight(), now=RUN_NOW)
    assert [row["code"] for row in preview["write_context"]["blocked_reasons"]] == ["invalid_batch_date"]
    assert parse_stored_due_date("2026-9-9")[2:] == ("invalid", "due_date_invalid")


def test_non_text_stored_batch_dates_are_preserved_and_rejected_at_admission(job_case):
    from core.infrastructure.database import get_connection
    from core.models.workbench_run_compute import CandidateRunInputError
    from core.services.workbench.facts.production_capture import ProductionFactsCapture
    from core.services.workbench.facts.run_input_rows import batch_model
    from tests.workbench.run_jobs_support import JobCase

    conn = get_connection(str(job_case.path))
    try:
        native_case = JobCase(conn)
        for bad_due in (20261015, b"\xff\xfe"):
            job_case.conn.execute("UPDATE Batches SET due_date=?, ready_date=NULL WHERE batch_id='B1'", (bad_due,))
            job_case.conn.commit()
            conn.execute("BEGIN")
            try:
                capture = ProductionFactsCapture(conn)
                row = next(item for item in capture.business_table("Batches") if item["batch_id"] == "B1")
                assert row["due_date"] == bad_due
                assert conn.execute("SELECT due_date FROM Batches WHERE batch_id='B1'").fetchone()[0] is not None
            finally:
                conn.rollback()
            preview = run_service(conn).preview(native_case.preflight(), now=RUN_NOW)
            assert preview["write_context"]["capabilities"]["scheduling.run"] is False
            assert preview["write_context"]["blocked_reasons"] == [
                {
                    "code": "invalid_batch_date",
                    "message": "有批次的交期或齐套日期填得不对，这次排产没有开始。请到批次管理按 2026-09-13 这样改好。",
                }
            ]

        job_case.conn.execute(
            "UPDATE Batches SET due_date='2026-10-15', ready_date=20261005 WHERE batch_id='B1'"
        )
        job_case.conn.commit()
        conn.execute("BEGIN")
        try:
            capture = ProductionFactsCapture(conn)
            row = next(item for item in capture.business_table("Batches") if item["batch_id"] == "B1")
            assert row["ready_date"] == 20261005
            with pytest.raises(CandidateRunInputError) as exc_info:
                batch_model(row)
            assert exc_info.value.code == "invalid_batch_date"
        finally:
            conn.rollback()
        preview = run_service(conn).preview(native_case.preflight(), now=RUN_NOW)
        assert preview["write_context"]["capabilities"]["scheduling.run"] is False
        assert preview["write_context"]["blocked_reasons"]
    finally:
        conn.close()


_RECEIPT = ("INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_json,outcome_json) "
            "VALUES ('preflight-receipt-0001','" + "c" * 32 + "','{}','context','{{}}','{{\"result\":\"{}\"}}')")


@pytest.mark.parametrize("change,stale", [(_RECEIPT.format("dashboard.transition", "committed"), False), (_RECEIPT.format("calendar.defaults", "committed"), True)])
def test_input_ref_uses_the_run_worker_facts_scope(pf, change, stale, monkeypatch):
    # 检查到开始之间：日志、自动维护时钟、看板处置、试调和“无改动”回执排产都不读，和排产计算同一口径，不算现场变化；
    # 其他已提交的回执仍保守地算变化。
    from core.services.workbench.run.preflight import PreflightService
    from data.repositories.workbench_preflight_facts_repo import WorkbenchPreflightFactsRepository

    data = checked(pf)
    pf.conn.execute(change)
    pf.conn.commit()
    with pf.application.app_context():
        pf.conn.execute("BEGIN")
        try:
            table_reads = []
            if stale:
                monkeypatch.setattr(
                    WorkbenchPreflightFactsRepository,
                    "capture_table",
                    lambda _repo, name: table_reads.append(name),
                )

                def forbid_evaluate(*_args, **_kwargs):
                    raise AssertionError("stale input_ref must be rejected before evaluate_prepared")

                monkeypatch.setattr(PreflightService, "evaluate_prepared", forbid_evaluate)
            with PreflightFacts.open(pf.conn) as facts:
                if stale:
                    with pytest.raises(WorkbenchCommandRejected, match="有变化"):
                        evaluate_preflight_input_prepared(pf.conn, data["input_ref"], facts=facts, material_day=date.today().isoformat())
                    assert table_reads == []
                else:
                    first = evaluate_preflight_input_prepared(pf.conn, data["input_ref"], facts=facts, material_day=date.today().isoformat())
                    second = evaluate_preflight_input_prepared(pf.conn, data["input_ref"], facts=facts, material_day=date.today().isoformat())
                    assert first.data["normalized_input"] == second.data["normalized_input"] == payload(pf, material_strategy="strict")
                    assert first.preflight_facts is second.preflight_facts is facts
                    assert first.capture is second.capture is facts.capture
                    assert all("op_id" in row for row in first.evaluation_rows)
                    assert all("op_id" not in row for row in first.data["tasks"])
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
    data, _fingerprint = PreflightService(case.conn).evaluate(case.settings(), material_day=date.today().isoformat())
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


def test_external_cycle_gap_reports_only_an_unset_cycle(pf):
    # 库里外协周期只剩“没填”和合法值两种（表上限定 (0, 36500]），排产检查只报没填。
    with PreflightFacts.open(pf.conn) as facts:
        checks = facts.checks()
        batch = next(row for row in facts.tables["Batches"] if row["batch_id"] == "PF-0000")
        op = next(row for row in facts.tables["BatchOperations"] if row["batch_id"] == "PF-0000")
        gaps = {days: [gap for gap in checks.fields(batch, dict(op, source="external", supplier_id="S1", ext_days=days))
                       if gap["code"] == "external_days_missing"] for days in (None, 2)}
    assert [gap["message"] for gap in gaps[None]] == ["外协周期没填，缺设备人员时的规则也补不上。请到基础资料补填周期。"]
    assert gaps[2] == []


@pytest.mark.parametrize(("patch", "paths", "message"), [
    ({"start_date": "2026-9-09"}, ["start_date"], "排产日期范围必须填完整日期。"),
    ({"end_date": "2026-02-30"}, ["end_date"], "排产日期范围里的日期不存在。"),
    ({"start_date": "1899-12-31"}, ["start_date"], "排产日期范围超出支持的年份。"),
    ({"end_date": "9999-12-31"}, ["end_date"], "排产日期范围超出支持的年份。"),
    ({"start_date": "2026-09-10"}, ["end_date"], "结束日期不能早于开始日期。"),
], ids=["shape", "missing-day", "before-1900", "max-date", "reversed"])
def test_preflight_date_rejection_points_at_the_start_or_end_date(pf, patch, paths, message):
    from tests.workbench.preflight_support import snapshot

    before = snapshot(pf.conn)
    response = pf.post(BASE, json=payload(pf, **patch))
    assert response.status_code == 422, response.get_data(as_text=True)
    error = response.get_json()["error"]
    assert (error["code"], error["message"]) == ("invalid_input", message)
    assert error["fields"] == [{"path": path, "message": message} for path in paths]
    assert snapshot(pf.conn) == before


def test_solve_operation_limit_stops_preflight_and_run_start_by_one_rule(job_case, monkeypatch):
    """选中批次展开后的工序数超过单次求解上限：排产检查和开始排产（授权预览、受理）经同一条规则拒绝，提示指向批次选择。"""
    from flask import Blueprint, g

    from core.services.workbench.run import preflight as preflight_service
    from web.routes.workbench.preflight import register_preflight_routes
    from web.routes.workbench.scheduling_jobs import register_scheduling_job_routes

    case = job_case
    case.operation(seq=2)
    case.conn.commit()
    dispatched = []
    case.app.config["WORKBENCH_RUN_JOBS_ENABLED"] = True
    case.app.extensions["workbench_run_dispatcher"] = dispatched.append
    bp = Blueprint("solve_limit", __name__)
    register_preflight_routes(bp)
    register_scheduling_job_routes(bp)
    case.app.register_blueprint(bp)

    @case.app.before_request
    def bind():
        g.db = case.conn

    client = case.app.test_client()
    base = "/api/workbench/v1/scheduling"
    checked = client.post(base + "/preflight", json=case.settings())
    assert checked.status_code == 200, checked.get_json()
    input_ref = checked.get_json()["data"]["input_ref"]
    preview = client.post(base + "/runs/preview", json={"input_ref": input_ref})
    assert preview.status_code == 200, preview.get_json()
    context = preview.get_json()["data"]["write_context"]
    assert context["capabilities"]["scheduling.run"] is True
    # 只把上限调小来代替上万道工序；检查时取得的 input_ref 在开始排产时重新展开，同一条规则照样拦下。
    monkeypatch.setattr(preflight_service, "MAX_SOLVE_OPERATIONS", 1)
    message = "选中的批次展开后共 2 道工序，超过单次自动排产上限 1 道，排产没有继续。请减少勾选的批次后重新检查。"
    for path, body in (("/preflight", case.settings()), ("/runs/preview", {"input_ref": input_ref}),
                       ("/runs", {"input_ref": input_ref, "write_token": context["write_token"],
                                  "request_key": "run-request-solve-limit"})):
        response = client.post(base + path, json=body)
        assert response.status_code == 422, (path, response.get_json())
        error = response.get_json()["error"]
        assert (error["code"], error["message"]) == ("invalid_input", message)
        assert error["fields"] == [{"path": "batch_refs", "message": message}]
    assert dispatched == []
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 0


def test_storage_rejection_in_preflight_logs_the_request_ref_shown_to_the_user(pf, monkeypatch, caplog):
    """500 拒绝走共同映射：日志记下的编号就是信封里的编号。"""
    import logging

    from core.models.content import StoredJsonCorrupt
    from core.services.workbench.run.preflight import PreflightService

    def corrupt(service, value, *, material_day):
        raise StoredJsonCorrupt()

    monkeypatch.setattr(PreflightService, "evaluate", corrupt)
    with caplog.at_level(logging.ERROR):
        response = pf.post(BASE, json=payload(pf))
    assert response.status_code == 500, response.get_data(as_text=True)
    error = response.get_json()["error"]
    assert (error["code"], error["fields"]) == ("storage_failure", [])
    record, = [item for item in caplog.records if item.getMessage().startswith("工作台请求失败")]
    assert record.getMessage() == "工作台请求失败 code=storage_failure request_ref=" + error["request_ref"]
    assert isinstance(record.exc_info[1], StoredJsonCorrupt)


def test_unexpected_preflight_failure_logs_the_request_ref_shown_to_the_user(pf, monkeypatch, caplog):
    """排产检查的未预期错误：日志记下的编号就是用户看到的「下方编号」，原始异常留在日志里。"""
    import logging

    from core.services.workbench.run.preflight import PreflightService

    def broken(service, value, *, material_day):
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


def test_reviewed_batch_readiness_follows_the_preflight_request_day(pf):
    conn = pf.conn
    conn.execute("INSERT INTO Materials(material_id,name,unit) VALUES ('RM-DAY','day material','kg')")
    requirement = conn.execute("INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty,ready_status) "
                               "VALUES ('PF-0000','RM-DAY',10,2,'no')").lastrowid
    conn.execute("INSERT INTO BatchMaterialReviews(requirement_id,batch_quantity) VALUES (?,3)", (requirement,))
    conn.execute("INSERT INTO BatchMaterialArrivals(requirement_id,arrival_date,quantity) VALUES (?,'2026-10-08',8)",
                 (requirement,))
    conn.commit()
    unready = [{"batch_ref": ref_for(conn), "batch_id": "PF-0000"}]
    # The remaining 8 arrive on the 8th: the batch is short until midnight and complete from then on.
    for moment, expected in ((datetime(2026, 10, 7, 23, 59, 59, 900000), unready), (datetime(2026, 10, 8), [])):
        install_wall_clock(pf.application, lambda moment=moment: moment)
        response = pf.post(BASE, json=payload(pf))
        assert response.status_code == 200, response.get_json()
        body = response.get_json()
        assert body["data"]["unready_batches"] == expected
        assert body["data"]["counts"]["unready_batches"] == len(expected)
        assert body["meta"]["as_of"] == moment.isoformat(timespec="seconds")
