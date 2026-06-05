from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from core.infrastructure.errors import ValidationError
from core.models.schedule_adjustment import (
    DRAFT_STATUS_SAVED_SCENARIO,
    SCENARIO_STATUS_ACTIVE,
    ScheduleAdjustmentScenario,
    ScheduleAdjustmentScenarioRow,
)
from data.repositories import ScheduleAdjustmentRepository, ScheduleAdjustmentScenarioRepository

from .execution_snapshot import ExecutionSnapshot, collect_execution_snapshot_for_plan_rows
from .gantt_adjustment_validation_service import GanttAdjustmentEvaluation, GanttAdjustmentValidationService


def _text(value: Any) -> str:
    return str(value or "").strip()


def _required_text(value: Any, *, field: str, label: str) -> str:
    text = _text(value)
    if not text:
        raise ValidationError(f"{label}不能为空。", field=field)
    return text


def _execution_plan_fields(evaluation: GanttAdjustmentEvaluation) -> Dict[str, Any]:
    resolution = evaluation.plan_resolution
    return {
        "version": getattr(resolution, "version", None),
        "source_table": getattr(resolution, "source_table", None),
        "effective_plan_role": getattr(resolution, "selected_role", None),
        "scenario_id": getattr(resolution, "scenario_id", None),
    }


class GanttAdjustmentScenarioService:
    """把通过校验的 Draft 保存为 Scenario 模拟方案，不写正式排产版本。"""

    def __init__(self, conn, logger=None):
        self.conn = conn
        self.logger = logger
        self.draft_repo = ScheduleAdjustmentRepository(conn, logger=logger)
        self.scenario_repo = ScheduleAdjustmentScenarioRepository(conn, logger=logger)
        self.validation_service = GanttAdjustmentValidationService(conn, logger=logger)

    def save_scenario(
        self,
        *,
        draft_id: Any,
        scenario_name: Optional[str] = None,
        created_by: Optional[str] = None,
        expected_base_version: Optional[Any] = None,
        expected_base_plan_role: Optional[Any] = None,
    ) -> ScheduleAdjustmentScenario:
        draft_key = _required_text(draft_id, field="draft_id", label="草稿编号")
        evaluation = self.validation_service.evaluate_draft(
            draft_id=draft_key,
            expected_base_version=expected_base_version,
            expected_base_plan_role=expected_base_plan_role,
        )
        if not evaluation.can_apply:
            raise ValidationError("草稿还有阻塞问题，不能保存为模拟方案。", field="draft_id")

        execution_snapshot = collect_execution_snapshot_for_plan_rows(
            self.conn,
            evaluation.adjusted_rows,
            _execution_plan_fields(evaluation),
            op_ids=[row.op_id for row in evaluation.adjusted_rows],
            logger=self.logger,
        )
        scenario = self._scenario_header(
            evaluation,
            scenario_name=scenario_name,
            created_by=created_by,
            execution_snapshot=execution_snapshot,
        )
        rows = [
            ScheduleAdjustmentScenarioRow(
                id=None,
                scenario_id=scenario.scenario_id,
                source_table=evaluation.plan_resolution.source_table,
                source_row_id=row.schedule_id,
                op_id=row.op_id,
                machine_id=row.machine_id,
                operator_id=row.operator_id,
                start_time=row.start.strftime("%Y-%m-%d %H:%M:%S"),
                end_time=row.end.strftime("%Y-%m-%d %H:%M:%S"),
                lock_status=row.lock_status,
                is_changed="yes" if row.is_changed else "no",
            )
            for row in evaluation.adjusted_rows
        ]
        with self.conn:
            created = self.scenario_repo.create_scenario(scenario, rows)
            self.draft_repo.update_draft_status(
                draft_id=evaluation.draft.draft_id,
                status=DRAFT_STATUS_SAVED_SCENARIO,
            )
        return created

    def _scenario_header(
        self,
        evaluation,
        *,
        scenario_name: Optional[str],
        created_by: Optional[str],
        execution_snapshot: ExecutionSnapshot,
    ) -> ScheduleAdjustmentScenario:
        resolution = evaluation.plan_resolution
        scenario_id = "scenario-" + uuid.uuid4().hex[:16]
        name = _text(scenario_name) or "模拟预览（未命名）"
        return ScheduleAdjustmentScenario(
            scenario_id=scenario_id,
            source_draft_id=evaluation.draft.draft_id,
            base_version=evaluation.draft.base_version,
            base_plan_role=evaluation.draft.base_plan_role,
            base_source_table=resolution.source_table,
            base_candidate_id=resolution.candidate_id,
            base_candidate_key=resolution.candidate_key,
            scenario_name=name,
            status=SCENARIO_STATUS_ACTIVE,
            validation_status=evaluation.status,
            issue_count=len(evaluation.issues),
            issues_json=json.dumps([issue.to_dict() for issue in evaluation.issues], ensure_ascii=False),
            execution_snapshot_revision=execution_snapshot.revision,
            execution_snapshot_op_ids=json.dumps(list(execution_snapshot.op_ids), ensure_ascii=False),
            execution_snapshot_op_count=int(execution_snapshot.op_count),
            created_by=_text(created_by) or evaluation.draft.created_by,
        )
