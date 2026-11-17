"""Bounded SELECTs of the run ledger. Request-local reuse only; zero global caches."""

from contextlib import contextmanager
from typing import Optional

from core.models.content import read_stored_json
from core.models.enums import RUN_RESULT_STATE_VALUES, RUN_UNFINISHED_STATE_VALUES, RunState
from core.models.workbench_load_limits import MAX_RUN_RECORD_TASKS
from core.models.workbench_run_candidate import (
    MAX_ARTIFACT_BYTES,
    MAX_CANDIDATES,
    MAX_COLLECTION_BYTES,
    MAX_FACT_BYTES,
    local_time,
    reject,
)
from core.models.workbench_run_receipt import (
    FAILED_RECEIPT_KEYS,
    FAILED_RECEIPT_OPTIONAL_KEYS,
    PERSISTED_RECEIPT_KEYS,
    FailedReceipt,
    PersistedReceipt,
    RunReceipt,
)
from core.shared.key_sets import keys_conform
from core.shared.local_datetime import row_interval
from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository

from .candidate_artifact import admit_artifact
from .candidate_facts import admit_generation_facts
from .candidate_projection import scheduled_ids
from .candidate_values import bounded_size, corrupt
from .run_history_projection import admitted_run_input
from .run_input_readonly import candidate_read_snapshot

_CAPTURE_BYTE_KEYS = (
    "normalized_input_bytes",
    "execution_bytes",
    "baseline_bytes",
    "revisions_bytes",
    "conditions_archive_bytes",
)


def _candidate_record(row):
    """The one read boundary of a stored candidate: sizes, the admitted artifact (D3-5), then the row facts the
    artifact repeats: the same sequence and one validated operation per task row.

    ``WorkbenchRunCandidates`` DDL holds the candidate ref, the sequence and the task count, and its run ref is the
    key of a ``WorkbenchRunJobs`` row, whose DDL holds that ref.
    """
    bounded_size(row[5], MAX_ARTIFACT_BYTES)
    bounded_size(row[2], MAX_RUN_RECORD_TASKS)
    artifact = admit_artifact(read_stored_json(row[4], dict))
    if artifact["sequence"] != row[3] or len(artifact["validated_payload"]["scheduled_op_ids"]) != row[2]:
        corrupt()
    return {
        "candidate_ref": row[0],
        "run_ref": row[1],
        "task_count": row[2],
        "sequence": row[3],
        "artifact": artifact,
    }


def _receipt_record(state, raw) -> RunReceipt:
    """The one read boundary of a stored receipt: the form its run state allows, with exactly that form's keys.

    ``WorkbenchRunReceipts`` keeps the state of a finished run; one that saved candidate results is complete or
    partial, and one that failed or was interrupted saved none (``result_preparation``, ``worker``,
    ``worker_recovery``). The body records the same state.
    """
    body = read_stored_json(raw, dict)
    if state in RUN_RESULT_STATE_VALUES:
        if (not keys_conform(body, PERSISTED_RECEIPT_KEYS) or body["result_persisted"] is not True
                or body["error"] is not None or body["state"] != state):
            corrupt()
        return PersistedReceipt(state, body["candidates"], body["selection"], body["dispositions"], body["summary"],
                                body["unified_process"], body["operation_effort"])
    if (state not in (RunState.FAILED.value, RunState.INTERRUPTED.value)
            or not keys_conform(body, FAILED_RECEIPT_KEYS, FAILED_RECEIPT_OPTIONAL_KEYS)
            or body["result_persisted"] is not False or body["candidates"] != [] or body["state"] != state):
        corrupt()
    return FailedReceipt(state, body["error"], body.get("diagnostic"))


class CandidateStore:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchRunCandidateRepository(conn)
        self._receipt_by_run = {}
        self._candidates_by_run = {}
        self._candidate_by_ref = {}
        self._capture_by_run = {}
        self._facts_by_run = {}
        self._scheduled_ids_by_candidate = {}
        self._tasks_by_candidate = {}

    @contextmanager
    def snapshot(self):
        with candidate_read_snapshot(self.conn):
            yield

    def run(self, run_ref):
        row = self.repo.job_head(run_ref)
        if row is None:
            reject("entity_not_found", "找不到这次排产，页面没有打开。请到「排产记录」重新选择。", 404)
        try:
            local_time(row[2])
            if row[3] is not None:
                local_time(row[3])
        except (TypeError, ValueError):
            corrupt()
        return {
            "run_ref": row[0],
            "state": row[1],
            "accepted_at": row[2],
            "finished_at": row[3],
        }

    def receipt(self, run) -> Optional[RunReceipt]:
        """The run's receipt, or None while it is queued or running."""
        run_ref = run["run_ref"]
        if run_ref in self._receipt_by_run:
            result = self._receipt_by_run[run_ref]
            if result is None and run["state"] not in RUN_UNFINISHED_STATE_VALUES:
                corrupt()
            if result is not None and result.state != run["state"]:
                corrupt()
            return result
        row = self.repo.receipt_state_and_result(run_ref)
        if row is None:
            if run["state"] not in RUN_UNFINISHED_STATE_VALUES:
                corrupt()
            self._receipt_by_run[run_ref] = None
            return None
        bounded_size(row[2], MAX_ARTIFACT_BYTES)
        if row[0] != run["state"]:
            corrupt()
        result = _receipt_record(row[0], row[1])
        self._receipt_by_run[run_ref] = result
        return result

    def candidates(self, run_ref):
        if run_ref in self._candidates_by_run:
            return self._candidates_by_run[run_ref]
        rows, total_bytes = [], 0
        for row in self.repo.candidate_rows(run_ref, MAX_CANDIDATES + 1):
            bounded_size(len(rows) + 1, MAX_CANDIDATES)
            record = _candidate_record(row)
            total_bytes += row[5]
            bounded_size(total_bytes, MAX_COLLECTION_BYTES)
            self._candidate_by_ref[record["candidate_ref"]] = record
            rows.append(record)
        self._candidates_by_run[run_ref] = rows
        return rows

    def candidate(self, candidate_ref):
        if candidate_ref in self._candidate_by_ref:
            return self._candidate_by_ref[candidate_ref]
        row = self.repo.candidate_row(candidate_ref)
        if row is None:
            reject("entity_not_found", "未找到该永久候选，未改查最新结果。", 404)
        record = _candidate_record(row)
        self._candidate_by_ref[record["candidate_ref"]] = record
        return record

    def candidate_identity(self, candidate_ref):
        from .decision_read_models import decode_model

        row = self.repo.candidate_identity(candidate_ref)
        if row is None:
            reject("entity_not_found", "未找到该永久候选，未改查最新结果。", 404)
        summary = decode_model(row, ("summary",))["summary"]
        if summary["candidate_ref"] != row["candidate_ref"] or summary["run_ref"] != row["run_ref"]:
            corrupt()
        return {
            "candidate_ref": row["candidate_ref"],
            "run_ref": row["run_ref"],
            "label": summary["label"],
            "status": summary["catalog"]["status"],
        }

    def candidate_run(self, candidate_ref):
        run_ref = self.repo.candidate_run_ref(candidate_ref)
        if run_ref is None:
            reject("entity_not_found", "未找到该永久候选，未改查最新结果。", 404)
        return run_ref

    def capture(self, run_ref):
        if run_ref in self._capture_by_run:
            return self._capture_by_run[run_ref]
        row = self.repo.job_capture(run_ref)
        if row is None:
            corrupt()
        for key in _CAPTURE_BYTE_KEYS:
            bounded_size(row[key], MAX_FACT_BYTES)
        parsed = {
            "run_ref": run_ref,
            "input": admitted_run_input(read_stored_json(row["normalized_input_json"], dict)),
            "execution": read_stored_json(row["execution_json"], list),
            "baseline": read_stored_json(row["baseline_json"], dict),
            "revisions": read_stored_json(row["revisions_json"], dict),
            "facts": read_stored_json(row["conditions_archive_json"], dict),
        }
        self._capture_by_run[run_ref] = parsed
        return parsed

    def generation_facts(self, capture):
        """The admitted generation facts of a capture this store read (``capture``)."""
        run_ref = capture["run_ref"]
        if run_ref not in self._facts_by_run:
            self._facts_by_run[run_ref] = admit_generation_facts(capture)
        return self._facts_by_run[run_ref]

    def scheduled_op_ids(self, candidate):
        ref = candidate["candidate_ref"]
        if ref in self._scheduled_ids_by_candidate and self._candidate_by_ref.get(ref) is candidate:
            return set(self._scheduled_ids_by_candidate[ref])
        ids = scheduled_ids(candidate)
        if self._candidate_by_ref.get(ref) is candidate:
            self._scheduled_ids_by_candidate[ref] = frozenset(ids)
        return ids

    def tasks(self, candidate_ref):
        """The candidate's saved arrangements in ordinal order, typed once here.

        DDL holds the row identities, the source domain, both instants as integers a datetime can hold,
        start_us <= end_us, the point flag and the lock domain (workbench_run_schema.py:59,64,70-71,73-77);
        a gapless ordinal and one row per task its candidate row counts are beyond it and are checked here, so the
        rows are as many as the candidate's validated operations (``_candidate_record``). The text time columns are
        display only and are not read.
        """
        if candidate_ref in self._tasks_by_candidate:
            return self._tasks_by_candidate[candidate_ref]
        result = []
        for row in self.repo.task_rows(candidate_ref, MAX_RUN_RECORD_TASKS + 1):
            bounded_size(len(result) + 1, MAX_RUN_RECORD_TASKS)
            if row["ordinal"] != len(result):
                corrupt()
            start, end = row_interval(row)
            result.append({
                "row_ref": row["row_ref"],
                "operation_ref": row["operation_ref"],
                "op_id": row["op_id"],
                "source": row["source"],
                "machine_id": row["machine_id"],
                "operator_id": row["operator_id"],
                "start_time": start,
                "end_time": end,
                "locked": row["locked"] == 1,
            })
        if len(result) != self.candidate(candidate_ref)["task_count"]:
            corrupt()
        self._tasks_by_candidate[candidate_ref] = result
        return result
