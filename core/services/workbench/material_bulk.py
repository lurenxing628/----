"""Private atomic bulk deletion, without HTTP or token persistence.

preview_delete(refs, *, scope) -> MaterialPreview. refs is the explicit ordered
selection (including hidden selected rows); scope is filter context, never an
instruction to expand that selection. No writes or reference repair occur.

confirm_delete(preview, refs, *, scope) -> WorkbenchCommandOutcome. Call inside
WorkbenchCommandService.execute.mutate after the outer guard validates the
temporary preview/write context. Set normalized_input=preview.intent(). The
original frozen preview must come from that context, not from a browser DTO.
Confirmation rechecks the entire request and every row before any delete. Its
savepoint also rolls back the whole batch if a later domain operation fails.
"""

from __future__ import annotations

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_material_file import (
    MaterialPreview,
    check_preview,
    check_request,
    normalize_refs,
    normalize_scope,
    preview_row,
    reject_row,
)
from core.services.workbench.materials import WorkbenchMaterialService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_material_file_repo import WorkbenchMaterialFileRepository


def full_material_snapshot(adapter, repo, identity):
    snapshot = adapter.snapshot(identity)
    raw = repo.raw_material(identity.entity_key)
    if raw is None:
        raise WorkbenchCommandRejected("entity_not_found", "物料已不存在，请重新预检。", 404)
    snapshot["material"].update(raw)
    snapshot["requirements"] = repo.requirements(identity.entity_key)
    return snapshot


class WorkbenchMaterialBulkService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.adapter = WorkbenchMaterialService(conn, logger=logger)
        self.repo = WorkbenchMaterialFileRepository(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self.tx = TransactionManager(conn)

    def preview_delete(self, refs, *, scope):
        request = {"refs": normalize_refs(refs), "scope": normalize_scope(scope)}
        with self.tx.transaction():
            rows = [self._delete_row(index, ref) for index, ref in enumerate(request["refs"], 1)]
            return MaterialPreview.build("material.bulk_delete", request, rows)

    def _delete_row(self, number, ref):
        row = preview_row(number, action="delete", normalized={})
        row["entity_ref"] = ref
        identity = self.identities.get(ref)
        if identity is None or identity.kind != "material" or not identity.active:
            reject_row(row, "物料引用不存在或已失效。", field="entity_ref", code="entity_not_found")
            return row
        row["business_code"] = identity.entity_key
        row["expected"] = full_material_snapshot(self.adapter, self.repo, identity)
        if identity.entity_key != identity.entity_key.strip():
            reject_row(row, "物料编号含首尾空白，不能由领域服务安全删除。", code="constraint_conflict")
        elif row["expected"]["requirements"]:
            reject_row(row, "物料仍被批次物料需求引用，不能删除。", field="entity_ref", code="constraint_conflict")
        else:
            row["result"] = "delete"
        return row

    def confirm_delete(self, preview, refs, *, scope):
        if not self.conn.in_transaction:
            raise RuntimeError("批量删除必须在外层工作台写事务中执行。")
        try:
            request = {"refs": normalize_refs(refs), "scope": normalize_scope(scope)}
        except (ValidationError, WorkbenchCommandRejected) as exc:
            raise WorkbenchCommandRejected("stale_write", "物料选择或范围已变化，请重新预检。") from exc
        check_request(preview, "material.bulk_delete", request)
        with self.tx.transaction():
            current = self.preview_delete(refs, scope=scope)
            check_preview(preview, current)
            results = []
            for row in current.as_dict()["rows"]:
                identity = self.identities.get(row["entity_ref"])
                outcome = self.adapter.apply("delete", row["input"], identity)
                results.append({"row": row["row"], "result": outcome.result, **outcome.data})
            return WorkbenchCommandOutcome("committed", {"rows": results, "deleted_count": len(results)})
