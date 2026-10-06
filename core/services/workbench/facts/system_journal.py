"""External file-operation records survive database replacement; reads never replay work."""

import hashlib
import os
import re
import uuid
from datetime import datetime
from typing import Any

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
_NOT_CAPTURED = object()


def file_fingerprint(path):
    digest = hashlib.sha256()
    with open_fixed_file_for_read_binary(path) as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class SystemMaintenanceJournal:
    def __init__(self, directory, database_path):
        if not directory or not os.path.isabs(directory):
            raise WorkbenchCommandRejected("maintenance_unavailable", "还没有配置维护目录，备份和恢复暂时不能用。请先在系统维护页设置维护目录。", 503)
        self.directory = directory
        database = os.path.normcase(os.path.realpath(database_path))
        self._path_scope = input_fingerprint(database)
        # The default journal travels with user-data. Its existing history keeps
        # the same identity after a move; a separately configured directory must
        # still prove that it belongs to the currently configured database path.
        follows_database = os.path.normcase(os.path.realpath(directory)) == database + ".system-journal"
        self._database_scope = None if follows_database else self._path_scope

    @property
    def database_scope(self):
        if self._database_scope is None:
            self.records()
            if self._database_scope is None:
                self._database_scope = self._path_scope
        return self._database_scope

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
        if self._database_scope is None:
            self._database_scope = row["database_scope"]
        return row

    def _record_content(self, row):
        if (not isinstance(row, dict) or row.get("version") != 1
                or not re.fullmatch(r"[a-f0-9]{64}", str(row.get("database_scope", "")))
                or (self._database_scope is not None and row["database_scope"] != self._database_scope)
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

    def pending(self, records=None):
        captured = self.records() if records is None else records
        return [row for row in captured if row["state"] not in TERMINAL_STATES]

    def records(self, *, names=None):
        if names is None:
            try:
                names = os.listdir(self.directory)
            except FileNotFoundError:
                return []
        return [self._read(os.path.join(self.directory, name)) for name in names if name.endswith(".json")]

    def assert_ready(self, records=None):
        if self.pending(records):
            raise WorkbenchCommandRejected("maintenance_active", "上一次维护还没有确认结果，这次没有执行。请先用操作编号查询上次维护的结果。", 503)

    def admission(self, request_key):
        """Capture readiness before guards; the caller owns the maintenance window."""
        try:
            previous = self.lookup(request_key)
            if previous is None:
                self.assert_ready()
        except WorkbenchCommandRejected:
            raise
        except Exception as exc:
            raise WorkbenchCommandRejected("maintenance_unconfirmed", "维护记录读不出来，不能提交新的维护。请先查询原操作结果并联系维护人员。", 503) from exc
        return previous

    def begin(self, request_key, action, intent, *, previous: Any = _NOT_CAPTURED):
        if previous is _NOT_CAPTURED:
            previous = self.admission(request_key)
        digest = input_fingerprint({"action": action, "input": intent})
        if previous:
            if previous["input_hash"] != digest:
                raise WorkbenchCommandRejected("request_key_conflict", "这个操作编号对应的是另一次维护，这次没有执行。请重新提交。")
            return previous, True
        row = {"version": 1, "database_scope": self.database_scope, "job_ref": uuid.uuid4().hex,
               "request_key": request_key, "input_hash": digest, "action": action, "state": "accepted",
               "code": "accepted", "message": "维护已接收，还没有完成。", "history": [],
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
