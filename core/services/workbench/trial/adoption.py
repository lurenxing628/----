"""One saved scenario, one transactional official adoption and durable receipt."""

from core.models.workbench_command import (
    WorkbenchCommandOutcome,
    WorkbenchCommandRejected,
    validate_request_key,
)
from core.models.workbench_run_adoption import adoption_input
from core.models.workbench_run_job import valid_data_context_ref
from core.models.workbench_trial import reference
from core.models.workbench_trial_adoption import ADOPT_ACTION, TrialAdoptionBlocked
from core.services.workbench.commands import command_lookup_payload
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.messages import UNAVAILABLE
from core.services.workbench.plan.official_persistence import persist_official_plan_in_tx
from core.services.workbench.run.adoption_host import AdoptionCommandHost
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository

from .adoption_validation import validate_trial_adoption


def _persist_trial_adoption_in_tx(conn, evidence, intent, request_key, *, application_operator):
    audit = {
        "source": "workbench_trial_adoption",
        "action": "adopt_trial_scenario",
        "request_key": request_key,
        "scenario_ref": evidence.scenario_ref,
        "draft_ref": evidence.draft_ref,
        "proof": evidence.proof,
        "reason": intent["reason"],
        "declared_operator": intent["declared_operator"],
    }
    result = persist_official_plan_in_tx(
        conn,
        prepared=evidence.prepared,
        payload=evidence.outcome.validated_payload,
        baseline=evidence.baseline,
        audit=audit,
        application_operator=application_operator,
        run_window=evidence.run_window,
    )
    result["official_plan"].update(
        source_scenario_ref=evidence.scenario_ref,
        source_draft_ref=evidence.draft_ref,
    )
    return WorkbenchCommandOutcome(
        "committed",
        {"scenario_ref": evidence.scenario_ref, "draft_ref": evidence.draft_ref, **result},
    )


class WorkbenchTrialAdoptionService(AdoptionCommandHost):
    _action = ADOPT_ACTION
    _blocked_error = TrialAdoptionBlocked
    _disabled_code = "scenario_adoption_not_connected"
    _outer_message = "Scenario adoption must own the outer transaction"
    _point_message = UNAVAILABLE
    _stale_message = "请先点「预检」并核对试调方案，再采用。"
    _busy_message = "正在排产，这次采用没有执行。请等排产结束后重新点「确认正式采用」。"
    _conflict_message = "这个操作编号不是本试调方案的采用结果，请回到试调列表重新打开。"

    def _validate(self, conn, scenario_ref):
        return validate_trial_adoption(conn, scenario_ref, data_context=self.data_context)

    def preview(self, scenario_ref):
        self._outer()
        reference(scenario_ref)
        try:
            evidence, data_context_ref = self._prepare_preview(scenario_ref, self._validate)
        except TrialAdoptionBlocked as exc:
            return {"scenario_ref": scenario_ref,
                    "validation": {"status": "blocked", "can_adopt": False, "issues": exc.issues},
                    "write_context": {"write_token": None, "expires_at": None,
                        "capabilities": {ADOPT_ACTION: False}, "blocked_reasons": exc.issues}}
        return {"scenario_ref": scenario_ref, "draft_ref": evidence.draft_ref,
                **self._preview_result(scenario_ref, evidence, data_context_ref)}

    def adopt(self, scenario_ref, write_token, request_key, value):
        reference(scenario_ref)
        validate_request_key(request_key)
        intent = adoption_input(value)
        return self._execute_adoption(scenario_ref, write_token, request_key, intent,
                                      validate=self._validate, persist=_persist_trial_adoption_in_tx)

    def resolve_command(self, scenario_ref, request_key, *, data_context_ref):
        reference(scenario_ref)
        if not valid_data_context_ref(data_context_ref):
            raise WorkbenchCommandRejected("invalid_input", "这条待确认采用记录的数据来源编号无效，请核对本机保存的记录。", 400)
        with candidate_read_snapshot(self.conn):
            found = self._lookup_in_snapshot(scenario_ref, request_key)
            if found is not None:
                return command_lookup_payload(found, data_context_ref=data_context_ref)
            exists = WorkbenchTrialRepository(self.conn).scenario_header(scenario_ref) is not None
            current_context = self.data_context.ref()
            may_be_in_flight = exists and current_context == data_context_ref
        return command_lookup_payload(
            None,
            may_be_in_flight=may_be_in_flight,
            data_context_ref=current_context,
        )
