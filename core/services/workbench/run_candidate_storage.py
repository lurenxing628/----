"""Bounded SELECTs of the run ledger. No install, repair or live-entity lookup."""

from contextlib import contextmanager

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

from .run_candidate_values import bounded_size, corrupt, stored_json
from .run_input_readonly import candidate_read_snapshot


class CandidateStore:
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def snapshot(self):
        with candidate_read_snapshot(self.conn):
            if workbench_run_contract_issues(self.conn):
                reject("candidate_schema_unavailable", "排产记录用的结构还没装好或不完整，读不出来，系统也不会自动修。请联系维护人员。", 503)
            yield

    def run(self, run_ref):
        row = self.conn.execute("""SELECT run_ref,state,accepted_at,finished_at,
            length(CAST(normalized_input_json AS BLOB)),length(CAST(execution_json AS BLOB)),
            length(CAST(baseline_json AS BLOB)),length(CAST(facts_json AS BLOB))
            FROM WorkbenchRunJobs WHERE run_ref=?""", (run_ref,)).fetchone()
        if row is None:
            reject("entity_not_found", "找不到这次排产，页面没有打开。请到「排产记录」重新选择。", 404)
        for size in row[4:]:
            bounded_size(size, MAX_FACT_BYTES)
        try:
            local_time(row[2])
            if row[3] is not None:
                local_time(row[3])
        except (TypeError, ValueError):
            corrupt()
        return {"run_ref": reference(row[0], stored=True), "state": row[1],
                "accepted_at": row[2], "finished_at": row[3]}

    def receipt(self, run):
        row = self.conn.execute("SELECT length(CAST(result_json AS BLOB)) FROM WorkbenchRunReceipts WHERE run_ref=?",
                                (run["run_ref"],)).fetchone()
        if row is None:
            if run["state"] not in ("queued", "running"):
                corrupt()
            return None
        bounded_size(row[0], MAX_ARTIFACT_BYTES)
        row = self.conn.execute("SELECT state,result_json FROM WorkbenchRunReceipts WHERE run_ref=?",
                                (run["run_ref"],)).fetchone()
        result = stored_json(row[1])
        if row[0] != run["state"] or result.get("state") != run["state"]:
            corrupt()
        return result

    def candidates(self, run_ref):
        sizes = list(self.conn.execute("""SELECT candidate_ref,length(CAST(artifact_json AS BLOB)),task_count
            FROM WorkbenchRunCandidates WHERE run_ref=? ORDER BY sequence LIMIT ?""", (run_ref, MAX_CANDIDATES + 1)))
        bounded_size(len(sizes), MAX_CANDIDATES)
        for _, size, count in sizes:
            bounded_size(size, MAX_ARTIFACT_BYTES)
            bounded_size(count, MAX_TASKS)
        bounded_size(sum(row[1] for row in sizes), MAX_COLLECTION_BYTES)
        counts = {row[0]: row[1] for row in self.conn.execute("""SELECT t.candidate_ref,COUNT(*)
            FROM WorkbenchRunCandidates c JOIN WorkbenchRunCandidateTasks t ON t.candidate_ref=c.candidate_ref
            WHERE c.run_ref=? GROUP BY t.candidate_ref""", (run_ref,))}
        rows = []
        for row in self.conn.execute("""SELECT candidate_ref,run_ref,status,task_count,sequence,artifact_json
            FROM WorkbenchRunCandidates WHERE run_ref=? ORDER BY sequence""", (run_ref,)):
            if counts.get(row[0], 0) != row[3]:
                corrupt()
            rows.append({"candidate_ref": reference(row[0], stored=True), "run_ref": row[1], "status": row[2],
                         "task_count": row[3], "sequence": row[4], "artifact": stored_json(row[5])})
        return rows

    def candidate_run(self, candidate_ref):
        row = self.conn.execute("SELECT run_ref FROM WorkbenchRunCandidates WHERE candidate_ref=?", (candidate_ref,)).fetchone()
        if row is None:
            reject("entity_not_found", "未找到该永久候选，未改查最新结果。", 404)
        return reference(row[0], stored=True)

    def capture(self, run_ref):
        row = self.conn.execute("""SELECT normalized_input_json,execution_json,baseline_json,facts_json,facts_hash
            FROM WorkbenchRunJobs WHERE run_ref=?""", (run_ref,)).fetchone()
        return {"input": stored_json(row[0]), "execution": stored_json(row[1], list),
                "baseline": stored_json(row[2]), "facts_text": row[3], "facts_hash": row[4]}

    def tasks(self, candidate_ref):
        sizes = self.conn.execute("""SELECT COUNT(*),COALESCE(SUM(length(CAST(payload_json AS BLOB))),0),
            COALESCE(MAX(length(CAST(payload_json AS BLOB))),0)
            FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?""", (candidate_ref,)).fetchone()
        bounded_size(sizes[0], MAX_TASKS)
        bounded_size(sizes[1], MAX_COLLECTION_BYTES)
        bounded_size(sizes[2], MAX_ARTIFACT_BYTES)
        result = []
        for row in self.conn.execute("""SELECT row_ref,operation_ref,ordinal,payload_json
            FROM WorkbenchRunCandidateTasks WHERE candidate_ref=? ORDER BY ordinal""", (candidate_ref,)):
            if row[2] != len(result):
                corrupt()
            result.append({"row_ref": reference(row[0], stored=True), "operation_ref": reference(row[1], stored=True),
                           "payload": stored_json(row[3])})
        return result
