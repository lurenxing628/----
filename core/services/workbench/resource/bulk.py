"""Explicit-ref atomic deletion. Historical authorization/calendar rows block it."""

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_resource_action import (
    ResourceActionPreview,
    action_kind,
    action_row,
    check_category,
    check_resource_preview,
    reject_action_row,
    resource_refs,
    resource_scope,
)
from data.repositories.workbench_resource_file_repo import WorkbenchResourceFileRepository

from .file_projection import flat_resource, reference_count
from .queries import WorkbenchResourceQueryService


class WorkbenchResourceBulkService:
    def __init__(self, conn, kind, logger=None, reader=None):
        self.conn, self.kind = conn, action_kind(kind)
        self.reader = reader if reader is not None else WorkbenchResourceQueryService(conn, kind, logger)
        self.adapter = self.reader.domain
        self.repo = WorkbenchResourceFileRepository(conn, logger)
        self.tx = TransactionManager(conn)

    def preview_delete(self, refs, *, scope):
        if self.conn.in_transaction:
            return self._prepare_delete(refs, scope)[0]
        with self.tx.transaction():
            return self._prepare_delete(refs, scope)[0]

    def _prepare_delete(self, refs, scope):
        request = {"refs": resource_refs(refs), "scope": resource_scope(self.kind, scope)}
        preparation = self.reader.preparation(refs=request["refs"], machine_authorizations=(self.kind == "machine"))
        identities = [preparation.find_by_ref(self.kind, ref) for ref in request["refs"]]
        codes = [identity.entity_key for identity in identities if identity is not None]
        references = preparation.capture_references(self.repo, self.kind, codes)
        states = preparation.states(self.kind, codes)
        planned = [self._row(number, ref, identity, request["scope"], preparation, states, references)
                   for number, (ref, identity) in enumerate(zip(request["refs"], identities), 1)]
        rows = [row for row, _change in planned]
        return ResourceActionPreview.build(self.kind + ".bulk_delete", request, rows), [change for _row, change in planned]

    def _row(self, number, ref, identity, scope, preparation, states, references):
        row = action_row(number, action="delete")
        row.update(entity_ref=ref, input={})
        change = None
        try:
            if identity is None:
                raise WorkbenchCommandRejected("entity_not_found", "这条资源已经删除了，请刷新后重新选择。", 404)
            code = identity.entity_key
            row["business_code"] = code
            expected = {"state": states[code], "references": references[code]}
            authorizations = preparation.authorizations(self.kind, code) if self.kind in ("machine", "operator") else ()
            row.update(expected=expected, before=flat_resource(self.kind, identity, states[code], authorizations),
                       reference_count=reference_count(expected))
            check_category(self.kind, row["before"], scope)
            change = self.adapter.prepare("delete", {}, states[code], preparation)
            row["result"] = "delete"
        except WorkbenchCommandRejected as exc:
            if exc.status >= 500:
                raise
            reject_action_row(row, str(exc), code=exc.code, field="entity_ref")
        return row, change

    def confirm_delete(self, preview, refs, *, scope):
        if not self.conn.in_transaction:
            raise RuntimeError("批量删除必须在外层工作台写事务中执行。")
        try:
            current, changes = self._prepare_delete(refs, scope)
        except ValidationError as exc:
            raise WorkbenchCommandRejected("stale_write", "要删的记录或范围已经变了，没有删除。请点「重新预检」。") from exc
        body = check_resource_preview(preview, current)
        results = []
        for row, change in zip(body["rows"], changes):
            outcome = self.adapter.apply_prepared(change)
            results.append({"row": row["row"], "result": outcome.result, **outcome.data})
        return WorkbenchCommandOutcome("committed", {"rows": results, "deleted_count": len(results)})
