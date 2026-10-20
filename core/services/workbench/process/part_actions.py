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

from core.errors import BusinessError, ErrorCode, ValidationError
from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.transaction import TransactionManager
from core.models import Part
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_process_actions import (
    check_process_part_preview,
    normalize_process_part_create,
    process_part_refs,
    process_part_scope,
)
from core.models.workbench_resource_action import ResourceActionPreview, action_row, reject_action_row
from core.services.process.workflow_state import start_workflow
from data.repositories.part_repo import PartRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository

from .part_actions_facts import ProcessPartActionFacts, check_part_action_storage, plain_part_action_facts


class WorkbenchProcessPartActionService:
    def __init__(self, conn, logger=None, contracts=None):
        self.conn = conn
        self.facts = ProcessPartActionFacts(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self.tx = TransactionManager(conn)
        # 文件逐行导入共用本命令的结构和连接事实；下一请求新建实例，命令内不执行 DDL。
        self._contracts = contracts

    @property
    def contracts(self):
        return self._contracts if self._contracts is not None else schema_contract_memo(self.conn)

    @staticmethod
    def normalize_create(input):
        return normalize_process_part_create(input)

    def _require_transaction(self):
        if not self.conn.in_transaction:
            raise RuntimeError("零件保存和删除必须在外层工作台写事务中执行。")

    def create(self, input):
        self._require_transaction()
        payload = self.normalize_create(input)
        return self.apply_create(self.prepare_create(payload))

    def prepare_create(self, payload, *, parts=None, route_parsed="no"):
        existing = PartRepository(self.conn).get(payload["business_code"]) if parts is None else parts.get(payload["business_code"])
        if existing is not None:
            raise BusinessError(ErrorCode.PART_ALREADY_EXISTS, "图号“{}”已存在，这次没有保存。请改用别的图号，或去修改已有的那个零件。".format(payload["business_code"]))
        return Part(payload["business_code"], payload["label"], payload["route_raw"], route_parsed, payload["remark"])

    def apply_create(self, part):
        """Persist the prepared initial fields, including an imported route state."""
        self._require_transaction()
        with self.tx.transaction():
            check_part_action_storage(self.conn, self.contracts)
            PartRepository(self.conn).create(part)
            try:
                workflow = start_workflow(self.conn, part.part_no, contracts=self.contracts)
            except RuntimeError as exc:
                raise WorkbenchCommandRejected("storage_failure", "工艺确认流程没有建立，这次没有保存零件。请刷新重试；仍不行请联系维护人员。", 500) from exc
            identity = self.identities.find_active("part", part.part_no)
            if identity is None:
                raise WorkbenchCommandRejected("storage_failure", "新零件没有完整保存。请刷新重试；仍不行请联系维护人员。", 500)
            return WorkbenchCommandOutcome("committed", {"entity_ref": identity.ref,
                "business_code": part.part_no, "workflow": workflow})

    def preview_delete(self, refs, *, scope):
        return self.preview_delete_normalized(refs, scope=process_part_scope(scope))

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
            expected = self.facts.snapshot(identity, captured)
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
        with self.tx.transaction():
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
