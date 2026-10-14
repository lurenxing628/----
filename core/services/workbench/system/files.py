"""File operations use maintenance_window plus an external durable result, not SQLite receipts."""

import os
import uuid

from core.infrastructure.backup import BackupManager, maintenance_window
from core.infrastructure.safe_files import remove_fixed_file
from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.facts.run_data_context import restored_context_ref
from core.services.workbench.facts.system_journal import SystemMaintenanceJournal, file_content
from core.services.workbench.facts.system_reads import backup_signature

from .restore import SystemRestoreManager, restore_outcome


class SystemFileWorkspace:
    def __init__(self, *, database_path, backup_dir, journal_dir, logger):
        self.database_path, self.backup_dir, self.logger = database_path, backup_dir, logger
        self.journal = SystemMaintenanceJournal(journal_dir, database_path)
        self._restore_source = None
        root, backups = os.path.realpath(journal_dir), os.path.realpath(backup_dir)
        if os.path.commonpath((root, backups)) == backups or root == os.path.dirname(os.path.realpath(database_path)):
            raise WorkbenchCommandRejected("maintenance_unavailable", "维护记录必须放在单独的维护目录里，不能放在备份目录或数据库所在的文件夹。", 503)

    def selected_path(self, selected):
        name = selected["filename"]
        if (os.path.basename(name) != name or "\\" in name or not name.startswith("aps_backup_") or not name.endswith(".db")):
            raise WorkbenchCommandRejected("invalid_input", "这个备份文件名不对，没有执行任何操作。请回到备份列表重新选择。", 400)
        path = os.path.join(self.backup_dir, name)
        try:
            signature = backup_signature(path)
        except OSError as exc:
            raise WorkbenchCommandRejected("entity_not_found", "所选备份已不存在或读不到，请刷新后重新选择。", 404) from exc
        if not same(signature, selected["signature"]):
            raise WorkbenchCommandRejected("stale_write", "这个备份文件已经变了，没有执行任何操作。请刷新后重新选择并确认。")
        return path

    @staticmethod
    def _capture_source(path):
        signature = backup_signature(path)
        original = file_content(path)
        if not same(signature, backup_signature(path)):
            raise WorkbenchCommandRejected("stale_write", "所选备份在预检时发生了变化，请刷新后重新选择。")
        return {"filename": os.path.basename(path), "signature": signature}, original

    def execute(self, *, request_key, action, intent, guard, audit, restore_runner=None):
        if action not in ("create", "delete", "restore"):
            raise WorkbenchCommandRejected("invalid_input", "不支持这个维护动作，没有执行任何操作。", 400)
        with maintenance_window(self.database_path, logger=self.logger, action="workbench_" + action):
            old = self.journal.admission(request_key)
            if old:
                row, replayed = self.journal.begin(request_key, action, intent, previous=old)
                return self.journal.public(row, replayed)
            selected = guard()
            path = self.selected_path(selected) if selected else None
            target = {"filename": selected["filename"], "signature": selected["signature"]} if path else None
            original = None
            if action == "restore":
                target, original = self._capture_source(path)
            # Intent and target identity are durable before any destructive operation.
            row, _ = self.journal.begin(request_key, action, intent, previous=old)
            if action == "restore":
                self._restore_source = (row["job_ref"], path, original)
            verification = {**row["source_verification"], "target": "captured" if action == "restore" else "not_checked"}
            self.journal.record(row, "checking", target=target, source_verification=verification)
            return self._finish(row, action, path, restore_runner, audit)

    def prepare_restore(self, *, request_key, intent, guard):
        """Short maintenance section only; release it BEFORE waiting for HTTP/workers."""
        with maintenance_window(self.database_path, logger=self.logger, action="restore_accept"):
            previous = self.journal.admission(request_key)
            if previous:
                row, replayed = self.journal.begin(request_key, "restore", intent, previous=previous)
                return row, replayed, None
            selected = guard()
            path = self.selected_path(selected)
            target, original = self._capture_source(path)
            row, _ = self.journal.begin(request_key, "restore", intent, previous=previous)
            self._restore_source = (row["job_ref"], path, original)
            verification = {**row["source_verification"], "target": "captured"}
            self.journal.record(row, "checking", target=target, restart_required=True,
                                source_verification=verification,
                                database_origin="unconfirmed", code="host_draining",
                                message="恢复已接收，正在停止当前操作和排产；请不要关闭页面，稍后在本页查看结果。")
            return row, False, path

    def finish_restore(self, row, path, *, restore_runner, audit, confirm_host):
        """Host already owns the HTTP lease, joined worker and original scheduler lock."""
        with maintenance_window(self.database_path, logger=self.logger, action="restore_host"):
            if not same(row, self.journal.lookup(row["request_key"])) or row["state"] != "checking":
                raise RuntimeError("Restore record changed before exclusive execution")
            return self._finish(row, "restore", path, restore_runner, audit, confirm_host)

    def _finish(self, row, action, path, restore_runner, audit, confirm_host=None):
        try:
            state, code, message = self._perform(row, action, path, restore_runner)
        except WorkbenchCommandRejected:
            raise
        except Exception:
            self.logger.exception("系统文件维护结果待核查 job_ref=%s", row["job_ref"])
            self.journal.record(row, "recovery_required", code="storage_failure",
                                message="维护过程中磁盘出错，这次结果还不能确认。请不要再操作，联系维护人员。")
            return self.journal.public(row)
        persisted = False
        if state == "succeeded":
            try:
                persisted = bool(audit(self.journal.public({**row, "state": state, "code": code, "message": message})))
            except Exception:
                self.logger.exception("系统文件维护留痕失败 job_ref=%s", row["job_ref"])
        evidence = {}
        if action == "restore":
            origin = {"succeeded": "selected_backup", "rolled_back": "protection_backup", "failed": "unchanged"}
            evidence["database_origin"] = origin.get(state, "unconfirmed")
            if state == "succeeded":
                evidence["data_context_before"] = restored_context_ref(self.journal.database_scope, self.journal.records())
        if confirm_host is not None:
            confirm_host()
        self.journal.record(row, state, code=code, message=message, audit_persisted=persisted, **evidence)
        return self.journal.public(row)

    def _perform(self, row, action, path, restore_runner):
        if action == "restore":
            if restore_runner is None:
                raise RuntimeError("恢复执行合同尚未接入。")
            captured = self._restore_source
            if captured is None or captured[0] != row["job_ref"] or captured[1] != path:
                raise RuntimeError("本次恢复缺少已预检的原始来源内容。")
            manager = SystemRestoreManager(journal=self.journal, record=row, db_path=self.database_path,
                                           backup_dir=self.backup_dir, logger=self.logger, source_content=captured[2])
            try:
                outcome = restore_outcome(restore_runner(manager, path))
                if outcome[0] in ("succeeded", "rolled_back"):
                    verification = {**row["source_verification"], "sqlite_integrity": "passed"}
                    self.journal.record(row, row["state"], source_verification=verification)
                return outcome
            finally:
                self._restore_source = None
        if action == "delete":
            remove_fixed_file(path, missing_ok=False)
            return "succeeded", "deleted", "已删除所选备份文件，删除不能撤销。"
        manager = BackupManager(self.database_path, self.backup_dir, logger=self.logger)
        path = manager.backup(suffix="manual_" + uuid.uuid4().hex[:12])
        verification = {**row["source_verification"], "target": "verified", "sqlite_integrity": "passed"}
        self.journal.record(row, "checking", target={"filename": os.path.basename(path), "signature": backup_signature(path)},
                            source_verification=verification)
        return "succeeded", "backup_verified", "备份已新增并通过完整性检查；还没有做过恢复演练。"
