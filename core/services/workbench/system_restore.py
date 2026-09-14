"""Observe the existing restore flow without replacing its protection or rollback logic."""

import os

from core.infrastructure.backup import BackupManager
from core.services.workbench.system_journal import file_fingerprint


class SystemRestoreManager(BackupManager):
    def __init__(self, *, journal, record, **kwargs):
        super().__init__(**kwargs)
        self.journal = journal
        self.record = record
        self.restore_result = None
        self.rollback_result = None
        self.rolling_back = False

    def backup(self, suffix=None):
        if suffix == "before_restore":
            self.journal.record(self.record, "protecting")
        # A second restore in the same second must not overwrite its selected source.
        actual_suffix = self.record["job_ref"] + "_before_restore" if suffix == "before_restore" else suffix
        path = super().backup(suffix=actual_suffix)
        if suffix == "before_restore":
            self.journal.record(self.record, "protecting", protection={
                "filename": os.path.basename(path), "sha256": file_fingerprint(path)})
        return path

    def _copy_db_file(self, source_path, *, locked_warning_message):
        source = self.record["protection" if self.rolling_back else "target"]
        self._require_source(source_path, source)
        self.journal.record(self.record, "rolling_back" if self.rolling_back else "restoring")
        super()._copy_db_file(source_path, locked_warning_message=locked_warning_message)
        # A source changed during copying cannot authorize success, even if SQLite opened it.
        self._require_source(source_path, source)
        if not self.rolling_back:
            self.journal.record(self.record, "verifying")

    @staticmethod
    def _require_source(path, source):
        if (not source or os.path.basename(path) != source["filename"]
                or file_fingerprint(path) != source["sha256"]):
            raise RuntimeError("Restore source no longer matches its durable fingerprint")

    def restore(self, backup_path):
        self.restore_result = super().restore(backup_path)
        return self.restore_result

    def _auto_rollback(self, before_restore_path, **kwargs):
        self.rolling_back = True
        self.journal.record(self.record, "rolling_back")
        self.rollback_result = super()._auto_rollback(before_restore_path, **kwargs)
        return self.rollback_result


def restore_outcome(manager, outcome):
    result = outcome.result or manager.rollback_result or manager.restore_result
    if result is None:
        return "recovery_required", "result_missing", "这次恢复没有留下完整结果，现在不能确认数据库内容。请不要再操作，联系维护人员。"
    code = result.code
    if code == "verified" and result.ok is True and outcome.category == "success":
        return "succeeded", code, "已恢复所选备份并通过完整性检查。请重启本软件再打开工作台，只刷新页面不够。"
    if result.ok is not False or outcome.category not in ("error", "warning"):
        return "recovery_required", code, "恢复结果前后不一致，不能确认数据库内容。请不要再操作，联系维护人员。"
    if code in ("restore_failed_rollback_failed", "verify_failed_rollback_failed"):
        return "rollback_failed", code, "恢复失败，自动还原也没有成功。请不要再操作，留好恢复前的保护副本并联系维护人员。"
    if code in ("restore_failed_rolled_back", "verify_failed_rolled_back"):
        return "rolled_back", code, "恢复没有成功，已自动还原到恢复前的保护副本。请重启本软件后核对上次操作结果。"
    messages = {
        "busy": "数据库正在维护，这次恢复没有执行。请稍后重新点「恢复」。",
        "before_restore_backup_failed": "恢复前的保护副本没有生成成功，原数据库没有改动。请稍后重新点「恢复」。",
        "backup_integrity_failed": "所选备份没有通过完整性检查，原数据库没有改动。请换一个备份再试。",
        "backup_missing": "所选备份文件已不在了，恢复没有执行。请刷新后重新选择。",
        "backup_unreadable": "所选备份文件读不到，恢复没有执行。请换一个备份再试。",
        "db_target_unreadable": "当前数据库不能写入，恢复没有执行。请不要再操作，联系维护人员。",
    }
    if code in messages:
        return "failed", code, messages[code]
    return "recovery_required", code, "恢复没有得到能确认的最终结果，现在不能确认数据库内容。请不要再操作，联系维护人员。"
