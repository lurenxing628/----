"""External file-operation records survive database replacement; reads never replay work."""

import json
import os
import re
import uuid
from datetime import datetime
from typing import Any

from core.infrastructure.safe_files import (
    create_fixed_file_exclusive,
    guard_fixed_file_replace_target,
    open_fixed_file_for_read_binary,
)
from core.models.content import content_text, same
from core.models.workbench_command import (
    WorkbenchCommandRejected,
    canonical_json,
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


def file_content(path):
    """The original bytes stay in the owning operation, never in the journal or public DTO."""
    with open_fixed_file_for_read_binary(path) as stream:
        return stream.read()


class SystemMaintenanceJournal:
    def __init__(self, directory, database_path):
        if not directory or not os.path.isabs(directory):
            raise WorkbenchCommandRejected("maintenance_unavailable", "还没有配置维护目录，备份和恢复暂时不能用。请先在系统维护页设置维护目录。", 503)
        self.directory = directory
        database = os.path.normcase(os.path.realpath(database_path))
        self._path_scope = database
        # The default journal travels with user-data. Its existing history keeps
        # the same identity after a move; a separately configured directory must
        # still prove that it belongs to the currently configured database path.
        self._follows_database = os.path.normcase(os.path.realpath(directory)) == database + ".system-journal"
        self._database_scope = None

    @property
    def database_scope(self):
        if self._database_scope is None:
            self.records()
            if self._database_scope is None:
                self._database_scope = self._path_scope
        return self._database_scope

    def scope_from_records(self, records):
        """Project the identity from this operation's already validated capture."""
        return records[0]["database_scope"] if records else self._path_scope

    def _path(self, job_ref):
        if not isinstance(job_ref, str) or re.fullmatch(r"[a-f0-9]{32}", job_ref) is None:
            raise RuntimeError("维护操作编号不完整，须人工核查。")
        return os.path.join(self.directory, job_ref + ".json")

    def _read(self, path):
        limit = 256 * 1024
        with open_fixed_file_for_read_binary(path) as stream:
            content = stream.read(limit + 1)
        if len(content) > limit:
            raise RuntimeError("维护记录超过允许大小，须人工核查。")
        row = self._record_content(json.loads(content.decode("utf-8")))
        name = os.path.basename(path)
        if (row["version"] == 2 and os.path.abspath(path) != os.path.abspath(self._path(row["job_ref"]))
                or row["version"] == 1 and re.fullmatch(r"[a-f0-9]{64}\.json", name) is None):
            raise RuntimeError("维护请求记录与文件身份不符，须人工核查。")
        if (row["action"] == "restore" and row["state"] in TERMINAL_STATES
                and row.get("code") not in _RESTORE_TERMINALS[row["state"]]):
            raise RuntimeError("恢复记录没有可确认的终态，须人工核查。")
        if self._database_scope is None:
            self._database_scope = row["database_scope"]
        return row

    def _record_content(self, row):
        if (not isinstance(row, dict) or row.get("version") not in (1, 2)
                or not isinstance(row.get("database_scope"), str) or not row["database_scope"]
                or (self._database_scope is not None and not same(row["database_scope"], self._database_scope))
                or row.get("state") not in JOB_STATES or not isinstance(row.get("history"), list)
                or row.get("action") not in ("create", "delete", "restore")
                or not re.fullmatch(r"[a-f0-9]{32}", str(row.get("job_ref", "")))):
            raise RuntimeError("维护记录不完整或不属于当前数据库，须人工核查。")
        validate_request_key(row.get("request_key"))
        if row["version"] == 1:
            if re.fullmatch(r"[a-f0-9]{64}", row["database_scope"]) is None:
                raise RuntimeError("旧维护记录的数据库来源不完整，须人工核查。")
        elif (not isinstance(row.get("database_path"), str) or not os.path.isabs(row["database_path"])
              or not self._follows_database and not same(row["database_path"], self._path_scope)
              or not isinstance(row.get("intent"), dict) or set(row["intent"]) != {"action", "input"}
              or row["intent"]["action"] != row["action"]):
            raise RuntimeError("维护记录不完整或不属于当前数据库，须人工核查。")
        return row

    def lookup(self, request_key):
        key = validate_request_key(request_key)
        return next((row for row in self.records() if row["request_key"] == key), None)

    def pending(self, records=None):
        captured = self.records() if records is None else records
        return [row for row in captured if row["state"] not in TERMINAL_STATES]

    def records(self, *, names=None):
        if names is None:
            try:
                names = os.listdir(self.directory)
            except FileNotFoundError:
                return []
        rows, requests, jobs = [], set(), set()
        for name in sorted(names):
            if not name.endswith(".json"):
                continue
            if os.path.basename(name) != name:
                raise RuntimeError("维护记录文件名不完整，须人工核查。")
            row = self._read(os.path.join(self.directory, name))
            if row["request_key"] in requests or row["job_ref"] in jobs:
                raise RuntimeError("维护请求或操作编号重复，须人工核查。")
            requests.add(row["request_key"])
            jobs.add(row["job_ref"])
            rows.append(row)
        return rows

    def assert_ready(self, records=None):
        captured = self.records() if records is None else records
        if self.pending(captured):
            raise WorkbenchCommandRejected("maintenance_active", "上一次维护还没有确认结果，这次没有执行。请先用操作编号查询上次维护的结果。", 503)
        if not self._follows_database and any(row["version"] == 1 for row in captured):
            raise WorkbenchCommandRejected("maintenance_origin_unavailable", "旧维护记录缺少原数据库路径。历史结果已保留，请先核对维护目录归属。", 503)

    def admission(self, request_key):
        """Capture readiness before guards; the caller owns the maintenance window."""
        try:
            records = self.records()
            key = validate_request_key(request_key)
            self._database_scope = self.scope_from_records(records)
            previous = next((row for row in records if row["request_key"] == key), None)
            if previous is None:
                self.assert_ready(records)
        except WorkbenchCommandRejected:
            raise
        except Exception as exc:
            raise WorkbenchCommandRejected("maintenance_unconfirmed", "维护记录读不出来，不能提交新的维护。请先查询原操作结果并联系维护人员。", 503) from exc
        return previous

    def begin(self, request_key, action, intent, *, previous: Any = _NOT_CAPTURED):
        if previous is _NOT_CAPTURED:
            previous = self.admission(request_key)
        original = json.loads(content_text({"action": action, "input": intent}))
        if previous:
            if previous["action"] != action:
                raise WorkbenchCommandRejected("request_key_conflict", "这个操作编号对应的是另一次维护，这次没有执行。请重新提交。")
            if previous.get("version") == 1 or not isinstance(previous.get("intent"), dict):
                raise WorkbenchCommandRejected("original_intent_unavailable", "这条旧维护记录缺少原始提交内容。原操作结果已保留，请按原操作编号查询；本次没有重复执行。")
            if not same(previous["intent"], original):
                raise WorkbenchCommandRejected("request_key_conflict", "这个操作编号对应的是另一次维护，这次没有执行。请重新提交。")
            return previous, True
        row = {"version": 2, "database_scope": self.database_scope, "database_path": self._path_scope,
               "job_ref": uuid.uuid4().hex, "request_key": request_key, "intent": original, "action": action, "state": "accepted",
               "code": "accepted", "message": "维护已接收，还没有完成。", "history": [],
               "target": None, "protection": None, "audit_persisted": False,
               "source_verification": {"basis": "original_file_content_and_sqlite", "target": "not_checked",
                                       "protection": "not_checked", "sqlite_integrity": "not_checked"}}
        self.record(row, "accepted")
        return row, False

    def record(self, row, state, **values):
        if state not in JOB_STATES:
            raise ValueError("未知维护状态。")
        if row.get("version") != 2:
            raise WorkbenchCommandRejected("original_intent_unavailable", "旧维护记录保持原件，只提供历史结果查询。")
        updated = {**row, **values, "state": state, "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
        updated["history"] = row["history"] + [{"state": state, "time": updated["updated_at"]}]
        path = self._path(row["job_ref"])
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
        legacy = row.get("version") == 1
        verification = (dict(row["source_verification"]) if not legacy else
                        {"basis": "legacy_record", "target": "unavailable" if row["target"] else "not_checked",
                         "protection": "unavailable" if row["protection"] else "not_checked", "sqlite_integrity": "unavailable"})
        result = {"job_ref": row["job_ref"], "request_key": row["request_key"], "action": row["action"],
                "state": row["state"], "terminal": row["state"] in TERMINAL_STATES, "code": row["code"],
                "message": row["message"], "updated_at": row["updated_at"], "replayed": replayed,
                "protection_filename": row["protection"]["filename"] if row["protection"] else None,
                "filename": row["target"]["filename"] if row["target"] else None,
                "audit_persisted": row["audit_persisted"], "history": row["history"],
                "result_source": "external_maintenance_journal",
                "source_verification": verification,
                "database_origin": row.get("database_origin", "unconfirmed"),
                "restart_required": row.get("restart_required", False),
                "restart_scope": "restoring_process" if row["action"] == "restore" else None,
                "references_require_reload": row["action"] == "restore"}
        if legacy:
            result.update(target_sha256=(row["target"] or {}).get("sha256"),
                          protection_sha256=(row["protection"] or {}).get("sha256"),
                          database_after_sha256=row.get("database_after_sha256"))
        return result


def assert_system_maintenance_ready(database_path, journal_dir):
    """Host hook: call BEFORE opening/migrating/writing the DB; never auto-resume."""
    SystemMaintenanceJournal(journal_dir, database_path).assert_ready()
