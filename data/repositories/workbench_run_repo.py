"""Connection-bound run journal. No implicit transaction, commit or schema repair."""

import json

from core.infrastructure.workbench_run_schema import workbench_run_contract_issues
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_run_job import TERMINAL_STATES, new_run_ref


class WorkbenchRunRepository:
    def __init__(self, conn):
        self.conn = conn

    def require_schema(self):
        issues = workbench_run_contract_issues(self.conn)
        if issues:
            raise WorkbenchCommandRejected("run_schema_unavailable", "运行台账尚未完整安装，未补建或修复。", 503)

    def get(self, run_ref):
        row = self.conn.execute("SELECT * FROM WorkbenchRunJobs WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None

    def by_request(self, request_key):
        row = self.conn.execute("SELECT run_ref FROM WorkbenchRunJobs WHERE request_key=?", (request_key,)).fetchone()
        return self.get(row[0]) if row else None

    def receipt(self, run_ref):
        row = self.conn.execute("SELECT * FROM WorkbenchRunReceipts WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None

    def require_admission(self, row):
        receipt = self.conn.execute("""SELECT action,context_ref,outcome_json FROM WorkbenchCommandReceipts
            WHERE request_key=?""", (row["request_key"],)).fetchone()
        if (receipt is None or receipt[0] != "scheduling.run" or receipt[1] != row["input_ref"]
                or json.loads(receipt[2])["data"] != {"run_ref": row["run_ref"]}):
            raise WorkbenchCommandRejected("run_result_inconsistent", "排产运行缺少一致的受理回执，必须核对台账。", 500)

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

    def unfinished(self):
        return [dict(row) for row in self.conn.execute("SELECT * FROM WorkbenchRunJobs WHERE state IN ('queued','running') ORDER BY accepted_at,run_ref")]

    def awaiting_reconciliation(self, run_ref):
        self.conn.execute("UPDATE WorkbenchRunJobs SET stage='awaiting_reconciliation' WHERE run_ref=? AND state IN ('queued','running')", (run_ref,))

    def public(self, row):
        self.require_admission(row)
        receipt = self.receipt(row["run_ref"])
        result = json.loads(receipt["result_json"]) if receipt else None
        if ((row["state"] in TERMINAL_STATES) != bool(receipt)
                or (receipt and (not isinstance(result, dict) or receipt["state"] != row["state"]
                                 or result["state"] != receipt["state"]))):
            raise WorkbenchCommandRejected("run_result_inconsistent", "运行终态与结果回执不一致，必须核对台账。", 500)
        if receipt:
            from .workbench_run_result_repo import WorkbenchRunResultRepository
            if not WorkbenchRunResultRepository(self.conn).consistent(row["run_ref"], result):
                raise WorkbenchCommandRejected("run_result_inconsistent", "候选明细与结果回执不一致，必须核对台账。", 500)
        return {"run_ref": row["run_ref"], "job_ref": row["run_ref"], "state": row["state"], "stage": row["stage"],
                "progress": None, "plans": [], "plan_catalog_connected": False,
                "candidates": result["candidates"] if result else [], "result_persisted": bool(result and result["result_persisted"]),
                "accepted_at": row["accepted_at"], "started_at": row["started_at"], "finished_at": row["finished_at"],
                "receipt_ref": receipt["receipt_ref"] if receipt else None, "error": result.get("error") if result else None,
                "recovery_required": row["stage"] == "awaiting_reconciliation"}
