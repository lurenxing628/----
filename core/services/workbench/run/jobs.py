"""Admission owns a short transaction. Query and restart recovery never rerun work."""

from datetime import datetime
from typing import Any, Callable, Dict, Optional, Tuple, cast

from core.algorithm_contracts.operation_effort import RUNTIME_REQUIREMENT_BASIS
from core.infrastructure.read_evidence import read_evidence_scope
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import (
    WorkbenchCommandOutcome,
    WorkbenchCommandRejected,
    WorkbenchCommandUncertain,
    validate_request_key,
)
from core.models.workbench_run_job import durable_value, new_run_ref, validate_run_ref
from core.services.workbench import messages
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.decision_baseline import read_decision_baseline
from core.services.workbench.facts.decision_baseline_source import decision_baseline_source_resolver
from core.services.workbench.facts.decision_read_models import public_job_head, public_job_status
from core.services.workbench.facts.run_data_context import RunDataContext
from core.services.workbench.facts.run_policy import require_run_schema
from data.repositories.workbench_run_repo import WorkbenchRunRepository

from .input_admission import candidate_admission_issues
from .jobs_facts import capture_run_facts
from .preflight import PreflightService, PreparedPreflight
from .preflight_facts import PreflightFacts
from .progress import read_progress


class WorkbenchRunService:
    def __init__(self, conn, *, integration_enabled=False,
                 input_resolver: Optional[Callable[..., Tuple[Dict[str, Any], str]]] = None, context_factory=None,
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
        facts = PreflightFacts(self.conn)
        with read_evidence_scope(self.conn), facts.snapshot(fingerprint=False):
            continuation = getattr(self.input_resolver, "prepared", None)
            if callable(continuation):
                prepared = cast(Callable[..., PreparedPreflight], continuation)(self.conn, input_ref, facts=facts)
            else:
                data, fingerprint = self.input_resolver(self.conn, input_ref)
                prepared = PreflightService(self.conn, facts=facts).evaluate_prepared(data["normalized_input"])
                prepared.data, prepared.fingerprint = data, fingerprint
            if not prepared.data["blockers"]:
                issues = candidate_admission_issues(self.conn, prepared=prepared)
                prepared.data["blockers"].extend(issues)
            snapshot = {"input_ref": input_ref, "normalized_input": prepared.settings,
                        "data_context_ref": self.data_context.ref()}
            return prepared, snapshot

    @staticmethod
    def _used_input_reason():
        return {"code": "input_already_used", "message": "这份检查结果已经开始过排产，请重新检查后再开始下一次。"}

    def _prepare_admission(self, prepared, input_ref, request_key):
        from core.services.workbench.facts.decision_read_model import prepare_admission_read_models

        prepared.run_ref = new_run_ref()
        prepared.accepted_at = self.clock().isoformat(timespec="microseconds")
        _, facts_text = capture_run_facts(self.conn, prepared.capture)
        capture = {"input": prepared.settings, "facts_text": facts_text, "facts_hash": None,
                   "execution": [row.to_dict() for row in prepared.execution_projections],
                   "baseline": prepared.baseline, "run_options": prepared.run_options}
        facts = GenerationFacts(capture)
        receipt = {"dispositions": prepared.prepared_input.dispositions,
                   "operation_effort": {"effort_basis": RUNTIME_REQUIREMENT_BASIS, "items": [
                       {**durable_value(item.to_dict()), "operation_ref": prepared.preflight_facts.operation_refs[item.op_id]}
                       for item in prepared.prepared_input.operation_efforts]}}
        disposition = {row["operation_ref"]: row for row in receipt["dispositions"]}
        official = read_decision_baseline(capture, facts, disposition, prepared.accepted_at,
                                         source_resolver=decision_baseline_source_resolver(self.conn))
        states = official["source_states"]
        dependencies = self.repo.dependency_heads(
            sorted({row["source_candidate_ref"] for row in states if row.get("source_candidate_ref") is not None}),
            sorted({row["source_scenario_ref"] for row in states if row.get("source_scenario_ref") is not None}))
        prepared.head = {"run_ref": prepared.run_ref, "request_key": request_key, "input_ref": input_ref,
                         "accepted_at": prepared.accepted_at, "state": "queued", "stage": "queued",
                         "executor_ref": None, "started_at": None, "finished_at": None, "error_json": None}
        prepared.read_models = prepare_admission_read_models(prepared.head, capture, official,
                                                            facts=facts, receipt=receipt, dependencies=dependencies)
        prepared.capture_payload = capture
        return prepared

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
            require_run_schema(self.repo)
            used = self.repo.input_admitted(input_ref)
            prepared, snapshot = self._resolve(input_ref)
            settings, data = prepared.settings, prepared.data
            reasons = self._reasons(data)
            if used:
                reasons.append(self._used_input_reason())
            context = {"write_token": None, "expires_at": None,
                       "capabilities": {"scheduling.run": False}, "blocked_reasons": reasons}
            if not reasons:
                if not callable(self.context_factory) or not callable(self.context_validator):
                    raise RuntimeError("Run authorization callbacks are not connected")
                context = self.context_factory(input_ref, ["scheduling.run"], snapshot)
            return {"input_ref": input_ref, "normalized_input": settings, "write_context": context,
                    "run_options": prepared.run_options,
                    "data_context_ref": snapshot["data_context_ref"],
                    "calendar_check": data["calendar_check"], "warnings": data["warnings"]}

    def accept(self, input_ref, write_token, request_key):
        require_run_schema(self.repo)
        if not isinstance(input_ref, str) or not input_ref or len(input_ref) > 256:
            raise WorkbenchCommandRejected("invalid_input", "这份排产检查结果已失效，排产没有开始。请重新做一次排产检查。", 400)

        admitted = []

        def guard():
            if not self.integration_enabled:
                raise WorkbenchCommandRejected("run_worker_not_connected", "排产功能尚未开通，这次排产没有开始。请联系维护人员。", 503)
            if not isinstance(write_token, str) or not write_token:
                raise WorkbenchCommandRejected("stale_write", "还没有确认开始排产，这次排产没有开始。请在排产检查页点「开始排产」。")
            if self.repo.input_admitted(input_ref):
                reason = self._used_input_reason()
                raise WorkbenchCommandRejected(reason["code"], reason["message"])
            with read_evidence_scope(self.conn):
                prepared, snapshot = self._resolve(input_ref)
                if self._reasons(prepared.data):
                    raise WorkbenchCommandRejected("constraint_conflict", "排产检查还有缺资料的项，这次排产没有开始。请先按上面列出的项补齐。")
                if not callable(self.context_validator):
                    raise RuntimeError("Run authorization validator is not connected")
                self.context_validator(write_token, input_ref, "scheduling.run", snapshot)
                prepared.data_context_ref = snapshot["data_context_ref"]
                return self._prepare_admission(prepared, input_ref, request_key)

        def mutate(prepared):
            ref = self.repo.insert(request_key=request_key, input_ref=input_ref, settings=prepared.settings,
                facts_hash=None, facts_json=prepared.capture_payload["facts_text"],
                projections=prepared.execution_projections, baseline=prepared.baseline,
                now=prepared.accepted_at, run_ref=prepared.run_ref)
            self.repo.insert_admission_read_model(ref, prepared.read_models["scope"], prepared.read_models["decision"])
            admitted.append(prepared)
            return WorkbenchCommandOutcome("committed", {"run_ref": ref})

        result = WorkbenchCommandService(self.conn).execute(request_key=request_key, action="scheduling.run",
            context_ref=input_ref, normalized_input={"input_ref": input_ref}, guard=guard, mutate=mutate)
        ref = result["data"]["run_ref"]
        try:
            state = (public_job_head(admitted[0].head, admitted[0].read_models["scope"], None)
                     if admitted else self.get(ref))
        except Exception as exc:
            raise WorkbenchCommandUncertain(request_key) from exc
        return {"ok": True, "result": "accepted", "job_ref": ref, "run_ref": ref,
                "data_context_ref": admitted[0].data_context_ref if admitted else self.data_context.ref(),
                "status_target": "/api/workbench/v1/scheduling/runs/" + ref,
                "receipt_ref": result["receipt_ref"], "replayed": result["replayed"], "data": state}

    def get(self, run_ref):
        validate_run_ref(run_ref)
        with TransactionManager(self.conn).transaction():
            require_run_schema(self.repo)
            row = self.repo.status(run_ref)
            if row is None:
                raise WorkbenchCommandRejected("entity_not_found", "找不到这次排产，页面没有打开。请到「排产记录」重新选择。", 404)
            return self._status(row)

    def lookup(self, request_key):
        validate_request_key(request_key)
        with TransactionManager(self.conn).transaction():
            require_run_schema(self.repo)
            row = self.repo.status_by_request(request_key)
            if row is not None:
                return self._status(row)
            if self.repo.command_receipt_action(request_key) == "scheduling.run":
                raise WorkbenchCommandRejected("run_result_inconsistent", messages.unknown("排产"), 500)
            return None

    @staticmethod
    def _status(row):
        payload = public_job_status(row)
        if payload["state"] == "running" and payload["stage"] == "computing":
            payload["progress"] = read_progress(payload["run_ref"])
        return payload

    def recover_unfinished_runs(self, *, executor_is_active=None):
        from .worker_recovery import recover_unfinished_runs
        return recover_unfinished_runs(self.conn, executor_is_active=executor_is_active, clock=self.clock)
