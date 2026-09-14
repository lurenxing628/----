"""Delivery-owned SELECTs; no transaction, identity repair or latest lookup."""

from __future__ import annotations

from typing import NoReturn

from core.models.schedule_plan_role import (
    SOURCE_ADJUSTMENT_SCENARIO_ROWS,
    SOURCE_CANDIDATE_ROWS,
    SOURCE_SCHEDULE,
)
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import MAX_PLAN_TASKS
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository


def _binding_error() -> NoReturn:
    raise WorkbenchCommandRejected("plan_binding_invalid", "交付风险查询和指定的计划对不上，系统不会自动换计划。请刷新后重新选择计划。")


def _bounded(rows):
    if len(rows) > MAX_PLAN_TASKS:
        raise WorkbenchCommandRejected(
            "query_too_large", "整个计划或相关批次工序超过 10000 条上限，没有读取，也不会只给一部分。请缩小时间范围后重试。", 413,
        )
    return rows


class PlanDeliveryRepository(SchedulePlanQueryRepository):
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
            scenario = self.fetchone("SELECT scenario_id, base_version, base_plan_role, base_source_table, "
                                     "base_candidate_id, base_candidate_key, status, validation_status, row_count, "
                                     "issues_json FROM ScheduleAdjustmentScenario WHERE scenario_id = ?",
                                     (locator.scenario_id,))
            if scenario is None or scenario["status"] != "active":
                raise WorkbenchCommandRejected("plan_unavailable", "所选试调方案无效，系统不会改去读别的计划。请回「试调」重新选一个。")
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
        sql, extra = self._plan_rows_sql(source_table=identity.source_table, candidate_id=identity.candidate_id,
                                         scenario_id=identity.scenario_id)
        if identity.source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS:
            # The legacy SQL helper strips scenario keys; permanent keys are exact.
            extra = [identity.scenario_id]
        params = [identity.version] + extra
        # Admit before joins, parsing, aggregation or applying a visible range.
        _bounded(self.fetchall("SELECT id FROM (" + sql + ") LIMIT ?", params + [MAX_PLAN_TASKS + 1]))
        rows = self.fetchall("WITH plan_rows AS (" + sql + ") SELECT s.id AS schedule_id, s.version, "
                             "s.op_id, CAST(s.start_time AS TEXT) AS start_time, CAST(s.end_time AS TEXT) AS end_time, "
                             "s.machine_id,s.operator_id,bo.batch_id FROM plan_rows s LEFT JOIN BatchOperations bo ON bo.id = s.op_id "
                             "ORDER BY s.id", params)
        if any(row["batch_id"] is None for row in rows):
            raise WorkbenchCommandRejected("plan_unavailable", "计划里有安排找不到对应的批次工序，交付风险算不完整。请到批次管理核对。")
        return rows

    def batch_facts(self, keys):
        batches, operations = [], []
        for start in range(0, len(keys), 400):
            chunk = keys[start:start + 400]
            marks = ",".join("?" for _ in chunk)
            batches.extend(self.fetchall(
                "SELECT batch_id, part_no, part_name, CAST(due_date AS TEXT) AS due_date FROM Batches "
                "WHERE batch_id IN (" + marks + ") ORDER BY batch_id COLLATE BINARY", chunk,
            ))
            operations.extend(self.fetchall(
                "SELECT id AS op_id, batch_id, seq, piece_id FROM BatchOperations WHERE batch_id IN (" + marks +
                ") ORDER BY batch_id COLLATE BINARY, id LIMIT ?", chunk + [MAX_PLAN_TASKS + 1 - len(operations)],
            ))
            _bounded(operations)
        if {row["batch_id"] for row in batches} != set(keys):
            raise WorkbenchCommandRejected("plan_unavailable", "计划涉及的批次已经不在了，系统不会拿别的批次凑数。请到批次管理核对。")
        return batches, operations

    def completion_record(self, identity, scenario):
        if identity.source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS:
            return {"source": identity.source_table, "scenario": scenario}
        if identity.source_table == SOURCE_CANDIDATE_ROWS:
            row = self.fetchone("SELECT summary_json FROM ScheduleCandidate WHERE version = ? AND id = ?",
                                (identity.version, identity.candidate_id))
            if row is None:
                _binding_error()
            return {"source": identity.source_table, "summary": row["summary_json"]}
        history = self.get_history_identity_row(identity.version)
        if history is None:
            _binding_error()
        return {"source": SOURCE_SCHEDULE, "summary": history["result_summary"],
                "result_status": history["result_status"]}
