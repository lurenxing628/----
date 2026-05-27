from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Sequence, Set

from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.models import Schedule
from core.models.enums import SourceType
from core.models.operation_execution_event import (
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_EXCEPTION,
    EXECUTION_STATUS_PAUSED,
    EXECUTION_STATUS_PROCESSING,
)
from core.models.schedule_adjustment import (
    DRAFT_STATUS_PUBLISHED,
    DRAFT_STATUS_SAVED_SCENARIO,
    SCENARIO_STATUS_ACTIVE,
)
from core.models.schedule_plan_role import ROLE_ADOPTED
from core.services.scheduler.execution_fact_provider import ExecutionFactProvider
from core.services.scheduler.run.schedule_payload_contract import ValidatedSchedulePayload, ValidatedScheduleRow
from core.services.scheduler.run.schedule_persistence import validate_execution_guard_before_persist
from data.repositories import (
    ScheduleAdjustmentRepository,
    ScheduleAdjustmentScenarioRepository,
    ScheduleHistoryRepository,
    ScheduleRepository,
)

from .execution_snapshot import collect_execution_snapshot
from .gantt_adjustment_validation_service import GanttAdjustmentEvaluation, GanttAdjustmentValidationService

PUBLISH_CONFIRM_TEXT = "正式采用"


@dataclass(frozen=True)
class GanttAdjustmentPublishResult:
    scenario_id: str
    source_draft_id: str
    base_version: int
    base_plan_role: str
    new_version: int
    row_count: int
    change_count: int
    published_by: str
    reason: str
    validation_status: str
    issue_count: int

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


class GanttAdjustmentPublishService:
    """把已保存 Scenario 正式采用为新的 Schedule 版本。"""

    def __init__(self, conn, logger=None, op_logger=None):
        self.conn = conn
        self.logger = logger
        self.op_logger = op_logger
        self.draft_repo = ScheduleAdjustmentRepository(conn, logger=logger)
        self.scenario_repo = ScheduleAdjustmentScenarioRepository(conn, logger=logger)
        self.schedule_repo = ScheduleRepository(conn, logger=logger)
        self.history_repo = ScheduleHistoryRepository(conn, logger=logger)
        self.validation_service = GanttAdjustmentValidationService(conn, logger=logger)

    def publish_scenario(
        self,
        *,
        scenario_id: Any,
        confirm_text: Any,
        reason: Any,
        published_by: Any = None,
        expected_base_version: Any = None,
        expected_base_plan_role: Any = None,
    ) -> GanttAdjustmentPublishResult:
        scenario_key = _required_text(scenario_id, field="scenario_id", label="模拟预览")
        clean_reason = _required_text(reason, field="reason", label="正式采用原因")
        operator = _trusted_operator(published_by)
        _require_confirm(confirm_text)

        scenario = self.scenario_repo.get_scenario(scenario_key)
        if scenario is None:
            raise ValidationError("模拟方案不存在。", field="scenario_id")
        if scenario.status != SCENARIO_STATUS_ACTIVE:
            raise ValidationError("只有可预览的模拟方案才能正式采用。", field="scenario_id")
        _check_expected_base(scenario.base_version, scenario.base_plan_role, expected_base_version, expected_base_plan_role)
        if str(scenario.base_plan_role or "").strip() != ROLE_ADOPTED:
            raise ValidationError("只有从正式采用方案调整出来的模拟方案，才能正式采用。", field="base_plan_role")

        evaluation = self.validation_service.evaluate_draft(
            draft_id=scenario.source_draft_id,
            expected_base_version=scenario.base_version,
            expected_base_plan_role=scenario.base_plan_role,
            allowed_statuses=(DRAFT_STATUS_SAVED_SCENARIO,),
        )
        if not evaluation.can_apply:
            raise ValidationError("模拟方案重新校验后仍有阻塞问题，不能正式采用。", field="scenario_id")

        scenario_rows = self.scenario_repo.list_rows(scenario.scenario_id)
        _check_scenario_rows(scenario_rows, evaluation)

        with self.conn:
            self.conn.execute("BEGIN IMMEDIATE")
            latest_version = self.history_repo.get_latest_version()
            if latest_version != scenario.base_version:
                raise ValidationError("模拟方案的调整依据版本已经不是最新正式版本，请重新模拟后再正式采用。", field="base_version")
            _check_execution_snapshot_current(self, scenario)
            _validate_scenario_execution_guard(self, scenario=scenario, evaluation=evaluation, scenario_rows=scenario_rows)
            new_version = self.history_repo.allocate_next_version()
            claimed = self.scenario_repo.mark_published(
                scenario_id=scenario.scenario_id,
                new_version=new_version,
                published_by=operator,
                reason=clean_reason,
            )
            if claimed is None:
                raise ValidationError("模拟方案已经被采用或状态已变化，请刷新后重试。", field="scenario_id")
            self.schedule_repo.bulk_create(_schedule_rows(scenario_rows, version=new_version))
            self.history_repo.create(
                _history_payload(
                    scenario=scenario,
                    evaluation=evaluation,
                    new_version=new_version,
                    published_by=operator,
                    reason=clean_reason,
                )
            )
            self.draft_repo.update_draft_status(
                draft_id=scenario.source_draft_id,
                status=DRAFT_STATUS_PUBLISHED,
                reason=clean_reason,
            )
            result = GanttAdjustmentPublishResult(
                scenario_id=scenario.scenario_id,
                source_draft_id=scenario.source_draft_id,
                base_version=scenario.base_version,
                base_plan_role=scenario.base_plan_role,
                new_version=new_version,
                row_count=len(scenario_rows),
                change_count=len(evaluation.changes),
                published_by=operator,
                reason=clean_reason,
                validation_status=evaluation.status,
                issue_count=len(evaluation.issues),
            )
            self._log_publish(result)
        return result

    def _log_publish(self, result: GanttAdjustmentPublishResult) -> None:
        if self.op_logger is None:
            raise ValidationError("缺少操作日志记录器，不能正式采用。", field="operator")
        detail = result.to_dict()
        try:
            ok = self.op_logger.info(
                module="scheduler",
                action="publish_scenario",
                target_type="schedule",
                target_id=str(result.new_version),
                operator=result.published_by,
                detail=detail,
                raise_on_fail=True,
            )
        except Exception as exc:
            raise AppError(ErrorCode.DB_TRANSACTION_ERROR, "正式采用操作日志写入失败，已取消发布。", cause=exc) from exc
        if not ok:
            raise AppError(ErrorCode.DB_TRANSACTION_ERROR, "正式采用操作日志写入失败，已取消发布。")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _required_text(value: Any, *, field: str, label: str) -> str:
    text = _text(value)
    if not text:
        raise ValidationError(f"{label}不能为空。", field=field)
    return text


def _require_confirm(confirm_text: Any) -> None:
    if _text(confirm_text) != PUBLISH_CONFIRM_TEXT:
        raise ValidationError("请二次确认输入“正式采用”。", field="confirm_text")


def _trusted_operator(value: Any) -> str:
    return _text(value) or "system"


def _check_expected_base(actual_version: int, actual_role: str, expected_version: Any, expected_role: Any) -> None:
    if expected_version is not None and _text(expected_version) != str(actual_version):
        raise ValidationError("页面方案的调整依据版本已变化，请刷新后重试。", field="base_version")
    if expected_role is not None and _text(expected_role) != actual_role:
        raise ValidationError("页面方案的调整依据口径已变化，请刷新后重试。", field="base_plan_role")


def _check_scenario_rows(rows: Sequence[Any], evaluation: GanttAdjustmentEvaluation) -> None:
    if not rows:
        raise ValidationError("模拟方案没有可发布的排程明细。", field="scenario_id")
    expected = {
        row.op_id: (
            _none_to_text(row.machine_id),
            _none_to_text(row.operator_id),
            row.start.strftime("%Y-%m-%d %H:%M:%S"),
            row.end.strftime("%Y-%m-%d %H:%M:%S"),
            _none_to_text(row.lock_status),
        )
        for row in evaluation.adjusted_rows
    }
    actual = {
        row.op_id: (
            _none_to_text(row.machine_id),
            _none_to_text(row.operator_id),
            str(row.start_time),
            str(row.end_time),
            _none_to_text(row.lock_status),
        )
        for row in rows
    }
    if actual != expected:
        raise ValidationError("模拟方案明细和草稿重新校验结果不一致，请重新保存模拟方案。", field="scenario_id")


def _scenario_snapshot_op_ids(scenario: Any) -> List[int]:
    text = str(getattr(scenario, "execution_snapshot_op_ids", "") or "").strip()
    if not text:
        raise AppError(
            ErrorCode.SCHEDULE_CONFLICT,
            "模拟方案缺少现场状态快照，请重新保存模拟方案后再正式采用。",
            details={"reason": "missing_execution_snapshot"},
        )
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AppError(
            ErrorCode.SCHEDULE_CONFLICT,
            "模拟方案的现场状态快照已损坏，请重新保存模拟方案后再正式采用。",
            details={"reason": "invalid_execution_snapshot"},
            cause=exc,
        ) from exc
    if not isinstance(raw, list):
        raise AppError(
            ErrorCode.SCHEDULE_CONFLICT,
            "模拟方案的现场状态快照已损坏，请重新保存模拟方案后再正式采用。",
            details={"reason": "invalid_execution_snapshot"},
        )
    op_ids: List[int] = []
    for value in raw:
        try:
            op_id = int(value)
        except (TypeError, ValueError) as exc:
            raise AppError(
                ErrorCode.SCHEDULE_CONFLICT,
                "模拟方案的现场状态快照已损坏，请重新保存模拟方案后再正式采用。",
                details={"reason": "invalid_execution_snapshot"},
                cause=exc,
            ) from exc
        if op_id > 0:
            op_ids.append(int(op_id))
    if not op_ids:
        raise AppError(
            ErrorCode.SCHEDULE_CONFLICT,
            "模拟方案缺少现场状态快照，请重新保存模拟方案后再正式采用。",
            details={"reason": "missing_execution_snapshot"},
        )
    return sorted(set(op_ids))


def _check_execution_snapshot_current(service: GanttAdjustmentPublishService, scenario: Any) -> None:
    expected_revision = str(getattr(scenario, "execution_snapshot_revision", "") or "").strip()
    if not expected_revision:
        raise AppError(
            ErrorCode.SCHEDULE_CONFLICT,
            "模拟方案缺少现场状态快照，请重新保存模拟方案后再正式采用。",
            details={"reason": "missing_execution_snapshot"},
        )
    op_ids = _scenario_snapshot_op_ids(scenario)
    current = collect_execution_snapshot(service.conn, op_ids, logger=service.logger)
    if current.revision != expected_revision:
        raise AppError(
            ErrorCode.SCHEDULE_CONFLICT,
            "现场状态刚刚变了，这个模拟方案没有正式采用。请刷新后重新模拟。",
            details={
                "reason": "execution_snapshot_changed",
                "execution_snapshot_op_count": int(len(op_ids)),
            },
        )


def _parse_schedule_time(value: Any, *, field: str) -> datetime:
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValidationError(f"{field}写法不对，请重新保存模拟方案。", field=field)


def _scenario_validated_payload(rows: Sequence[Any]) -> ValidatedSchedulePayload:
    schedule_rows = [
        ValidatedScheduleRow(
            op_id=int(row.op_id),
            machine_id=row.machine_id,
            operator_id=row.operator_id,
            start_time=_parse_schedule_time(row.start_time, field="开始时间"),
            end_time=_parse_schedule_time(row.end_time, field="结束时间"),
            source=SourceType.INTERNAL.value,
        )
        for row in rows
    ]
    return ValidatedSchedulePayload(
        schedule_rows=schedule_rows,
        scheduled_op_ids={int(row.op_id) for row in schedule_rows},
        assigned_by_op_id={
            int(row.op_id): {"machine_id": row.machine_id, "operator_id": row.operator_id}
            for row in schedule_rows
        },
    )


def _scenario_validation_operations(evaluation: GanttAdjustmentEvaluation) -> List[Any]:
    return [
        SimpleNamespace(id=int(row.op_id), batch_id=row.batch_id, seq=int(row.seq or 0))
        for row in list(evaluation.adjusted_rows or [])
    ]


def _validate_scenario_execution_guard(
    service: GanttAdjustmentPublishService,
    *,
    scenario: Any,
    evaluation: GanttAdjustmentEvaluation,
    scenario_rows: Sequence[Any],
) -> None:
    op_ids = _scenario_snapshot_op_ids(scenario)
    facts = ExecutionFactProvider(service.conn, logger=service.logger).facts_by_op_id(op_ids)
    exception_op_ids = {
        int(op_id)
        for op_id, fact in facts.items()
        if str(fact.actual_status or "").strip().lower() == EXECUTION_STATUS_EXCEPTION
    }
    if exception_op_ids:
        raise AppError(
            ErrorCode.SCHEDULE_CONFLICT,
            "存在异常中的工序，请先处理现场异常后再正式采用模拟方案。",
            details={"reason": "execution_exception_blocks_scenario_publish", "op_ids": sorted(exception_op_ids)},
        )

    fixed_op_ids: Set[int] = {
        int(op_id)
        for op_id, fact in facts.items()
        if str(fact.actual_status or "").strip().lower() in (EXECUTION_STATUS_PROCESSING, EXECUTION_STATUS_PAUSED)
    }
    completed_op_ids: Set[int] = {
        int(op_id)
        for op_id, fact in facts.items()
        if str(fact.actual_status or "").strip().lower() == EXECUTION_STATUS_COMPLETED
    }
    validate_execution_guard_before_persist(
        service,
        validated_schedule_payload=_scenario_validated_payload(scenario_rows),
        execution_guard_state_revisions={int(op_id): fact.state_revision for op_id, fact in facts.items()},
        execution_facts=facts,
        execution_fixed_op_ids=fixed_op_ids,
        execution_completed_op_ids=completed_op_ids,
        execution_snapshot_revision=scenario.execution_snapshot_revision,
        execution_snapshot_op_ids=op_ids,
        payload_validation_operations=_scenario_validation_operations(evaluation),
    )


def _schedule_rows(rows: Sequence[Any], *, version: int) -> Sequence[Schedule]:
    return [
        Schedule(
            id=None,
            op_id=row.op_id,
            machine_id=row.machine_id,
            operator_id=row.operator_id,
            start_time=row.start_time,
            end_time=row.end_time,
            lock_status=row.lock_status or "unlocked",
            version=version,
        )
        for row in rows
    ]


def _history_payload(
    *,
    scenario: Any,
    evaluation: GanttAdjustmentEvaluation,
    new_version: int,
    published_by: str,
    reason: str,
) -> Dict[str, Any]:
    summary = {
        "source": "gantt_scenario_publish",
        "scenario_id": scenario.scenario_id,
        "scenario_name": scenario.scenario_name,
        "source_draft_id": scenario.source_draft_id,
        "base_version": scenario.base_version,
        "base_plan_role": scenario.base_plan_role,
        "new_version": int(new_version),
        "change_count": len(evaluation.changes),
        "validation_status": evaluation.status,
        "issue_count": len(evaluation.issues),
        "reason": reason,
        "execution_snapshot": {
            "execution_snapshot_revision": scenario.execution_snapshot_revision,
            "execution_snapshot_op_ids": _scenario_snapshot_op_ids(scenario),
            "execution_snapshot_op_count": int(scenario.execution_snapshot_op_count or 0),
        },
    }
    return {
        "version": int(new_version),
        "strategy": "manual",
        "batch_count": _count_batches(evaluation.adjusted_rows),
        "op_count": len(evaluation.adjusted_rows),
        "result_status": "success",
        "result_summary": json.dumps(summary, ensure_ascii=False),
        "created_by": published_by,
    }


def _count_batches(rows: Sequence[Any]) -> int:
    return len({row.batch_id for row in rows if row.batch_id})


def _none_to_text(value: Any) -> str:
    return str(value or "").strip()
