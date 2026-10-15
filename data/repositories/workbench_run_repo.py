"""Connection-bound run journal. No implicit transaction, commit, schema repair or ruling."""

from core.infrastructure.workbench_run_schema import workbench_run_contract_issues
from core.models.workbench_command import canonical_json
from core.models.workbench_run_job import TERMINAL_STATES, new_run_ref

_HEAD_COLUMNS = ("run_ref,request_key,input_ref,accepted_at,state,stage,executor_ref,"
                 "started_at,finished_at,error_json")
_DECISION_COLUMNS = frozenset(("header", "context", "memberships", "calendar", "official", "process"))
_CANDIDATE_COLUMNS = frozenset(("summary", "preparation", "completion", "delivery", "delivery_detail", "arrangements"))
_RUN_MODEL_FIELDS = ("header", "context", "memberships", "calendar", "official", "process")
_CANDIDATE_MODEL_FIELDS = ("summary", "preparation", "completion", "delivery", "delivery_detail", "arrangements")


def encode_result(result):
    """Encode the receipt body and its separately stored small state fields."""
    return {"state": result["state"], "result_json": canonical_json(result),
            "error_json": canonical_json(result.get("error"))}


def encode_decision_read_models(read_models):
    """Convert the fixed physical columns once; the storage packet holds strings."""
    model = read_models["run_model"]
    run = {key: model[key] for key in ("run_ref", "projection_version") if key in model}
    run.update({name + "_json": None if name == "process" and model.get(name) is None else canonical_json(model[name])
                for name in _RUN_MODEL_FIELDS})
    candidates = []
    for model in read_models["candidate_models"]:
        row = {key: model[key] for key in ("candidate_ref", "run_ref", "projection_version") if key in model}
        row.update({name + "_json": canonical_json(model[name]) for name in _CANDIDATE_MODEL_FIELDS})
        candidates.append(row)
    return {"run_model": run, "candidate_models": candidates}


class WorkbenchRunRepository:
    def __init__(self, conn):
        self.conn = conn

    def schema_issues(self):
        """Run contract issues as reported by the schema probe; [] when the schema is complete."""
        return workbench_run_contract_issues(self.conn)

    def get(self, run_ref):
        row = self.conn.execute("SELECT * FROM WorkbenchRunJobs WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None

    def head(self, run_ref):
        row = self.conn.execute("SELECT " + _HEAD_COLUMNS + " FROM WorkbenchRunJobs WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None

    def status(self, run_ref):
        columns = ",".join("j." + column for column in _HEAD_COLUMNS.split(","))
        row = self.conn.execute("SELECT " + columns + ",a.projection_version AS scope_version,a.scope_json,"
            "d.projection_version AS header_version,d.header_json,r.receipt_ref FROM WorkbenchRunJobs j "
            "LEFT JOIN WorkbenchRunAdmissionReadModels a ON a.run_ref=j.run_ref "
            "LEFT JOIN WorkbenchRunDecisionReadModels d ON d.run_ref=j.run_ref "
            "LEFT JOIN WorkbenchRunReceipts r ON r.run_ref=j.run_ref WHERE j.run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None

    def by_request_head(self, request_key):
        row = self.conn.execute("SELECT " + _HEAD_COLUMNS + " FROM WorkbenchRunJobs WHERE request_key=?", (request_key,)).fetchone()
        return dict(row) if row else None

    def claim_head(self, run_ref):
        row = self.conn.execute("SELECT run_ref,state,stage,executor_ref FROM WorkbenchRunJobs WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None

    def input_admitted(self, input_ref):
        return self.conn.execute("SELECT 1 FROM WorkbenchRunJobs WHERE input_ref=? LIMIT 1", (input_ref,)).fetchone() is not None

    def admission_read_model(self, run_ref, fields=("scope",)):
        columns = self._read_columns(fields, frozenset(("scope", "decision")))
        row = self.conn.execute("SELECT run_ref,projection_version," + columns + " FROM WorkbenchRunAdmissionReadModels WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None

    def decision_read_model(self, run_ref, fields=("header", "context", "memberships")):
        columns = self._read_columns(fields, _DECISION_COLUMNS)
        row = self.conn.execute("SELECT run_ref,projection_version," + columns +
                                " FROM WorkbenchRunDecisionReadModels WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None

    def candidate_read_models(self, run_ref, fields=("summary",)):
        columns = self._read_columns(fields, _CANDIDATE_COLUMNS, prefix="m.")
        return [dict(row) for row in self.conn.execute("SELECT m.candidate_ref,m.run_ref,m.projection_version," + columns +
            " FROM WorkbenchRunCandidateReadModels m JOIN WorkbenchRunCandidates c ON c.candidate_ref=m.candidate_ref "
            "WHERE m.run_ref=? ORDER BY c.sequence", (run_ref,))]

    def candidate_read_model(self, candidate_ref, fields):
        columns = self._read_columns(fields, _CANDIDATE_COLUMNS)
        row = self.conn.execute("SELECT candidate_ref,run_ref,projection_version," + columns +
                                " FROM WorkbenchRunCandidateReadModels WHERE candidate_ref=?", (candidate_ref,)).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _read_columns(fields, allowed, prefix=""):
        if not fields or len(set(fields)) != len(fields) or not set(fields) <= allowed:
            raise ValueError("Unknown decision read-model columns")
        return ",".join(prefix + field + "_json" for field in fields)

    def insert_admission_read_model(self, run_ref, scope, decision):
        self.conn.execute("INSERT INTO WorkbenchRunAdmissionReadModels(run_ref,projection_version,scope_json,decision_json) VALUES (?,?,?,?)",
                          (run_ref, "decision-read-v1", canonical_json(scope), canonical_json(decision)))

    def insert_decision_read_models(self, run_ref, run_read_model, candidate_read_models):
        prepared = encode_decision_read_models({"run_model": run_read_model, "candidate_models": candidate_read_models})
        self.insert_prepared_decision_read_models(run_ref, prepared["run_model"], prepared["candidate_models"])

    def insert_prepared_decision_read_models(self, run_ref, run_read_model, candidate_read_models):
        self.conn.execute("INSERT INTO WorkbenchRunDecisionReadModels"
            "(run_ref,projection_version,header_json,context_json,memberships_json,calendar_json,official_json,process_json) "
            "VALUES (?,?,?,?,?,?,?,?)", (run_ref, "decision-read-v1", *(run_read_model[name + "_json"] for name in _RUN_MODEL_FIELDS)))
        for candidate in candidate_read_models:
            self.conn.execute("INSERT INTO WorkbenchRunCandidateReadModels"
                "(candidate_ref,run_ref,projection_version,summary_json,preparation_json,completion_json,delivery_json,delivery_detail_json,arrangements_json) "
                "VALUES (?,?,?,?,?,?,?,?,?)", (candidate["candidate_ref"], run_ref, "decision-read-v1",
                    *(candidate[name + "_json"] for name in _CANDIDATE_MODEL_FIELDS)))

    def dependency_heads(self, candidate_refs, scenario_refs):
        candidates, scenarios = {}, {}
        if candidate_refs:
            marks = ",".join("?" for _ in candidate_refs)
            candidates = {row["candidate_ref"]: dict(row) for row in self.conn.execute(
                "SELECT c.candidate_ref,c.run_ref,c.status,c.task_count,j.state AS run_state,"
                "r.receipt_ref,r.state AS receipt_state FROM WorkbenchRunCandidates c "
                "LEFT JOIN WorkbenchRunJobs j ON j.run_ref=c.run_ref "
                "LEFT JOIN WorkbenchRunReceipts r ON r.run_ref=c.run_ref "
                "WHERE c.candidate_ref IN (" + marks + ")", tuple(candidate_refs))}
        if scenario_refs:
            marks = ",".join("?" for _ in scenario_refs)
            scenarios = {row["scenario_ref"]: dict(row) for row in self.conn.execute(
                "SELECT s.scenario_ref,s.draft_ref,s.revision,s.request_key,d.revision AS draft_revision,"
                "d.status AS draft_status,d.row_count AS draft_row_count,d.request_key AS draft_request_key,"
                "c.receipt_ref AS create_receipt_ref,r.receipt_ref AS save_receipt_ref "
                "FROM WorkbenchTrialScenarios s LEFT JOIN WorkbenchTrialDrafts d ON d.draft_ref=s.draft_ref "
                "LEFT JOIN WorkbenchCommandReceipts c ON c.request_key=d.request_key "
                "LEFT JOIN WorkbenchCommandReceipts r ON r.request_key=s.request_key "
                "WHERE s.scenario_ref IN (" + marks + ")", tuple(scenario_refs))}
        names = ("run_ref", "status", "task_count", "run_state", "receipt_ref", "receipt_state")
        candidate_rows = [candidates.get(ref, {"candidate_ref": ref, **dict.fromkeys(names)}) for ref in candidate_refs]
        names = ("draft_ref", "revision", "request_key", "draft_revision", "draft_status", "draft_row_count",
                 "draft_request_key", "create_receipt_ref", "save_receipt_ref")
        scenario_rows = [scenarios.get(ref, {"scenario_ref": ref, **dict.fromkeys(names)}) for ref in scenario_refs]
        return {"candidates": candidate_rows, "scenarios": scenario_rows}

    def dependencies_match(self, expected):
        return self.dependency_heads([row["candidate_ref"] for row in expected["candidates"]],
                                     [row["scenario_ref"] for row in expected["scenarios"]]) == expected

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

    def insert(self, *, request_key, input_ref, settings, facts_hash, facts_json, projections, baseline, now, run_ref=None):
        ref = run_ref if run_ref is not None else new_run_ref()
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
        prepared = encode_result(result)
        prepared["state"] = state
        self.finish_prepared(run_ref, prepared, now)

    def finish_prepared(self, run_ref, result, now):
        state = result["state"]
        if state not in TERMINAL_STATES:
            raise ValueError("Invalid terminal run state")
        receipt_ref = new_run_ref()
        self.conn.execute("INSERT INTO WorkbenchRunReceipts VALUES (?,?,?,?,?)",
                          (receipt_ref, run_ref, state, result["result_json"], now))
        cursor = self.conn.execute("""UPDATE WorkbenchRunJobs SET state=?,stage='finished',finished_at=?,error_json=?
            WHERE run_ref=? AND state IN ('running','queued')""",
            (state, now, result["error_json"], run_ref))
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
