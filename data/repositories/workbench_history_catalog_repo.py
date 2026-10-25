"""SELECT-only directory facts for the two history timelines."""

from .base_repo import BaseRepository

ADOPTION_ACTIONS = ("scheduling.candidate.adopt", "trial.scenario.adopt")


class WorkbenchHistoryCatalogRepository(BaseRepository):
    def runs(self):
        return self.iter_rows("""SELECT j.run_ref,j.request_key,j.input_ref,j.executor_ref,
            j.state,j.stage,j.accepted_at,j.started_at,j.finished_at,
            a.projection_version AS scope_version,a.scope_json,
            d.projection_version AS header_version,d.header_json,
            r.receipt_ref,r.state AS receipt_state,r.recorded_at
            FROM WorkbenchRunJobs j
            LEFT JOIN WorkbenchRunAdmissionReadModels a ON a.run_ref=j.run_ref
            LEFT JOIN WorkbenchRunDecisionReadModels d ON d.run_ref=j.run_ref
            LEFT JOIN WorkbenchRunReceipts r ON r.run_ref=j.run_ref ORDER BY j.run_ref""")

    def adoption_receipts(self):
        return self.iter_rows("SELECT * FROM WorkbenchCommandReceipts WHERE action IN (?,?)", ADOPTION_ACTIONS)

    def histories(self):
        return self.iter_rows("SELECT id,schedule_time,version,strategy,batch_count,op_count,result_status,result_summary,created_by "
                              "FROM ScheduleHistory ORDER BY id")

    def official_bindings(self):
        return self.iter_rows("SELECT ref,source_key,version,plan_role,source_table,active FROM WorkbenchPlanSourceRefs "
                              "WHERE kind='official' ORDER BY ref")

    def identity_clock(self):
        return self.fetchone("SELECT singleton,revision FROM WorkbenchPlanIdentityClock WHERE singleton=1")
