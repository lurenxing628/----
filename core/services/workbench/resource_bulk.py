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
from core.services.workbench.resource_file_projection import flat_resource, reference_count, resource_file_state
from core.services.workbench.resource_queries import WorkbenchResourceQueryService
from data.repositories.workbench_resource_file_repo import WorkbenchResourceFileRepository


class WorkbenchResourceBulkService:
    def __init__(self, conn, kind, logger=None):
        self.conn, self.kind = conn, action_kind(kind)
        self.reader = WorkbenchResourceQueryService(conn, kind, logger)
        self.adapter = self.reader.domain
        self.repo = WorkbenchResourceFileRepository(conn, logger)
        self.tx = TransactionManager(conn)

    def preview_delete(self, refs, *, scope):
        request = {"refs": resource_refs(refs), "scope": resource_scope(self.kind, scope)}
        with self.tx.transaction():
            rows = [self._row(number, ref, request["scope"]) for number, ref in enumerate(request["refs"], 1)]
            return ResourceActionPreview.build(self.kind + ".bulk_delete", request, rows)

    def _row(self, number, ref, scope):
        row = action_row(number, action="delete")
        row.update(entity_ref=ref, input={})
        try:
            identity = self.reader.resolve(ref)
            row["business_code"] = identity.entity_key
            expected = resource_file_state(self.reader, self.repo, identity)
            row.update(expected=expected, before=flat_resource(self.kind, identity, expected, self.repo),
                       reference_count=reference_count(expected))
            check_category(self.kind, row["before"], scope)
            if identity.entity_key != identity.entity_key.strip():
                raise WorkbenchCommandRejected("constraint_conflict", "这条旧记录的编号前后带空格，没有删除，以免删错记录。请联系维护人员修正编号。")
            if row["reference_count"]:
                raise WorkbenchCommandRejected("constraint_conflict", "这个资源还被工序、授权、班表或历史报工用着，没有删除。请先解除这些关联。")
            row["result"] = "delete"
        except WorkbenchCommandRejected as exc:
            if exc.status >= 500:
                raise
            reject_action_row(row, str(exc), code=exc.code, field="entity_ref")
        return row

    def confirm_delete(self, preview, refs, *, scope):
        if not self.conn.in_transaction:
            raise RuntimeError("批量删除必须在外层工作台写事务中执行。")
        with self.tx.transaction():
            try:
                current = self.preview_delete(refs, scope=scope)
            except ValidationError as exc:
                raise WorkbenchCommandRejected("stale_write", "要删的记录或范围已经变了，没有删除。请重新点「预检」。") from exc
            check_resource_preview(preview, current)
            results = []
            for row in current.as_dict()["rows"]:
                outcome = self.adapter.apply("delete", {}, self.reader.resolve(row["entity_ref"]))
                results.append({"row": row["row"], "result": outcome.result, **outcome.data})
            return WorkbenchCommandOutcome("committed", {"rows": results, "deleted_count": len(results)})
