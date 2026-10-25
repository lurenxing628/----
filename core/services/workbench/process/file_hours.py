"""Hours-file domain operations; the coordinator owns file/scope/snapshot binding.

The caller must re-preview identical rows against complete current facts under
BEGIN IMMEDIATE before apply. This layer requires that outer transaction and
never records or refreshes process-stage confirmations.
"""

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.template_hours import ProcessTemplateHours
from data.repositories.workbench_process_hours_repo import WorkbenchProcessHoursRepository

from .file_hours_preview import HoursFilePreview


class ProcessHoursFileOperations:
    def __init__(self, conn, logger):
        self.conn, self.logger = conn, logger
        self.repo = WorkbenchProcessHoursRepository(conn, logger)
        self.facts = {}

    def preview_rows(self, decoded_rows, facts, target_ref):
        self.facts = facts
        rows, extra = HoursFilePreview(facts, target_ref).build(decoded_rows)
        return rows, extra

    def apply_rows(self, rows):
        if not self.conn.in_transaction:
            raise RuntimeError("工时文件写入必须在外层 BEGIN IMMEDIATE 事务中执行。")
        hours = ProcessTemplateHours(self.conn)
        current = {row["ref"]: row for row in self.facts["operations"]}
        groups = self._group_updates(rows)
        results, affected = [], set()
        for row in rows:
            self._operation_update(row, current[row["expected"]["operation_ref"]], hours)
            affected.add(row["expected"]["part_ref"])
            results.append({"row": row["row"], "result": "committed" if row["result"] == "update" else "unchanged",
                            "entity_ref": row["entity_ref"], "business_code": row["business_code"],
                            "sequence": row["sequence"]})
        for group, total in groups.values():
            self._group_update(group, total)
        return results, sorted(affected)

    @staticmethod
    def _group_updates(rows):
        groups = {}
        for row in rows:
            if "group_total_days" not in row["input"]["hours"]:
                continue
            group = row["expected"]["group"]
            total = row["input"]["hours"]["group_total_days"]
            groups[group["ref"]] = (group, total)
        return {ref: item for ref, item in groups.items() if item[0]["total_days"] != item[1]}

    def _operation_update(self, row, current, hours):
        old = row["expected"]["operation"]
        updates = {}
        for field, value in row["input"]["hours"].items():
            if field == "group_total_days":
                continue
            column = "ext_days" if field == "external_days" else field
            if old[column] != value:
                updates[column] = value
        if updates:
            hours.revise_current(current, updates, expected_revision=old["revision"])

    def _group_update(self, group, total):
        count = self.repo.update_group_cycle(group["group_id"], {"total_days": total},
                                            ref=group["ref"], revision=group["revision"])
        if count != 1:
            raise WorkbenchCommandRejected("stale_write", "预检时的工序或外协组已经变了，这批写入已经全部还原。请重新预检。")
