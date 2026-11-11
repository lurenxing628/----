"""One command session for adopting a validated plan into the official schedule."""

import getpass
import threading
from typing import Type

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.scheduler.schedule_lock import RUN_SCHEDULE_LOCK
from core.services.workbench import messages
from core.services.workbench.commands import WorkbenchCommandService

_ADOPTION_LOCK = threading.Lock()


class AdoptionCommandHost:
    _action: str
    _blocked_error: Type[WorkbenchCommandRejected]
    _disabled_code: str
    _outer_message: str
    _point_message: str
    _stale_message: str
    _busy_message: str
    _conflict_message: str

    def __init__(self, conn, *, integration_enabled=False, context_factory, context_validator,
                 point_rendering_enabled=False, data_context):
        self.conn = conn
        self.integration_enabled = integration_enabled is True
        self.context_factory = context_factory
        self.context_validator = context_validator
        self.point_rendering_enabled = point_rendering_enabled is True
        self.data_context = data_context
        self.commands = WorkbenchCommandService(conn)

    def _point_surface(self, evidence):
        if not self.point_rendering_enabled and any(
            start == end for start, end in evidence.outcome.resolved_intervals.values()
        ):
            raise self._blocked_error("point_rendering_not_connected", self._point_message)

    def _outer(self):
        if self.conn.in_transaction:
            raise RuntimeError(self._outer_message)

    def _enabled(self):
        if not self.integration_enabled:
            raise self._blocked_error(self._disabled_code, messages.UNAVAILABLE)

    def _prepare_preview(self, context_ref, validate):
        self._enabled()
        evidence = validate(self.conn, context_ref)
        self._point_surface(evidence)
        data_context_ref = (evidence.snapshot["data_context_ref"]
                            if "data_context_ref" in evidence.snapshot else self.data_context.ref())
        return evidence, data_context_ref

    def _preview_result(self, context_ref, evidence, data_context_ref):
        return {"baseline": {"plan_ref": evidence.baseline["plan_ref"], "version": evidence.baseline["version"]},
                "task_count": len(evidence.outcome.validated_payload.schedule_rows), "scope_complete": True,
                "validation": {"status": "valid", "can_adopt": True, "issues": []},
                "write_context": self.context_factory(context_ref, [self._action], evidence.snapshot),
                "data_context_ref": data_context_ref}

    def _execute_adoption(self, context_ref, write_token, request_key, intent, *, validate, persist):
        def guard():
            self._enabled()
            if type(write_token) is not str or not write_token:
                raise WorkbenchCommandRejected("stale_write", self._stale_message)
            evidence = validate(self.conn, context_ref)
            self._point_surface(evidence)
            self.context_validator(write_token, context_ref, self._action, evidence.snapshot)
            return evidence

        def mutate(evidence):
            return persist(self.conn, evidence, intent, request_key, application_operator=getpass.getuser())

        # A committed intent replays even while the scheduler refuses new work.
        replayed = self.commands.replay(request_key=request_key, action=self._action, context_ref=context_ref,
                                       normalized_input=intent)
        if replayed is not None:
            return replayed
        # Short adoption requests share one mutex; never wait behind a long run.
        # BEGIN IMMEDIATE still serializes writers on independent connections.
        with _ADOPTION_LOCK:
            if not RUN_SCHEDULE_LOCK.acquire(blocking=False):
                raise WorkbenchCommandRejected("scheduling_busy", self._busy_message)
            try:
                return self.commands.execute(request_key=request_key, action=self._action, context_ref=context_ref,
                                             normalized_input=intent, guard=guard, mutate=mutate)
            finally:
                RUN_SCHEDULE_LOCK.release()

    def _lookup_in_snapshot(self, context_ref, request_key):
        return self.commands.lookup(
            request_key,
            action=self._action,
            context_ref=context_ref,
            conflict_message=self._conflict_message,
        )
