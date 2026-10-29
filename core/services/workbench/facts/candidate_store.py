"""Bounded SELECTs of the run ledger. No install, repair or live-entity lookup."""

import threading
from contextlib import contextmanager

from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.workbench_run_schema import workbench_run_contract_issues
from core.models.workbench_run_candidate import (
    MAX_ARTIFACT_BYTES,
    MAX_CANDIDATES,
    MAX_COLLECTION_BYTES,
    MAX_FACT_BYTES,
    MAX_TASKS,
    local_time,
    reference,
    reject,
)
from core.shared.strict_json import clone_json
from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository

from .candidate_facts import GenerationFacts
from .candidate_projection import completed_dispositions, scheduled_ids
from .candidate_values import bounded_size, corrupt, stored_json
from .decision_metrics import admission_operation_refs
from .run_input_readonly import candidate_read_snapshot

_CACHE_LOCK = threading.RLock()
_CANDIDATE_RECORD_CACHE = {}
_RECEIPT_CACHE = {}
_CAPTURE_CACHE = {}
_TASKS_CACHE = {}
_GENERATION_FACTS_CACHE = {}
_DISPOSITIONS_CACHE = {}
_SCHEDULED_IDS_CACHE = {}


def cache_get(cache, key):
    with _CACHE_LOCK:
        return cache.get(key)


def cache_memo(cache, key, value, limit=32):
    with _CACHE_LOCK:
        if key in cache:
            cache.pop(key)
        elif len(cache) >= limit:
            cache.pop(next(iter(cache)))
        cache[key] = value
        return value


def _copy_capture(cached):
    return {
        "input": clone_json(cached["input"]),
        "execution": clone_json(cached["execution"]),
        "baseline": clone_json(cached["baseline"]),
        "facts_text": cached["facts_text"],
    }


def _copy_scope(scope):
    return clone_json(scope)


def _copy_receipt(result):
    return clone_json(result)


def _candidate_record(row, *, copy_on_read=True):
    cached = cache_get(_CANDIDATE_RECORD_CACHE, row)
    if cached is not None:
        return dict(cached, artifact=clone_json(cached["artifact"])) if copy_on_read else cached
    bounded_size(row[6], MAX_ARTIFACT_BYTES)
    bounded_size(row[3], MAX_TASKS)
    if type(row[4]) is not int or row[4] < 0:
        corrupt()
    record = {"candidate_ref": reference(row[0], stored=True), "run_ref": reference(row[1], stored=True),
              "status": row[2], "task_count": row[3], "sequence": row[4], "artifact": stored_json(row[5])}
    cache_memo(_CANDIDATE_RECORD_CACHE, row, record, limit=64)
    return dict(record, artifact=clone_json(record["artifact"])) if copy_on_read else record


def _execution_cache_key(execution):
    if type(execution) is not list:
        return None
    items = []
    for row in execution:
        if type(row) is not dict:
            return None
        items.append((
            row.get("operation_ref"),
            row.get("target_quantity"),
            row.get("known_completed_quantity"),
            row.get("remaining_quantity"),
            row.get("execution_state"),
            row.get("data_quality"),
            row.get("target_basis"),
            row.get("first_actual_start"),
            row.get("confirmed_finish"),
            row.get("completion_basis"),
            row.get("quantity_complete"),
            row.get("records_complete"),
            row.get("unknown_record_count"),
        ))
    return tuple(items)


def cached_generation_facts(capture, *, raw_row=None):
    if type(capture) is not dict or type(capture.get("facts_text")) is not str:
        return GenerationFacts(capture)
    facts_text = capture["facts_text"]
    raw_key = (raw_row[3], raw_row[1]) if raw_row is not None and raw_row[3] == facts_text else None
    if raw_key is not None:
        cached = cache_get(_GENERATION_FACTS_CACHE, raw_key)
        if cached is not None:
            return cached
    exec_key = _execution_cache_key(capture.get("execution"))
    content_key = (facts_text, exec_key) if exec_key is not None else None
    if content_key is not None:
        cached = cache_get(_GENERATION_FACTS_CACHE, content_key)
        if cached is not None:
            if raw_key is not None:
                cache_memo(_GENERATION_FACTS_CACHE, raw_key, cached)
            return cached
    facts = GenerationFacts(capture)
    if content_key is not None:
        cache_memo(_GENERATION_FACTS_CACHE, content_key, facts)
    if raw_key is not None:
        cache_memo(_GENERATION_FACTS_CACHE, raw_key, facts)
    return facts


class CandidateStore:
    def __init__(self, conn, *, copy_on_read: bool = True):
        self.conn = conn
        self.copy_on_read = copy_on_read
        self.repo = WorkbenchRunCandidateRepository(conn)
        self._last_run_row = None
        self._last_receipt_row = None
        self._last_candidate_row_by_ref = {}
        self._last_capture_row = None
        self._last_task_rows_by_ref = {}

    @contextmanager
    def snapshot(self):
        with candidate_read_snapshot(self.conn):
            if schema_contract_memo(self.conn).get_schema(workbench_run_contract_issues):
                reject("candidate_schema_unavailable", "排产记录结构不完整，请联系维护人员。", 503)
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
        self._last_run_row = row
        return {"run_ref": reference(row[0], stored=True), "state": row[1],
                "accepted_at": row[2], "finished_at": row[3]}

    def receipt(self, run):
        row = self.repo.receipt_state_and_result(run["run_ref"])
        self._last_receipt_row = row
        if row is None:
            if run["state"] not in ("queued", "running"):
                corrupt()
            return None
        bounded_size(row[2], MAX_ARTIFACT_BYTES)
        result = cache_get(_RECEIPT_CACHE, (row[1], row[2]))
        if result is None:
            result = cache_memo(_RECEIPT_CACHE, (row[1], row[2]), stored_json(row[1]))
        if row[0] != run["state"] or result.get("state") != run["state"]:
            corrupt()
        return _copy_receipt(result) if self.copy_on_read else result

    def candidates(self, run_ref):
        rows, total_bytes, seen = [], 0, set()
        for row in self.repo.candidate_rows(run_ref, MAX_CANDIDATES + 1):
            bounded_size(len(rows) + 1, MAX_CANDIDATES)
            record = _candidate_record(row, copy_on_read=self.copy_on_read)
            total_bytes += row[6]
            bounded_size(total_bytes, MAX_COLLECTION_BYTES)
            if row[0] in seen or row[1] != run_ref:
                corrupt()
            seen.add(row[0])
            self._last_candidate_row_by_ref[record["candidate_ref"]] = row
            rows.append(record)
        return rows

    def candidate(self, candidate_ref):
        row = self.repo.candidate_row(candidate_ref)
        if row is None:
            reject("entity_not_found", "未找到该永久候选，未改查最新结果。", 404)
        record = _candidate_record(row, copy_on_read=self.copy_on_read)
        self._last_candidate_row_by_ref[record["candidate_ref"]] = row
        return record

    def candidate_identity(self, candidate_ref):
        from .decision_read_models import decode_model

        row = self.repo.candidate_identity(candidate_ref)
        if row is None:
            reject("entity_not_found", "未找到该永久候选，未改查最新结果。", 404)
        summary = decode_model(row, ("summary",))["summary"]
        if (summary.get("candidate_ref") != row["candidate_ref"] or summary.get("run_ref") != row["run_ref"]
                or summary.get("persisted_status") != row["status"]):
            corrupt()
        return {"candidate_ref": reference(row["candidate_ref"], stored=True),
                "run_ref": reference(row["run_ref"], stored=True), "label": summary.get("label"), "status": row["status"]}

    def candidate_run(self, candidate_ref):
        run_ref = self.repo.candidate_run_ref(candidate_ref)
        if run_ref is None:
            reject("entity_not_found", "未找到该永久候选，未改查最新结果。", 404)
        return reference(run_ref, stored=True)

    def capture(self, run_ref):
        row = self.repo.job_capture(run_ref)
        if row is None:
            corrupt()
        self._last_capture_row = row
        cached = cache_get(_CAPTURE_CACHE, row)
        if cached is not None:
            return _copy_capture(cached) if self.copy_on_read else cached
        for size in row[4:]:
            bounded_size(size, MAX_FACT_BYTES)
        parsed = {"input": stored_json(row[0]), "execution": stored_json(row[1], list),
                  "baseline": stored_json(row[2]), "facts_text": row[3]}
        cache_memo(_CAPTURE_CACHE, row, parsed)
        return _copy_capture(parsed) if self.copy_on_read else parsed

    def generation_facts(self, capture):
        return cached_generation_facts(capture, raw_row=self._last_capture_row)

    def dispositions(self, receipt, facts, capture):
        raw_receipt, raw_capture = self._last_receipt_row, self._last_capture_row
        if raw_receipt is not None and raw_capture is not None:
            key = (raw_receipt[1], raw_capture[0], raw_capture[3])
            cached = cache_get(_DISPOSITIONS_CACHE, key)
            if cached is not None:
                return _copy_scope(cached) if self.copy_on_read else cached
            scope = completed_dispositions(receipt, expected_refs=admission_operation_refs(facts, capture["input"]))
            cached = cache_memo(_DISPOSITIONS_CACHE, key, _copy_scope(scope) if self.copy_on_read else scope)
            return _copy_scope(cached) if self.copy_on_read else cached
        return completed_dispositions(receipt, expected_refs=admission_operation_refs(facts, capture["input"]))

    def scheduled_op_ids(self, candidate):
        raw_row = self._last_candidate_row_by_ref.get(candidate["candidate_ref"])
        if raw_row is not None:
            key = (raw_row[0], raw_row[3], raw_row[5])
            cached = cache_get(_SCHEDULED_IDS_CACHE, key)
            if cached is not None:
                return set(cached)
            ids = scheduled_ids(candidate)
            cache_memo(_SCHEDULED_IDS_CACHE, key, frozenset(ids), limit=64)
            return ids
        return scheduled_ids(candidate)

    def tasks(self, candidate_ref):
        raw_rows, total_bytes = [], 0
        for row in self.repo.task_rows(candidate_ref, MAX_TASKS + 1):
            bounded_size(len(raw_rows) + 1, MAX_TASKS)
            bounded_size(row[4], MAX_ARTIFACT_BYTES)
            total_bytes += row[4]
            bounded_size(total_bytes, MAX_COLLECTION_BYTES)
            if row[2] != len(raw_rows):
                corrupt()
            raw_rows.append(row)
        raw_rows = tuple(raw_rows)
        self._last_task_rows_by_ref[candidate_ref] = raw_rows
        cached = cache_get(_TASKS_CACHE, (candidate_ref, raw_rows))
        if cached is not None:
            return [dict(row, payload=clone_json(row["payload"])) for row in cached] if self.copy_on_read else cached
        result = [
            {
                "row_ref": reference(row[0], stored=True),
                "operation_ref": reference(row[1], stored=True),
                "payload": stored_json(row[3]),
            }
            for row in raw_rows
        ]
        cache_memo(_TASKS_CACHE, (candidate_ref, raw_rows), result)
        return [dict(row, payload=clone_json(row["payload"])) for row in result] if self.copy_on_read else result

    def build_adoption_raw_key(self, candidate_ref, admission_head):
        if self._last_run_row is None or self._last_capture_row is None:
            return None
        return (
            self._last_run_row,
            admission_head.get("request_key") if type(admission_head) is dict else None,
            admission_head.get("input_ref") if type(admission_head) is dict else None,
            self._last_receipt_row,
            self._last_candidate_row_by_ref.get(candidate_ref),
            self._last_capture_row,
            self._last_task_rows_by_ref.get(candidate_ref),
        )


class ReadOnlyCandidateStore(CandidateStore):
    def __init__(self, conn):
        super().__init__(conn, copy_on_read=False)
