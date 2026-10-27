"""Only unstarted, freshly verified run claims may retry transient SQLite locks."""

import sqlite3
from typing import Any, Dict, Optional, Tuple, cast

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_job import PROCESS_EXECUTOR_REF
from core.services.workbench.facts.decision_read_models import public_job_status
from core.services.workbench.facts.run_policy import require_admission, require_run_schema
from core.shared.strict_json import canonical_json
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


def claim_run(conn, run_ref, now, retry_original=None) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    repo = WorkbenchRunRepository(conn)
    try:
        with TransactionManager(conn).transaction(begin_immediate=True):
            require_run_schema(repo)
            row = repo.get(run_ref) if retry_original is not None else repo.claim_head(run_ref)
            if row is None:
                raise WorkbenchCommandRejected("entity_not_found", "找不到这次排产，页面没有打开。请到「排产记录」重新选择。", 404)
            if retry_original is not None:
                _require_unchanged_unclaimed(repo, row, retry_original)
            else:
                if row["state"] != "queued" or row["stage"] != "queued":
                    return row, public_job_status(repo.status(run_ref))
                # The same write transaction already owns this observed job.
                row = cast(Dict[str, Any], repo.get(run_ref))
                require_admission(repo, row)
            claimed = repo.claim(run_ref, PROCESS_EXECUTOR_REF, now())
            if claimed is None:
                raise RuntimeError("Run was claimed by another worker")
            row.update(claimed)
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
        _require_unclaimed_row(repo, row)
        return {"job": row, "admission": _admission(conn, row)}


def _admission(conn, row):
    repo = WorkbenchCommandRepository(conn)
    receipt = repo.get(row["request_key"])
    if (receipt is None or receipt["action"] != "scheduling.run" or receipt["context_ref"] != row["input_ref"]
            or repo.input_content(receipt) != canonical_json({"input_ref": row["input_ref"]})):
        raise RuntimeError("Run claim admission is inconsistent")
    outcome = repo.public_result(receipt, replayed=True)
    if outcome["result"] != "committed" or outcome["data"] != {"run_ref": row["run_ref"]}:
        raise RuntimeError("Run claim admission did not commit this original run")
    return receipt


def _require_unclaimed_row(repo, row):
    if (row is None or row["state"] != "queued" or row["stage"] != "queued"
            or any(row[key] is not None for key in ("executor_ref", "started_at", "finished_at", "error_json"))
            or repo.receipt(row["run_ref"]) is not None or repo.has_candidates(row["run_ref"])):
        raise RuntimeError("Run claim retry evidence changed; reconciliation required")


def _require_unchanged_unclaimed(repo, row, original):
    _require_unclaimed_row(repo, row)
    if row != original["job"]:
        raise RuntimeError("Run claim retry evidence changed; reconciliation required")
    if WorkbenchCommandRepository(repo.conn).get(row["request_key"]) != original["admission"]:
        raise RuntimeError("Run claim admission changed; reconciliation required")
