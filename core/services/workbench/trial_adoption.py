"""One saved scenario, one transactional official adoption and durable receipt."""

import getpass

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_run_adoption import adoption_input
from core.models.workbench_trial import reference
from core.models.workbench_trial_adoption import ADOPT_ACTION, TrialAdoptionBlocked
from core.services.scheduler import schedule_service

from .commands import WorkbenchCommandService
from .run_candidate_adoption import _ADOPTION_LOCK
from .run_input_readonly import candidate_read_snapshot
from .trial_adoption_persistence import persist_trial_adoption_in_tx
from .trial_adoption_validation import validate_trial_adoption


class WorkbenchTrialAdoptionService:
    def __init__(self, conn, *, integration_enabled=False, context_factory=None, context_validator=None,
                 point_rendering_enabled=False):
        self.conn = conn
        self.integration_enabled = integration_enabled is True
        self.context_factory, self.context_validator = context_factory, context_validator
        self.point_rendering_enabled = point_rendering_enabled is True

    def _point_surface(self, evidence):
        if not self.point_rendering_enabled and any(row.start_time == row.end_time for row in evidence.payload.schedule_rows):
            raise TrialAdoptionBlocked("point_rendering_not_connected", "后端点事件已验证，但前端点标记尚未联合接入，正式采用保持关闭。")

    def _outer(self):
        if self.conn.in_transaction:
            raise RuntimeError("Scenario adoption must own the outer transaction")

    def _enabled(self):
        if not self.integration_enabled:
            raise TrialAdoptionBlocked("scenario_adoption_not_connected", "正式采用尚未完成运行锁与HTTP生命周期接入，保持关闭。")
        factory, validator = self.context_factory, self.context_validator
        if not callable(factory) or not callable(validator):
            raise RuntimeError("Scenario adoption authorization callbacks are not connected")
        return factory, validator

    def preview(self, scenario_ref):
        self._outer()
        reference(scenario_ref)
        try:
            context_factory, _ = self._enabled()
            evidence = validate_trial_adoption(self.conn, scenario_ref)
            self._point_surface(evidence)
        except TrialAdoptionBlocked as exc:
            return {"scenario_ref": scenario_ref,
                    "validation": {"status": "blocked", "can_adopt": False, "issues": exc.issues},
                    "write_context": {"write_token": None, "expires_at": None,
                        "capabilities": {ADOPT_ACTION: False}, "blocked_reasons": exc.issues}}
        except WorkbenchCommandRejected:
            raise
        except Exception as exc:
            raise WorkbenchCommandRejected("storage_failure", "场景采用预览失败，未改变正式计划，请核对运行日志。", 500) from exc
        return {"scenario_ref": scenario_ref, "draft_ref": evidence.draft_ref,
                "baseline": {key: evidence.baseline[key] for key in ("plan_ref", "version")},
                "task_count": len(evidence.payload.schedule_rows), "scope_complete": True,
                "validation": {"status": "valid", "can_adopt": True, "issues": []},
                "write_context": context_factory(scenario_ref, [ADOPT_ACTION], evidence.snapshot)}

    def adopt(self, scenario_ref, write_token, request_key, value):
        self._outer()
        reference(scenario_ref)
        validate_request_key(request_key)
        intent = adoption_input(value)

        def guard():
            _, context_validator = self._enabled()
            if type(write_token) is not str or not write_token:
                raise WorkbenchCommandRejected("stale_write", "请先预览并复核场景正式采用。")
            evidence = validate_trial_adoption(self.conn, scenario_ref)
            self._point_surface(evidence)
            context_validator(write_token, scenario_ref, ADOPT_ACTION, evidence.snapshot)
            return evidence

        def mutate(evidence):
            return persist_trial_adoption_in_tx(self.conn, evidence, intent, request_key,
                                                application_operator=getpass.getuser())

        # Same admission mutex and global scheduler lock as real candidate adopt.
        with _ADOPTION_LOCK:
            lock = schedule_service._RUN_SCHEDULE_LOCK
            if not lock.acquire(blocking=False):
                raise WorkbenchCommandRejected("scheduling_busy", "已有排产正在运行，未执行场景采用，请稍后核对。")
            try:
                return WorkbenchCommandService(self.conn).execute(request_key=request_key, action=ADOPT_ACTION,
                    context_ref=scenario_ref, normalized_input=intent, guard=guard, mutate=mutate)
            finally:
                lock.release()

    def lookup(self, scenario_ref, request_key):
        reference(scenario_ref)
        validate_request_key(request_key)
        with candidate_read_snapshot(self.conn):
            commands = WorkbenchCommandService(self.conn)
            row = commands.repo.get(request_key)
            if row is None:
                return None
            if (row["action"], row["context_ref"]) != (ADOPT_ACTION, scenario_ref):
                raise WorkbenchCommandRejected("request_key_conflict", "原请求回执不属于此场景采用，请核对原对象。")
            return commands.repo.public_result(row, replayed=True)
