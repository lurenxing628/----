"""Connection-bound run journal. No implicit transaction, commit, schema repair or ruling."""

from core.infrastructure.workbench_run_schema import workbench_run_contract_issues
from core.models.workbench_command import canonical_json
from core.models.workbench_run_job import TERMINAL_STATES, new_run_ref


class WorkbenchRunRepository:
    def __init__(self, conn):
        self.conn = conn

    def schema_issues(self):
        """Run contract issues as reported by the schema probe; [] when the schema is complete."""
        return workbench_run_contract_issues(self.conn)

    def get(self, run_ref):
        row = self.conn.execute("SELECT * FROM WorkbenchRunJobs WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None

    def by_request(self, request_key):
        row = self.conn.execute("SELECT run_ref FROM WorkbenchRunJobs WHERE request_key=?", (request_key,)).fetchone()
        return self.get(row[0]) if row else None

    def receipt(self, run_ref):
        row = self.conn.execute("SELECT * FROM WorkbenchRunReceipts WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None

    def admission_receipt(self, request_key):
        """(action, context_ref, outcome_json) of the command receipt that admitted a run, or None."""
        row = self.conn.execute("""SELECT action,context_ref,outcome_json FROM WorkbenchCommandReceipts
            WHERE request_key=?""", (request_key,)).fetchone()
        return None if row is None else tuple(row)

    def insert(self, *, request_key, input_ref, settings, facts_hash, facts_json, projections, baseline, now):
        ref = new_run_ref()
        self.conn.execute("""INSERT INTO WorkbenchRunJobs
            (run_ref,request_key,input_ref,normalized_input_json,facts_hash,facts_json,execution_json,baseline_json,accepted_at,state,stage)
            VALUES (?,?,?,?,?,?,?,?,?,'queued','queued')""", (ref, request_key, input_ref, canonical_json(settings), facts_hash,
                           facts_json, canonical_json([item.to_dict() for item in projections]), canonical_json(baseline), now))
        return ref

    def claim(self, run_ref, executor_ref, now):
        cursor = self.conn.execute("""UPDATE WorkbenchRunJobs SET state='running',stage='computing',executor_ref=?,started_at=?
            WHERE run_ref=? AND state='queued' AND stage='queued'""", (executor_ref, now, run_ref))
        return cursor.rowcount == 1

    def finish(self, run_ref, state, result, now):
        if state not in TERMINAL_STATES:
            raise ValueError("Invalid terminal run state")
        receipt_ref = new_run_ref()
        self.conn.execute("INSERT INTO WorkbenchRunReceipts VALUES (?,?,?,?,?)",
                          (receipt_ref, run_ref, state, canonical_json(result), now))
        cursor = self.conn.execute("""UPDATE WorkbenchRunJobs SET state=?,stage='finished',finished_at=?,error_json=?
            WHERE run_ref=? AND state IN ('running','queued')""",
            (state, now, canonical_json(result.get("error")), run_ref))
        if cursor.rowcount != 1:
            raise ValueError("Run terminal update did not affect exactly one admission")

    def record_reconciled_finish(self, run_ref, state, finished_at, error_json):
        """按已存在的回执把作业行补写成 finished；对账场景不再校验 running/queued 前态。"""
        self.conn.execute("UPDATE WorkbenchRunJobs SET state=?,stage='finished',finished_at=?,error_json=? WHERE run_ref=?",
                          (state, finished_at, error_json, run_ref))

    def scheduling_run_admitted(self, request_key):
        """该 request_key 是否有 scheduling.run 回执且对应作业行存在（只读证据核对）。"""
        return self.conn.execute("""SELECT 1 FROM WorkbenchRunJobs j
            JOIN WorkbenchCommandReceipts r ON r.request_key=j.request_key
            WHERE j.request_key=? AND r.action='scheduling.run' LIMIT 1""", (request_key,)).fetchone() is not None

    def command_receipt_action(self, request_key):
        """该 request_key 的命令回执 action；没有回执返回 None。"""
        row = self.conn.execute("SELECT action FROM WorkbenchCommandReceipts WHERE request_key=?", (request_key,)).fetchone()
        return row[0] if row else None

    def has_candidates(self, run_ref):
        return self.conn.execute("SELECT 1 FROM WorkbenchRunCandidates WHERE run_ref=? LIMIT 1", (run_ref,)).fetchone() is not None

    def unfinished(self):
        return [dict(row) for row in self.conn.execute("SELECT * FROM WorkbenchRunJobs WHERE state IN ('queued','running') ORDER BY accepted_at,run_ref")]

    def awaiting_reconciliation(self, run_ref):
        self.conn.execute("UPDATE WorkbenchRunJobs SET stage='awaiting_reconciliation' WHERE run_ref=? AND state IN ('queued','running')", (run_ref,))
