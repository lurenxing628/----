"""Preview, serialized confirmation and durable receipt for template-only adoption."""

import getpass
from datetime import datetime

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_calibration_adoption import ADOPT_ACTION, adoption_input, closed_context, preview_input
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected, validate_request_key
from core.models.workbench_execution_input import public_ref
from data.repositories.workbench_calibration_adoption_repo import WorkbenchCalibrationAdoptionRepository

from . import messages
from .calibration_adoption_evidence import read_evidence
from .commands import WorkbenchCommandService


class WorkbenchCalibrationAdoptionService:
    def __init__(self, conn, *, integration_enabled=False, context_factory=None, context_validator=None,
                 clock=None, actor_provider=None):
        self.conn = conn
        self.integration_enabled = integration_enabled is True
        self.context_factory = context_factory
        self.context_validator = context_validator
        self.clock = clock or datetime.now
        self.actor_provider = actor_provider or getpass.getuser
        self.repo = WorkbenchCalibrationAdoptionRepository(conn)
        self.commands = WorkbenchCommandService(conn)

    def _enabled(self):
        if not self.integration_enabled:
            raise WorkbenchCommandRejected("calibration_adoption_not_connected", messages.UNAVAILABLE, 503)
        factory, validator = self.context_factory, self.context_validator
        if not callable(factory) or not callable(validator):
            raise RuntimeError("Calibration adoption write-context callbacks are not connected.")
        return factory, validator

    def _outer(self):
        if self.conn.in_transaction:
            raise RuntimeError("Calibration adoption must own the outer transaction.")

    def preview(self, template_operation_ref, value):
        self._outer()
        public_ref(template_operation_ref)
        intent = preview_input(value)
        factory, _ = self._enabled()
        with TransactionManager(self.conn).transaction():
            evidence = read_evidence(self.conn, self.repo, template_operation_ref, intent, self.clock)
            context = (closed_context(evidence.blockers) if evidence.blockers else
                       factory(template_operation_ref, [ADOPT_ACTION], evidence.snapshot))
            return {"template_operation_ref": template_operation_ref, "suggestion": evidence.suggestion,
                    "generated_at": evidence.generated_at, "input": intent, "samples": evidence.samples,
                    "effect_scope": "future_template_use_only", "quota_lock": evidence.snapshot["locks"].get(template_operation_ref),
                    "validation": {"can_adopt": not evidence.blockers, "issues": evidence.blockers}, "write_context": context}

    def confirm(self, template_operation_ref, write_token, request_key, value):
        self._outer()
        public_ref(template_operation_ref)
        intent = adoption_input(value)

        def guard():
            _, validator = self._enabled()
            if type(write_token) is not str or not write_token:
                raise WorkbenchCommandRejected("stale_write", messages.STALE)
            evidence = read_evidence(self.conn, self.repo, template_operation_ref, intent, self.clock)
            validator(write_token, template_operation_ref, ADOPT_ACTION, evidence.snapshot)
            evidence.require_adoptable()
            return evidence

        def mutate(evidence):
            actor = self.actor_provider()
            if type(actor) is not str or not actor.strip() or len(actor) > 512 or "\x00" in actor:
                raise RuntimeError("The server must supply a valid local application operator.")
            after = self.repo.update_quota(evidence.template, evidence.suggestion["suggested_unit_hours"])
            audit = self.repo.append(evidence, after, intent, request_key=request_key, actor=actor,
                                     adopted_at=evidence.generated_at)
            return WorkbenchCommandOutcome("committed", {**audit, "locked": True,
                "sample_refs": evidence.suggestion["sample_refs"], "sample_revisions": evidence.suggestion["sample_revisions"],
                "effect_scope": "future_template_use_only"})

        return self.commands.execute(request_key=request_key, action=ADOPT_ACTION, context_ref=template_operation_ref,
                                     normalized_input=intent, guard=guard, mutate=mutate)

    def receipt(self, template_operation_ref, request_key):
        public_ref(template_operation_ref)
        validate_request_key(request_key)
        row = self.commands.repo.get(request_key)
        if row is None:
            return None
        if (row["action"], row["context_ref"]) != (ADOPT_ACTION, template_operation_ref):
            raise WorkbenchCommandRejected("request_key_conflict", "这个操作编号属于另一条记录或另一个操作，请核对上次提交的内容。")
        return self.commands.repo.public_result(row, replayed=True)
