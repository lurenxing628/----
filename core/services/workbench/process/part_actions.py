"""Part create/delete actions inside the caller's command and receipt transaction.

prepare_create(payload, *, parts=None) -> Part.
apply_create(part) -> WorkbenchCommandOutcome persists the prepared part.
preview_delete(refs, *, scope) -> PartDeletePreview is read-only inside the
caller's read snapshot; scope is the viewed list's validated ProcessTablePageRequest.
confirm_delete(preview) -> WorkbenchCommandOutcome rechecks the preview's whole
selection before mutation. A one-ref selection is single-part deletion.
scope binds the original filters but never expands or trims explicit refs.

The host retains the original preview server-side and validates its write token.
Use the normalized create input / {"preview_ref": ref} for command replay.
apply_create and confirm_delete require the host's BEGIN IMMEDIATE transaction,
which rolls back all writes if any check or mutation fails.
"""

from core.errors import BusinessError, ErrorCode
from core.models.part import Part
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_process_actions import PartDeletePreview, process_part_refs
from core.models.workbench_process_table_query import wire_process_scope
from core.models.workbench_resource_action import action_row, reject_action_row
from core.services.process.workflow_state import start_workflow
from data.repositories.part_repo import PartRepository
from data.repositories.workbench_process_part_facts_repo import WorkbenchProcessPartFactsRepository

from .part_actions_facts import plain_part_action_facts


class WorkbenchProcessPartActionService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.facts = WorkbenchProcessPartFactsRepository(conn, logger=logger)

    def _require_transaction(self):
        if not self.conn.in_transaction:
            raise RuntimeError("零件保存、删除和删除预检必须在外层工作台事务中执行。")

    def prepare_create(self, payload, *, parts=None, route_parsed="no"):
        exists = PartRepository(self.conn).exists(payload["business_code"]) if parts is None else payload["business_code"] in parts
        if exists:
            raise BusinessError(ErrorCode.PART_ALREADY_EXISTS, "图号“{}”已存在，这次没有保存。请改用别的图号，或去修改已有的那个零件。".format(payload["business_code"]))
        return Part(payload["business_code"], payload["label"], payload["route_raw"], route_parsed, payload["remark"])

    def apply_create(self, part):
        """Persist the prepared initial fields, including an imported route state."""
        self._require_transaction()
        PartRepository(self.conn).create(part)
        try:
            ref, workflow = start_workflow(self.conn, part.part_no)
        except RuntimeError as exc:
            raise WorkbenchCommandRejected("storage_failure", "工艺确认流程没有建立，这次没有保存零件。请刷新重试；仍不行请联系维护人员。", 500) from exc
        return WorkbenchCommandOutcome("committed", {"entity_ref": ref, "business_code": part.part_no, "workflow": workflow})

    def preview_delete(self, refs, *, scope):
        self._require_transaction()
        request = {"refs": process_part_refs(refs), "scope": wire_process_scope(scope)}
        preview, _ = self._prepare_delete(request)
        return preview

    def _prepare_delete(self, request):
        captured = self.facts.capture(request["refs"])
        rows = [self._delete_row(number, ref, captured) for number, ref in enumerate(request["refs"], 1)]
        return PartDeletePreview.build("part.bulk_delete", request, rows), rows

    def _delete_row(self, number, ref, captured):
        row = action_row(number, action="delete")
        row.update(entity_ref=ref, input={})
        raw = captured["identities"].get(ref)
        identity = WorkbenchEntityIdentity(raw["ref"], raw["kind"], raw["entity_key"], raw["revision"], bool(raw["active"])) if raw else None
        if identity is None or identity.kind != "part" or not identity.active:
            reject_action_row(row, "零件已不存在，请返回列表重新选择。", field="entity_ref", code="entity_not_found")
            return row
        row["business_code"] = identity.entity_key
        try:
            snapshot = captured["parts"].get(identity.entity_key)
            if snapshot is None:
                raise WorkbenchCommandRejected("entity_not_found", "零件已不存在，请返回列表重新选择。", 404)
            expected = dict(snapshot, identity=raw)
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
        if not code.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "原图号是空的。请到基础资料核对图号。")
        if expected["batches"]:
            raise WorkbenchCommandRejected("constraint_conflict", "该零件已被批次使用，不能删除。")
        if expected["foreign_group_members"]:
            raise WorkbenchCommandRejected("constraint_conflict", "该零件的外协组被其他零件工序使用，不能删除。")
        if len(expected["template_identities"]) != len(expected["operations"]) + len(expected["groups"]):
            raise WorkbenchCommandRejected("storage_failure", "原工序或外协组记录不完整，这次没有删除任何资料。请刷新重试；仍不行请联系维护人员。", 500)

    def confirm_delete(self, preview):
        self._require_transaction()
        current, rows = self._prepare_delete(preview.as_dict()["request"])
        preview.check_current(current)
        results = []
        repo = PartRepository(self.conn)
        for row in rows:
            repo.delete(row["business_code"])
            results.append({"row": row["row"], "result": "committed", "entity_ref": row["entity_ref"],
                            "business_code": row["business_code"]})
        return WorkbenchCommandOutcome("committed", {"rows": results, "deleted_count": len(results)})
