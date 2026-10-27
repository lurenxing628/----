"""Bounded SELECTs of the run ledger. No install, repair or live-entity lookup."""

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
from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository

from .candidate_values import bounded_size, corrupt, stored_json
from .run_input_readonly import candidate_read_snapshot


def _candidate_record(row):
    bounded_size(row[6], MAX_ARTIFACT_BYTES)
    bounded_size(row[3], MAX_TASKS)
    if type(row[4]) is not int or row[4] < 0:
        corrupt()
    return {"candidate_ref": reference(row[0], stored=True), "run_ref": reference(row[1], stored=True),
            "status": row[2], "task_count": row[3], "sequence": row[4], "artifact": stored_json(row[5])}


class CandidateStore:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchRunCandidateRepository(conn)

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
        return {"run_ref": reference(row[0], stored=True), "state": row[1],
                "accepted_at": row[2], "finished_at": row[3]}

    def receipt(self, run):
        row = self.repo.receipt_state_and_result(run["run_ref"])
        if row is None:
            if run["state"] not in ("queued", "running"):
                corrupt()
            return None
        bounded_size(row[2], MAX_ARTIFACT_BYTES)
        result = stored_json(row[1])
        if row[0] != run["state"] or result.get("state") != run["state"]:
            corrupt()
        return result

    def candidates(self, run_ref):
        rows, total_bytes, seen = [], 0, set()
        for row in self.repo.candidate_rows(run_ref, MAX_CANDIDATES + 1):
            bounded_size(len(rows) + 1, MAX_CANDIDATES)
            record = _candidate_record(row)
            total_bytes += row[6]
            bounded_size(total_bytes, MAX_COLLECTION_BYTES)
            if row[0] in seen or row[1] != run_ref:
                corrupt()
            seen.add(row[0])
            rows.append(record)
        return rows

    def candidate(self, candidate_ref):
        row = self.repo.candidate_row(candidate_ref)
        if row is None:
            reject("entity_not_found", "未找到该永久候选，未改查最新结果。", 404)
        return _candidate_record(row)

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
        for size in row[4:]:
            bounded_size(size, MAX_FACT_BYTES)
        return {"input": stored_json(row[0]), "execution": stored_json(row[1], list),
                "baseline": stored_json(row[2]), "facts_text": row[3]}

    def tasks(self, candidate_ref):
        result, total_bytes = [], 0
        for row in self.repo.task_rows(candidate_ref, MAX_TASKS + 1):
            bounded_size(len(result) + 1, MAX_TASKS)
            bounded_size(row[4], MAX_ARTIFACT_BYTES)
            total_bytes += row[4]
            bounded_size(total_bytes, MAX_COLLECTION_BYTES)
            if row[2] != len(result):
                corrupt()
            result.append({"row_ref": reference(row[0], stored=True), "operation_ref": reference(row[1], stored=True),
                           "payload": stored_json(row[3])})
        return result
