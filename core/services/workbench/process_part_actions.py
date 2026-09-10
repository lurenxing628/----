"""Part create/delete actions inside the caller's command and receipt transaction.

normalize_create(input) -> dict; create(input) -> WorkbenchCommandOutcome.
preview_delete(refs, *, scope) -> ResourceActionPreview is read-only.
confirm_delete(preview, refs, *, scope) -> WorkbenchCommandOutcome rechecks the
whole selection before mutation. A one-ref selection is single-part deletion.
scope binds the original filters but never expands or trims explicit refs.

The host retains the original preview server-side and validates its write token.
Use the normalized create input / original preview.intent() for command replay.
create and confirm_delete require the host's BEGIN IMMEDIATE transaction; their
savepoints cannot commit it and undo all local writes even if the host catches.
"""

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_process_actions import (
    check_process_part_preview,
    normalize_process_part_create,
    process_part_refs,
    process_part_scope,
)
from core.models.workbench_resource_action import ResourceActionPreview, action_row, reject_action_row
from core.services.process.part_service import PartService
from core.services.process.workflow_state import start_workflow
from core.services.workbench.process_part_actions_facts import (
    ProcessPartActionFacts,
    check_part_action_storage,
    plain_part_action_facts,
)
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository


class WorkbenchProcessPartActionService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.domain = PartService(conn, logger=logger)
        self.facts = ProcessPartActionFacts(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self.tx = TransactionManager(conn)

    @staticmethod
    def normalize_create(input):
        return normalize_process_part_create(input)

    def _require_transaction(self):
        if not self.conn.in_transaction:
            raise RuntimeError("零件保存和删除必须在外层工作台写事务中执行。")

    def create(self, input):
        self._require_transaction()
        payload = self.normalize_create(input)
        with self.tx.transaction():
            check_part_action_storage(self.conn)
            # PartService.create parses any nonempty route, even in non-strict mode.
            part = self.domain.create(payload["business_code"], payload["label"], remark=payload["remark"])
            if payload["route_raw"] is not None:
                self.domain.update(part.part_no, route_raw=payload["route_raw"])
            try:
                workflow = start_workflow(self.conn, part.part_no)
            except RuntimeError as exc:
                raise WorkbenchCommandRejected("storage_failure", "工艺确认流程未能建立，本次未保存零件，请检查本机数据库。", 500) from exc
            identity = self.identities.find_active("part", part.part_no)
            if identity is None:
                raise WorkbenchCommandRejected("storage_failure", "新零件未能完整保存，请检查本机数据库。", 500)
            return WorkbenchCommandOutcome("committed", {"entity_ref": identity.ref,
                "business_code": part.part_no, "workflow": workflow})

    def preview_delete(self, refs, *, scope):
        request = {"refs": process_part_refs(refs), "scope": process_part_scope(scope)}
        with self.tx.transaction():
            check_part_action_storage(self.conn)
            rows = [self._delete_row(number, ref) for number, ref in enumerate(request["refs"], 1)]
            return ResourceActionPreview.build("part.bulk_delete", request, rows)

    def _delete_row(self, number, ref):
        row = action_row(number, action="delete")
        row.update(entity_ref=ref, input={})
        identity = self.identities.get(ref)
        if identity is None or identity.kind != "part" or not identity.active:
            reject_action_row(row, "零件已不存在，请返回列表重新选择。", field="entity_ref", code="entity_not_found")
            return row
        row["business_code"] = identity.entity_key
        try:
            expected = self.facts.snapshot(identity)
            part = expected["part"]
            row.update(expected=plain_part_action_facts(expected), reference_count=len(expected["batches"]),
                       before={"business_code": part["part_no"], "label": part["part_name"],
                               "route_raw": part["route_raw"], "route_parsed": part["route_parsed"],
                               "remark": part["remark"], "operation_count": len(expected["operations"]),
                               "external_group_count": len(expected["groups"])})
            self._check_delete(expected, identity.entity_key)
            row["result"] = "delete"
        except WorkbenchCommandRejected as exc:
            if exc.status >= 500:
                raise
            reject_action_row(row, str(exc), field="entity_ref", code=exc.code)
        return row

    @staticmethod
    def _check_delete(expected, code):
        if not code.strip() or code != code.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "原图号为空或含首尾空白，请先核对，未删除其他同号零件。")
        if expected["batches"]:
            raise WorkbenchCommandRejected("constraint_conflict", "该零件已被批次使用，不能删除。")
        if expected["foreign_group_members"]:
            raise WorkbenchCommandRejected("constraint_conflict", "该零件的外协组被其他零件工序使用，不能删除。")
        if len(expected["template_identities"]) != len(expected["operations"]) + len(expected["groups"]):
            raise WorkbenchCommandRejected("storage_failure", "原工序或外协组记录不完整，请检查本机数据库；未删除资料。", 500)

    def confirm_delete(self, preview, refs, *, scope):
        self._require_transaction()
        with self.tx.transaction():
            try:
                current = self.preview_delete(refs, scope=scope)
            except (ValidationError, WorkbenchCommandRejected) as exc:
                if isinstance(exc, WorkbenchCommandRejected) and exc.status >= 500:
                    raise
                raise WorkbenchCommandRejected("stale_write", "删除选择或筛选条件已变化，请重新预检。") from exc
            check_process_part_preview(preview, current)
            results = []
            for row in current.as_dict()["rows"]:
                self.domain.delete(row["business_code"])
                results.append({"row": row["row"], "result": "committed", "entity_ref": row["entity_ref"],
                                "business_code": row["business_code"]})
            return WorkbenchCommandOutcome("committed", {"rows": results, "deleted_count": len(results)})
