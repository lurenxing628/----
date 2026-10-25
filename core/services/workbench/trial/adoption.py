"""One saved scenario, one transactional official adoption and durable receipt."""

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_run_adoption import adoption_input
from core.models.workbench_run_job import valid_data_context_ref
from core.models.workbench_trial import reference
from core.models.workbench_trial_adoption import ADOPT_ACTION, TrialAdoptionBlocked
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.messages import UNAVAILABLE
from core.services.workbench.run.adoption_host import AdoptionCommandHost
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository

from .adoption_persistence import persist_trial_adoption_in_tx
from .adoption_validation import validate_trial_adoption


class WorkbenchTrialAdoptionService(AdoptionCommandHost):
    _action = ADOPT_ACTION
    _blocked_error = TrialAdoptionBlocked
    _disabled_code = "scenario_adoption_not_connected"
    _outer_message = "Scenario adoption must own the outer transaction"
    _authorization_message = "Scenario adoption authorization callbacks are not connected"
    _point_message = UNAVAILABLE
    _stale_message = "请先点「预检」并核对试调方案，再采用。"
    _busy_message = "正在排产，这次采用没有执行。请等排产结束后重新点「确认正式采用」。"
    _conflict_message = "这个操作编号不是本试调方案的采用结果，请回到试调列表重新打开。"

    def preview(self, scenario_ref):
        self._outer()
        reference(scenario_ref)
        try:
            evidence, context_factory, data_context_ref = self._prepare_preview(scenario_ref, validate_trial_adoption)
        except TrialAdoptionBlocked as exc:
            return {"scenario_ref": scenario_ref,
                    "validation": {"status": "blocked", "can_adopt": False, "issues": exc.issues},
                    "write_context": {"write_token": None, "expires_at": None,
                        "capabilities": {ADOPT_ACTION: False}, "blocked_reasons": exc.issues}}
        except WorkbenchCommandRejected:
            raise
        except Exception as exc:
            raise WorkbenchCommandRejected("storage_failure", "试调方案的采用预检没有完成，正式计划没有改变。请刷新重试；仍不行请联系维护人员。", 500) from exc
        return {"scenario_ref": scenario_ref, "draft_ref": evidence.draft_ref,
                **self._preview_result(scenario_ref, evidence, context_factory, data_context_ref)}

    def adopt(self, scenario_ref, write_token, request_key, value):
        reference(scenario_ref)
        validate_request_key(request_key)
        intent = adoption_input(value)
        return self._execute_adoption(scenario_ref, write_token, request_key, intent,
                                      validate=validate_trial_adoption, persist=persist_trial_adoption_in_tx)

    def lookup(self, scenario_ref, request_key):
        reference(scenario_ref)
        return self._lookup(scenario_ref, request_key)

    def resolve_command(self, scenario_ref, request_key, *, data_context_ref=None):
        if data_context_ref is not None and not valid_data_context_ref(data_context_ref):
            raise WorkbenchCommandRejected("invalid_input", "这条待确认采用记录的数据来源编号无效，请核对本机保存的记录。", 400)
        found = self.lookup(scenario_ref, request_key)
        if found is not None:
            return {"state": "committed", "receipt": found}
        with candidate_read_snapshot(self.conn):
            exists = WorkbenchTrialRepository(self.conn).scenario_header(scenario_ref) is not None
            may_be_in_flight = exists and (data_context_ref is None or self.data_context.ref() == data_context_ref)
        return {"state": "not_observed", "receipt": None, "may_be_in_flight": may_be_in_flight,
                "can_retry_automatically": False}
