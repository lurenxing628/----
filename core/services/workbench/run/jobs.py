"""Admission owns a short transaction. Query and restart recovery never rerun work."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict

from core.infrastructure.transaction import TransactionManager
from core.models.content import content_text
from core.models.workbench_command import (
    WorkbenchCommandOutcome,
    WorkbenchCommandRejected,
    WorkbenchCommandUncertain,
    validate_request_key,
)
from core.models.workbench_run_candidate import MAX_FACT_BYTES
from core.models.workbench_run_job import validate_run_ref
from core.services.workbench import messages
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.facts.candidate_facts import GenerationFacts, build_run_archive_rows
from core.services.workbench.facts.decision_baseline import read_decision_baseline
from core.services.workbench.facts.decision_read_model import prepare_admission_read_models
from core.services.workbench.facts.decision_read_models import public_job_head, public_job_status
from core.services.workbench.history_entries.writer import record_run_admitted
from core.shared.refs import new_ref
from data.repositories.workbench_run_repo import WorkbenchRunRepository

from .input_admission import PreparedAdmission, prepare_candidate_admission
from .preflight import PreparedPreflight
from .preflight_facts import PreflightFacts


@dataclass(frozen=True)
class AdmittedRun:
    """What admission adds to one checked preflight: the new run's identity, head, capture and read models."""
    admission: PreparedAdmission
    run_ref: str
    accepted_at: str
    data_context_ref: str
    head: Dict[str, Any]
    capture: Dict[str, Any]
    facts: GenerationFacts
    revisions_json: str
    conditions_archive_json: str
    batches: Any
    operations: Any
    read_models: Dict[str, Any]


def read_run_head(conn, run_ref):
    validate_run_ref(run_ref)
    with TransactionManager(conn).transaction():
        row = WorkbenchRunRepository(conn).head(run_ref)
        if row is None:
            raise WorkbenchCommandRejected("entity_not_found", "找不到这次排产，页面没有打开。请到「排产记录」重新选择。", 404)
        return row


class WorkbenchRunService:
    def __init__(self, conn, *, integration_enabled=False,
                 input_resolver: Callable[..., PreparedPreflight], context_factory,
                 context_validator, clock: Callable[[], datetime], data_context):
        self.conn = conn
        self.repo = WorkbenchRunRepository(conn)
        self.integration_enabled = integration_enabled is True
        self.input_resolver = input_resolver
        self.context_factory = context_factory
        self.context_validator = context_validator
        self.clock = clock
        self.data_context = data_context

    def _require_outer(self):
        if self.conn.in_transaction:
            raise RuntimeError("Run service must own the outer transaction")

    def _resolve(self, input_ref, now: datetime):
        with PreflightFacts.open(self.conn) as facts:
            prepared = self.input_resolver(self.conn, input_ref, facts=facts, material_day=now.date().isoformat())
            if not prepared.data["blockers"]:
                admission = prepare_candidate_admission(self.conn, prepared=prepared)
            else:
                admission = PreparedAdmission(
                    preflight=prepared,
                    baseline=None,
                    execution_projections=prepared.execution_projections,
                    business_input=None,
                    issues=(),
                )
            snapshot = {"input_ref": input_ref, "normalized_input": prepared.settings,
                        "data_context_ref": self.data_context.ref()}
            return admission, snapshot

    @staticmethod
    def _used_input_reason():
        return {"code": "input_already_used", "message": "这份检查结果已经开始过排产，请重新检查后再开始下一次。"}

    def _prepare_admission(self, admission, input_ref, request_key, data_context_ref, now: datetime):
        prepared = admission.preflight
        business = admission.business_input
        run_ref = new_ref()
        accepted_at = now.isoformat(timespec="microseconds")
        revisions = prepared.capture.revisions_record()
        busy_refs = [
            row.operation_ref
            for row in admission.execution_projections
            if row.execution_state in ("partial", "started")
        ]
        archive = prepared.capture.scoped_archive(
            prepared.settings["batch_refs"],
            baseline_version=admission.baseline["version"],
            busy_operation_refs=busy_refs,
        )
        revisions_json = content_text(revisions)
        conditions_archive_json = content_text(archive)
        # 读取时按同一上限核验存档；超限的存档受理后再也读不出，所以受理前就按最终字节数拒绝。
        if len(conditions_archive_json.encode("utf-8")) > MAX_FACT_BYTES:
            raise WorkbenchCommandRejected(
                "candidate_capacity_exceeded",
                "这次排产涉及的现场资料超过单次保存上限，排产没有开始。请缩小批次范围后重新检查。",
                413,
            )
        capture = {
            "run_ref": run_ref,
            "input": prepared.settings,
            "revisions": revisions,
            "facts": archive,
            "execution": [row.to_dict() for row in admission.execution_projections],
            "baseline": admission.baseline,
            "run_options": prepared.run_options,
        }
        facts = GenerationFacts(capture)
        batches, operations = build_run_archive_rows(run_ref, facts)
        disposition = {row["operation_ref"]: row for row in business.dispositions}
        official = read_decision_baseline(capture, facts, disposition)
        head = {"run_ref": run_ref, "request_key": request_key, "input_ref": input_ref,
                "accepted_at": accepted_at, "state": "queued", "stage": "queued",
                "executor_ref": None, "started_at": None, "finished_at": None, "error_json": None}
        read_models = prepare_admission_read_models(head, capture, official, facts=facts, dispositions=business.dispositions,
                                                    dates=prepared.dates)
        return AdmittedRun(
            admission, run_ref, accepted_at, data_context_ref, head, capture, facts,
            revisions_json, conditions_archive_json, batches, operations, read_models,
        )

    def _reasons(self, admission):
        reasons = [*admission.preflight.data["blockers"], *admission.issues]
        if not self.integration_enabled:
            reasons.append({"code": "run_worker_not_connected", "message": "排产功能尚未开通，这次排产不能开始。请联系维护人员。"})
        return reasons

    def preview(self, input_ref, *, now: datetime):
        """Separate authorization preview at ``now``, the request's one clock reading; an ordinary preflight never
        authorizes writes."""
        self._require_outer()
        with TransactionManager(self.conn).transaction():
            used = self.repo.input_admitted(input_ref)
            admission, snapshot = self._resolve(input_ref, now)
            prepared = admission.preflight
            settings, data = prepared.settings, prepared.data
            reasons = self._reasons(admission)
            if used:
                reasons.append(self._used_input_reason())
            context = {"write_token": None, "expires_at": None,
                       "capabilities": {"scheduling.run": False}, "blocked_reasons": reasons}
            if not reasons:
                context = self.context_factory(input_ref, ["scheduling.run"], snapshot)
            return {"input_ref": input_ref, "normalized_input": settings, "write_context": context,
                    "run_options": prepared.run_options,
                    "data_context_ref": snapshot["data_context_ref"],
                    "calendar_check": data["calendar_check"], "warnings": data["warnings"]}

    def accept(self, input_ref, write_token, request_key):
        if not isinstance(input_ref, str) or not input_ref or len(input_ref) > 256:
            raise WorkbenchCommandRejected("invalid_input", "这份排产检查结果已失效，排产没有开始。请重新做一次排产检查。", 400)

        admitted = []

        def guard():
            if not self.integration_enabled:
                raise WorkbenchCommandRejected("run_worker_not_connected", "排产功能尚未开通，这次排产没有开始。请联系维护人员。", 503)
            if self.repo.input_admitted(input_ref):
                reason = self._used_input_reason()
                raise WorkbenchCommandRejected(reason["code"], reason["message"])
            # One moment admits this run: its preflight material day and its accepted_at.
            now = self.clock()
            admission, snapshot = self._resolve(input_ref, now)
            if self._reasons(admission):
                raise WorkbenchCommandRejected("constraint_conflict", "排产检查还有缺资料的项，这次排产没有开始。请先按上面列出的项补齐。")
            self.context_validator(write_token, input_ref, "scheduling.run", snapshot)
            return self._prepare_admission(admission, input_ref, request_key, snapshot["data_context_ref"], now)

        def mutate(admitted_run):
            admission = admitted_run.admission
            prepared = admission.preflight
            ref = self.repo.insert(
                request_key=request_key,
                input_ref=input_ref,
                settings=prepared.settings,
                revisions_json=admitted_run.revisions_json,
                conditions_archive_json=admitted_run.conditions_archive_json,
                projections=admission.execution_projections,
                baseline=admission.baseline,
                now=admitted_run.accepted_at,
                run_ref=admitted_run.run_ref,
                batches=admitted_run.batches,
                operations=admitted_run.operations,
            )
            self.repo.insert_admission_read_model(ref, admitted_run.read_models["scope"], admitted_run.read_models["decision"])
            record_run_admitted(
                self.conn,
                head=admitted_run.head,
                capture=admitted_run.capture,
                facts=admitted_run.facts,
            )
            admitted.append(admitted_run)
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
            row = self.repo.status(run_ref)
            if row is None:
                raise WorkbenchCommandRejected("entity_not_found", "找不到这次排产，页面没有打开。请到「排产记录」重新选择。", 404)
            return public_job_status(row)

    def lookup(self, request_key):
        validate_request_key(request_key)
        with TransactionManager(self.conn).transaction():
            row = self.repo.status_by_request(request_key)
            if row is not None:
                return public_job_status(row)
            if self.repo.command_receipt_action(request_key) == "scheduling.run":
                raise WorkbenchCommandRejected("run_result_inconsistent", messages.unknown("排产"), 500)
            return None
