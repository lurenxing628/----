"""Atomic route-file domain operations, subordinate to the file coordinator.

preview_rows consumes decoded rows and complete facts from the caller's one read
snapshot. The coordinator binds bytes, scope, target and all facts, then compares
the entire ResourceActionPreview document again under BEGIN IMMEDIATE before
calling apply_rows. Private row data carries only the selected write inputs.
Neither method owns the caller's commit, receipt, file token or public stage DTO.
Affected part refs include unchanged rows for the coordinator's read refresh.
"""

from contextlib import ExitStack

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_action import resource_refs
from core.services.process.workflow_state import record_confirmation
from core.services.workbench.process_file_route_preview import RouteFilePreview, reject_duplicates
from core.services.workbench.process_part_actions import WorkbenchProcessPartActionService
from core.services.workbench.process_part_actions_facts import check_part_action_storage
from core.services.workbench.process_route_apply import apply_route, discard_groups, require_group_ack
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository


class ProcessRouteFileOperations:
    def __init__(self, conn, logger=None):
        self.conn, self.logger = conn, logger
        self.tx = TransactionManager(conn)
        self.identities = WorkbenchIdentityRepository(conn, logger)

    def preview_rows(self, decoded_rows, facts, target_ref=None):
        if not self.conn.in_transaction:
            raise RuntimeError("路线文件预检必须在调用方的完整事实快照事务中执行。")
        with ExitStack() as stack:
            preview = RouteFilePreview(self.conn, self.logger, facts, target_ref, stack)
            rows = [preview.row(source) for source in decoded_rows]
            reject_duplicates(rows)
            extra = {"affected_groups": preview.affected_groups(rows), "zero_review_required": False}
        return rows, extra

    def apply_rows(self, rows, *, discard_group_refs, confirm_zero_unit_hours):
        if not self.conn.in_transaction:
            raise RuntimeError("路线文件保存必须在外层BEGIN IMMEDIATE事务中执行。")
        with self.tx.transaction():
            self._validate_batch(rows, discard_group_refs, confirm_zero_unit_hours)
            check_part_action_storage(self.conn)
            results, affected_refs = [], set()
            for row in rows:
                result = self._apply_row(row)
                results.append(result)
                affected_refs.add(result["entity_ref"])
            return results, sorted(affected_refs)

    @staticmethod
    def _validate_batch(rows, discard_group_refs, confirm_zero_unit_hours):
        if type(rows) is not list or any(row["errors"] or row["result"] not in ("new", "update", "unchanged") for row in rows):
            raise WorkbenchCommandRejected("constraint_conflict", "预检里有被拒绝的行，这批一条都没写入。请改好文件后重新预检。")
        codes = [row["business_code"] for row in rows]
        if len(codes) != len(set(codes)):
            raise WorkbenchCommandRejected("constraint_conflict", "文件里有重复图号，这批不能导入。请合并重复行后重新导入。")
        try:
            refs = resource_refs(discard_group_refs, allow_empty=True)
        except ValidationError as exc:
            raise WorkbenchCommandRejected("group_discard_required", "受影响的外协组要逐个确认，不能重复也不能漏。请在受影响外协组列表里全部勾选。") from exc
        affected = [group for row in rows for group in row["related"]["affected_groups"]]
        require_group_ack({"discard_group_refs": refs}, affected)
        if type(confirm_zero_unit_hours) is not bool:
            raise ValidationError("请明确勾选是否已复核零工时。", field="confirm_zero_unit_hours")

    def _apply_row(self, row):
        if row["action"] == "create":
            outcome = WorkbenchProcessPartActionService(self.conn, self.logger).create(row["input"])
            ref = outcome.data["entity_ref"]
            part = {"part_no": row["business_code"], "route_raw": row["after"]["route_raw"], "route_parsed": "no"}
            operations = []
        else:
            ref = row["entity_ref"]
            identity = self.identities.get(ref)
            if identity is None or not identity.active or identity.kind != "part" or identity.entity_key != row["business_code"]:
                raise WorkbenchCommandRejected("stale_write", "这个零件已失效。请刷新列表后重新选择。")
            if identity.revision != row["expected"]["revision"]:
                raise WorkbenchCommandRejected("stale_write", "零件资料已变化，请重新预检。")
            part, operations = row["expected"]["part"], row["expected"]["operations"]
            self._update_text(row)
        route = row["related"]["route"]
        if route is not None:
            discard_groups(self.conn, row["business_code"], row["related"]["affected_groups"])
            apply_route(self.conn, part, operations, route, self.identities)
            record_confirmation(self.conn, row["business_code"], "route")
        return {"row": row["row"], "result": "unchanged" if row["result"] == "unchanged" else "committed",
                "entity_ref": ref, "business_code": row["business_code"]}

    def _update_text(self, row):
        columns = {"label": "part_name", "remark": "remark"}
        fields = {column: row["after"][key] for key, column in columns.items() if key in row["changes"]}
        if fields:
            self.conn.execute("UPDATE Parts SET " + ",".join(column + "=?" for column in fields)
                              + ",updated_at=CURRENT_TIMESTAMP WHERE part_no=?",
                              list(fields.values()) + [row["business_code"]])
