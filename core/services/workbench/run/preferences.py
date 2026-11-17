"""Remember the exact scheduling input without admitting or executing a run."""

from typing import Any, Dict, NoReturn, Tuple

from core.infrastructure.operation_logging import OperationLogger
from core.models.content import StoredJsonCorrupt, read_stored_json
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_preflight import (
    SCHEDULING_PREFERENCES_ACTION,
    SCHEDULING_PREFERENCES_KEY,
    SCHEDULING_PREFERENCES_SUBJECT,
    normalize_preflight_input,
)
from core.services.workbench.commands import WorkbenchCommandService
from core.shared.strict_json import canonical_json
from data.repositories.system_config_repo import SystemConfigRepository


def _invalid_preferences() -> NoReturn:
    raise WorkbenchCommandRejected("scheduling_preferences_invalid", "保存的排产范围或条件无法读取，请联系维护人员核对。", 409)


class SchedulingPreferencesService:
    def __init__(self, conn, logger=None):
        self.conn, self.logger = conn, logger
        self.repo = SystemConfigRepository(conn, logger)

    def snapshot(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        present, stored = self.repo.get_value_with_presence(SCHEDULING_PREFERENCES_KEY)
        state = {"present": present, "stored": stored}
        if not present:
            return {"input": None}, state
        try:
            value = read_stored_json(stored, dict)
        except StoredJsonCorrupt:
            # 偏好读不出来时给可操作的 409 提示，不按整页 500 报；其他存储失败照常上抛。
            _invalid_preferences()
        if set(value) != {"version", "input"} or type(value["version"]) is not int or value["version"] != 1:
            _invalid_preferences()
        try:
            normalized = normalize_preflight_input(value["input"])
        except (TypeError, ValueError) as exc:
            raise WorkbenchCommandRejected("scheduling_preferences_invalid", "保存的排产范围或条件无法读取，请联系维护人员核对。", 409) from exc
        return {"input": normalized}, state

    def save(self, value, *, request_key, validate_context):
        normalized = normalize_preflight_input(value)

        def guard():
            before, state = self.snapshot()
            validate_context(SCHEDULING_PREFERENCES_SUBJECT, SCHEDULING_PREFERENCES_ACTION, state)
            return before

        def mutate(before):
            if before["input"] == normalized:
                return WorkbenchCommandOutcome("unchanged", {"input": normalized, "audit_persisted": False})
            self.repo.set(SCHEDULING_PREFERENCES_KEY, canonical_json({"version": 1, "input": normalized}))
            OperationLogger(self.conn, self.logger).info(
                module="scheduling", action="workbench_scheduling_preferences_save", target_type="system_config",
                target_id=SCHEDULING_PREFERENCES_KEY,
                detail={"before": before["input"], "after": normalized}, raise_on_fail=True)
            return WorkbenchCommandOutcome("committed", {"input": normalized, "audit_persisted": True})

        return WorkbenchCommandService(self.conn, self.logger).execute(
            request_key=request_key, action=SCHEDULING_PREFERENCES_ACTION,
            context_ref=SCHEDULING_PREFERENCES_SUBJECT, normalized_input=normalized,
            guard=guard, mutate=mutate)
