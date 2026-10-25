"""Private atomic bulk deletion, without HTTP or token persistence.

preview_delete(refs, *, scope) -> MaterialPreview. refs is the explicit ordered
selection (including hidden selected rows); scope is filter context, never an
instruction to expand that selection. No writes or reference repair occur.

confirm_delete(preview, refs, *, scope) -> WorkbenchCommandOutcome. Call inside
WorkbenchCommandService.execute.mutate after the outer guard validates the
temporary preview/write context. Set normalized_input=preview.intent(). The
original frozen preview must come from that context, not from a browser DTO.
Confirmation rechecks the entire request and every row before any delete. The
outer command transaction rolls back the whole batch if a domain operation fails.
"""

from __future__ import annotations

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_material_file import (
    MaterialPreview,
    check_preview,
    normalize_refs,
    normalize_scope,
    preview_row,
    reject_row,
)
from data.repositories.workbench_material_file_repo import WorkbenchMaterialFileRepository

from .service import WorkbenchMaterialService


def full_material_snapshot(adapter, captured, identity):
    material = captured["materials"].get(identity.entity_key)
    if material is None:
        raise WorkbenchCommandRejected("entity_not_found", "该物料已不存在，请刷新。", 404)
    snapshot = adapter._snapshot_from_current(identity, material)
    snapshot["requirements"] = captured["requirements"].get(identity.entity_key, [])
    return snapshot


class WorkbenchMaterialBulkService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.adapter = WorkbenchMaterialService(conn, logger=logger)
        self.repo = WorkbenchMaterialFileRepository(conn, logger=logger)
        self.tx = TransactionManager(conn)

    def preview_delete(self, refs, *, scope):
        request = {"refs": normalize_refs(refs), "scope": normalize_scope(scope)}
        with self.tx.transaction():
            preview, _ = self._prepare_delete(request)
            return preview

    def _prepare_delete(self, request):
        captured = self.repo.capture(refs=request["refs"])
        rows = [self._delete_row(index, ref, captured) for index, ref in enumerate(request["refs"], 1)]
        return MaterialPreview.build("material.bulk_delete", request, rows), rows

    def _delete_row(self, number, ref, captured):
        row = preview_row(number, action="delete", normalized={})
        row["entity_ref"] = ref
        identity = captured["identities"].get(ref)
        identity = WorkbenchEntityIdentity(identity["ref"], identity["kind"], identity["entity_key"],
                                            identity["revision"], bool(identity["active"])) if identity else None
        if identity is None or identity.kind != "material" or not identity.active:
            reject_row(row, "这条物料记录已失效，请重新选择。", field="entity_ref", code="entity_not_found")
            return row
        row["business_code"] = identity.entity_key
        row["expected"] = full_material_snapshot(self.adapter, captured, identity)
        if identity.entity_key != identity.entity_key.strip():
            reject_row(row, "这个物料编号首尾有空格，不能安全删除。请先核对原记录。", code="constraint_conflict")
        elif row["expected"]["requirements"]:
            reject_row(row, "这个物料还挂在批次的物料需求上，不能删除。", field="entity_ref", code="constraint_conflict")
        else:
            row["result"] = "delete"
        return row

    def confirm_delete(self, preview, refs, *, scope):
        if not self.conn.in_transaction:
            raise RuntimeError("批量删除必须在外层工作台写事务中执行。")
        if not isinstance(preview, MaterialPreview):
            raise WorkbenchCommandRejected("stale_write", "找不到刚才的预检结果，没有写入数据。请点「重新预检」。")
        try:
            request = {"refs": normalize_refs(refs), "scope": normalize_scope(scope)}
        except (ValidationError, WorkbenchCommandRejected) as exc:
            raise WorkbenchCommandRejected("stale_write", "物料选择或范围已变化，请重新预检。") from exc
        current, rows = self._prepare_delete(request)
        check_preview(preview, current)
        prepared = [self.adapter.prepare_checked("delete", row["input"], row["expected"]) for row in rows]
        outcomes = self.adapter.apply_prepared_many(prepared)
        results = [{"row": row["row"], "result": outcome.result, **outcome.data}
                   for row, outcome in zip(rows, outcomes)]
        return WorkbenchCommandOutcome("committed", {"rows": results, "deleted_count": len(results)})
