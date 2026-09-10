"""Read-only proof of the launcher's current, exact database lock ownership."""

import os
import sys

from .launcher_lock_result import read_runtime_lock_result_from_path
from .launcher_paths import (
    _normalize_db_path_for_runtime,
    current_runtime_owner,
    db_scope_lock_path,
    runtime_lock_path,
)


class RunRuntimeOwnershipError(RuntimeError):
    pass


def _identity(payload):
    return tuple(str(payload.get(key) or "") for key in
                 ("pid", "owner", "exe_path", "started_at", "db_path"))


def _read_owned(path, db_path):
    result = read_runtime_lock_result_from_path(path)
    if not result.ok or result.payload is None:
        raise RunRuntimeOwnershipError("runtime_lock_" + result.status + ": " + path)
    payload = result.payload
    if (payload["pid"] != os.getpid()
            or payload.get("owner") != current_runtime_owner()
            or _normalize_db_path_for_runtime(payload.get("exe_path")) !=
            _normalize_db_path_for_runtime(sys.executable)
            or _normalize_db_path_for_runtime(payload.get("db_path")) != db_path
            or not payload.get("started_at")):
        raise RunRuntimeOwnershipError("runtime_lock_owner_mismatch: " + path)
    stat = os.stat(path)
    return _identity(payload), (stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_size)


class RunRuntimeLockProof:
    """A payload is only a claim; both real lock files must still match it.

    The launcher acquires shell and DB locks separately, possibly across a clock
    second. Their started_at values need not match; each is pinned independently.
    No path here acquires, removes, repairs, or releases a lock.
    """

    def __init__(self, db_path, runtime_lock):
        self.db_path = _normalize_db_path_for_runtime(db_path)
        if not isinstance(runtime_lock, dict) or not self.db_path:
            raise RunRuntimeOwnershipError("runtime_lock_not_supplied")
        self.claim = dict(runtime_lock)
        state_dir = str(self.claim.get("state_dir") or "")
        self.shell_path = str(self.claim.get("path") or "")
        if (not state_dir or not self.shell_path
                or _normalize_db_path_for_runtime(self.shell_path) !=
                _normalize_db_path_for_runtime(runtime_lock_path(state_dir))):
            raise RunRuntimeOwnershipError("runtime_lock_shell_path_mismatch")
        self.db_lock_path = db_scope_lock_path(self.db_path)
        self._require_database()
        self.shell = _read_owned(self.shell_path, self.db_path)
        if self.shell[0] != _identity(self.claim):
            raise RunRuntimeOwnershipError("runtime_lock_claim_mismatch")
        self.database_lock = _read_owned(self.db_lock_path, self.db_path)

    def _require_database(self):
        # The legacy lock is lexical. Aliases would have a second lock namespace.
        if (self.db_path != os.path.normcase(os.path.realpath(self.db_path))
                or not os.path.isfile(self.db_path) or os.stat(self.db_path).st_nlink != 1):
            raise RunRuntimeOwnershipError("runtime_database_missing_or_aliased")

    def verify(self):
        self._require_database()
        if (_read_owned(self.shell_path, self.db_path) != self.shell
                or _read_owned(self.db_lock_path, self.db_path) != self.database_lock):
            raise RunRuntimeOwnershipError("runtime_lock_replaced")

    def matches(self, db_path, runtime_lock):
        return (self.db_path == _normalize_db_path_for_runtime(db_path)
                and isinstance(runtime_lock, dict) and runtime_lock == self.claim)
