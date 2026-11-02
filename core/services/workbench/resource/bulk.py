"""Explicit-ref atomic deletion. Historical authorization/calendar rows block it."""

from core.models.workbench_action_values import AtomicActionPreview
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_resource_action import (
    action_row,
    check_category,
    reject_action_row,
    resource_refs,
    wire_resource_scope,
)
from data.repositories.workbench_resource_file_repo import WorkbenchResourceFileRepository

from .file_projection import flat_resource, reference_count
from .queries import WorkbenchResourceQueryService


class WorkbenchResourceBulkService:
    def __init__(self, conn, kind, logger=None, reader=None):
        self.conn, self.kind = conn, kind
        self.reader = reader if reader is not None else WorkbenchResourceQueryService(conn, kind, logger)
        self.adapter = self.reader.domain
        self.repo = WorkbenchResourceFileRepository(conn, logger)

    def preview_delete(self, refs, *, scope):
        """Preview inside the caller's read snapshot; scope is the viewed list's validated request."""
        request = {"refs": resource_refs(refs), "scope": wire_resource_scope(scope)}
        return self._prepare_delete(request)[0]

    def _prepare_delete(self, request):
        preparation = self.reader.preparation(refs=request["refs"], machine_authorizations=(self.kind == "machine"))
        identities = [preparation.find_by_ref(self.kind, ref) for ref in request["refs"]]
        codes = [identity.entity_key for identity in identities if identity is not None]
        references = preparation.capture_references(self.repo, self.kind, codes)
        states = preparation.states(self.kind, codes)
        planned = [self._row(number, ref, identity, request["scope"], preparation, states, references)
                   for number, (ref, identity) in enumerate(zip(request["refs"], identities), 1)]
        rows = [row for row, _change in planned]
        return AtomicActionPreview.build(self.kind + ".bulk_delete", request, rows), [change for _row, change in planned]

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
            check_category(self.kind, row["before"], scope["category"])
            change = self.adapter.prepare("delete", {}, states[code], preparation)
            row["result"] = "delete"
        except WorkbenchCommandRejected as exc:
            if exc.status >= 500:
                raise
            reject_action_row(row, str(exc), code=exc.code, field="entity_ref")
        return row, change

    def confirm_delete(self, preview):
        if not self.conn.in_transaction:
            raise RuntimeError("批量删除必须在外层工作台写事务中执行。")
        current, changes = self._prepare_delete(preview.as_dict()["request"])
        body = preview.check_current(current)
        results = []
        for row, change in zip(body["rows"], changes):
            outcome = self.adapter.apply_prepared(change)
            results.append({"row": row["row"], "result": outcome.result, **outcome.data})
        return WorkbenchCommandOutcome("committed", {"rows": results, "deleted_count": len(results)})
