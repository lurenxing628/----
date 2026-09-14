"""Read-only preview, then serialized revalidation and one durable adoption receipt."""

import getpass
import threading

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_run_adoption import ADOPT_ACTION, CandidateAdoptionBlocked, adoption_input
from core.models.workbench_run_job import validate_run_ref
from core.services.scheduler import schedule_service

from . import messages
from .commands import WorkbenchCommandService
from .run_candidate_adoption_persistence import persist_adoption_in_tx
from .run_candidate_adoption_validation import validate_adoption

_ADOPTION_LOCK = threading.Lock()


class WorkbenchRunCandidateAdoptionService:
    def __init__(self, conn, *, integration_enabled=False, context_factory=None, context_validator=None,
                 point_rendering_enabled=False):
        self.conn = conn
        self.integration_enabled = integration_enabled is True
        self.context_factory = context_factory
        self.context_validator = context_validator
        self.point_rendering_enabled = point_rendering_enabled is True

    def _point_surface(self, evidence):
        if not self.point_rendering_enabled and any(row.start_time == row.end_time for row in evidence.payload.schedule_rows):
            raise CandidateAdoptionBlocked("point_rendering_not_connected", "这个方案里有零工时工序，界面还显示不出来，暂时不能采用。请联系维护人员。")

    def _outer(self):
        if self.conn.in_transaction:
            raise RuntimeError("Candidate adoption must own the outer transaction")

    def _enabled(self):
        if not self.integration_enabled:
            raise CandidateAdoptionBlocked("candidate_adoption_not_connected", messages.UNAVAILABLE)
        factory, validator = self.context_factory, self.context_validator
        if not callable(factory) or not callable(validator):
            raise RuntimeError("Candidate adoption authorization callbacks are not connected")
        return factory, validator

    def preview(self, candidate_ref):
        self._outer()
        validate_run_ref(candidate_ref)
        context = {"write_token": None, "expires_at": None, "capabilities": {ADOPT_ACTION: False}, "blocked_reasons": []}
        try:
            context_factory, _ = self._enabled()
            evidence = validate_adoption(self.conn, candidate_ref)
            self._point_surface(evidence)
        except CandidateAdoptionBlocked as exc:
            reason = {"code": exc.code, "message": str(exc), "severity": "blocker"}
            context["blocked_reasons"] = [reason]
            return {"candidate_ref": candidate_ref, "validation": {"status": "blocked", "can_adopt": False,
                    "issues": [reason]}, "write_context": context}
        except WorkbenchCommandRejected:
            raise
        except Exception as exc:
            raise WorkbenchCommandRejected("storage_failure", messages.FAILURE, 500) from exc
        context = context_factory(candidate_ref, [ADOPT_ACTION], evidence.snapshot)
        return {"candidate_ref": candidate_ref, "run_ref": evidence.run_ref,
                "baseline": {"plan_ref": evidence.baseline["plan_ref"], "version": evidence.baseline["version"]},
                "task_count": len(evidence.payload.schedule_rows), "scope_complete": True,
                "validation": {"status": "valid", "can_adopt": True, "issues": []}, "write_context": context}

    def adopt(self, candidate_ref, write_token, request_key, value):
        self._outer()
        validate_run_ref(candidate_ref)
        validate_request_key(request_key)
        intent = adoption_input(value)
        commands = WorkbenchCommandService(self.conn)

        def guard():
            _, context_validator = self._enabled()
            if type(write_token) is not str or not write_token:
                raise WorkbenchCommandRejected("stale_write", "还没有确认采用，正式计划没有改动。请先点「预检」核对，再点「采用」。")
            evidence = validate_adoption(self.conn, candidate_ref)
            self._point_surface(evidence)
            context_validator(write_token, candidate_ref, ADOPT_ACTION, evidence.snapshot)
            return evidence

        def mutate(evidence):
            return persist_adoption_in_tx(self.conn, evidence, intent, request_key,
                                         application_operator=getpass.getuser())

        # Serialize short adoption requests, but do not wait behind a long worker.
        # BEGIN IMMEDIATE still serializes writers on independent connections.
        with _ADOPTION_LOCK:
            run_lock = schedule_service._RUN_SCHEDULE_LOCK
            if not run_lock.acquire(blocking=False):
                raise WorkbenchCommandRejected("scheduling_busy", "正在排产，这次采用没有执行，正式计划没有改动。请等排产结束后重试。")
            try:
                return commands.execute(request_key=request_key, action=ADOPT_ACTION, context_ref=candidate_ref,
                                        normalized_input=intent, guard=guard, mutate=mutate)
            finally:
                run_lock.release()

    def lookup(self, candidate_ref, request_key):
        validate_run_ref(candidate_ref)
        validate_request_key(request_key)
        commands = WorkbenchCommandService(self.conn)
        row = commands.repo.get(request_key)
        if row is None:
            return None
        if (row["action"], row["context_ref"]) != (ADOPT_ACTION, candidate_ref):
            raise WorkbenchCommandRejected("request_key_conflict", "这条操作记录不属于这个候选方案，没有查到结果。请核对上次提交的操作编号。")
        return commands.repo.public_result(row, replayed=True)
