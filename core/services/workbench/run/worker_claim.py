"""Only unstarted, freshly verified run claims may retry transient SQLite locks."""

import sqlite3

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_run_job import PROCESS_EXECUTOR_REF
from core.services.workbench.facts.run_policy import public_run, require_admission, require_run_schema
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_run_repo import WorkbenchRunRepository


class RunClaimBusy(RuntimeError):
    """Claim ended on a clean connection; a fresh read must prove no commit won.

    This is never raised for computation or result persistence. A clean old
    connection alone does NOT establish that the claim was rolled back.
    """


def _is_sqlite_lock(exc):
    code = getattr(exc, "sqlite_errorcode", None)
    if isinstance(code, int):
        return code & 0xFF in (5, 6)  # SQLITE_BUSY / SQLITE_LOCKED, including extended codes.
    # Python 3.8 does not expose sqlite_errorcode. Do not classify other failures
    # from a vague substring such as "lock".
    return str(exc).lower() in ("database is locked", "database table is locked")


def claim_run(conn, run_ref, now, retry_original=None):
    repo = WorkbenchRunRepository(conn)
    try:
        with TransactionManager(conn).transaction(begin_immediate=True):
            require_run_schema(repo)
            row = repo.get(run_ref)
            if row is None:
                raise WorkbenchCommandRejected("entity_not_found", "找不到这次排产，页面没有打开。请到「排产记录」重新选择。", 404)
            if retry_original is not None:
                _require_unchanged_unclaimed(repo, row, retry_original)
            if row["state"] != "queued" or row["stage"] != "queued":
                return None, public_run(conn, row)
            require_admission(repo, row)
            if not repo.claim(run_ref, PROCESS_EXECUTOR_REF, now()):
                raise RuntimeError("Run was claimed by another worker")
        return row, None
    except sqlite3.OperationalError as exc:
        # TransactionManager surfaces rollback failure as RuntimeError. BEGIN
        # contention also reaches here without ever opening a transaction.
        if _is_sqlite_lock(exc) and not conn.in_transaction:
            raise RunClaimBusy("Run claim hit a transient SQLite lock before computation") from exc
        raise


def require_retryable_claim(conn, original):
    """Read one consistent, fresh snapshot without taking a write reservation."""
    if conn.in_transaction:
        raise RuntimeError("Claim retry verification requires a fresh connection")
    repo = WorkbenchRunRepository(conn)
    with TransactionManager(conn).transaction():
        require_run_schema(repo)
        row = repo.get(original["job"]["run_ref"])
        _require_unchanged_unclaimed(repo, row, original)


def capture_claim_retry_state(conn, run_ref):
    """Remember both immutable records before the first claim can encounter BUSY."""
    repo = WorkbenchRunRepository(conn)
    with TransactionManager(conn).transaction():
        require_run_schema(repo)
        row = repo.get(run_ref)
        if row is None:
            raise RuntimeError("Run disappeared before claim")
        original = {"job": row, "admission": _admission(conn, row)}
        _require_unchanged_unclaimed(repo, row, original)
        return original


def _admission(conn, row):
    repo = WorkbenchCommandRepository(conn)
    receipt = repo.get(row["request_key"])
    if (receipt is None or receipt["action"] != "scheduling.run" or receipt["context_ref"] != row["input_ref"]
            or receipt["input_hash"] != input_fingerprint({"input_ref": row["input_ref"]})):
        raise RuntimeError("Run claim admission is inconsistent")
    outcome = repo.public_result(receipt, replayed=True)
    if outcome["result"] != "committed" or outcome["data"] != {"run_ref": row["run_ref"]}:
        raise RuntimeError("Run claim admission did not commit this original run")
    return receipt


def _require_unchanged_unclaimed(repo, row, original):
    if (row is None or row != original["job"] or row["state"] != "queued" or row["stage"] != "queued"
            or any(row[key] is not None for key in ("executor_ref", "started_at", "finished_at", "error_json"))
            or repo.receipt(row["run_ref"]) is not None or repo.has_candidates(row["run_ref"])):
        raise RuntimeError("Run claim retry evidence changed; reconciliation required")
    require_admission(repo, row)
    if _admission(repo.conn, row) != original["admission"]:
        raise RuntimeError("Run claim admission changed; reconciliation required")
