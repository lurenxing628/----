"""One scheduler lock, short claim/result transactions, actual read-only computation."""

from datetime import datetime

from core.errors import AppError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.models.workbench_run_compute import CandidateRunInputError
from core.models.workbench_run_job import PROCESS_EXECUTOR_REF, validate_run_ref
from core.services.scheduler.schedule_lock import RUN_SCHEDULE_LOCK
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.candidate_values import stored_json
from core.services.workbench.facts.decision_read_model import build_failure_read_models
from core.services.workbench.facts.decision_read_models import decode_model, public_job_head
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.facts.run_history_projection import (
    COMPUTATION_FAILED,
    failure_message,
    hold_failure_message,
)
from core.services.workbench.facts.run_input_codec import restore_execution_projections
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from data.repositories.workbench_run_result_repo import WorkbenchRunResultRepository

from .compute import compute_candidate_run
from .jobs_facts import production_facts_match
from .result_preparation import prepare_run_result
from .worker_claim import claim_run
from .worker_snapshot import computation_database

# 计算子进程只把清洗后的提示带回 AppError，原异常类型和原文放在 internal_details 的这个键里，只进诊断。
CHILD_EXCEPTION = "child_exception"


def failure_diagnostic(exc):
    """诊断记原异常类型和原文；子进程带回的 AppError 用它在子进程里的原样，和线程模式记的一致。"""
    details = exc.internal_details if isinstance(exc, AppError) and isinstance(exc.internal_details, dict) else {}
    carried = details.get(CHILD_EXCEPTION)
    if isinstance(carried, dict) and all(type(carried.get(key)) is str for key in ("exception_type", "message")):
        return {"exception_type": carried["exception_type"], "message": carried["message"]}
    return {"exception_type": type(exc).__name__, "message": str(exc)}


class WorkbenchRunWorker:
    def __init__(self, conn, *, clock=None, compute_runner=None, app_error_message=None):
        self.conn = conn
        self.clock = clock or datetime.now
        self.repo = WorkbenchRunRepository(conn)
        self.results = WorkbenchRunResultRepository(conn)
        self.compute_runner = compute_runner
        # AppError 给用户看的提示由宿主传入的 web 层清洗函数给出；没传时按计算失败处理，不外露原文。
        self.app_error_message = app_error_message

    def _now(self):
        return self.clock().isoformat(timespec="microseconds")

    def _check_facts(self, row, conn=None, *, capture=None):
        if not production_facts_match(self.conn if conn is None else conn, row["facts_json"], capture=capture):
            raise WorkbenchCommandRejected("snapshot_stale", "排产之后现场数据有变化，这次的候选方案没有保存。请重新做一次排产检查。")

    def execute(self, run_ref, *, retry_original=None):
        validate_run_ref(run_ref)
        if self.conn.in_transaction:
            raise RuntimeError("Run worker must own its connection's transactions")
        lock = RUN_SCHEDULE_LOCK
        if not lock.acquire(blocking=False):
            raise WorkbenchCommandRejected("scheduling_busy", "已经有一次排产在跑，这次没有重复计算。请等它结束后再看。")
        try:
            row, existing = claim_run(self.conn, run_ref, self._now, retry_original)
            if existing is not None:
                return existing
            admission = decode_model(self.repo.admission_read_model(run_ref, fields=("scope", "decision")), ("scope", "decision"))
            try:
                prepared_result = self._compute(row, admission["decision"])
            except Exception as exc:
                self._record_failure(row, exc, admission["decision"])
                raise
            written = self._persist(row, prepared_result, admission["decision"])
            return public_job_head({**row, **written}, admission["scope"], prepared_result.status_header)
        finally:
            lock.release()

    def _compute(self, row, admission):
        if self.compute_runner is not None:
            return self.compute_runner(self.conn, row, admission=admission)
        with computation_database(self.conn) as snapshot:
            return self.compute_owned_snapshot(snapshot, row, admission)

    def compute_owned_snapshot(self, snapshot, row, admission):
        """Consume the caller's isolated database without copying it again."""
        with candidate_read_snapshot(snapshot):
            current_capture = ProductionFactsCapture(snapshot)
            self._check_facts(row, snapshot, capture=current_capture)
            # 与 CandidateStore.capture 读同一组排产原件，同一个严格读取器。
            raw_execution = stored_json(row["execution_json"], list)
            normalized_input = stored_json(row["normalized_input_json"])
            projections = restore_execution_projections(raw_execution)
            computation = compute_candidate_run(snapshot, normalized_input, projections, capture=current_capture,
                                                dispositions=admission["dispositions"])
            capture = {"input": normalized_input, "execution": raw_execution,
                       "baseline": stored_json(row["baseline_json"]), "facts_text": row["facts_json"],
                       "facts_hash": row["facts_hash"]}
            facts = GenerationFacts(capture)
            identities = {op_id: ref for ref, op_id in facts.operations.items()}
            return prepare_run_result(computation, identities, run=row, capture=capture, admission=admission, facts=facts)

    def _persist(self, row, prepared, admission):
        candidates, result = prepared.candidates, prepared.result
        try:
            with TransactionManager(self.conn).transaction(begin_immediate=True):
                self._check_facts(row)
                current = self.repo.claim_head(row["run_ref"])
                if current is None or current["state"] != "running" or current["executor_ref"] != PROCESS_EXECUTOR_REF:
                    raise RuntimeError("Run ownership changed before result persistence")
                self.results.save(row["run_ref"], candidates)
                self.repo.insert_prepared_decision_read_models(row["run_ref"], prepared.read_models["run_model"],
                                                     prepared.read_models["candidate_models"])
                written = self.repo.finish_prepared(row["run_ref"], result, self._now())
            return written
        except WorkbenchCommandRejected as exc:
            self._record_failure(row, exc, admission)
            raise
        except Exception as exc:
            # A COMMIT acknowledgement can fail after persistence. Recovery decides.
            raise WorkbenchCommandUncertain(row["request_key"]) from exc

    def _public_error(self, exc):
        """这次失败的确定原因，原样给用户；内部异常的原文（堆栈、SQL、英文校验）只进 diagnostic。"""
        if isinstance(exc, WorkbenchCommandRejected) and exc.code == "snapshot_stale":
            return {"code": exc.code, "message": str(exc)}
        if isinstance(exc, CandidateRunInputError):
            return {"code": exc.reason, "message": failure_message(exc.reason, str(exc))}
        held = hold_failure_message(exc) if isinstance(exc, AppError) else None
        if held is not None:
            return {"code": "candidate_input_invalid", "message": held}
        if isinstance(exc, AppError) and self.app_error_message is not None:
            return {"code": "candidate_input_invalid", "message": self.app_error_message(exc)}
        return {"code": "candidate_computation_failed", "message": COMPUTATION_FAILED}

    def _record_failure(self, row, exc, admission):
        result = {"state": "failed", "result_persisted": False, "candidates": [], "error": self._public_error(exc),
                  "diagnostic": failure_diagnostic(exc)}
        try:
            with TransactionManager(self.conn).transaction(begin_immediate=True):
                models = build_failure_read_models(row, admission, result)
                self.repo.insert_decision_read_models(row["run_ref"], models["run_model"], models["candidate_models"])
                self.repo.finish(row["run_ref"], "failed", result, self._now())
        except Exception as storage_exc:
            raise WorkbenchCommandUncertain(row["request_key"]) from storage_exc
