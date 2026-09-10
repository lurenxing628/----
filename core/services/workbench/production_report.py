"""Ordinary report commands: one outer transaction and one immutable receipt."""

import getpass
import re

from core.models.workbench_command import WorkbenchCommandOutcome
from core.models.workbench_execution_input import reject
from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.workbench_execution_report_repo import WorkbenchExecutionReportRepository

from .execution_ledger import ExecutionLedgerService
from .production_report_prepare import ReportBatchPreparation, normalize_items


class WorkbenchProductionReportService:
    def __init__(self, conn, *, clock=None, context_factory=None, actor_provider=None):
        self.conn = conn
        self.ledger = ExecutionLedgerService(conn, clock=clock, context_factory=context_factory)
        self.actor_provider = actor_provider or getpass.getuser
        self.commands = WorkbenchCommandService(conn)

    def _prepare(self, items):
        actor = self.actor_provider()
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("Local application operator must be supplied by the server.")
        self.ledger.repo.require_schema()
        return ReportBatchPreparation(self.ledger, items, actor).prepare()

    def preview(self, action, ref, payload):
        return self.preview_batch([{"action": action, "ref": ref, "payload": payload}])

    def preview_batch(self, items):
        normalized = normalize_items(items)
        with self.ledger.read_snapshot():
            return self._prepare(normalized).public()

    def execute(self, action, ref, payload, *, request_key, validate_context):
        items = normalize_items([{"action": action, "ref": ref, "payload": payload}])

        def guard():
            prepared = self._prepare(items)
            operation_ref = prepared.resolved[0]["operation_ref"]
            snapshot = self.ledger.fact_snapshot(prepared.before, operation_ref)
            validate_context(ref, action, snapshot)
            return prepared

        return self._execute(items, request_key, "execution." + action, ref, guard)

    def execute_batch(self, items, *, context_ref, request_key, validate_context):
        normalized = normalize_items(items)
        self._batch_context(context_ref)

        def guard():
            prepared = self._prepare(normalized)
            validate_context(context_ref, "batch", prepared.snapshot)
            return prepared

        return self._execute(normalized, request_key, "execution.batch", context_ref, guard)

    @staticmethod
    def _batch_context(ref):
        if not isinstance(ref, str) or re.fullmatch(r"[A-Za-z0-9_-]{32,48}", ref) is None:
            reject("批量操作上下文引用无效。", status=400)

    def execute_import(self, preview_ref, *, request_key, load_items, validate_context):
        """Replay before resolving expiring retained bytes, with the same intent hash.

        load_items is server-owned: it must resolve the immutable original preview
        bytes/mode/rows or reject. It is never called for a committed replay.
        """
        self._batch_context(preview_ref)

        def guard():
            prepared = self._prepare(normalize_items(load_items()))
            validate_context(preview_ref, "import_confirm", prepared.snapshot)
            return prepared

        return self._execute({"preview_ref": preview_ref}, request_key, "execution.import_confirm", preview_ref, guard)

    def _execute(self, items, request_key, action, context_ref, guard):
        def mutate(prepared):
            repo = WorkbenchExecutionReportRepository(self.conn)
            allocated = {}
            for row in prepared.appended:
                if row.get("allocate_number"):
                    if row["report_ref"] not in allocated:
                        allocated[row["report_ref"]] = repo.allocate_number()
                    row["report_no"] = allocated[row["report_ref"]]
                repo.append(row, request_key=request_key)
            for row in prepared.rows:
                if row["report_ref"] in allocated:
                    row["report_no"] = allocated[row["report_ref"]]
            return WorkbenchCommandOutcome("committed" if prepared.appended else "unchanged",
                {"rows": prepared.rows, "summary": {"total": len(prepared.items), "changed": len(prepared.appended),
                 "unchanged": len(prepared.items) - len(prepared.appended)},
                 "operation_refs": list(prepared.facts["operations"])})

        return self.commands.execute(request_key=request_key, action=action, context_ref=context_ref,
            normalized_input=items, guard=guard, mutate=mutate)
