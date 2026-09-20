"""Delivery-owned admission and binding decisions over WorkbenchPlanDeliveryRepository facts."""

from __future__ import annotations

from typing import NoReturn

from core.models.schedule_plan_role import (
    SOURCE_ADJUSTMENT_SCENARIO_ROWS,
    SOURCE_CANDIDATE_ROWS,
    SOURCE_SCHEDULE,
)
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import MAX_PLAN_TASKS
from data.repositories.workbench_plan_delivery_repo import WorkbenchPlanDeliveryRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository


def _binding_error() -> NoReturn:
    raise WorkbenchCommandRejected("plan_binding_invalid", "交付风险数据与所选计划不一致，请重新选择计划。")


def _bounded(rows):
    if len(rows) > MAX_PLAN_TASKS:
        raise WorkbenchCommandRejected(
            "query_too_large", "整个计划或相关批次工序超过 10000 条上限。请缩小时间范围后重试。", 413,
        )
    return rows


def _task_query(identity):
    return {"version": identity.version, "source_table": identity.source_table,
            "candidate_id": identity.candidate_id, "scenario_id": identity.scenario_id}


class PlanDeliveryRepository(WorkbenchPlanDeliveryRepository):
    def validate_identity(self, scope, identity):
        locator = WorkbenchPlanIdentityRepository(self.conn, logger=self.logger).resolve_plan(scope.plan_ref)
        if (identity.version, identity.requested_plan_role, identity.effective_plan_role, identity.scenario_id) != (
            locator.version, locator.plan_role, locator.plan_role, locator.scenario_id,
        ) or identity.plan_resolution_status == "fallback_to_adopted":
            _binding_error()
        roles = self.list_plan_role_options(locator.version)
        option = next((row for row in roles if row["role"] == locator.plan_role), None)
        expected = (SOURCE_SCHEDULE, None, None) if option is None else (
            option["source_table"], option["candidate_id"], option["candidate_key"],
        )
        scenario = None
        if locator.scenario_id is not None:
            scenario = self.get_scenario_binding(locator.scenario_id)
            if scenario is None or scenario["status"] != "active":
                raise WorkbenchCommandRejected("plan_unavailable", "所选试调方案无效，请到「试调排产方案」重新选择。")
            if expected != (scenario["base_source_table"], scenario["base_candidate_id"], scenario["base_candidate_key"]):
                _binding_error()
            expected = (SOURCE_ADJUSTMENT_SCENARIO_ROWS, None, expected[2])
        if (identity.source_table, identity.candidate_id, identity.candidate_key) != expected:
            _binding_error()
        if option is not None and (option["candidate_status"] != "completed" or (
            option["source_table"] == SOURCE_CANDIDATE_ROWS and option["detail_saved"] != "yes"
        )):
            raise WorkbenchCommandRejected("plan_unavailable", "所选候选方案没有完整保存的明细，看不了。请回「选择排产方案」重新选一个。")
        return scenario

    def task_rows(self, identity):
        query = _task_query(identity)
        # Admit before joins, parsing, aggregation or applying a visible range.
        _bounded(self.list_task_ids_bounded(limit=MAX_PLAN_TASKS + 1, **query))
        rows = self.list_task_rows_with_batch(**query)
        if any(row["batch_id"] is None for row in rows):
            raise WorkbenchCommandRejected("plan_unavailable", "计划里有安排找不到对应的批次工序，交付风险算不完整。请到批次管理核对。")
        return rows

    def batch_facts(self, keys):
        batches, operations = [], []
        for start in range(0, len(keys), 400):
            chunk = keys[start:start + 400]
            batches.extend(self.list_batches_by_ids(chunk))
            operations.extend(self.list_batch_operations_by_ids(chunk, limit=MAX_PLAN_TASKS + 1 - len(operations)))
            _bounded(operations)
        if {row["batch_id"] for row in batches} != set(keys):
            raise WorkbenchCommandRejected("plan_unavailable", "计划涉及的批次已不存在，请到批次管理核对。")
        return batches, operations

    def completion_record(self, identity, scenario):
        if identity.source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS:
            return {"source": identity.source_table, "scenario": scenario}
        if identity.source_table == SOURCE_CANDIDATE_ROWS:
            row = self.get_candidate_summary(identity.version, identity.candidate_id)
            if row is None:
                _binding_error()
            return {"source": identity.source_table, "summary": row["summary_json"]}
        history = self.get_history_identity_row(identity.version)
        if history is None:
            _binding_error()
        return {"source": SOURCE_SCHEDULE, "summary": history["result_summary"],
                "result_status": history["result_status"]}
