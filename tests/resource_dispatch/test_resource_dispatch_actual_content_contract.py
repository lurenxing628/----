"""实际记录按原内容确认，并保留现场事件的原键、状态版本和事务。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from core.errors import AppError, ErrorCode, ValidationError
from core.services.scheduler.resource_dispatch.actual_import import preview_token
from core.services.scheduler.resource_dispatch.actual_record_service import ResourceDispatchActualRecordService
from tests.operation_execution.operation_execution_state_revision_support import (
    _connect,
    _context,
    _event_count,
    _seed_plan,
)


def _actual_payload():
    return {
        "actual_start_time": "2026-05-01 08:10:00",
        "pause_start_time": "2026-05-01 08:20:00",
        "pause_end_time": "2026-05-01 08:30:00",
        "pause_reason": "equipment", "pause_remark": "更换刀具",
        "exception_time": "2026-05-01 08:40:00",
        "exception_reason": "equipment", "exception_severity": "low",
        "exception_remark": "刀具损坏",
        "actual_finish_time": "2026-05-01 08:50:00",
        "quantity_done": 1, "quantity_scrapped": 0,
        "feedback_person": "张三", "remark": "完成首件",
    }


def test_actual_import_requires_original_task_ownership_and_compares_typed_rows(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = ResourceDispatchActualRecordService(conn)
        query = {"version": 1, "period_preset": "custom", "start_date": "2026-05-01", "end_date": "2026-05-01"}
        tasks = service._task_refs_from_context(service._execution_context_for_write(**query))
        assert len(tasks) == 1
        legacy_code = tasks[0].task_code.rsplit("-task_", 1)[0] + "-task_OP10_0123456789ab"
        rows = [{"sheet": "任务反馈", "row_number": 2, "任务识别码": legacy_code,
                 "实际开工时间": "2026-05-01 08:10:00", "实际完工时间": "2026-05-01 08:50:00",
                 "完成数量": 1, "报废数量": 0, "反馈人": "张三", "备注": "完成首件"}]
        unknown = service._preview_raw_rows(rows, **query)
        assert unknown.summary["can_confirm"] is False
        assert unknown.summary["error_count"] == 1
        assert "原任务归属" in unknown.rows[0]["message"]
        with pytest.raises(ValidationError):
            service.confirm_import(rows, preview_token(rows, query), **query)
        assert _event_count(conn) == 0
        # An actually retained task-code mapping is read exactly as issued.
        mapped = service.previewer.preview(rows, [replace(tasks[0], task_code=legacy_code)])
        assert mapped.summary["can_confirm"] is True
        assert mapped.raw_rows[0]["任务识别码"] == legacy_code
        rows = [dict(rows[0], 任务识别码=tasks[0].task_code)]
        preview = service._preview_raw_rows(rows, **query)
        assert preview.summary["can_confirm"] is True
        assert preview.raw_rows[0]["任务识别码"] == tasks[0].task_code
        token = preview_token(preview.raw_rows, query)
        assert token != preview_token([dict(rows[0], 完成数量=True)], query)
        assert token != preview_token([dict(rows[0], 完成数量=1.0)], query)
        assert preview_token(rows, {"version": True}) != preview_token(rows, {"version": 1})
        with pytest.raises(ValidationError):
            service.confirm_import([dict(rows[0], 完成数量=True)], token, **query)
        assert _event_count(conn) == 0

        first = service.confirm_import(rows, token, **query)
        assert first["summary"]["added_events"] == 2
        original_keys = [row[0] for row in conn.execute("SELECT idempotency_key FROM OperationExecutionEvents ORDER BY id")]
        assert all(key.startswith("resource-dispatch-actual-v2:") for key in original_keys)
        assert conn.execute("SELECT COUNT(*) FROM OperationExecutionEvents WHERE request_fingerprint IS NOT NULL").fetchone()[0] == 0
        replay = service.confirm_import(rows, token, **query)
        assert replay["summary"]["added_events"] == 0
        assert _event_count(conn) == 2
        changed = [dict(rows[0], 完成数量=2)]
        with pytest.raises(AppError) as conflict:
            service.confirm_import(changed, preview_token(changed, query), **query)
        assert conflict.value.details["reason"] == "idempotency_conflict"
        assert [row[0] for row in conn.execute("SELECT idempotency_key FROM OperationExecutionEvents ORDER BY id")] == original_keys
    finally:
        conn.close()


def test_manual_actual_replay_preserves_saved_legacy_event_keys_and_original_revisions(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = ResourceDispatchActualRecordService(conn)
        payload = _actual_payload()
        first = service.record_actual_situation(_context(), payload)
        assert first["written"] == 5
        assert first["state"].current_status == "completed"
        original_events = list(conn.execute("SELECT id, event_type, previous_state_revision FROM OperationExecutionEvents ORDER BY id"))
        assert [row["event_type"] for row in original_events] == ["start", "pause", "resume", "exception", "finish"]
        query = {"version": 1, "period_preset": "custom", "start_date": "2026-05-01", "end_date": "2026-05-01"}
        task = service._task_refs_from_context(service._execution_context_for_write(**query))[0]
        rows = [{"sheet": "任务反馈", "row_number": 2, "任务识别码": task.task_code,
                 "实际开工时间": payload["actual_start_time"], "实际完工时间": payload["actual_finish_time"],
                 "完成数量": 1, "报废数量": 0, "异常时间": payload["exception_time"],
                 "异常原因": "equipment", "异常严重程度": "low", "异常说明": "刀具损坏",
                 "反馈人": "张三", "备注": "完成首件"},
                {"sheet": "暂停明细", "row_number": 2, "任务识别码": task.task_code,
                 "暂停开始时间": payload["pause_start_time"], "暂停结束时间": payload["pause_end_time"],
                 "暂停原因": "equipment", "暂停说明": "更换刀具", "反馈人": "张三"}]
        # New keys retain their origin; an import cannot claim a manual submission.
        assert service._preview_raw_rows(rows, **query).summary["can_confirm"] is False
        for index, row in enumerate(original_events, start=1):
            conn.execute("UPDATE OperationExecutionEvents SET idempotency_key=?, request_fingerprint=? WHERE id=?",
                         ("resource-dispatch-actual-" + str(index) * 16, "original-event-" + str(index), row["id"]))
        conn.commit()
        originals = [tuple(row) for row in conn.execute("SELECT id, idempotency_key, request_fingerprint, previous_state_revision FROM OperationExecutionEvents ORDER BY id")]
        assert service.actual_payload_replay_state_revision(_context(), payload) == "10:0:0"
        replay = service.record_actual_situation(_context(), payload)
        assert replay["written"] == 0
        assert replay["result"].idempotency_reused is True
        assert replay["result"].event.id == original_events[-1]["id"]
        imported_replay = service.confirm_import(rows, preview_token(rows, query), **query)
        assert imported_replay["summary"]["added_events"] == 0
        for mutation in ({"quantity_done": 2}, {"feedback_person": "李四"}, {"remark": "改后的说明"}):
            with pytest.raises(AppError) as conflict:
                service.record_actual_situation(_context(), dict(payload, **mutation))
            assert conflict.value.details["reason"] == "idempotency_conflict"
        with pytest.raises(ValidationError):
            service.record_actual_situation(_context(), dict(payload, quantity_done=True))
        assert [tuple(row) for row in conn.execute("SELECT id, idempotency_key, request_fingerprint, previous_state_revision FROM OperationExecutionEvents ORDER BY id")] == originals
        assert _event_count(conn) == 5
    finally:
        conn.close()


def test_manual_actual_keeps_final_transaction_and_current_official_revision(tmp_path: Path, monkeypatch) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_plan(conn)
        service = ResourceDispatchActualRecordService(conn)

        def reject_finish(*args, **kwargs):
            raise AppError(ErrorCode.SCHEDULE_CONFLICT, "现场完工写入失败。", details={"reason": "finish_write_failed"})

        with monkeypatch.context() as patch:
            patch.setattr(service.feedback_service, "finish_operation", reject_finish)
            with pytest.raises(AppError) as rejected:
                service.record_actual_situation(_context(), _actual_payload())
            assert rejected.value.details["reason"] == "finish_write_failed"
        assert _event_count(conn) == 0
        payload = {"actual_start_time": "2026-05-01 08:10:00", "feedback_person": "张三", "idempotency_key": "A"}
        first = service.record_actual_situation(_context(), payload)
        assert service.actual_payload_replay_state_revision(_context(), payload) == "10:0:0"
        assert service.record_actual_situation(_context(), payload)["written"] == 0
        other_submission = dict(payload, idempotency_key="B")
        assert service.actual_payload_replay_state_revision(_context(), other_submission) is None
        with pytest.raises(ValidationError):
            service.record_actual_situation(_context(), other_submission)
        assert _event_count(conn) == 1
        exception = {"exception_time": "2026-05-01 08:20:00", "exception_reason": "equipment",
                     "exception_severity": "low", "exception_remark": "刀具损坏", "feedback_person": "张三"}
        with pytest.raises(AppError) as stale:
            service.record_actual_situation(_context(), exception)
        assert stale.value.details["reason"] == "stale_state_revision"
        with pytest.raises(AppError) as comparison:
            service.record_actual_situation(replace(_context(), requested_plan_role="baseline_best",
                effective_plan_role="baseline_best", source_table="candidate_rows", expected_state_revision=first["state"].state_revision), payload)
        assert comparison.value.details["reason"] == "not_current_official_plan"
        conn.execute("INSERT INTO ScheduleHistory(version,strategy,batch_count,op_count,result_status,result_summary,created_by) VALUES (2,'priority_first',0,0,'success','{}','pytest')")
        conn.commit()
        with pytest.raises(AppError) as old_plan:
            service.record_actual_situation(_context(), payload)
        assert old_plan.value.details["reason"] == "not_current_official_plan"
        assert _event_count(conn) == 1
    finally:
        conn.close()
