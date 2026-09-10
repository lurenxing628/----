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
        return "recovery_required", "result_missing", "恢复结果不完整，请停止使用数据库并核查维护记录。"
    code = result.code
    if code == "verified" and result.ok is True and outcome.category == "success":
        return "succeeded", code, "已恢复备份并完成结构校验；须重启宿主并重新读取工作台，不能只刷新页面。"
    if result.ok is not False or outcome.category not in ("error", "warning"):
        return "recovery_required", code, "恢复结果标志不一致，请保持停止并核查原操作。"
    if code in ("restore_failed_rollback_failed", "verify_failed_rollback_failed"):
        return "rollback_failed", code, "恢复失败且自动回滚未成功，请停止使用数据库，保留保护副本并人工核查。"
    if code in ("restore_failed_rolled_back", "verify_failed_rolled_back"):
        return "rolled_back", code, "恢复未成功，已经自动回滚到恢复前副本；须重启宿主并核对原操作结果。"
    messages = {
        "busy": "数据库正在维护，本次恢复未执行。",
        "before_restore_backup_failed": "恢复前保护副本创建或校验失败，原数据库未被修改。",
        "backup_integrity_failed": "备份完整性检查失败，原数据库未被修改。",
        "backup_missing": "备份文件已不存在，恢复未执行。",
        "backup_unreadable": "备份文件无法读取，恢复未执行。",
        "db_target_unreadable": "目标数据库不可写，恢复未执行。",
    }
    if code in messages:
        return "failed", code, messages[code]
    return "recovery_required", code, "恢复没有得到可确认的终态，请停止使用数据库并核查维护记录。"
