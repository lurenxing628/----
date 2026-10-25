"""One command session for adopting a validated plan into the official schedule."""

import getpass
import threading
from typing import Type

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.services.scheduler.schedule_lock import RUN_SCHEDULE_LOCK
from core.services.workbench import messages
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.facts.run_data_context import RunDataContext
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot

_ADOPTION_LOCK = threading.Lock()


class AdoptionCommandHost:
    _action: str
    _blocked_error: Type[WorkbenchCommandRejected]
    _disabled_code: str
    _outer_message: str
    _authorization_message: str
    _point_message: str
    _stale_message: str
    _busy_message: str
    _conflict_message: str

    def __init__(self, conn, *, integration_enabled=False, context_factory=None, context_validator=None,
                 point_rendering_enabled=False, data_context=None):
        self.conn = conn
        self.integration_enabled = integration_enabled is True
        self.context_factory = context_factory
        self.context_validator = context_validator
        self.point_rendering_enabled = point_rendering_enabled is True
        self.data_context = data_context if data_context is not None else RunDataContext(conn)
        self.commands = WorkbenchCommandService(conn)

    def _point_surface(self, evidence):
        if not self.point_rendering_enabled and any(row.start_time == row.end_time for row in evidence.payload.schedule_rows):
            raise self._blocked_error("point_rendering_not_connected", self._point_message)

    def _outer(self):
        if self.conn.in_transaction:
            raise RuntimeError(self._outer_message)

    def _enabled(self):
        if not self.integration_enabled:
            raise self._blocked_error(self._disabled_code, messages.UNAVAILABLE)
        factory, validator = self.context_factory, self.context_validator
        if not callable(factory) or not callable(validator):
            raise RuntimeError(self._authorization_message)
        return factory, validator

    def _prepare_preview(self, context_ref, validate):
        context_factory, _ = self._enabled()
        evidence = validate(self.conn, context_ref)
        self._point_surface(evidence)
        return evidence, context_factory, self.data_context.ref()

    def _preview_result(self, context_ref, evidence, context_factory, data_context_ref):
        return {"baseline": {"plan_ref": evidence.baseline["plan_ref"], "version": evidence.baseline["version"]},
                "task_count": len(evidence.payload.schedule_rows), "scope_complete": True,
                "validation": {"status": "valid", "can_adopt": True, "issues": []},
                "write_context": context_factory(context_ref, [self._action], evidence.snapshot),
                "data_context_ref": data_context_ref}

    def _execute_adoption(self, context_ref, write_token, request_key, intent, *, validate, persist):
        def guard():
            _, context_validator = self._enabled()
            if type(write_token) is not str or not write_token:
                raise WorkbenchCommandRejected("stale_write", self._stale_message)
            evidence = validate(self.conn, context_ref)
            self._point_surface(evidence)
            context_validator(write_token, context_ref, self._action, evidence.snapshot)
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

    def _lookup(self, context_ref, request_key):
        validate_request_key(request_key)
        with candidate_read_snapshot(self.conn):
            row = self.commands.repo.get(request_key)
            if row is None:
                return None
            if (row["action"], row["context_ref"]) != (self._action, context_ref):
                raise WorkbenchCommandRejected("request_key_conflict", self._conflict_message)
            return self.commands.repo.public_result(row, replayed=True)
