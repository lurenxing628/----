"""Snapshot-local indexes for immutable identities, locks and execution facts."""

from core.models.workbench_trial import issue


class TrialProtection:
    def __init__(self, live):
        tables = live["facts"]["tables"]
        self.identities = {row["ref"]: row for row in tables["WorkbenchPlanSourceRefs"] if row["kind"] == "operation"}
        self.latest = {}
        for row in tables["Schedule"]:
            old = self.latest.get(row["op_id"])
            if old is None or (row["version"], row["id"]) > (old["version"], old["id"]):
                self.latest[row["op_id"]] = row
        self.execution = live["execution"]
        self.operations = {row["id"]: row for row in tables["BatchOperations"]}
        self.batches = {row["batch_id"]: row for row in tables["Batches"]}

    def check(self, row):
        return self._identity_and_lock(row) or self._execution(row) or self._closed(row)

    def _identity_and_lock(self, row):
        original, ref = row["original"], row["task_ref"]
        op_id = original["operation"]["id"]
        identity = self.identities.get(row["operation_ref"])
        if identity is None or identity["active"] != 1 or identity["source_key"] != str(op_id):
            return issue("operation_identity_changed", "该工序已删除或被替换，无法继续调整。", ref)
        if not original["lock_known"]:
            return issue("lock_state_unknown", "这道工序是不是已固定读不到，这里不当成未固定处理。", ref)
        latest = self.latest.get(op_id)
        if original["locked"] or (latest is not None and latest["lock_status"] != "unlocked"):
            return issue("task_locked", "固定工序不可调整。", ref)
        return None

    def _execution(self, row):
        original, ref = row["original"], row["task_ref"]
        execution = self.execution.get(row["operation_ref"])
        if execution is None or execution["data_quality"] == "invalid":
            return issue("execution_unproven", "这道工序的报工记录缺失或有坏数据，不能确认可以调整。", ref)
        for facts in (execution, original["execution"]):
            if facts and (facts["execution_state"] != "unreported" or facts["reports"] or facts["legacy_facts"]
                          or facts["first_actual_start"] or facts["confirmed_finish"]):
                return issue("execution_protected", "这道工序已经开工、报工或完工，不能用试调改安排。", ref)
        return None

    def _closed(self, row):
        op_id, ref = row["original"]["operation"]["id"], row["task_ref"]
        op = self.operations.get(op_id)
        batch = self.batches.get(op["batch_id"]) if op else None
        if op is None or batch is None or op["status"] not in ("pending", "scheduled") or batch["status"] not in ("pending", "scheduled", "processing"):
            return issue("operation_not_editable", "原工序或批次已关闭、跳过，或状态不能证明可调整。", ref)
        return None
