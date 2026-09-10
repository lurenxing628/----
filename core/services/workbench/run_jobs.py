"""Admission owns a short transaction. Query and restart recovery never rerun work."""

from datetime import datetime

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import (
    WorkbenchCommandOutcome,
    WorkbenchCommandRejected,
    WorkbenchCommandUncertain,
    validate_request_key,
)
from core.models.workbench_run_job import validate_run_ref
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.preflight import PreflightService
from data.repositories.workbench_run_repo import WorkbenchRunRepository

from .run_input_admission import piece_admission_issues
from .run_jobs_facts import capture_run_facts, run_baseline, run_execution_projections


class WorkbenchRunService:
    def __init__(self, conn, *, integration_enabled=False, input_resolver=None, context_factory=None,
                 context_validator=None, clock=None):
        self.conn = conn
        self.repo = WorkbenchRunRepository(conn)
        self.integration_enabled = integration_enabled is True
        self.input_resolver = input_resolver
        self.context_factory = context_factory
        self.context_validator = context_validator
        self.clock = clock or datetime.now

    def _require_outer(self):
        if self.conn.in_transaction:
            raise RuntimeError("Run service must own the outer transaction")

    def _resolve(self, input_ref):
        if not callable(self.input_resolver):
            raise WorkbenchCommandRejected("run_worker_not_connected", "候选排产受理服务尚未接入。", 503)
        settings = self.input_resolver(self.conn, input_ref)
        data, fingerprint = PreflightService(self.conn).evaluate(settings)
        data["blockers"].extend(piece_admission_issues(self.conn, settings))
        snapshot = {"input_ref": input_ref, "normalized_input": settings, "fingerprint": fingerprint}
        return settings, data, snapshot

    def _reasons(self, data):
        reasons = list(data["blockers"])
        if data["execution_projection_source"] != "execution_ledger":
            reasons.append({"code": "execution_ledger_unavailable", "message": "执行台账未完整接入。"})
        if not self.integration_enabled:
            reasons.append({"code": "run_worker_not_connected", "message": "候选排产运行服务尚未启用。"})
        return reasons

    def preview(self, input_ref):
        """Separate authorization preview; an ordinary preflight never authorizes writes."""
        self._require_outer()
        with TransactionManager(self.conn).transaction():
            self.repo.require_schema()
            settings, data, snapshot = self._resolve(input_ref)
            reasons = self._reasons(data)
            context = {"write_token": None, "expires_at": None,
                       "capabilities": {"scheduling.run": False}, "blocked_reasons": reasons}
            if not reasons:
                if not callable(self.context_factory) or not callable(self.context_validator):
                    raise RuntimeError("Run authorization callbacks are not connected")
                context = self.context_factory(input_ref, ["scheduling.run"], snapshot)
            return {"input_ref": input_ref, "normalized_input": settings, "write_context": context,
                    "calendar_check": data["calendar_check"], "warnings": data["warnings"]}

    def accept(self, input_ref, write_token, request_key):
        self.repo.require_schema()
        if not isinstance(input_ref, str) or not input_ref or len(input_ref) > 256:
            raise WorkbenchCommandRejected("invalid_input", "检查结果引用无效。", 400)

        def guard():
            if not self.integration_enabled:
                raise WorkbenchCommandRejected("run_worker_not_connected", "候选排产运行服务尚未启用，未受理。", 503)
            if not isinstance(write_token, str) or not write_token:
                raise WorkbenchCommandRejected("stale_write", "请先复核排产授权，检查结果本身不能启动排产。")
            settings, data, snapshot = self._resolve(input_ref)
            if self._reasons(data):
                raise WorkbenchCommandRejected("constraint_conflict", "排产检查仍有阻断项，未受理。")
            if not callable(self.context_validator):
                raise RuntimeError("Run authorization validator is not connected")
            self.context_validator(write_token, input_ref, "scheduling.run", snapshot)
            return settings

        def mutate(settings):
            projections = run_execution_projections(self.conn, settings)
            baseline = run_baseline(self.conn)
            fingerprint, facts = capture_run_facts(self.conn)
            ref = self.repo.insert(request_key=request_key, input_ref=input_ref, settings=settings,
                facts_hash=fingerprint, facts_json=facts, projections=projections, baseline=baseline,
                now=self.clock().isoformat(timespec="seconds"))
            return WorkbenchCommandOutcome("committed", {"run_ref": ref})

        result = WorkbenchCommandService(self.conn).execute(request_key=request_key, action="scheduling.run",
            context_ref=input_ref, normalized_input={"input_ref": input_ref}, guard=guard, mutate=mutate)
        ref = result["data"]["run_ref"]
        try:
            state = self.get(ref)
        except Exception as exc:
            raise WorkbenchCommandUncertain(request_key) from exc
        return {"ok": True, "result": "accepted", "job_ref": ref, "run_ref": ref,
                "status_target": "/api/workbench/v1/scheduling/runs/" + ref,
                "receipt_ref": result["receipt_ref"], "replayed": result["replayed"], "data": state}

    def get(self, run_ref):
        validate_run_ref(run_ref)
        with TransactionManager(self.conn).transaction():
            self.repo.require_schema()
            row = self.repo.get(run_ref)
            if row is None:
                raise WorkbenchCommandRejected("entity_not_found", "未找到该排产运行。", 404)
            return self.repo.public(row)

    def lookup(self, request_key):
        validate_request_key(request_key)
        with TransactionManager(self.conn).transaction():
            self.repo.require_schema()
            row = self.repo.by_request(request_key)
            receipt = self.conn.execute("SELECT action FROM WorkbenchCommandReceipts WHERE request_key=?", (request_key,)).fetchone()
            if row is None and receipt is not None and receipt[0] == "scheduling.run":
                raise WorkbenchCommandRejected("run_result_inconsistent", "受理回执存在但运行记录缺失，必须核对台账。", 500)
            return self.repo.public(row) if row else None

    def recover_unfinished_runs(self, *, executor_is_active=None):
        from .run_worker_recovery import recover_unfinished_runs
        return recover_unfinished_runs(self.conn, executor_is_active=executor_is_active, clock=self.clock)
