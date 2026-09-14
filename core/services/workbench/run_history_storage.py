"""One bounded directory read; task payloads and current resource tables stay unread."""

from core.infrastructure.workbench_run_schema import workbench_run_contract_issues
from core.models.workbench_run_history import (
    MAX_DIRECTORY_BYTES,
    MAX_DIRECTORY_ROWS,
    MAX_DOCUMENT_BYTES,
    inconsistent,
    reject,
)


def _bounded(value, limit):
    if type(value) is not int or value < 0:
        inconsistent()
    if value > limit:
        reject("run_history_capacity_exceeded", "排产记录条数超出一次能读的上限，列表没有显示，也没有只给你看最新的几条。请缩小查询范围后重试。", 413)


class RunHistoryStore:
    def __init__(self, conn):
        self.conn = conn

    def require_schema(self):
        if workbench_run_contract_issues(self.conn):
            reject("run_schema_unavailable", "排产记录用的结构还没装好，读不出来，系统也不会自动补。请联系维护人员。", 503)

    def _capacity(self):
        total = 0
        for table, fields in (
            ("WorkbenchRunJobs", ("normalized_input_json",)),
            ("WorkbenchRunReceipts", ("result_json",)),
            ("WorkbenchCommandReceipts", ("outcome_json",)),
        ):
            size = "+".join("length(CAST(" + field + " AS BLOB))" for field in fields)
            where = " WHERE action='scheduling.run'" if table == "WorkbenchCommandReceipts" else ""
            row = self.conn.execute("SELECT COUNT(*),COALESCE(SUM(" + size + "),0),COALESCE(MAX(" + size + "),0) FROM " + table + where).fetchone()
            _bounded(row[0], MAX_DIRECTORY_ROWS)
            _bounded(row[2], MAX_DOCUMENT_BYTES)
            total += row[1]
        _bounded(total, MAX_DIRECTORY_BYTES)
        _bounded(self.conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidates").fetchone()[0], MAX_DIRECTORY_ROWS)

    def _require_parents(self):
        # These anti-joins also catch unfiltered/off-page orphans with foreign_keys disabled by an older writer.
        for sql in (
            "SELECT 1 FROM WorkbenchRunReceipts r LEFT JOIN WorkbenchRunJobs j ON j.run_ref=r.run_ref WHERE j.run_ref IS NULL LIMIT 1",
            "SELECT 1 FROM WorkbenchRunCandidates c LEFT JOIN WorkbenchRunJobs j ON j.run_ref=c.run_ref WHERE j.run_ref IS NULL LIMIT 1",
            "SELECT 1 FROM WorkbenchRunCandidateTasks t LEFT JOIN WorkbenchRunCandidates c ON c.candidate_ref=t.candidate_ref WHERE c.candidate_ref IS NULL LIMIT 1",
            "SELECT 1 FROM WorkbenchCommandReceipts a LEFT JOIN WorkbenchRunJobs j ON j.request_key=a.request_key WHERE a.action='scheduling.run' AND j.run_ref IS NULL LIMIT 1",
        ):
            if self.conn.execute(sql).fetchone():
                inconsistent()

    def read(self):
        self.require_schema()
        self._capacity()
        self._require_parents()
        jobs = [dict(row) for row in self.conn.execute("""SELECT j.run_ref,j.state,j.stage,j.accepted_at,
            j.started_at,j.finished_at,j.normalized_input_json,j.input_ref,j.executor_ref,
            a.action AS admission_action,a.context_ref AS admission_context,a.outcome_json AS admission_json,
            r.state AS receipt_state,r.result_json,r.recorded_at
            FROM WorkbenchRunJobs j LEFT JOIN WorkbenchCommandReceipts a ON a.request_key=j.request_key
            LEFT JOIN WorkbenchRunReceipts r ON r.run_ref=j.run_ref ORDER BY j.run_ref""")]
        candidates = [dict(row) for row in self.conn.execute("""SELECT c.run_ref,c.candidate_ref,c.status,c.sequence,
            c.task_count,COUNT(t.row_ref) AS actual_count,MIN(t.ordinal) AS first_ordinal,MAX(t.ordinal) AS last_ordinal
            FROM WorkbenchRunCandidates c LEFT JOIN WorkbenchRunCandidateTasks t ON t.candidate_ref=c.candidate_ref
            GROUP BY c.candidate_ref ORDER BY c.run_ref,c.sequence,c.candidate_ref""")]
        return jobs, candidates
