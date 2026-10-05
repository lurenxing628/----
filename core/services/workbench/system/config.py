"""One SQLite transaction owns all eight maintenance values, audit and receipt."""

from core.infrastructure.logging import OperationLogger
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_system import CONFIG_FIELDS, config_input
from core.services.system.system_config_service import SystemConfigService
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.messages import STALE


class SystemConfigWorkspace:
    def __init__(self, conn, logger=None, keep_days=7):
        self.conn = conn
        self.logger = logger
        self.keep_days = keep_days
        self.service = SystemConfigService(conn, logger=logger)

    def snapshot(self, *, capture_fingerprint=True):
        snapshot, raw = self.service.snapshot_with_storage(self.keep_days)
        snapshot = snapshot.to_dict()
        stored = {key: raw.get(key) for key in CONFIG_FIELDS}
        return {"values": {key: snapshot[key] for key in CONFIG_FIELDS},
                "stored_values": stored, "dirty_fields": snapshot["dirty_fields"],
                "dirty_reasons": snapshot["dirty_reasons"],
                "defaulted_fields": [key for key in CONFIG_FIELDS if stored[key] is None]}, (
                    input_fingerprint(stored) if capture_fingerprint else None)

    def save(self, *, request_key, values, guard):
        values = config_input(values)
        def mutate(before):
            if before["values"] == values and not before["dirty_fields"] and not before["defaulted_fields"]:
                return WorkbenchCommandOutcome("unchanged", {"config": before, "audit_persisted": False})
            for key, value in values.items():
                if before["stored_values"][key] != str(value):
                    self.service.set_value(key, value)
            after, _ = self.snapshot(capture_fingerprint=False)
            OperationLogger(self.conn, self.logger).info(
                module="system", action="workbench_config_save", target_type="system_config",
                detail={"before": before["stored_values"], "after": after["stored_values"]}, raise_on_fail=True)
            return WorkbenchCommandOutcome("committed", {"config": after, "audit_persisted": True})
        return WorkbenchCommandService(self.conn, self.logger).execute(
            request_key=request_key, action="system.config.save", context_ref="system-maintenance-config",
            normalized_input=values, guard=guard, mutate=mutate)

    def check(self, fingerprint):
        current, revision = self.snapshot()
        if revision != fingerprint:
            raise WorkbenchCommandRejected("stale_write", STALE)
        return current
