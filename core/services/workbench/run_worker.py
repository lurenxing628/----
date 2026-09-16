"""One scheduler lock, short claim/result transactions, actual read-only computation."""

import json
from datetime import datetime

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.models.workbench_run_compute import CandidateRunInputError
from core.models.workbench_run_job import PROCESS_EXECUTOR_REF, validate_run_ref
from core.services.scheduler import schedule_service
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from data.repositories.workbench_run_result_repo import WorkbenchRunResultRepository, prepare_run_result

from .run_compute import compute_candidate_run
from .run_input_projection_codec import restore_execution_projections
from .run_input_readonly import candidate_read_snapshot
from .run_jobs_facts import run_facts_unchanged
from .run_progress import clear_progress, report_progress
from .run_worker_snapshot import computation_database


class WorkbenchRunWorker:
    def __init__(self, conn, *, clock=None):
        self.conn = conn
        self.clock = clock or datetime.now
        self.repo = WorkbenchRunRepository(conn)
        self.results = WorkbenchRunResultRepository(conn)

    def _now(self):
        return self.clock().isoformat(timespec="seconds")

    def _check_facts(self, row, conn=None):
        if not run_facts_unchanged(self.conn if conn is None else conn, row["facts_json"], row["facts_hash"]):
            raise WorkbenchCommandRejected("snapshot_stale", "排产之后现场数据有变化，这次的候选方案没有保存。请重新做一次排产检查。")

    def execute(self, run_ref):
        validate_run_ref(run_ref)
        if self.conn.in_transaction:
            raise RuntimeError("Run worker must own its connection's transactions")
        lock = schedule_service._RUN_SCHEDULE_LOCK
        if not lock.acquire(blocking=False):
            raise WorkbenchCommandRejected("scheduling_busy", "已经有一次排产在跑，这次没有重复计算。请等它结束后再看。")
        try:
            with TransactionManager(self.conn).transaction(begin_immediate=True):
                self.repo.require_schema()
                row = self.repo.get(run_ref)
                if row is None:
                    raise WorkbenchCommandRejected("entity_not_found", "找不到这次排产，页面没有打开。请到「排产记录」重新选择。", 404)
                if row["state"] != "queued" or row["stage"] != "queued":
                    return self.repo.public(row)
                self.repo.require_admission(row)
                if not self.repo.claim(run_ref, PROCESS_EXECUTOR_REF, self._now()):
                    raise RuntimeError("Run was claimed by another worker")
            try:
                candidates, result = self._compute(row)
            except Exception as exc:
                self._record_failure(row, exc)
                raise
            self._persist(row, candidates, result)
            return self.repo.public(self.repo.get(run_ref))
        finally:
            # The run is terminal (or failed to claim) here; the receipt is the record from now on.
            clear_progress(run_ref)
            lock.release()

    def _compute(self, row):
        with computation_database(self.conn) as snapshot, candidate_read_snapshot(snapshot):
            self._check_facts(row, snapshot)
            projections = restore_execution_projections(json.loads(row["execution_json"]))
            run_ref = row["run_ref"]
            computation = compute_candidate_run(
                snapshot, json.loads(row["normalized_input_json"]), projections,
                on_progress=lambda done, total: report_progress(run_ref, done, total, self._now()))
            identities = {int(item[0]): item[1] for item in snapshot.execute(
                "SELECT source_key,ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")}
            return prepare_run_result(computation, identities)

    def _persist(self, row, candidates, result):
        try:
            with TransactionManager(self.conn).transaction(begin_immediate=True):
                self._check_facts(row)
                current = self.repo.get(row["run_ref"])
                if current is None or current["state"] != "running" or current["executor_ref"] != PROCESS_EXECUTOR_REF:
                    raise RuntimeError("Run ownership changed before result persistence")
                self.results.save(row["run_ref"], candidates)
                self.repo.finish(row["run_ref"], result["state"], result, self._now())
        except WorkbenchCommandRejected as exc:
            self._record_failure(row, exc)
            raise
        except Exception as exc:
            # A COMMIT acknowledgement can fail after persistence. Recovery decides.
            raise WorkbenchCommandUncertain(row["request_key"]) from exc

    def _record_failure(self, row, exc):
        code = "snapshot_stale" if isinstance(exc, WorkbenchCommandRejected) and exc.code == "snapshot_stale" else "candidate_computation_failed"
        if isinstance(exc, CandidateRunInputError):
            code = exc.reason
        error = {"code": code, "message": "候选排产没有完成。请到「排产记录」查看原因，改好后重新做排产检查。"}
        result = {"state": "failed", "result_persisted": False, "candidates": [], "error": error,
                  "diagnostic": {"exception_type": type(exc).__name__, "message": str(exc)}}
        try:
            with TransactionManager(self.conn).transaction(begin_immediate=True):
                self.repo.finish(row["run_ref"], "failed", result, self._now())
        except Exception as storage_exc:
            raise WorkbenchCommandUncertain(row["request_key"]) from storage_exc
