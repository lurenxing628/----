"""Delivery-owned admission and binding decisions over WorkbenchPlanDeliveryRepository facts."""

from __future__ import annotations

from typing import NoReturn

from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories.workbench_plan_delivery_repo import WorkbenchPlanDeliveryRepository


def _binding_error() -> NoReturn:
    raise WorkbenchCommandRejected("plan_binding_invalid", "交付风险数据与所选计划不一致，请重新选择计划。")


class PlanDeliveryRepository(WorkbenchPlanDeliveryRepository):
    def validate_identity(self, scope, identity, *, context):
        locator = context.resolve(scope.plan_ref)
        if (identity.version, identity.requested_plan_role, identity.effective_plan_role) != (
            locator.version, locator.plan_role, locator.plan_role,
        ):
            _binding_error()
        if locator.plan_role != ROLE_ADOPTED or identity.source_table != SOURCE_SCHEDULE:
            _binding_error()

    def task_rows(self, *, context, entry):
        details = context.detail_rows(entry)
        fields = ("schedule_id", "version", "op_id", "machine_id", "operator_id", "batch_id")
        rows = [{**{key: row[key] for key in fields},
                 "start_time": row["start_time"],
                 "end_time": row["end_time"],
                 **({"_point_work": row["_point_work"]} if row.get("_point_work") else {})}
                for row in sorted(details, key=lambda row: row["schedule_id"])]
        if any(row["batch_id"] is None for row in rows):
            raise WorkbenchCommandRejected("plan_unavailable", "计划里有安排找不到对应的批次工序，交付风险算不完整。请到批次管理核对。")
        return rows

    def batch_facts(self, keys):
        batches, operations = [], []
        for start in range(0, len(keys), 400):
            chunk = keys[start:start + 400]
            batches.extend(self.list_batches_by_ids(chunk))
            operations.extend(self.list_batch_operations_by_ids(chunk))
        if {row["batch_id"] for row in batches} != set(keys):
            raise WorkbenchCommandRejected("plan_unavailable", "计划涉及的批次已不存在，请到批次管理核对。")
        return batches, operations

    def deferred_batch_keys(self, operation_ids):
        values, rows = sorted(operation_ids), []
        for start in range(0, len(values), 400):
            rows.extend(self.list_operation_batch_ids(values[start:start + 400]))
        issues = [] if {row["op_id"] for row in rows} == operation_ids else ["deferred_operation_source_missing"]
        return {row["batch_id"] for row in rows}, issues

    def completion_record(self, identity, *, context):
        history = context.history(identity.version)
        if history is None:
            _binding_error()
        return {"source": SOURCE_SCHEDULE, "summary": history["result_summary"],
                "result_status": history["result_status"]}
