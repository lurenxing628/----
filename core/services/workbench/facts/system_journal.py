"""External file-operation records survive database replacement; reads never replay work."""

import os
import re
import uuid
from datetime import datetime
from typing import Any, NoReturn

from core.infrastructure.safe_files import (
    create_fixed_file_exclusive,
    guard_fixed_file_open_target,
    open_fixed_file_for_read_binary,
)
from core.models.content import same
from core.models.workbench_command import (
    WorkbenchCommandRejected,
    validate_request_key,
)
from core.models.workbench_system import JOB_STATES, TERMINAL_STATES
from core.shared.strict_json import canonical_json, load_strict_json

_RESTORE_TERMINALS = {
    "succeeded": ("verified",),
    "rolled_back": ("restore_failed_rolled_back", "verify_failed_rolled_back"),
    "failed": ("busy", "before_restore_backup_failed", "backup_integrity_failed", "backup_missing",
               "backup_unreadable", "db_target_unreadable"),
}
_NOT_CAPTURED = object()
_JOURNAL_LIMIT = 2000


def _unreadable_record() -> NoReturn:
    raise RuntimeError("维护记录不是严格的 UTF-8 JSON，须人工核查。")


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
        self._records = None
        self._entry_names = None
        self._requests = {}
        self._jobs = {}

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
        row = self._record_content(load_strict_json(content, on_malformed=_unreadable_record))
        if os.path.abspath(path) != os.path.abspath(self._path(row["job_ref"])):
            raise RuntimeError("维护请求记录与文件身份不符，须人工核查。")
        if (row["action"] == "restore" and row["state"] in TERMINAL_STATES
                and row.get("code") not in _RESTORE_TERMINALS[row["state"]]):
            raise RuntimeError("恢复记录没有可确认的终态，须人工核查。")
        if row["action"] == "restore" and row["state"] == "succeeded" and not isinstance(row.get("data_context_before"), str):
            # Every successful restore records the data generation it replaced.
            raise RuntimeError("恢复成功的记录缺少恢复前的数据来源，须人工核查。")
        if self._database_scope is None:
            self._database_scope = row["database_scope"]
        return row

    def _record_content(self, row):
        if (not isinstance(row, dict) or row.get("version") != 2
                or not isinstance(row.get("database_scope"), str) or not row["database_scope"]
                or (self._database_scope is not None and not same(row["database_scope"], self._database_scope))
                or row.get("state") not in JOB_STATES or not isinstance(row.get("history"), list)
                or row.get("action") not in ("create", "delete", "restore")
                or not re.fullmatch(r"[a-f0-9]{32}", str(row.get("job_ref", "")))):
            raise RuntimeError("维护记录不完整或不属于当前数据库，须人工核查。")
        validate_request_key(row.get("request_key"))
        if (not isinstance(row.get("database_path"), str) or not os.path.isabs(row["database_path"])
                or not self._follows_database and not same(row["database_path"], self._path_scope)
                or not isinstance(row.get("intent"), dict) or set(row["intent"]) != {"action", "input"}
                or row["intent"]["action"] != row["action"]):
            raise RuntimeError("维护记录不完整或不属于当前数据库，须人工核查。")
        return row

    def lookup(self, request_key):
        key = validate_request_key(request_key)
        if self._records is None:
            self.records()
        return self._requests.get(key)

    def lookup_job(self, job_ref):
        path = self._path(job_ref)
        if job_ref in self._jobs:
            return self._jobs[job_ref]
        if self._records is not None:
            return None
        try:
            row = self._read(path)
        except FileNotFoundError:
            self.collection()
            return self._jobs.get(job_ref)
        self._jobs[job_ref] = row
        return row

    def pending(self, records=None):
        captured = self.records() if records is None else records
        return [row for row in captured if row["state"] not in TERMINAL_STATES]

    def _directory_entries(self):
        if self._entry_names is None:
            try:
                self._entry_names = os.listdir(self.directory)
            except FileNotFoundError:
                self._entry_names = []
        return self._entry_names

    def collection(self):
        count = (len(self._records) if self._records is not None else
                 sum(name.endswith(".json") for name in self._directory_entries()))
        if count > _JOURNAL_LIMIT:
            raise WorkbenchCommandRejected("maintenance_record_capacity", "维护记录条数超过一次能读的上限，这次没有列出。请让维护人员清理维护目录后再看。", 413)
        return self.records()

    def records(self):
        if self._records is not None:
            return self._records
        rows, requests, jobs = [], {}, {}
        for name in sorted(self._directory_entries()):
            if not name.endswith(".json"):
                continue
            if os.path.basename(name) != name:
                raise RuntimeError("维护记录文件名不完整，须人工核查。")
            cached = self._jobs.get(name[:-5])
            row = cached if cached is not None else self._read(os.path.join(self.directory, name))
            if row["request_key"] in requests or row["job_ref"] in jobs:
                raise RuntimeError("维护请求或操作编号重复，须人工核查。")
            requests[row["request_key"]] = row
            jobs[row["job_ref"]] = row
            rows.append(row)
        self._records, self._requests, self._jobs = rows, requests, jobs
        return rows

    def refresh(self):
        """Begin a new observation after a lock/transaction or request boundary."""
        self._records, self._requests, self._jobs = None, {}, {}
        self._entry_names = None
        self._database_scope = None
        return self.records()

    def assert_ready(self, records=None):
        captured = self.records() if records is None else records
        if self.pending(captured):
            raise WorkbenchCommandRejected("maintenance_active", "上一次维护还没有确认结果，这次没有执行。请先用操作编号查询上次维护的结果。", 503)

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
        original = {"action": action, "input": dict(intent)}
        if previous:
            if previous["action"] != action:
                raise WorkbenchCommandRejected("request_key_conflict", "这个操作编号对应的是另一次维护，这次没有执行。请重新提交。")
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
        updated = {**row, **values, "state": state, "updated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}
        updated["history"] = row["history"] + [{"state": state, "time": updated["updated_at"]}]
        path = self._path(row["job_ref"])
        temporary = path + "." + uuid.uuid4().hex + ".tmp"
        fd = create_fixed_file_exclusive(temporary)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(canonical_json(updated))
            stream.flush()
            os.fsync(stream.fileno())
        guard_fixed_file_open_target(path)
        os.replace(temporary, path)
        if os.name != "nt":
            directory_fd = os.open(self.directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        row.clear()
        row.update(updated)
        cached = self._jobs.get(row["job_ref"])
        if cached is not None and cached is not row:
            cached.clear()
            cached.update(updated)
        else:
            if self._records is not None and cached is None:
                self._records.append(row)
            self._jobs[row["job_ref"]] = row
            self._requests[row["request_key"]] = row
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
                "source_verification": dict(row["source_verification"]),
                "database_origin": row.get("database_origin", "unconfirmed"),
                "restart_required": row.get("restart_required", False),
                "restart_scope": "restoring_process" if row["action"] == "restore" else None,
                "references_require_reload": row["action"] == "restore"}


def assert_system_maintenance_ready(database_path, journal_dir):
    """Host hook: call BEFORE opening/migrating/writing the DB; never auto-resume."""
    journal = SystemMaintenanceJournal(journal_dir, database_path)
    records = journal.records()
    journal.assert_ready(records)
    return records
