"""Durable admission, real candidates, replay, and original-library preservation."""

import json

import pytest

from core.infrastructure.logging import OperationLogger
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.run.jobs_facts import capture_run_facts
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.run_jobs_support import connection, service  # noqa: F401
from tests.workbench.run_jobs_support import job_case as _job_case


def test_accept_and_real_candidate_result_preserve_original_database(job_case):
    case = job_case
    before = capture_run_facts(case.conn)
    accepted = case.accept()
    assert accepted["result"] == "accepted"
    assert accepted["data"]["state"] == "queued"
    assert capture_run_facts(case.conn) == before
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete"
    assert result["result_persisted"] is True
    assert result["progress"] is None
    assert result["plans"] == [] and result["plan_catalog_connected"] is False
    assert len(result["candidates"]) == 4
    assert capture_run_facts(case.conn) == before
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] == 4
    for row in case.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates"):
        artifact = json.loads(row[0])
        assert len(artifact["results"]) == len(artifact["validated_payload"]["schedule_rows"]) == 1
    with connection(case.path) as reopened:
        assert service(reopened).get(accepted["run_ref"]) == result
        assert service(reopened).lookup("run-request-00000001") == result


def test_replay_after_token_expiry_does_not_compute_or_reauthorize(job_case):
    case = job_case
    ref, token = case.intent()
    first = service(case.conn).accept(ref, token, "run-request-00000001")
    second = service(case.conn, enabled=False).accept(ref, None, "run-request-00000001")
    assert second["replayed"] is True
    assert second["receipt_ref"] == first["receipt_ref"]
    assert second["run_ref"] == first["run_ref"]
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 1
    with pytest.raises(WorkbenchCommandRejected) as conflict:
        service(case.conn).accept("another-input-ref", token, "run-request-00000001")
    assert conflict.value.code == "request_key_conflict"


@pytest.mark.parametrize("token", [None, "", "not-issued"])
def test_preflight_is_not_run_authorization(job_case, token):
    case = job_case
    ref = case.preflight()
    with pytest.raises(WorkbenchCommandRejected):
        service(case.conn).accept(ref, token, "run-request-00000001")
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 0


def test_disabled_preview_and_accept_are_closed(job_case):
    ref, token = job_case.intent()
    disabled = service(job_case.conn, enabled=False)
    context = disabled.preview(ref)["write_context"]
    assert context["write_token"] is None
    assert context["capabilities"]["scheduling.run"] is False
    with pytest.raises(WorkbenchCommandRejected) as error:
        disabled.accept(ref, token, "run-request-00000001")
    assert error.value.code == "run_worker_not_connected"


def test_preflight_fact_drift_rejected_before_any_admission(job_case):
    case = job_case
    ref, token = case.intent()
    case.conn.execute("UPDATE Machines SET name='changed unselected display fact'")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected) as error:
        service(case.conn).accept(ref, token, "run-request-00000001")
    assert error.value.code == "snapshot_stale"
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchRunJobs").fetchone()[0] == 0


def test_post_acceptance_fact_drift_records_failure_without_candidates(job_case):
    case = job_case
    accepted = case.accept()
    case.conn.execute("UPDATE Machines SET name='changed after accept'")
    case.conn.commit()
    before = capture_run_facts(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert error.value.code == "snapshot_stale"
    result = service(case.conn).get(accepted["run_ref"])
    assert result["state"] == "failed" and result["result_persisted"] is False
    assert capture_run_facts(case.conn) == before


def test_existing_official_history_and_legacy_candidates_are_preserved(job_case):
    case = job_case
    case.plan(1, [case.op_id])
    candidate = case.conn.execute("""INSERT INTO ScheduleCandidate
        (version,candidate_key,candidate_label,candidate_kind,status,detail_saved)
        VALUES (1,'legacy-preserved','Existing candidate','baseline','completed','yes')""").lastrowid
    case.conn.execute("""INSERT INTO ScheduleCandidateRows
        (version,candidate_id,op_id,machine_id,operator_id,start_time,end_time)
        VALUES (1,?,?,'M1','O1','2026-09-09 08:00:00','2026-09-09 08:45:00')""", (candidate, case.op_id))
    case.conn.commit()
    before = capture_run_facts(case.conn)
    accepted = case.accept()
    stored = case.conn.execute("SELECT baseline_json FROM WorkbenchRunJobs").fetchone()[0]
    baseline = json.loads(stored)
    assert baseline["plan_ref"] == case.plan_ref(1) and baseline["version"] == 1 and len(baseline["rows"]) == 1
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete"
    assert capture_run_facts(case.conn) == before


def test_actual_excluded_batch_produces_persisted_partial_result(job_case):
    case = job_case
    case.batch("B2")
    case.operation("B2")
    case.conn.execute("UPDATE Batches SET ready_status='no' WHERE batch_id='B2'")
    case.conn.commit()
    before = capture_run_facts(case.conn)
    accepted = case.accept(settings=case.settings("B1", "B2"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "partial" and result["result_persisted"] is True
    assert all(row["task_count"] == 1 for row in result["candidates"])
    payload = json.loads(case.conn.execute("SELECT result_json FROM WorkbenchRunReceipts").fetchone()[0])
    assert any(row["status"] == "skipped" for row in payload["dispositions"])
    assert capture_run_facts(case.conn) == before


def test_audit_writes_before_compute_and_before_persist_preserve_run(job_case, monkeypatch):
    from core.services.workbench.run import worker as run_worker

    case = job_case
    accepted = case.accept()
    captured = tuple(case.conn.execute("SELECT facts_json,facts_hash FROM WorkbenchRunJobs").fetchone())
    assert OperationLogger(case.conn).info("plugins", "load", detail={"startup": True})
    real_compute = run_worker.compute_candidate_run

    def compute_with_audit(*args, **kwargs):
        result = real_compute(*args, **kwargs)
        assert OperationLogger(case.conn).info("system", "backup", detail={"complete": True})
        return result

    monkeypatch.setattr(run_worker, "compute_candidate_run", compute_with_audit)
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    assert result["state"] == "complete" and result["result_persisted"] is True
    assert tuple(case.conn.execute("SELECT facts_json,facts_hash FROM WorkbenchRunJobs").fetchone()) == captured
    assert case.conn.execute("SELECT COUNT(*) FROM OperationLogs WHERE action IN ('load','backup')").fetchone()[0] == 2


@pytest.mark.parametrize("outcome,state", [("unchanged", "complete"), ("committed", "failed")])
def test_only_no_change_receipts_during_compute_preserve_run(job_case, monkeypatch, outcome, state):
    from core.models.workbench_command import WorkbenchCommandOutcome
    from core.services.workbench.commands import WorkbenchCommandService
    from core.services.workbench.run import worker as run_worker

    case = job_case
    accepted = case.accept()
    real_compute = run_worker.compute_candidate_run

    def compute_with_receipt(*args, **kwargs):
        result = real_compute(*args, **kwargs)
        # 计算期间另一条命令只留下回执：“无改动”回执不是现场变化；“已提交”回执保守地仍算变化。
        saved = WorkbenchCommandService(case.conn).execute(
            request_key="receipt-during-run-0001", action="calendar.defaults", context_ref="calendar-defaults",
            normalized_input={"periods": []}, guard=lambda: None,
            mutate=lambda _checked: WorkbenchCommandOutcome(outcome, {"saved": False}))
        assert saved["result"] == outcome and saved["replayed"] is False
        return result

    monkeypatch.setattr(run_worker, "compute_candidate_run", compute_with_receipt)
    if state == "complete":
        result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
        assert result["state"] == "complete" and result["result_persisted"] is True
    else:
        with pytest.raises(WorkbenchCommandRejected) as error:
            WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
        assert error.value.code == "snapshot_stale"
        assert service(case.conn).get(accepted["run_ref"])["state"] == "failed"


@pytest.mark.parametrize("raised,sanitized,code,message", [
    ("calendar", False, "invalid_calendar_shift", "工作日历里有班次时间读不出来或者填得不对，这次排产没有开始。请到工作日历按 08:30 这样改好。"),
    ("internal_input", False, "adoption_evidence_missing", "本次候选计算失败。请联系维护人员，再重新做排产检查。"),
    ("blocked", False, "input_blocked", "排产资料还有缺项，这次排产没有开始。请重新做排产检查，按检查结果补齐后再排产。"),
    ("app_error", True, "candidate_input_invalid", "结束日期填写不正确，请检查后重试。"),
    ("app_error", False, "candidate_computation_failed", "本次候选计算失败。请联系维护人员，再重新做排产检查。"),
    ("bug", True, "candidate_computation_failed", "本次候选计算失败。请联系维护人员，再重新做排产检查。")])
def test_failed_run_tells_the_real_reason_without_internal_text(job_case, raised, sanitized, code, message):
    # 失败已经确定：写给用户的原因原样给出；内部校验原文、SQL、路径只留在诊断里。
    from core.errors import ValidationError
    from core.models.workbench_run_compute import CandidateRunInputError
    from web.error_boundary import user_visible_app_error_message

    errors = {"calendar": CandidateRunInputError("invalid_calendar_shift", message),
              "internal_input": CandidateRunInputError("adoption_evidence_missing", "run.facts.Schedule"),
              "blocked": CandidateRunInputError("input_blocked", "排产资料还有缺项，不能开始。请先补齐下方列出的项。"),
              "app_error": ValidationError("end_date 不能早于 start_date", field="end_date"),
              "bug": RuntimeError("sqlite3.OperationalError: no such column x_y in /home/aps/core/x.py")}

    def fail(conn, row, on_progress):
        raise errors[raised]

    accepted = job_case.accept()
    worker = WorkbenchRunWorker(job_case.conn, compute_runner=fail,
                                app_error_message=user_visible_app_error_message if sanitized else None)
    with pytest.raises(type(errors[raised])):
        worker.execute(accepted["run_ref"])
    assert service(job_case.conn).get(accepted["run_ref"])["error"] == {"code": code, "message": message}
    stored = json.loads(job_case.conn.execute("SELECT result_json FROM WorkbenchRunReceipts").fetchone()[0])
    assert stored["diagnostic"] == {"exception_type": type(errors[raised]).__name__, "message": str(errors[raised])}


@pytest.mark.parametrize("raised,code", [("window", "candidate_input_invalid"), ("conflict", "candidate_input_invalid"),
                                         ("late_finish", "candidate_input_invalid"), ("all_held", "all_operations_frozen")])
def test_old_freeze_window_wording_becomes_the_hold_window_with_a_way_out(job_case, raised, code):
    """旧排产服务按“冻结窗口”“冻结期”说的失败，工作台改说不重排时段并给出路；线程和子进程两种算法一致。"""
    from core.errors import AppError, ErrorCode, ValidationError
    from core.models.workbench_run_compute import CandidateRunInputError
    from web.bootstrap.run_compute_process import _error_message
    from web.error_boundary import user_visible_app_error_message

    errors = {"window": ValidationError("冻结窗口内排程记录无法解析", field="freeze_window"),
              "conflict": AppError(ErrorCode.SCHEDULE_CONFLICT, "现场反馈和冻结窗口里的排程记录对不上，本次没有写入新排程。请刷新后重新排。",
                                   details={"reason": "execution_seed_conflict", "op_id": 1}),
              "late_finish": AppError(ErrorCode.SCHEDULE_CONFLICT, "已完工的前道工序有真实完工时间，后续工序不能排在它之前。",
                                      details={"reason": "execution_completed_downstream_before_actual_finish", "op_id": 2}),
              "all_held": CandidateRunInputError("all_operations_frozen", "冻结窗口内无可调整工序，本次未执行排产计算。")}

    def fail(conn, row, on_progress):
        raise errors[raised]

    accepted = job_case.accept()
    worker = WorkbenchRunWorker(job_case.conn, compute_runner=fail, app_error_message=user_visible_app_error_message)
    with pytest.raises(type(errors[raised])):
        worker.execute(accepted["run_ref"])
    error = service(job_case.conn).get(accepted["run_ref"])["error"]
    assert error["code"] == code and "不重排时段" in error["message"] and "冻结" not in error["message"]
    if raised != "all_held":
        assert _error_message(errors[raised])[2] == error["message"]
