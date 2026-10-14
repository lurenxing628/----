"""SELECT-only directory facts for the two history timelines."""

from typing import Dict

from .base_repo import BaseRepository

ADOPTION_ACTIONS = ("scheduling.candidate.adopt", "trial.scenario.adopt")


class WorkbenchHistoryCatalogRepository(BaseRepository):
    def capacity(self) -> Dict[str, Dict[str, int]]:
        documents = (
            ("runs", "WorkbenchRunJobs", "normalized_input_json", ""),
            ("run_receipts", "WorkbenchRunReceipts", "result_json", ""),
            ("run_admissions", "WorkbenchCommandReceipts", "outcome_json", " WHERE action='scheduling.run'"),
            ("adoptions", "WorkbenchCommandReceipts", "outcome_json",
             " WHERE action IN ('scheduling.candidate.adopt','trial.scenario.adopt')"),
            ("histories", "ScheduleHistory", "result_summary", ""),
            ("candidate_keys", "WorkbenchRunCandidates", "candidate_key", ""),
            ("official_bindings", "WorkbenchPlanSourceRefs", "ref", " WHERE kind='official'"),
        )
        return {kind: self.fetchall("SELECT COUNT(*) AS rows,COALESCE(SUM(length(CAST(" + field +
            " AS BLOB))),0) AS bytes,COALESCE(MAX(length(CAST(" + field +
            " AS BLOB))),0) AS max_document_bytes FROM " + table + where)[0]
            for kind, table, field, where in documents}

    def runs(self):
        return self.fetchall("""SELECT j.run_ref,j.request_key,j.input_ref,j.normalized_input_json,
            j.state,j.stage,j.accepted_at,j.started_at,j.finished_at,j.error_json,
            a.action AS admission_action,a.context_ref AS admission_context,a.outcome_json AS admission_json,
            r.receipt_ref,r.state AS receipt_state,r.result_json,r.recorded_at
            FROM WorkbenchRunJobs j
            LEFT JOIN WorkbenchCommandReceipts a ON a.request_key=j.request_key
            LEFT JOIN WorkbenchRunReceipts r ON r.run_ref=j.run_ref ORDER BY j.run_ref""")

    def candidate_keys(self):
        return self.fetchall("SELECT run_ref,candidate_ref,candidate_key FROM WorkbenchRunCandidates ORDER BY run_ref,sequence")

    def adoption_receipts(self):
        return self.fetchall("SELECT * FROM WorkbenchCommandReceipts WHERE action IN (?,?) ORDER BY committed_at_utc,request_key",
                             ADOPTION_ACTIONS)

    def histories(self):
        return self.fetchall("SELECT id,schedule_time,version,strategy,batch_count,op_count,result_status,result_summary,created_by "
                             "FROM ScheduleHistory ORDER BY id")

    def official_bindings(self):
        return self.fetchall("SELECT ref,source_key,version,plan_role,source_table,active FROM WorkbenchPlanSourceRefs "
                             "WHERE kind='official' ORDER BY ref")

    def identity_clock(self):
        return self.fetchone("SELECT singleton,revision FROM WorkbenchPlanIdentityClock WHERE singleton=1")
