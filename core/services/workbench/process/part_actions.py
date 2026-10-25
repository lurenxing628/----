"""Part create/delete actions inside the caller's command and receipt transaction.

prepare_create(payload, *, parts) -> Part.
apply_create(part) -> WorkbenchCommandOutcome persists the prepared part.
preview_delete_normalized(refs, *, scope) -> ResourceActionPreview is read-only.
confirm_delete(preview, refs, *, scope) -> WorkbenchCommandOutcome rechecks the
whole selection before mutation. A one-ref selection is single-part deletion.
scope binds the original filters but never expands or trims explicit refs.

The host retains the original preview server-side and validates its write token.
Use the normalized create input / original preview.intent() for command replay.
apply_create and confirm_delete require the host's BEGIN IMMEDIATE transaction,
which rolls back all writes if any check or mutation fails.
"""

from core.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.transaction import TransactionManager
from core.models import Part
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_process_actions import (
    check_process_part_preview,
    process_part_refs,
    process_part_scope,
)
from core.models.workbench_resource_action import ResourceActionPreview, action_row, reject_action_row
from core.services.process.workflow_state import start_workflow
from data.repositories.part_repo import PartRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_process_part_facts_repo import WorkbenchProcessPartFactsRepository

from .part_actions_facts import check_part_action_storage, plain_part_action_facts


class WorkbenchProcessPartActionService:
    def __init__(self, conn, logger=None, contracts=None):
        self.conn = conn
        self.facts = WorkbenchProcessPartFactsRepository(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self.tx = TransactionManager(conn)
        # 文件逐行导入共用本命令的结构和连接事实；下一请求新建实例，命令内不执行 DDL。
        self._contracts = contracts

    @property
    def contracts(self):
        return self._contracts if self._contracts is not None else schema_contract_memo(self.conn)

    def _require_transaction(self):
        if not self.conn.in_transaction:
            raise RuntimeError("零件保存和删除必须在外层工作台写事务中执行。")

    def prepare_create(self, payload, *, parts, route_parsed="no"):
        if payload["business_code"] in parts:
            raise BusinessError(ErrorCode.PART_ALREADY_EXISTS, "图号“{}”已存在，这次没有保存。请改用别的图号，或去修改已有的那个零件。".format(payload["business_code"]))
        return Part(payload["business_code"], payload["label"], payload["route_raw"], route_parsed, payload["remark"])

    def create_part(self, part, *, enroll_workflow=True):
        PartRepository(self.conn).create(part)
        workflow = None
        if enroll_workflow:
            try:
                workflow = start_workflow(self.conn, part.part_no, contracts=self.contracts)
            except RuntimeError as exc:
                raise WorkbenchCommandRejected("storage_failure", "工艺确认流程没有建立，这次没有保存零件。请刷新重试；仍不行请联系维护人员。", 500) from exc
        identity = self.identities.find_active("part", part.part_no)
        if identity is None:
            raise WorkbenchCommandRejected("storage_failure", "新零件没有完整保存。请刷新重试；仍不行请联系维护人员。", 500)
        return WorkbenchCommandOutcome("committed", {"entity_ref": identity.ref,
            "business_code": part.part_no, "workflow": workflow})

    def apply_create(self, part):
        """Persist the prepared initial fields, including an imported route state."""
        self._require_transaction()
        check_part_action_storage(self.conn, self.contracts)
        return self.create_part(part)

    def preview_delete_normalized(self, refs, *, scope):
        request = {"refs": process_part_refs(refs), "scope": scope}
        with self.tx.transaction():
            check_part_action_storage(self.conn, self.contracts)
            preview, _ = self._prepare_delete(request)
            return preview

    def _prepare_delete(self, request):
        captured = self.facts.capture(request["refs"])
        rows = [self._delete_row(number, ref, captured) for number, ref in enumerate(request["refs"], 1)]
        return ResourceActionPreview.build("part.bulk_delete", request, rows), rows

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
            expected = dict(snapshot, identity=captured["identities"].get(identity.ref))
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
            raise WorkbenchCommandRejected("constraint_conflict", "原图号是空的或前后有空格。请到基础资料核对图号。")
        if expected["batches"]:
            raise WorkbenchCommandRejected("constraint_conflict", "该零件已被批次使用，不能删除。")
        if expected["foreign_group_members"]:
            raise WorkbenchCommandRejected("constraint_conflict", "该零件的外协组被其他零件工序使用，不能删除。")
        if len(expected["template_identities"]) != len(expected["operations"]) + len(expected["groups"]):
            raise WorkbenchCommandRejected("storage_failure", "原工序或外协组记录不完整，这次没有删除任何资料。请刷新重试；仍不行请联系维护人员。", 500)

    def confirm_delete(self, preview, refs, *, scope):
        self._require_transaction()
        try:
            request = {"refs": process_part_refs(refs), "scope": process_part_scope(scope)}
            check_part_action_storage(self.conn, self.contracts)
            current, rows = self._prepare_delete(request)
        except (ValidationError, WorkbenchCommandRejected) as exc:
            if isinstance(exc, WorkbenchCommandRejected) and exc.status >= 500:
                raise
            raise WorkbenchCommandRejected("stale_write", "删除选择或筛选条件已变化，请重新预检。") from exc
        check_process_part_preview(preview, current)
        results = []
        repo = PartRepository(self.conn)
        for row in rows:
            repo.delete(row["business_code"])
            results.append({"row": row["row"], "result": "committed", "entity_ref": row["entity_ref"],
                            "business_code": row["business_code"]})
        return WorkbenchCommandOutcome("committed", {"rows": results, "deleted_count": len(results)})
