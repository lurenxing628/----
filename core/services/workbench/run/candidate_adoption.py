"""Read-only preview, then serialized revalidation and one durable adoption receipt."""

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_run_adoption import ADOPT_ACTION, CandidateAdoptionBlocked, adoption_input
from core.models.workbench_run_job import valid_data_context_ref, validate_run_ref
from core.services.workbench.facts.candidate_store import CandidateStore

from .adoption_host import AdoptionCommandHost
from .candidate_adoption_persistence import persist_adoption_in_tx
from .candidate_adoption_validation import validate_adoption


class WorkbenchRunCandidateAdoptionService(AdoptionCommandHost):
    _action = ADOPT_ACTION
    _blocked_error = CandidateAdoptionBlocked
    _disabled_code = "candidate_adoption_not_connected"
    _outer_message = "Candidate adoption must own the outer transaction"
    _authorization_message = "Candidate adoption authorization callbacks are not connected"
    _point_message = "这个方案里有零工时工序，界面还显示不出来，暂时不能采用。请联系维护人员。"
    _stale_message = "还没有确认采用，正式计划没有改动。请先点「预检」核对，再点「采用」。"
    _busy_message = "正在排产，这次采用没有执行，正式计划没有改动。请等排产结束后重试。"
    _conflict_message = "这条操作记录不属于这个候选方案，没有查到结果。请核对上次提交的操作编号。"

    def preview(self, candidate_ref):
        self._outer()
        validate_run_ref(candidate_ref)
        try:
            evidence, context_factory, data_context_ref = self._prepare_preview(candidate_ref, validate_adoption)
        except CandidateAdoptionBlocked as exc:
            reason = {"code": exc.code, "message": str(exc), "severity": "blocker"}
            return {"candidate_ref": candidate_ref, "validation": {"status": "blocked", "can_adopt": False,
                    "issues": [reason]}, "write_context": {"write_token": None, "expires_at": None,
                    "capabilities": {ADOPT_ACTION: False}, "blocked_reasons": [reason]},
                    "data_context_ref": self.data_context.ref()}
        return {"candidate_ref": candidate_ref, "run_ref": evidence.run_ref,
                **self._preview_result(candidate_ref, evidence, context_factory, data_context_ref)}

    def adopt(self, candidate_ref, write_token, request_key, value):
        validate_run_ref(candidate_ref)
        validate_request_key(request_key)
        intent = adoption_input(value)
        return self._execute_adoption(candidate_ref, write_token, request_key, intent,
                                      validate=validate_adoption, persist=persist_adoption_in_tx)

    def lookup(self, candidate_ref, request_key):
        validate_run_ref(candidate_ref)
        return self._lookup(candidate_ref, request_key)

    def resolve_command(self, candidate_ref, request_key, *, data_context_ref, run_ref=None):
        if run_ref is not None:
            validate_run_ref(run_ref)
        if not valid_data_context_ref(data_context_ref):
            raise WorkbenchCommandRejected("invalid_input", "这条待确认采用记录的数据来源编号无效，请核对本机保存的记录。", 400)
        receipt = self.lookup(candidate_ref, request_key)
        if receipt is not None:
            return "recorded", receipt
        store = CandidateStore(self.conn)
        with store.snapshot():
            saved_run_ref = store.repo.candidate_run_ref(candidate_ref)
            current_context = self.data_context.ref()
        replaced = (saved_run_ref is None or (run_ref is not None and saved_run_ref != run_ref)
                    or data_context_ref != current_context)
        return "not_recorded", {
            "ok": True, "result": "not_recorded", "request_key": request_key,
            "may_be_in_flight": not replaced,
            "resolution": "context_replaced" if replaced else "unresolved",
            "data_context_ref": current_context,
            "message": (
                "这条待确认采用记录来自旧数据库或恢复前的历史状态，当前数据源里没有这项候选采用操作。可安全结束本机待确认记录，再对当前候选执行采用。"
                if replaced else "尚未查到这次采用提交的处理结果；若请求仍在处理中，请稍后再次查询，避免重复提交。"
            ),
        }
