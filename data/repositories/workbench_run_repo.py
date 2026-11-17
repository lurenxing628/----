"""Connection-bound run journal. No implicit transaction, commit, schema repair or ruling."""

import json
from typing import Any, Dict, List, Optional, Sequence

from core.models.content import read_stored_json
from core.models.enums import RUN_UNFINISHED_STATE_VALUES, RunStage, RunState, enum_predicate
from core.shared.refs import new_ref
from core.shared.strict_json import canonical_json

_HEAD_COLUMNS = "run_ref,request_key,input_ref,accepted_at,state,stage,executor_ref,started_at,finished_at,error_json"
_RUN_MODEL_FIELDS = ("header", "context", "memberships", "calendar", "official", "process")
_CANDIDATE_MODEL_FIELDS = ("summary", "preparation", "completion", "delivery", "delivery_detail", "arrangements")
_BATCH_INSERT_SQL = ("INSERT INTO WorkbenchRunBatches(run_ref,batch_ref,batch_id,part_no,part_ref,part_name,"
    "quantity,due_date,priority,ready_status,ready_date,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)")
_OP_INSERT_SQL = ("INSERT INTO WorkbenchRunOperations(run_ref,operation_ref,op_id,op_code,batch_id,batch_ref,piece_id,seq,"
    "op_type_id,op_type_name,op_type_ref,op_type_label,source,setup_hours,unit_hours,ext_days,machine_id,machine_ref,machine_label,"
    "operator_id,operator_ref,operator_label,supplier_id,supplier_ref,supplier_label,status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
_SIDE_BATCH_INSERT_SQL = ("INSERT INTO WorkbenchRunSideBatches(run_ref,side_key,batch_ref,batch_label,due_date,is_overdue,delay_hours,"
    "finish_time,finish_us,status,scheduled_count,total_count,deferred_count,unplanned_count,detail_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
_OP_CATALOG_INSERT_SQL = ("INSERT INTO WorkbenchRunOperationCatalog(run_ref,operation_ref,batch_ref,batch_label,sequence,"
    "sequence_unknown,op_id,saved_machine_ref,label_json) VALUES (?,?,?,?,?,?,?,?,?)")
_SIDE_OP_INSERT_SQL = ("INSERT INTO WorkbenchRunSideOperations(run_ref,side_key,operation_ref,arranged,deferred,allocation_state,"
    "is_remaining,start_us,end_us,machine_ref,operator_ref,resource_refs_json,setup_hours,required_hours,"
    "arrangement_json,preparation_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
_SIDE_RESOURCE_INSERT_SQL = "INSERT INTO WorkbenchRunSideResources(run_ref,side_key,resource_view,payload_json) VALUES (?,?,?,?)"


def _json_diff_sql(field: str) -> str:
    left, right = f"json_extract(b.arrangement_json,'$.{field}')", f"json_extract(a.arrangement_json,'$.{field}')"
    return f"CASE WHEN b.arranged=1 AND a.arranged=1 THEN CASE WHEN {left} IS NULL OR {right} IS NULL THEN NULL WHEN {left}!={right} THEN 1 ELSE 0 END END"


_OP_CMP_CTE = f"""WITH op_raw AS (
    SELECT cat.operation_ref, cat.batch_ref, cat.batch_label, cat.sequence, cat.sequence_unknown,
        cat.saved_machine_ref, cat.label_json,
        b.arranged AS b_arr, b.deferred AS b_def, b.start_us AS b_start, b.end_us AS b_end,
        b.resource_refs_json AS b_res_json, b.arrangement_json AS b_arr_json, b.preparation_json AS b_prep_json,
        a.arranged AS a_arr, a.deferred AS a_def, a.start_us AS a_start, a.end_us AS a_end,
        a.resource_refs_json AS a_res_json, a.arrangement_json AS a_arr_json, a.preparation_json AS a_prep_json,
        CASE WHEN b.arranged=1 AND a.arranged=1 THEN (a.start_us - b.start_us) / 3600000000.0 END AS start_delta_hours,
        CASE WHEN b.arranged=1 AND a.arranged=1 THEN (a.end_us - b.end_us) / 3600000000.0 END AS end_delta_hours,
        {_json_diff_sql("m_tok")} AS m_chg, {_json_diff_sql("o_tok")} AS o_chg,
        {_json_diff_sql("s_tok")} AS s_chg, {_json_diff_sql("src")} AS src_chg
    FROM WorkbenchRunOperationCatalog cat
    JOIN WorkbenchRunSideOperations b ON b.run_ref=cat.run_ref AND b.side_key=:ref_side AND b.operation_ref=cat.operation_ref
    JOIN WorkbenchRunSideOperations a ON a.run_ref=cat.run_ref AND a.side_key=:sel_side AND a.operation_ref=cat.operation_ref
    WHERE cat.run_ref=:run_ref
), op_cmp AS (
    SELECT *,
        CASE WHEN :ref_avail=0 THEN NULL ELSE start_delta_hours END AS eff_start_delta,
        CASE WHEN :ref_avail=0 THEN NULL ELSE end_delta_hours END AS eff_end_delta,
        CASE WHEN :ref_avail=0 THEN 0
             WHEN b_arr=0 AND a_arr=1 THEN 1 WHEN b_arr=1 AND a_arr=0 THEN 1
             WHEN b_arr=0 AND a_arr=0 THEN CASE WHEN b_def!=a_def THEN 1 ELSE 0 END
             WHEN start_delta_hours!=0 OR end_delta_hours!=0 OR m_chg=1 OR o_chg=1 OR s_chg=1 OR src_chg=1 THEN 1 ELSE 0 END AS has_changed_fields,
        CASE WHEN :ref_avail=0 THEN 'unknown'
             WHEN b_arr=0 AND a_arr=1 THEN 'added,status_changed'
             WHEN b_arr=1 AND a_arr=0 THEN 'removed,status_changed'
             WHEN b_arr=0 AND a_arr=0 THEN CASE WHEN b_def!=a_def THEN 'unknown,status_changed' ELSE 'unknown' END
             ELSE CASE
                 WHEN start_delta_hours=0 AND end_delta_hours=0 AND src_chg=0 AND m_chg=0 AND o_chg=0 AND s_chg=0 THEN 'unchanged'
                 ELSE substr(
                     (CASE WHEN start_delta_hours!=0 OR end_delta_hours!=0 THEN ',moved' ELSE '' END)
                     || (CASE WHEN m_chg=1 THEN ',machine_changed' ELSE '' END)
                     || (CASE WHEN o_chg=1 THEN ',operator_changed' ELSE '' END)
                     || (CASE WHEN s_chg=1 THEN ',supplier_changed' ELSE '' END)
                     || (CASE WHEN src_chg=1 THEN ',source_changed' ELSE '' END)
                     || (CASE WHEN m_chg IS NULL OR o_chg IS NULL OR s_chg IS NULL THEN ',unknown' ELSE '' END), 2) END END AS change_kinds_csv
    FROM op_raw
)"""

_BATCH_CMP_TAIL = """, op_by_batch AS (
    SELECT batch_ref, COUNT(*) AS op_total, SUM(has_changed_fields) AS op_changed,
           SUM(CASE WHEN has_changed_fields=0 AND INSTR(','||change_kinds_csv||',', ',unknown,')>0 THEN 1 ELSE 0 END) AS op_unknown
    FROM op_cmp GROUP BY batch_ref
), batch_raw AS (
    SELECT a.batch_ref, a.batch_label, a.is_overdue AS a_overdue, a.delay_hours AS a_delay,
        a.status AS a_status, a.deferred_count AS a_def_cnt, a.unplanned_count AS a_unp_cnt,
        a.detail_json AS a_detail_json, b.detail_json AS b_detail_json,
        COALESCE(ob.op_total,0) AS op_total, COALESCE(ob.op_changed,0) AS op_changed, COALESCE(ob.op_unknown,0) AS op_unknown,
        CASE WHEN :ref_avail=1 AND b.delay_hours IS NOT NULL AND a.delay_hours IS NOT NULL
             THEN a.delay_hours - b.delay_hours END AS delay_delta_hours,
        CASE WHEN :ref_avail=1 AND b.finish_us IS NOT NULL AND a.finish_us IS NOT NULL
             THEN (a.finish_us - b.finish_us) / 3600000000.0 END AS finish_delta_hours,
        CASE WHEN :ref_avail=1 THEN
             (CASE WHEN b.finish_us IS NOT NULL AND a.finish_us IS NOT NULL AND a.finish_us < b.finish_us THEN ',earlier'
                   WHEN b.finish_us IS NOT NULL AND a.finish_us IS NOT NULL AND a.finish_us > b.finish_us THEN ',later' ELSE '' END)
             || (CASE WHEN b.is_overdue=0 AND a.is_overdue=1 THEN ',new_overdue'
                      WHEN b.is_overdue=1 AND a.is_overdue=0 THEN ',relieved_overdue' ELSE '' END)
             || (CASE WHEN b.status!='unknown' AND a.status!='unknown' AND b.status!='complete' AND a.status='complete' THEN ',completion_improved'
                      WHEN b.status!='unknown' AND a.status!='unknown' AND b.status='complete' AND a.status!='complete' THEN ',completion_worsened' ELSE '' END)
        ELSE '' END AS base_changes_raw,
        CASE WHEN json_extract(b.detail_json,'$.delivery.due_state')='invalid'
               OR json_extract(a.detail_json,'$.delivery.due_state')='invalid' THEN 1 ELSE 0 END AS due_invalid
    FROM WorkbenchRunSideBatches a
    JOIN WorkbenchRunSideBatches b ON b.run_ref=a.run_ref AND b.side_key=:ref_side AND b.batch_ref=a.batch_ref
    LEFT JOIN op_by_batch ob ON ob.batch_ref=a.batch_ref
    WHERE a.run_ref=:run_ref AND a.side_key=:sel_side
), batch_cmp AS (
    SELECT *,
        CASE WHEN :ref_avail=0 THEN CASE WHEN op_changed>0 THEN 'unknown,operation_changed' ELSE 'unknown' END
             WHEN base_changes_raw!='' THEN substr(base_changes_raw || (CASE WHEN op_changed>0 THEN ',operation_changed' ELSE '' END), 2)
             WHEN finish_delta_hours IS NULL OR due_invalid=1 THEN CASE WHEN op_changed>0 THEN 'unknown,operation_changed' ELSE 'unknown' END
             ELSE CASE WHEN op_changed>0 THEN 'operation_changed' ELSE 'unchanged' END END AS change_kinds_csv,
        CASE WHEN a_overdue=1 THEN 0 WHEN a_def_cnt>0 THEN 1 WHEN a_unp_cnt>0 THEN 2 ELSE 3 END AS prio_rank,
        -COALESCE(a_delay, 0.0) AS neg_after_delay
    FROM batch_raw
)"""


def encode_result(result):
    """Encode the receipt body and its separately stored small state fields."""
    return {"state": result["state"], "result_json": canonical_json(result), "error_json": canonical_json(result["error"])}


def encode_decision_read_models(read_models):
    """Convert the fixed physical columns and pagination rows once; the storage packet holds strings."""
    model = read_models["run_model"]
    run = {name + "_json": None if name == "process" and model[name] is None else canonical_json(model[name]) for name in _RUN_MODEL_FIELDS}
    candidates = [{"candidate_ref": cand["candidate_ref"], **{name + "_json": canonical_json(cand[name]) for name in _CANDIDATE_MODEL_FIELDS}}
                  for cand in read_models["candidate_models"]]
    side_batches = [{**{k: v for k, v in row.items() if k != "detail"}, "detail_json": canonical_json(row["detail"])}
                    for row in read_models["side_batches"]]
    operation_catalog = [{**{k: v for k, v in row.items() if k != "label"}, "label_json": canonical_json(row["label"])}
                         for row in read_models["operation_catalog"]]
    side_operations = [{**{k: v for k, v in row.items() if k not in ("resource_refs", "arrangement", "preparation")},
         "resource_refs_json": canonical_json(row["resource_refs"]),
         "arrangement_json": None if row["arrangement"] is None else canonical_json(row["arrangement"]),
         "preparation_json": canonical_json(row["preparation"])} for row in read_models["side_operations"]]
    side_resources = [{"side_key": row["side_key"], "resource_view": row["resource_view"], "payload_json": canonical_json(row["payload"])}
                      for row in read_models["side_resources"]]
    return {"run_model": run, "candidate_models": candidates, "side_batches": side_batches,
            "operation_catalog": operation_catalog, "side_operations": side_operations, "side_resources": side_resources}


def _batch_where_sql(filters, params) -> str:
    clauses = ["1=1"]
    if filters["batch_ref"] is not None:
        clauses.append("batch_ref = :batch_ref")
        params["batch_ref"] = filters["batch_ref"]
    change = filters["change_kind"]
    if change == "changed":
        clauses.append("(INSTR(change_kinds_csv, ',') > 0 OR change_kinds_csv NOT IN ('unchanged', 'unknown'))")
    elif change != "all":
        clauses.append("INSTR(','||change_kinds_csv||',', ','||:change_kind||',') > 0")
        params["change_kind"] = change
    delivery_clauses = {"attention": "(a_overdue=1 OR a_def_cnt>0 OR a_unp_cnt>0)", "on_time": "a_overdue=0",
                        "overdue": "a_overdue=1", "deferred": "a_def_cnt>0", "unplanned": "a_unp_cnt>0"}
    delivery = filters["delivery_filter"]
    if delivery in delivery_clauses:
        clauses.append(delivery_clauses[delivery])
    return " WHERE " + " AND ".join(clauses)


def _batch_order_sql(sort: str, direction: str) -> str:
    if sort == "current_priority":
        return f"prio_rank {direction}, neg_after_delay {direction}, batch_ref ASC"
    if sort in ("worsened", "improved"):
        ranks = ("',completion_worsened,'", "',new_overdue,'", "',later,'") if sort == "worsened" else (
            "',completion_improved,'", "',relieved_overdue,'", "',earlier,'")
        sign = "" if sort == "worsened" else "-"
        rank_expr = (f"(CASE WHEN INSTR(','||change_kinds_csv||',', {ranks[0]})>0 THEN 3 "
                     f"WHEN INSTR(','||change_kinds_csv||',', {ranks[1]})>0 THEN 2 "
                     f"WHEN INSTR(','||change_kinds_csv||',', {ranks[2]})>0 THEN 1 ELSE 0 END)")
        return (f"(change_kinds_csv='unknown') ASC, {rank_expr} {direction}, "
                f"({sign}COALESCE(delay_delta_hours, 0.0)) {direction}, "
                f"({sign}COALESCE(finish_delta_hours, 0.0)) {direction}, batch_ref ASC")
    col = {"after_delay_hours": "a_delay", "delay_delta_hours": "delay_delta_hours",
           "finish_delta_hours": "finish_delta_hours", "batch_id": "batch_label"}[sort]
    return f"({col} IS NULL) ASC, {col} {direction}, batch_ref ASC"


def _op_order_sql(sort: str, direction: str) -> str:
    if sort == "sequence":
        return f"sequence_unknown ASC, sequence {direction}, operation_ref ASC"
    col = {"start_delta_hours": "eff_start_delta", "end_delta_hours": "eff_end_delta",
           "batch_id": "batch_label", "change_kind": "change_kinds_csv"}[sort]
    return f"({col} IS NULL) ASC, {col} {direction}, operation_ref ASC"


def _prep_order_sql(sort: str, direction: str) -> str:
    if sort == "sequence":
        return f"cat.sequence_unknown ASC, cat.sequence {direction}, cat.operation_ref ASC"
    if sort == "setup_delta_hours":
        return f"((a.setup_hours - b.setup_hours) IS NULL) ASC, (a.setup_hours - b.setup_hours) {direction}, cat.operation_ref ASC"
    col = {"batch_id": "cat.batch_label", "after_setup_hours": "a.setup_hours", "after_required_hours": "a.required_hours"}[sort]
    return f"({col} IS NULL) ASC, {col} {direction}, cat.operation_ref ASC"


class WorkbenchRunRepository:
    def __init__(self, conn): self.conn = conn

    def get(self, run_ref):
        row = self.conn.execute("SELECT * FROM WorkbenchRunJobs WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None
    def head(self, run_ref):
        row = self.conn.execute("SELECT " + _HEAD_COLUMNS + " FROM WorkbenchRunJobs WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None
    def _status_query(self, where_clause, param):
        columns = ",".join("j." + column for column in _HEAD_COLUMNS.split(","))
        row = self.conn.execute("SELECT " + columns + ",a.scope_json,d.header_json,r.receipt_ref FROM WorkbenchRunJobs j "
            "LEFT JOIN WorkbenchRunAdmissionReadModels a ON a.run_ref=j.run_ref "
            "LEFT JOIN WorkbenchRunDecisionReadModels d ON d.run_ref=j.run_ref "
            "LEFT JOIN WorkbenchRunReceipts r ON r.run_ref=j.run_ref WHERE " + where_clause, (param,)).fetchone()
        return dict(row) if row else None
    def status(self, run_ref): return self._status_query("j.run_ref=?", run_ref)
    def status_by_request(self, request_key): return self._status_query("j.request_key=?", request_key)
    def claim_head(self, run_ref):
        row = self.conn.execute("SELECT run_ref,state,stage,executor_ref FROM WorkbenchRunJobs WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None
    def input_admitted(self, input_ref):
        return self.conn.execute("SELECT 1 FROM WorkbenchRunJobs WHERE input_ref=? LIMIT 1", (input_ref,)).fetchone() is not None
    def admission_read_model(self, run_ref, fields):
        row = self.conn.execute("SELECT run_ref," + self._read_columns(fields) +
                                " FROM WorkbenchRunAdmissionReadModels WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None
    def decision_read_model(self, run_ref, fields):
        row = self.conn.execute("SELECT run_ref," + self._read_columns(fields) +
                                " FROM WorkbenchRunDecisionReadModels WHERE run_ref=?", (run_ref,)).fetchone()
        return dict(row) if row else None
    def candidate_read_models(self, run_ref, fields=("summary",)):
        columns = self._read_columns(fields, prefix="m.")
        return [dict(row) for row in self.conn.execute("SELECT m.candidate_ref,m.run_ref," + columns +
            " FROM WorkbenchRunCandidateReadModels m JOIN WorkbenchRunCandidates c ON c.candidate_ref=m.candidate_ref "
            "WHERE m.run_ref=? ORDER BY c.sequence", (run_ref,))]
    def candidate_read_model(self, candidate_ref, fields):
        row = self.conn.execute("SELECT candidate_ref,run_ref," + self._read_columns(fields) +
                                " FROM WorkbenchRunCandidateReadModels WHERE candidate_ref=?", (candidate_ref,)).fetchone()
        return dict(row) if row else None
    @staticmethod
    def _read_columns(fields, prefix=""): return ",".join(prefix + field + "_json" for field in fields)

    def side_resource_detail(self, run_ref: str, side_key: str, resource_view: str) -> Optional[str]:
        row = self.conn.execute("SELECT payload_json FROM WorkbenchRunSideResources WHERE run_ref=? AND side_key=? AND resource_view=?",
                                (run_ref, side_key, resource_view)).fetchone()
        return row[0] if row is not None else None

    def insert_admission_read_model(self, run_ref, scope, decision):
        self.conn.execute("INSERT INTO WorkbenchRunAdmissionReadModels(run_ref,scope_json,decision_json) VALUES (?,?,?)",
                          (run_ref, canonical_json(scope), canonical_json(decision)))

    def insert_decision_read_models(self, run_ref, run_read_model, candidate_read_models, *,
                                    side_batches=(), operation_catalog=(), side_operations=(), side_resources=()):
        prepared = encode_decision_read_models({"run_model": run_read_model, "candidate_models": candidate_read_models,
            "side_batches": side_batches, "operation_catalog": operation_catalog,
            "side_operations": side_operations, "side_resources": side_resources})
        self.insert_prepared_decision_read_models(run_ref, prepared["run_model"], prepared["candidate_models"],
            side_batches=prepared["side_batches"], operation_catalog=prepared["operation_catalog"],
            side_operations=prepared["side_operations"], side_resources=prepared["side_resources"])

    def insert_prepared_decision_read_models(self, run_ref, run_read_model, candidate_read_models, *,
                                             side_batches=(), operation_catalog=(), side_operations=(), side_resources=()):
        self.conn.execute("INSERT INTO WorkbenchRunDecisionReadModels(run_ref,header_json,context_json,"
            "memberships_json,calendar_json,official_json,process_json) VALUES (?,?,?,?,?,?,?)",
            (run_ref, *(run_read_model[name + "_json"] for name in _RUN_MODEL_FIELDS)))
        for candidate in candidate_read_models:
            self.conn.execute("INSERT INTO WorkbenchRunCandidateReadModels(candidate_ref,run_ref,"
                "summary_json,preparation_json,completion_json,delivery_json,delivery_detail_json,arrangements_json) VALUES (?,?,?,?,?,?,?,?)",
                (candidate["candidate_ref"], run_ref, *(candidate[name + "_json"] for name in _CANDIDATE_MODEL_FIELDS)))
        if side_batches:
            self.conn.executemany(_SIDE_BATCH_INSERT_SQL, [(run_ref, r["side_key"], r["batch_ref"], r["batch_label"], r["due_date"],
                r["is_overdue"], r["delay_hours"], r["finish_time"], r["finish_us"], r["status"], r["scheduled_count"],
                r["total_count"], r["deferred_count"], r["unplanned_count"], r["detail_json"]) for r in side_batches])
        if operation_catalog:
            self.conn.executemany(_OP_CATALOG_INSERT_SQL, [(run_ref, r["operation_ref"], r["batch_ref"], r["batch_label"],
                r["sequence"], r["sequence_unknown"], r["op_id"], r["saved_machine_ref"], r["label_json"]) for r in operation_catalog])
        if side_operations:
            self.conn.executemany(_SIDE_OP_INSERT_SQL, [(run_ref, r["side_key"], r["operation_ref"], r["arranged"], r["deferred"],
                r["allocation_state"], r["is_remaining"], r["start_us"], r["end_us"], r["machine_ref"], r["operator_ref"],
                r["resource_refs_json"], r["setup_hours"], r["required_hours"], r["arrangement_json"], r["preparation_json"]) for r in side_operations])
        if side_resources:
            self.conn.executemany(_SIDE_RESOURCE_INSERT_SQL, [(run_ref, r["side_key"], r["resource_view"], r["payload_json"]) for r in side_resources])

    def admission_receipt(self, request_key):
        row = self.conn.execute("SELECT action,context_ref,outcome_json FROM WorkbenchCommandReceipts WHERE request_key=?",
                                (request_key,)).fetchone()
        return None if row is None else tuple(row)

    def insert(self, *, request_key, input_ref, settings, revisions_json, conditions_archive_json,
               projections, baseline, now, run_ref, batches, operations):
        self.conn.execute(
            "INSERT INTO WorkbenchRunJobs(run_ref,request_key,input_ref,normalized_input_json,revisions_json,"
            "conditions_archive_json,execution_json,baseline_json,accepted_at,state,stage)"
            f" VALUES (?,?,?,?,?,?,?,?,?,'{RunState.QUEUED.value}','{RunStage.QUEUED.value}')",
            (run_ref, request_key, input_ref, canonical_json(settings), revisions_json, conditions_archive_json,
             canonical_json([item.to_dict() for item in projections]), canonical_json(baseline), now))
        if batches:
            self.conn.executemany(_BATCH_INSERT_SQL, batches)
        if operations:
            self.conn.executemany(_OP_INSERT_SQL, operations)
        return run_ref

    def claim(self, run_ref, executor_ref, now):
        cursor = self.conn.execute(
            f"UPDATE WorkbenchRunJobs SET state='{RunState.RUNNING.value}',stage='{RunStage.COMPUTING.value}',executor_ref=?,"
            f"started_at=? WHERE run_ref=? AND state='{RunState.QUEUED.value}' AND stage='{RunStage.QUEUED.value}'",
            (executor_ref, now, run_ref))
        return ({"state": RunState.RUNNING.value, "stage": RunStage.COMPUTING.value, "executor_ref": executor_ref, "started_at": now}
                if cursor.rowcount == 1 else None)

    def finish_prepared(self, run_ref, result, now):
        """``result`` is the encoded receipt (``encode_result``)."""
        state, receipt_ref = result["state"], new_ref()
        self.conn.execute("INSERT INTO WorkbenchRunReceipts(receipt_ref,run_ref,state,result_json,recorded_at) VALUES (?,?,?,?,?)",
                          (receipt_ref, run_ref, state, result["result_json"], now))
        cursor = self.conn.execute(f"UPDATE WorkbenchRunJobs SET state=?,stage='{RunStage.FINISHED.value}',finished_at=?,error_json=? "
                                   f"WHERE run_ref=? AND {enum_predicate('state', RUN_UNFINISHED_STATE_VALUES)}",
                                   (state, now, result["error_json"], run_ref))
        if cursor.rowcount != 1:
            raise ValueError("Run terminal update did not affect exactly one admission")
        return {"state": state, "stage": RunStage.FINISHED.value, "finished_at": now, "error_json": result["error_json"],
                "receipt_ref": receipt_ref}

    def command_receipt_action(self, request_key):
        row = self.conn.execute("SELECT action FROM WorkbenchCommandReceipts WHERE request_key=?", (request_key,)).fetchone()
        return row[0] if row else None

    def unfinished(self, run_ref):
        where, params = ("", ()) if run_ref is None else (" AND run_ref=?", (run_ref,))
        return [dict(row) for row in self.conn.execute("SELECT " + _HEAD_COLUMNS + " FROM WorkbenchRunJobs "
            "WHERE " + enum_predicate("state", RUN_UNFINISHED_STATE_VALUES) + where + " ORDER BY accepted_at,run_ref", params)]

    def awaiting_reconciliation(self, run_ref):
        self.conn.execute(f"UPDATE WorkbenchRunJobs SET stage='{RunStage.AWAITING_RECONCILIATION.value}' WHERE run_ref=? "
                          f"AND {enum_predicate('state', RUN_UNFINISHED_STATE_VALUES)}", (run_ref,))

    def saved_catalog_machines(self, run_ref):
        return [dict(row) for row in self.conn.execute(
            "SELECT DISTINCT saved_machine_ref AS ref, json_extract(label_json, '$.saved_machine.label') AS label "
            "FROM WorkbenchRunOperationCatalog WHERE run_ref=? AND saved_machine_ref IS NOT NULL", (run_ref,))]

    def unarranged_batch_operation_refs(self, run_ref: str, side_key: str, *,
                                        batch_refs: Sequence[str]) -> Dict[str, Dict[str, List[str]]]:
        grouped: Dict[str, Dict[str, List[str]]] = {}
        for batch_ref, op_ref, deferred in self.conn.execute(
            "SELECT cat.batch_ref, cat.operation_ref, s.deferred FROM WorkbenchRunOperationCatalog cat "
            "JOIN WorkbenchRunSideOperations s ON s.run_ref=cat.run_ref AND s.side_key=? AND s.operation_ref=cat.operation_ref "
            "WHERE cat.run_ref=? AND s.arranged=0 AND cat.batch_ref IN (SELECT value FROM json_each(?)) "
            "ORDER BY cat.batch_ref ASC, cat.operation_ref ASC", (side_key, run_ref, json.dumps(list(batch_refs)))):
            grouped.setdefault(batch_ref, {"deferred": [], "unplanned": []})["deferred" if deferred else "unplanned"].append(op_ref)
        return grouped

    def operation_catalog_labels(self, run_ref: str, operation_refs) -> Dict[str, Dict[str, Any]]:
        return {op_ref: read_stored_json(raw, dict) for op_ref, raw in self.conn.execute(
            "SELECT operation_ref, label_json FROM WorkbenchRunOperationCatalog "
            "WHERE run_ref=? AND operation_ref IN (SELECT value FROM json_each(?))", (run_ref, json.dumps(list(operation_refs))))}

    def operation_change_counts(self, run_ref, ref_side_key, sel_side_key):
        """Counts against an available reference; the caller reports an unavailable one without comparing."""
        row = self.conn.execute(_OP_CMP_CTE + " SELECT COUNT(*) AS total, COALESCE(SUM(has_changed_fields),0) AS changed,"
            " COALESCE(SUM(CASE WHEN has_changed_fields=0 AND INSTR(','||change_kinds_csv||',',',unknown,')>0 THEN 1 ELSE 0 END),0) AS unknown,"
            " COALESCE(SUM(CASE WHEN m_chg=1 THEN 1 ELSE 0 END),0) AS machines,"
            " COALESCE(SUM(CASE WHEN b_arr=1 AND a_arr=1 AND m_chg IS NULL THEN 1 ELSE 0 END),0) AS machine_unknown"
            " FROM op_cmp", {"run_ref": run_ref, "ref_side": ref_side_key, "sel_side": sel_side_key, "ref_avail": 1}).fetchone()
        return dict(row)

    def page_side_batches(self, run_ref, ref_side_key, sel_side_key, *, ref_avail: bool,
                          filters, offset: int, limit: int, all_rows: bool = False, selected_batch_ref=None):
        params = {"run_ref": run_ref, "ref_side": ref_side_key, "sel_side": sel_side_key, "ref_avail": int(ref_avail)}
        cte = _OP_CMP_CTE + _BATCH_CMP_TAIL
        selected_row = None
        if selected_batch_ref is not None:
            raw = self.conn.execute(cte + " SELECT * FROM batch_cmp WHERE batch_ref=:sel_batch_ref",
                                    {**params, "sel_batch_ref": selected_batch_ref}).fetchone()
            selected_row = dict(raw) if raw else None
        where_sql = _batch_where_sql(filters, params)
        total = self.conn.execute(cte + " SELECT COUNT(*) FROM batch_cmp" + where_sql, params).fetchone()[0]
        order_sql = " ORDER BY " + _batch_order_sql(filters["sort"], "DESC" if filters["order"] == "desc" else "ASC")
        limit_sql = "" if all_rows else " LIMIT :limit OFFSET :offset"
        if not all_rows:
            params["limit"], params["offset"] = limit, offset
        rows = [dict(r) for r in self.conn.execute(cte + " SELECT * FROM batch_cmp" + where_sql + order_sql + limit_sql, params)]
        return rows, total, selected_row

    def page_side_operations(self, run_ref, ref_side_key, sel_side_key, *, ref_avail: bool,
                             filters, offset: int, limit: int, all_rows: bool = False):
        params = {"run_ref": run_ref, "ref_side": ref_side_key, "sel_side": sel_side_key, "ref_avail": int(ref_avail)}
        clauses = ["1=1"]
        if filters["batch_ref"] is not None:
            clauses.append("batch_ref = :batch_ref")
            params["batch_ref"] = filters["batch_ref"]
        change = filters["change_kind"]
        if change == "changed":
            clauses.append("has_changed_fields = 1")
        elif change != "all":
            clauses.append("INSTR(','||change_kinds_csv||',', ','||:change_kind||',') > 0")
            params["change_kind"] = change
        if filters["resource_ref"] is not None:
            clauses.append("(:res_ref IN (SELECT value FROM json_each(b_res_json)) "
                           "OR :res_ref IN (SELECT value FROM json_each(a_res_json)))")
            params["res_ref"] = filters["resource_ref"]
        where_sql = " WHERE " + " AND ".join(clauses)
        total = self.conn.execute(_OP_CMP_CTE + " SELECT COUNT(*) FROM op_cmp" + where_sql, params).fetchone()[0]
        order_sql = " ORDER BY " + _op_order_sql(filters["sort"], "DESC" if filters["order"] == "desc" else "ASC")
        limit_sql = "" if all_rows else " LIMIT :limit OFFSET :offset"
        if not all_rows:
            params["limit"], params["offset"] = limit, offset
        rows = [dict(r) for r in self.conn.execute(_OP_CMP_CTE + " SELECT * FROM op_cmp" + where_sql + order_sql + limit_sql, params)]
        return rows, total

    def page_preparation_operations(self, run_ref, ref_side_key, sel_side_key, *,
                                    filters, offset: int, limit: int, all_rows: bool = False):
        params = {"run_ref": run_ref, "ref_side": ref_side_key, "sel_side": sel_side_key}
        clauses = ["cat.run_ref = :run_ref"]
        if filters["work_scope"] == "remaining":
            clauses.append("a.is_remaining = 1")
        if filters["batch_ref"] is not None:
            clauses.append("cat.batch_ref = :batch_ref")
            params["batch_ref"] = filters["batch_ref"]
        if filters["allocation_state"] != "all":
            clauses.append("a.allocation_state = :alloc")
            params["alloc"] = filters["allocation_state"]
        if filters["machine_ref"] is not None:
            clauses.append(
                "((a.arranged=1 AND :m_ref IN (SELECT value FROM json_each(a.resource_refs_json))) "
                "OR (a.arranged=0 AND cat.saved_machine_ref=:m_ref) "
                "OR (b.arranged=1 AND :m_ref IN (SELECT value FROM json_each(b.resource_refs_json))) "
                "OR (:ref_side!='official' AND b.arranged=0 AND cat.saved_machine_ref=:m_ref))")
            params["m_ref"] = filters["machine_ref"]
        join_where = (
            " FROM WorkbenchRunOperationCatalog cat "
            "JOIN WorkbenchRunSideOperations b ON b.run_ref=cat.run_ref AND b.side_key=:ref_side AND b.operation_ref=cat.operation_ref "
            "JOIN WorkbenchRunSideOperations a ON a.run_ref=cat.run_ref AND a.side_key=:sel_side AND a.operation_ref=cat.operation_ref "
            "WHERE " + " AND ".join(clauses))
        total = self.conn.execute("SELECT COUNT(*)" + join_where, params).fetchone()[0]
        order_sql = " ORDER BY " + _prep_order_sql(filters["sort"], "DESC" if filters["order"] == "desc" else "ASC")
        limit_sql = "" if all_rows else " LIMIT :limit OFFSET :offset"
        if not all_rows:
            params["limit"], params["offset"] = limit, offset
        select_cols = (
            "SELECT cat.operation_ref, cat.batch_ref, cat.label_json, "
            "b.arranged AS b_arr, b.arrangement_json AS b_arr_json, b.preparation_json AS b_prep_json, "
            "a.arranged AS a_arr, a.arrangement_json AS a_arr_json, a.preparation_json AS a_prep_json")
        rows = [dict(r) for r in self.conn.execute(select_cols + join_where + order_sql + limit_sql, params)]
        return rows, total
