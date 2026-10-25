"""Ordinary report commands: one outer transaction and one immutable receipt."""

import getpass
import re

from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_execution_input import reject
from core.services.workbench.command_prefetch import run_prefetched, write_stamp
from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.workbench_execution_report_repo import WorkbenchExecutionReportRepository

from .ledger import ExecutionLedgerService
from .production_report_prepare import ReportBatchPreparation, normalize_items


class WorkbenchProductionReportService:
    def __init__(self, conn, *, clock=None, context_factory=None, actor_provider=None):
        self.conn = conn
        self.ledger = ExecutionLedgerService(conn, clock=clock, context_factory=context_factory)
        self.actor_provider = actor_provider or getpass.getuser
        self.commands = WorkbenchCommandService(conn)

    def _prepare(self, items):
        with self.ledger.read_snapshot():
            actor = self.actor_provider()
            if not isinstance(actor, str) or not actor.strip():
                raise ValueError("Local application operator must be supplied by the server.")
            return ReportBatchPreparation(self.ledger, items, actor).prepare()

    def preview(self, action, ref, payload):
        if action == "report_void":
            return self._void_service().preview(ref, payload)
        return self.preview_batch([{"action": action, "ref": ref, "payload": payload}])

    def _void_service(self):
        from .production_report_void import WorkbenchReportVoidService
        return WorkbenchReportVoidService(self.ledger, self.commands, self.actor_provider)

    def preview_batch(self, items):
        return self.prepare_batch(items).public()

    def prepare_batch(self, items):
        return self._prepare(normalize_items(items))

    def execute(self, action, ref, payload, *, request_key, validate_context):
        if action == "report_void":
            return self._void_service().execute(ref, payload, request_key=request_key, validate_context=validate_context)
        items = normalize_items([{"action": action, "ref": ref, "payload": payload}])

        def guard():
            prepared = self._prepare(items)
            operation_ref = prepared.resolved[0]["operation_ref"]
            snapshot = self.ledger.fact_snapshot(prepared.before, operation_ref)
            validate_context(ref, action, snapshot)
            return prepared

        return self._execute(items, request_key, "execution." + action, ref, guard)

    @staticmethod
    def _batch_context(ref):
        if not isinstance(ref, str) or re.fullmatch(r"[A-Za-z0-9_-]{32,48}", ref) is None:
            reject("本页数据已过期，请刷新后重试。", status=400)

    def execute_import(self, preview_ref, *, request_key, load_items, validate_context, admission):
        """Replay before resolving expiring retained bytes, with the same intent hash.

        load_items is server-owned: it must resolve the immutable original preview
        bytes/mode/rows or reject. It is never called for a committed replay.
        It rebuilds the whole field cohort and returns a checked preparation.
        Facts are reused only while the write stamp is unchanged; permanent refs are
        assigned during preparation, while recording times and actors are stamped at commit.
        """
        self._batch_context(preview_ref)
        intent = {"preview_ref": preview_ref}

        def committed():
            return self.commands.replay(request_key=request_key, action="execution.import_confirm",
                                        context_ref=preview_ref, normalized_input=intent)

        replayed = committed()
        if replayed is not None:
            return replayed

        def prefetch():
            with admission():
                with self.ledger.read_snapshot():
                    return load_items(), write_stamp(self.conn)

        def command(prefetched):
            def guard():
                prepared = prefetched.current(load_items)
                validate_context(preview_ref, "import_confirm", prepared.snapshot)
                return prepared

            return self._execute(intent, request_key, "execution.import_confirm", preview_ref, guard)

        try:
            return run_prefetched(self.conn, prefetch, command)
        except WorkbenchCommandRejected:
            # A retry can race its own first attempt: the original commits while this one waits
            # for the read slot, and the changed field facts then reject the old preview before
            # the in-lock receipt check is reached. Answer with that commit, not "nothing written".
            replayed = committed()
            if replayed is not None:
                return replayed
            raise

    def _execute(self, items, request_key, action, context_ref, guard):
        def mutate(prepared):
            prepared.materialize(self.ledger.clock())
            repo = WorkbenchExecutionReportRepository(self.conn)
            pending_refs = list(dict.fromkeys(row["report_ref"] for row in prepared.appended if row.get("allocate_number")))
            allocated = dict(zip(pending_refs, repo.allocate_numbers(len(pending_refs))))
            for row in prepared.appended:
                if row.get("allocate_number"):
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
