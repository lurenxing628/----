"""Private atomic bulk deletion, without HTTP or token persistence.

preview_delete(refs, *, scope) -> MaterialPreview is read-only inside the
caller's read snapshot transaction. refs is the explicit ordered selection
(including hidden selected rows); scope is the viewed list's validated
MaterialPageRequest, filter context and never an instruction to expand that
selection. No writes or reference repair occur.

confirm_delete(preview) -> WorkbenchCommandOutcome. Call inside
WorkbenchCommandService.execute.mutate after the outer guard validates the
temporary preview/write context. Set normalized_input={"preview_ref": ref}. The
original frozen preview must come from that context, not from a browser DTO.
Confirmation rebuilds every row of the preview's own request before any delete.
The outer command transaction rolls back the whole batch if a domain operation fails.
"""

from __future__ import annotations

from dataclasses import asdict

from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_material_file import (
    MaterialPreview,
    normalize_refs,
    preview_row,
    reject_row,
    wire_scope,
)
from data.repositories.workbench_material_file_repo import WorkbenchMaterialFileRepository

from .service import WorkbenchMaterialService


def full_material_snapshot(captured, identity):
    material = captured["materials"].get(identity.entity_key)
    if material is None:
        raise WorkbenchCommandRejected("entity_not_found", "该物料已不存在，请刷新。", 404)
    if (material["material_id"], material["ref"], material["revision"]) != (
            identity.entity_key, identity.ref, identity.revision):
        raise WorkbenchCommandRejected("stale_write", "物料和选中的记录对不上，请刷新后重新核对。")
    return {
        "identity": asdict(identity),
        "material": material,
        "requirements": captured["requirements"].get(identity.entity_key, []),
    }


class WorkbenchMaterialBulkService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.adapter = WorkbenchMaterialService(conn, logger=logger)
        self.repo = WorkbenchMaterialFileRepository(conn, logger=logger)

    def preview_delete(self, refs, *, scope):
        if not self.conn.in_transaction:
            raise RuntimeError("物料批量删除预检必须在外层读快照事务中执行。")
        request = {"refs": normalize_refs(refs), "scope": wire_scope(scope)}
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
        row["expected"] = full_material_snapshot(captured, identity)
        if row["expected"]["requirements"]:
            reject_row(row, "这个物料还挂在批次的物料需求上，不能删除。", field="entity_ref", code="constraint_conflict")
        else:
            row["result"] = "delete"
        return row

    def confirm_delete(self, preview):
        if not self.conn.in_transaction:
            raise RuntimeError("批量删除必须在外层工作台写事务中执行。")
        current, rows = self._prepare_delete(preview.as_dict()["request"])
        preview.check_current(current)
        prepared = [self.adapter.prepare_checked("delete", row["input"], row["expected"]) for row in rows]
        outcomes = self.adapter.apply_prepared_many(prepared)
        results = [{"row": row["row"], "result": outcome.result, **outcome.data}
                   for row, outcome in zip(rows, outcomes)]
        return WorkbenchCommandOutcome("committed", {"rows": results, "deleted_count": len(results)})
