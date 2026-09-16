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
from core.services.workbench import messages
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.preflight import PreflightService
from data.repositories.workbench_run_repo import WorkbenchRunRepository

from .run_data_context import RunDataContext
from .run_input_admission import piece_admission_issues
from .run_jobs_facts import capture_run_facts, run_baseline, run_execution_projections
from .run_progress import read_progress


def _with_progress(payload):
    """Attach the worker's in-process candidate progress while the run is still computing."""
    if payload is not None and payload["state"] == "running" and payload["stage"] == "computing":
        payload["progress"] = read_progress(payload["run_ref"])
    return payload


class WorkbenchRunService:
    def __init__(self, conn, *, integration_enabled=False, input_resolver=None, context_factory=None,
                 context_validator=None, clock=None, data_context=None):
        self.conn = conn
        self.repo = WorkbenchRunRepository(conn)
        self.integration_enabled = integration_enabled is True
        self.input_resolver = input_resolver
        self.context_factory = context_factory
        self.context_validator = context_validator
        self.clock = clock or datetime.now
        self.data_context = data_context or RunDataContext(conn)

    def _require_outer(self):
        if self.conn.in_transaction:
            raise RuntimeError("Run service must own the outer transaction")

    def _resolve(self, input_ref):
        if not callable(self.input_resolver):
            raise WorkbenchCommandRejected("run_worker_not_connected", messages.UNAVAILABLE, 503)
        settings = self.input_resolver(self.conn, input_ref)
        data, fingerprint = PreflightService(self.conn).evaluate(settings)
        data["blockers"].extend(piece_admission_issues(self.conn, settings))
        snapshot = {"input_ref": input_ref, "normalized_input": settings, "fingerprint": fingerprint,
                    "data_context_ref": self.data_context.ref()}
        return settings, data, snapshot

    def _reasons(self, data):
        reasons = list(data["blockers"])
        if data["execution_projection_source"] != "execution_ledger":
            reasons.append({"code": "execution_ledger_unavailable", "message": "报工记录还没有准备好，这次排产不能开始。请刷新重试；仍不行请联系维护人员。"})
        if not self.integration_enabled:
            reasons.append({"code": "run_worker_not_connected", "message": "排产功能尚未开通，这次排产不能开始。请联系维护人员。"})
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
                    "data_context_ref": snapshot["data_context_ref"],
                    "calendar_check": data["calendar_check"], "warnings": data["warnings"]}

    def accept(self, input_ref, write_token, request_key):
        self.repo.require_schema()
        if not isinstance(input_ref, str) or not input_ref or len(input_ref) > 256:
            raise WorkbenchCommandRejected("invalid_input", "这份排产检查结果已失效，排产没有开始。请重新做一次排产检查。", 400)

        def guard():
            if not self.integration_enabled:
                raise WorkbenchCommandRejected("run_worker_not_connected", "排产功能尚未开通，这次排产没有开始。请联系维护人员。", 503)
            if not isinstance(write_token, str) or not write_token:
                raise WorkbenchCommandRejected("stale_write", "还没有确认开始排产，这次排产没有开始。请在排产检查页点「开始排产」。")
            settings, data, snapshot = self._resolve(input_ref)
            if self._reasons(data):
                raise WorkbenchCommandRejected("constraint_conflict", "排产检查还有缺资料的项，这次排产没有开始。请先按上面列出的项补齐。")
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
                "data_context_ref": self.data_context.ref(),
                "status_target": "/api/workbench/v1/scheduling/runs/" + ref,
                "receipt_ref": result["receipt_ref"], "replayed": result["replayed"], "data": state}

    def get(self, run_ref):
        validate_run_ref(run_ref)
        with TransactionManager(self.conn).transaction():
            self.repo.require_schema()
            row = self.repo.get(run_ref)
            if row is None:
                raise WorkbenchCommandRejected("entity_not_found", "找不到这次排产，页面没有打开。请到「排产记录」重新选择。", 404)
            return _with_progress(self.repo.public(row))

    def lookup(self, request_key):
        validate_request_key(request_key)
        with TransactionManager(self.conn).transaction():
            self.repo.require_schema()
            row = self.repo.by_request(request_key)
            receipt = self.conn.execute("SELECT action FROM WorkbenchCommandReceipts WHERE request_key=?", (request_key,)).fetchone()
            if row is None and receipt is not None and receipt[0] == "scheduling.run":
                raise WorkbenchCommandRejected("run_result_inconsistent", messages.unknown("排产"), 500)
            return _with_progress(self.repo.public(row)) if row else None

    def recover_unfinished_runs(self, *, executor_is_active=None):
        from .run_worker_recovery import recover_unfinished_runs
        return recover_unfinished_runs(self.conn, executor_is_active=executor_is_active, clock=self.clock)
