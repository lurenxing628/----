"""Hours-file domain operations; the coordinator owns file/scope/snapshot binding.

The caller must re-preview identical rows against complete current facts under
BEGIN IMMEDIATE before apply. This layer requires that outer transaction, adds
its own savepoint, and never records or refreshes process-stage confirmations.
"""

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_commands import process_number
from core.services.workbench.process_file_hours_preview import HoursFilePreview, protect_hours_preview
from core.services.workbench.process_quota_protection import ProcessQuotaProtection, quota_skip


class ProcessHoursFileOperations:
    def __init__(self, conn, logger=None):
        self.conn, self.logger = conn, logger

    def preview_rows(self, decoded_rows, facts, target_ref=None):
        rows, extra = HoursFilePreview(facts, target_ref).build(decoded_rows)
        locks = ProcessQuotaProtection(self.conn).read_locks(
            [row["expected"]["operation_ref"] for row in rows if row["expected"] is not None])
        extra.update(protect_hours_preview(rows, locks))
        extra["zero_review_required"] = any(row["requires_confirmation"] for row in rows)
        return rows, extra

    def apply_rows(self, rows, *, discard_group_refs, confirm_zero_unit_hours):
        if not self.conn.in_transaction:
            raise RuntimeError("工时文件写入必须在外层 BEGIN IMMEDIATE 事务中执行。")
        with TransactionManager(self.conn).transaction():
            self._check_rows(rows, discard_group_refs, confirm_zero_unit_hours)
            current, locks = ProcessQuotaProtection(self.conn).current(
                [row["expected"]["operation_ref"] for row in rows])
            skipped = self._skipped_rows(rows, current, locks)
            writable = [row for row in rows if row["row"] not in skipped]
            if any(row["after"]["source"] == "internal" and row["after"]["unit_hours"] == 0
                   for row in writable) and not confirm_zero_unit_hours:
                raise WorkbenchCommandRejected("zero_unit_hours_review", "有单件工时是 0 的工序。请勾选确认已复核后再导入。", 422)
            groups = self._group_updates(writable)
            results, affected = [], set()
            for row in rows:
                if row["row"] in skipped:
                    results.append({"row": row["row"], "result": "skipped", "entity_ref": row["entity_ref"],
                                    "business_code": row["business_code"], "sequence": row["sequence"],
                                    "skip_reason": skipped[row["row"]]})
                    continue
                self._operation_update(row)
                affected.add(row["expected"]["part_ref"])
                results.append({"row": row["row"], "result": "committed" if row["result"] == "update" else "unchanged",
                                "entity_ref": row["entity_ref"], "business_code": row["business_code"],
                                "sequence": row["sequence"]})
            for group, total in groups.values():
                self._update("ExternalGroups", "group_id", group["group_id"], group, {"total_days": total})
            return results, sorted(affected)

    @staticmethod
    def _check_rows(rows, discarded, zero_ack):
        if type(discarded) is not list or discarded:
            raise WorkbenchCommandRejected("group_discard_mismatch", "工时导入不会解除外协组，请不要提交要解除的外协组。", 422)
        if type(zero_ack) is not bool:
            raise WorkbenchCommandRejected("invalid_input", "必须明确提供是否已复核零工时。", 422)
        if any(row["errors"] or row["result"] not in ("update", "unchanged", "skipped") or row["input"] is None for row in rows):
            raise WorkbenchCommandRejected("constraint_conflict", "预检里有被拒绝的行，这批一条都没写入。请改好文件后重新预检。", 422)
        refs = [row["expected"]["operation_ref"] for row in rows]
        if len(refs) != len(set(refs)):
            raise WorkbenchCommandRejected("duplicate_entry", "这批里有重复工序，一条都没写入。请合并重复行后重新导入。", 422)

    @staticmethod
    def _skipped_rows(rows, current, locks):
        skipped = {}
        for row in rows:
            ref = row["expected"]["operation_ref"]
            old = row["expected"]["operation"]
            live = current[ref]
            if old["id"] != live["id"] or old["part_no"] != live["part_no"] or old["seq"] != live["seq"]:
                raise WorkbenchCommandRejected("stale_write", "工序的归属或序号在预检之后变了，系统不会自动重新对应。请重新预检。")
            values = row["input"]["hours"]
            if ref in locks and "unit_hours" in values and values["unit_hours"] != live["unit_hours"]:
                skipped[row["row"]] = quota_skip(ref, locks[ref])
            elif row["result"] == "skipped":
                raise WorkbenchCommandRejected("stale_write", "原跳过原因已变化，请重新预检。")
            elif old["revision"] != live["revision"]:
                raise WorkbenchCommandRejected("stale_write", "预检时的工序已经变了，这批没有写入。请重新预检。")
        return skipped

    @staticmethod
    def _group_updates(rows):
        groups = {}
        for row in rows:
            if "group_total_days" not in row["input"]["hours"]:
                continue
            group = row["expected"]["group"]
            if group is None or group["merge_mode"] != "merged":
                raise WorkbenchCommandRejected("group_invalid", "只能编辑已有合并外协组的周期。", 422)
            total = process_number(row["input"]["hours"]["group_total_days"], positive=True)
            ref = group["ref"]
            if ref in groups and groups[ref] != (group, total):
                raise WorkbenchCommandRejected("group_value_conflict", "同一个合并组填了不一样的周期，这批没有写入。请统一后重新导入。", 422)
            groups[ref] = (group, total)
        return {ref: item for ref, item in groups.items() if item[0]["total_days"] != item[1]}

    def _operation_update(self, row):
        old = row["expected"]["operation"]
        updates = {}
        for field, value in row["input"]["hours"].items():
            if field == "group_total_days":
                continue
            column = "ext_days" if field == "external_days" else field
            if column not in ("setup_hours", "unit_hours", "ext_days"):
                raise WorkbenchCommandRejected("invalid_input", "工时文件里有不属于工时的列。请下载模板对照后重新导入。", 422)
            if old[column] != value:
                updates[column] = value
        if updates:
            self._update("PartOperations", "id", old["id"], old, updates)

    def _update(self, table, key_column, key, expected, values):
        assignments = ",".join(column + "=?" for column in values)
        sql = ("UPDATE " + table + " SET " + assignments + " WHERE " + key_column + "=? AND EXISTS "
               "(SELECT 1 FROM WorkbenchEntityRefs WHERE ref=? AND revision=? AND active=1 "
               "AND entity_key=CAST(" + table + "." + key_column + " AS TEXT))")
        cursor = self.conn.execute(sql, list(values.values()) + [key, expected["ref"], expected["revision"]])
        if cursor.rowcount != 1:
            raise WorkbenchCommandRejected("stale_write", "预检时的工序或外协组已经变了，这批写入已经全部还原。请重新预检。")
