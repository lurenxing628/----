"""External file-operation records survive database replacement; reads never replay work."""

import hashlib
import os
import re
import uuid
from datetime import datetime

from core.infrastructure.safe_files import (
    create_fixed_file_exclusive,
    guard_fixed_file_replace_target,
    open_fixed_file_for_read_binary,
    read_fixed_json,
    stat_regular_file,
)
from core.models.workbench_command import (
    WorkbenchCommandRejected,
    canonical_json,
    input_fingerprint,
    validate_request_key,
)
from core.models.workbench_system import JOB_STATES, TERMINAL_STATES

_RESTORE_TERMINALS = {
    "succeeded": ("verified",),
    "rolled_back": ("restore_failed_rolled_back", "verify_failed_rolled_back"),
    "failed": ("busy", "before_restore_backup_failed", "backup_integrity_failed", "backup_missing",
               "backup_unreadable", "db_target_unreadable"),
}


def file_fingerprint(path):
    digest = hashlib.sha256()
    with open_fixed_file_for_read_binary(path) as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class SystemMaintenanceJournal:
    def __init__(self, directory, database_path):
        if not directory or not os.path.isabs(directory):
            raise WorkbenchCommandRejected("maintenance_unavailable", "维护结果目录尚未配置，文件操作未启用。", 503)
        self.directory = directory
        self.database_scope = input_fingerprint(os.path.normcase(os.path.realpath(database_path)))

    def _path(self, request_key):
        key = validate_request_key(request_key)
        return os.path.join(self.directory, hashlib.sha256(key.encode("ascii")).hexdigest() + ".json")

    def _read(self, path):
        if stat_regular_file(path).st_size > 256 * 1024:
            raise RuntimeError("维护记录超过允许大小，须人工核查。")
        row = self._record_content(read_fixed_json(path))
        if os.path.abspath(path) != os.path.abspath(self._path(row.get("request_key"))):
            raise RuntimeError("维护请求记录与文件身份不符，须人工核查。")
        if (row["action"] == "restore" and row["state"] in TERMINAL_STATES
                and row.get("code") not in _RESTORE_TERMINALS[row["state"]]):
            raise RuntimeError("恢复记录没有可确认的终态，须人工核查。")
        return row

    def _record_content(self, row):
        if (not isinstance(row, dict) or row.get("version") != 1 or row.get("database_scope") != self.database_scope
                or row.get("state") not in JOB_STATES or not isinstance(row.get("history"), list)
                or row.get("action") not in ("create", "delete", "restore")
                or row.get("record_hash") != input_fingerprint({key: value for key, value in row.items() if key != "record_hash"})
                or not re.fullmatch(r"[a-f0-9]{32}", str(row.get("job_ref", "")))):
            raise RuntimeError("维护记录不完整或不属于当前数据库，须人工核查。")
        return row

    def lookup(self, request_key):
        try:
            return self._read(self._path(request_key))
        except FileNotFoundError:
            return None

    def pending(self):
        return [row for row in self.records() if row["state"] not in TERMINAL_STATES]

    def records(self):
        try:
            names = os.listdir(self.directory)
        except FileNotFoundError:
            return []
        return [self._read(os.path.join(self.directory, name)) for name in names if name.endswith(".json")]

    def assert_ready(self):
        if self.pending():
            raise WorkbenchCommandRejected("maintenance_active", "存在未核实的维护结果，已阻止新的写入；请保留现场并核查原操作。", 503)

    def begin(self, request_key, action, intent):
        previous = self.lookup(request_key)
        digest = input_fingerprint({"action": action, "input": intent})
        if previous:
            if previous["input_hash"] != digest:
                raise WorkbenchCommandRejected("request_key_conflict", "原请求对应的维护内容不同，请核对原结果。")
            return previous, True
        self.assert_ready()
        row = {"version": 1, "database_scope": self.database_scope, "job_ref": uuid.uuid4().hex,
               "request_key": request_key, "input_hash": digest, "action": action, "state": "accepted",
               "code": "accepted", "message": "已持久记录维护请求，尚未完成。", "history": [],
               "target": None, "protection": None, "audit_persisted": False}
        self.record(row, "accepted")
        return row, False

    def record(self, row, state, **values):
        if state not in JOB_STATES:
            raise ValueError("未知维护状态。")
        updated = {**row, **values, "state": state, "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
        updated["history"] = row["history"] + [{"state": state, "time": updated["updated_at"]}]
        updated.pop("record_hash", None)
        updated["record_hash"] = input_fingerprint(updated)
        path = self._path(row["request_key"])
        temporary = path + "." + uuid.uuid4().hex + ".tmp"
        fd = create_fixed_file_exclusive(temporary)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(canonical_json(updated))
            stream.flush()
            os.fsync(stream.fileno())
        guard_fixed_file_replace_target(path)
        os.replace(temporary, path)
        if os.name != "nt":
            directory_fd = os.open(self.directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        row.clear()
        row.update(updated)
        return row

    @staticmethod
    def public(row, replayed=False):
        return {"job_ref": row["job_ref"], "request_key": row["request_key"], "action": row["action"],
                "state": row["state"], "terminal": row["state"] in TERMINAL_STATES, "code": row["code"],
                "message": row["message"], "updated_at": row["updated_at"], "replayed": replayed,
                "protection_filename": row["protection"]["filename"] if row["protection"] else None,
                "filename": row["target"]["filename"] if row["target"] else None,
                "audit_persisted": row["audit_persisted"], "history": row["history"],
                "result_source": "external_maintenance_journal",
                "target_sha256": row["target"]["sha256"] if row["target"] else None,
                "protection_sha256": row["protection"]["sha256"] if row["protection"] else None,
                "database_after_sha256": row.get("database_after_sha256"),
                "database_origin": row.get("database_origin", "unconfirmed"),
                "restart_required": row.get("restart_required", False),
                "restart_scope": "restoring_process" if row["action"] == "restore" else None,
                "references_require_reload": row["action"] == "restore"}


def assert_system_maintenance_ready(database_path, journal_dir):
    """Host hook: call BEFORE opening/migrating/writing the DB; never auto-resume."""
    SystemMaintenanceJournal(journal_dir, database_path).assert_ready()
