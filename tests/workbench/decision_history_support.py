"""P7 histories in a controlled SQLite file, reusing the existing one-operation case."""

import json
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime

from flask import Blueprint, Flask, g

from core.models.workbench_command import WorkbenchCommandOutcome
from core.models.workbench_preflight import run_dates
from core.services.workbench.facts.candidate_projection import dispositions
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.candidate_tasks import validate_candidate_tasks
from core.services.workbench.facts.decision_baseline import read_decision_baseline
from core.services.workbench.facts.decision_metrics import admission_operation_refs
from core.services.workbench.facts.decision_read_model import build_decision_read_models, prepare_admission_read_models
from core.services.workbench.facts.decision_read_models import decode_model
from core.services.workbench.history_entries.conditions import (
    analyze_prepared_history_conditions,
    materialize_history_conditions,
    prepare_history_condition_side,
    prepare_history_condition_source,
)
from core.services.workbench.history_entries.writer import (
    record_run_admitted,
    record_run_finished,
    stage_official_adoption_entry,
)
from core.shared.refs import new_ref
from core.shared.strict_json import canonical_json
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_run_repo import WorkbenchRunRepository
from tests.workbench.plan_catalog_support import sync_history_from_schedule
from tests.workbench.run_candidate_adoption_support import INTENT as CANDIDATE_INTENT
from tests.workbench.run_candidate_adoption_support import preview as candidate_preview
from tests.workbench.run_candidate_adoption_support import service as candidate_service
from tests.workbench.run_candidate_support import compute, connect
from tests.workbench.run_jobs_support import JobCase
from tests.workbench.trial_adoption_support import INTENT as TRIAL_INTENT
from tests.workbench.trial_adoption_support import preview as trial_preview
from tests.workbench.trial_adoption_support import saved_scenario
from tests.workbench.trial_adoption_support import service as trial_adopter
from tests.workbench.trial_support import trial_case
from web.runtime_host import install_wall_clock

BASE = "/api/workbench/v1/scheduling/decision-history"


def compare_conditions(before_packet, after_packet, window):
    """两侧各自独立准备再比对；生产的成组读取经 HistoryReader 复用同一份准备结果。"""
    before, after = (
        prepare_history_condition_side(prepare_history_condition_source(packet), window)
        for packet in (before_packet, after_packet)
    )
    before_side, after_side, cond_analysis, configurations, objective = analyze_prepared_history_conditions(
        before, after
    )
    conditions = materialize_history_conditions(before_side, after_side, cond_analysis)
    return {"conditions": conditions, "configurations": configurations, "objective": objective}


def exported_history_references(headers, rows):
    """Reconstruct exported collections, preserving null, empty and member order."""
    columns = {label: index for index, label in enumerate(headers)}
    groups = {}
    for row in rows:
        kind = row[columns["记录类型"]]
        if kind == "指标值":
            continue
        assert kind in ("范围引用", "指标覆盖引用")
        metric = row[columns["指标键"]] or None
        assert (metric is None) == (kind == "范围引用")
        key = row[columns["历史条目编号"]], metric, row[columns["引用字段"]]
        groups.setdefault(key, []).append(row)
    result = {}
    for key, members in groups.items():
        first = members[0]
        value_type = first[columns["引用原值类型"]]
        count = first[columns["引用数量"]]
        if value_type == "null":
            assert len(members) == 1 and count in (None, "")
            result[key] = None
        else:
            assert value_type == "array" and len(members) == max(1, int(count))
            result[key] = []
        for position, row in enumerate(members, 1):
            reference, order = row[columns["引用永久编号"]], row[columns["引用顺序"]]
            assert row[columns["引用原值类型"]] == value_type and row[columns["引用数量"]] == count
            if value_type == "null" or int(count) == 0:
                assert reference in (None, "") and order in (None, "")
            else:
                assert int(order) == position
                result[key].append(reference[1:] if reference.startswith("'") else reference)
    return result


@contextmanager
def four_source_case(directory):
    """Compute the existing small fixture once; every later history point reuses its archive."""
    generator = trial_case.__wrapped__(directory)
    case = next(generator)
    try:
        run_ref, candidates = compute(case)
        selected = json.loads(
            case.conn.execute("SELECT result_json FROM WorkbenchRunReceipts WHERE run_ref=?", (run_ref,)).fetchone()[0]
        )
        candidate_ref = selected["selection"]["selected_candidate_ref"]
        adopted = candidate_service(case.conn).adopt(
            candidate_ref, candidate_preview(case, candidate_ref), "history-candidate-adopt-0001", CANDIDATE_INTENT
        )
        official = adopted["data"]["official_plan"]
        original_periods = case.conn.execute(
            "SELECT periods_json FROM WorkbenchCalendarDefaults WHERE singleton=1"
        ).fetchone()[0]
        case.conn.execute(
            "UPDATE WorkbenchCalendarDefaults SET periods_json=? WHERE singleton=1",
            ('[{"start":"08:00","end":"12:00","day_offset":0}]',),
        )
        case.conn.commit()
        saved = saved_scenario(case, {"base": {"candidate_ref": candidate_ref}}, changed=False, suffix="history-0001")
        trial = trial_adopter(case.conn).adopt(
            saved["scenario_ref"], trial_preview(case, saved), "history-trial-adopt-0001", TRIAL_INTENT
        )
        case.conn.execute("UPDATE WorkbenchCalendarDefaults SET periods_json=? WHERE singleton=1", (original_periods,))
        case.conn.commit()
        case.history_refs = {
            "run_ref": run_ref,
            "candidate_ref": candidate_ref,
            "candidate_refs": candidates,
            "candidate_receipt_ref": adopted["receipt_ref"],
            "candidate_plan_ref": official["plan_ref"],
            "candidate_version": official["version"],
            "scenario_ref": saved["scenario_ref"],
            "draft_ref": saved["draft_ref"],
            "trial_receipt_ref": trial["receipt_ref"],
            "trial_plan_ref": trial["data"]["official_plan"]["plan_ref"],
            "trial_version": trial["data"]["official_plan"]["version"],
        }
        append_candidate_adoption(case)
        yield case
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


def append_candidate_adoption(case):
    """Historical second event for one run, without replaying adoption against a changed baseline."""
    refs, conn = case.history_refs, case.conn
    original = conn.execute(
        "SELECT * FROM WorkbenchCommandReceipts WHERE receipt_ref=?",
        (refs["candidate_receipt_ref"],),
    ).fetchone()
    version = refs["trial_version"] + 1
    plan_ref = new_ref()
    request_key, receipt_ref = "history-candidate-adopt-0002", new_ref()[:32]
    adopted_at = "2026-09-11T10:00:00"
    # 采用事务先从 ScheduleVersionSeq 分配版本号，再写正式计划头、安排与回执。
    conn.execute("INSERT INTO ScheduleVersionSeq(version) VALUES (?)", (version,))
    conn.execute(
        """INSERT INTO ScheduleHistory (
            version, plan_ref, schedule_time, adopted_at, strategy, batch_count, op_count,
            result_status, created_by, request_key, declared_operator, application_operator, reason,
            source_kind, source_ref, source_label, run_ref, draft_ref, accepted_at, finished_at,
            algorithm_json, baseline_version, baseline_ref, baseline_kind, baseline_captured_at,
            baseline_captured_task_count, material_policy_json, deferred_operation_ids_json,
            operation_effort_json, plan_start_time, plan_end_time, end_includes_point,
            gantt_node_count, gantt_graph_json
        )
        SELECT
            ?, ?, ?, ?, strategy, batch_count, op_count,
            result_status, created_by, ?, declared_operator, application_operator, reason,
            source_kind, source_ref, source_label, run_ref, draft_ref, accepted_at, finished_at,
            algorithm_json, baseline_version, baseline_ref, baseline_kind, baseline_captured_at,
            baseline_captured_task_count, material_policy_json, deferred_operation_ids_json,
            operation_effort_json, plan_start_time, plan_end_time, end_includes_point,
            gantt_node_count, gantt_graph_json
        FROM ScheduleHistory WHERE version = ?""",
        (version, plan_ref, adopted_at, adopted_at, request_key, refs["candidate_version"]),
    )
    src_rows = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM Schedule WHERE version = ? ORDER BY id ASC",
            (refs["candidate_version"],),
        ).fetchall()
    ]
    for row in src_rows:
        conn.execute(
            """INSERT INTO Schedule (
                version, task_ref, op_id, operation_ref,
                start_time, end_time, start_us, end_us, is_point_event,
                batch_id, batch_priority, piece_id, seq,
                op_type_name, op_type_ref, op_type_label,
                source, setup_hours, unit_hours,
                quantity, remaining_quantity, batch_quantity, quantity_basis, quantity_reason,
                machine_id, machine_ref, machine_label,
                operator_id, operator_ref, operator_label,
                supplier_id, supplier_ref, supplier_label,
                lock_status
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?
            )""",
            (
                version,
                new_ref(),
                row["op_id"],
                row["operation_ref"],
                row["start_time"],
                row["end_time"],
                row["start_us"],
                row["end_us"],
                row["is_point_event"],
                row["batch_id"],
                row["batch_priority"],
                row["piece_id"],
                row["seq"],
                row["op_type_name"],
                row["op_type_ref"],
                row["op_type_label"],
                row["source"],
                row["setup_hours"],
                row["unit_hours"],
                row["quantity"],
                row["remaining_quantity"],
                row["batch_quantity"],
                row["quantity_basis"],
                row["quantity_reason"],
                row["machine_id"],
                row["machine_ref"],
                row["machine_label"],
                row["operator_id"],
                row["operator_ref"],
                row["operator_label"],
                row["supplier_id"],
                row["supplier_ref"],
                row["supplier_label"],
                row["lock_status"],
            ),
        )
    sync_history_from_schedule(conn, version)
    hist_row = dict(conn.execute("SELECT * FROM ScheduleHistory WHERE version = ?", (version,)).fetchone())
    provenance = {
        "source_kind": hist_row["source_kind"],
        "source_ref": hist_row["source_ref"],
        "run_ref": hist_row["run_ref"],
        "draft_ref": hist_row["draft_ref"],
        "baseline_ref": hist_row["baseline_ref"],
        "baseline_version": hist_row["baseline_version"],
    }
    stage_official_adoption_entry(
        conn,
        request_key=request_key,
        provenance=provenance,
        plan_ref=plan_ref,
        plan_version=version,
        adopted_at=adopted_at,
        schedule_time=hist_row["schedule_time"],
    )
    outcome = json.loads(original["outcome_json"])
    outcome["data"]["official_plan"].update(version=version, plan_ref=plan_ref)
    WorkbenchCommandRepository(conn).insert(
        request_key=request_key,
        receipt_ref=receipt_ref,
        action=original["action"],
        context_ref=original["context_ref"],
        input_json=original["input_json"],
        outcome=WorkbenchCommandOutcome(**outcome),
    )
    conn.commit()
    refs.update(
        second_candidate_receipt_ref=receipt_ref,
        second_candidate_plan_ref=plan_ref,
        second_candidate_version=version,
    )


def copy_case(source, directory):
    path = directory / "history.sqlite"
    conn = connect(path)
    source.conn.backup(conn)
    case = JobCase(conn)
    case.path, case.op_id = path, source.op_id
    case.history_refs = deepcopy(source.history_refs)
    case.app = Flask("decision-history-tests")
    install_wall_clock(case.app, datetime.now)
    return case


def _insert_dict_row(conn, table, row_dict):
    columns = tuple(row_dict)
    placeholders = ",".join("?" for _ in columns)
    conn.execute(
        f"INSERT INTO {table}({','.join(columns)}) VALUES ({placeholders})",
        tuple(row_dict.values()),
    )


def _clone_run_table_rows(conn, table, original_ref, clone_ref):
    rows = [dict(r) for r in conn.execute(f"SELECT * FROM {table} WHERE run_ref=?", (original_ref,))]
    for row in rows:
        row["run_ref"] = clone_ref
        _insert_dict_row(conn, table, row)


def clone_run(case, accepted, *, change_input=None, change_artifact=None, change_facts=None, change_receipt=None):
    """Append a complete historical archive; copied production facts keep their original identity."""
    conn, original_ref = case.conn, case.history_refs["run_ref"]
    source = dict(conn.execute("SELECT * FROM WorkbenchRunJobs WHERE run_ref=?", (original_ref,)).fetchone())
    ref, key = new_ref(), new_ref()
    source.update(
        run_ref=ref,
        request_key=key,
        input_ref="history-reuse-" + ref,
        accepted_at=accepted,
        started_at=accepted,
        finished_at=accepted,
        executor_ref=new_ref(),
    )
    if change_input is not None:
        value = json.loads(source["normalized_input_json"])
        change_input(value)
        source["normalized_input_json"] = canonical_json(value)
    if change_facts is not None:
        value = json.loads(source["conditions_archive_json"])
        change_facts(value)
        source["conditions_archive_json"] = canonical_json(value)
    _insert_dict_row(conn, "WorkbenchRunJobs", source)
    _clone_run_table_rows(conn, "WorkbenchRunBatches", original_ref, ref)
    _clone_run_table_rows(conn, "WorkbenchRunOperations", original_ref, ref)

    candidates = [
        dict(row)
        for row in conn.execute("SELECT * FROM WorkbenchRunCandidates WHERE run_ref=? ORDER BY sequence", (original_ref,))
    ]
    mapping = {row["candidate_ref"]: new_ref() for row in candidates}

    def remap(value):
        if isinstance(value, dict):
            return {k: remap(item) for k, item in value.items()}
        if isinstance(value, list):
            return [remap(item) for item in value]
        return mapping.get(value, ref if value == original_ref else value) if isinstance(value, str) else value

    for row in candidates:
        artifact = remap(json.loads(row["artifact_json"]))
        if change_artifact is not None:
            change_artifact(artifact)
        new_candidate = mapping[row["candidate_ref"]]
        _insert_dict_row(
            conn,
            "WorkbenchRunCandidates",
            {**row, "candidate_ref": new_candidate, "run_ref": ref, "artifact_json": canonical_json(artifact)},
        )
        for task in conn.execute(
            "SELECT * FROM WorkbenchRunCandidateTasks WHERE candidate_ref=? ORDER BY ordinal",
            (row["candidate_ref"],),
        ):
            task_dict = dict(task)
            task_dict["row_ref"] = new_ref()
            task_dict["candidate_ref"] = new_candidate
            _insert_dict_row(conn, "WorkbenchRunCandidateTasks", task_dict)

    receipt = conn.execute("SELECT * FROM WorkbenchRunReceipts WHERE run_ref=?", (original_ref,)).fetchone()
    result = remap(json.loads(receipt["result_json"]))
    if change_receipt is not None:
        change_receipt(result)
    run_receipt_ref = new_ref()
    conn.execute(
        "INSERT INTO WorkbenchRunReceipts VALUES (?,?,?,?,?)",
        (run_receipt_ref, ref, receipt["state"], canonical_json(result), accepted),
    )
    original = conn.execute(
        "SELECT * FROM WorkbenchCommandReceipts WHERE request_key=(SELECT request_key FROM WorkbenchRunJobs WHERE run_ref=?)",
        (original_ref,),
    ).fetchone()
    WorkbenchCommandRepository(conn).insert(
        request_key=key,
        receipt_ref=new_ref()[:32],
        action=original["action"],
        context_ref=source["input_ref"],
        input_json=original["input_json"],
        outcome=WorkbenchCommandOutcome("committed", {"run_ref": ref}),
    )
    _save_cloned_read_models(conn, ref, original_ref, run_receipt_ref, receipt["state"], accepted)
    conn.commit()
    return ref, mapping[case.history_refs["candidate_ref"]]


def _save_cloned_read_models(
    conn,
    run_ref,
    source_run_ref,
    run_receipt_ref,
    receipt_state,
    finished_at,
):
    """A copied archive gets read models and durable history entry from the same verified sources."""
    store, repo = CandidateStore(conn), WorkbenchRunRepository(conn)
    run = repo.head(run_ref)
    receipt, rows, capture = store.receipt(run), store.candidates(run_ref), store.capture(run_ref)
    facts = store.generation_facts(capture)
    admitted_head = {**run, "state": "queued", "started_at": None, "finished_at": None}
    record_run_admitted(conn, head=admitted_head, capture=capture, facts=facts)
    record_run_finished(
        conn,
        run_ref=run_ref,
        state=receipt_state,
        finished_at=finished_at,
        receipt_ref=run_receipt_ref,
        result=receipt,
    )
    source_scope = decode_model(repo.admission_read_model(source_run_ref, ("scope",)), ("scope",))["scope"]
    capture["run_options"] = source_scope["run_options"]
    disposition = dispositions(receipt, expected_refs=admission_operation_refs(facts, capture["input"]))
    prepared = {}
    for candidate in rows:
        tasks = validate_candidate_tasks(store, candidate, facts)
        prepared[candidate["candidate_ref"]] = {
            "raw_tasks": tasks.raw_tasks,
            "intervals": tasks.task_intervals,
            "scheduled_op_ids": tasks.scheduled_op_ids,
        }
    official = read_decision_baseline(capture, facts, disposition)
    admission = prepare_admission_read_models(run, capture, official, facts=facts, dispositions=receipt.dispositions,
                                              dates=run_dates(capture["input"]))
    repo.insert_admission_read_model(run_ref, admission["scope"], admission["decision"])
    models = build_decision_read_models(
        run,
        capture,
        receipt,
        rows,
        prepared,
        facts=facts,
        process=receipt.unified_process,
        admission=admission["decision"],
    )
    repo.insert_decision_read_models(
        run_ref,
        models["run_model"],
        models["candidate_models"],
        side_batches=models["side_batches"],
        operation_catalog=models["operation_catalog"],
        side_operations=models["side_operations"],
        side_resources=models["side_resources"],
    )


def api(case):
    from web.routes.workbench.decision_history import register_decision_history_routes

    bp = Blueprint("p7_decision_history", __name__)
    register_decision_history_routes(bp)
    case.app.register_blueprint(bp)
    statements = []

    @case.app.before_request
    def bind():
        g.db = connect(case.path)
        g.db.execute("PRAGMA query_only=ON")
        g.db.set_trace_callback(statements.append)

    @case.app.teardown_request
    def close(error):
        g.db.close()

    return case.app.test_client(), statements


def read(client, **query):
    if isinstance(query.get("metric_keys"), list):
        query["metric_keys"] = ",".join(query["metric_keys"])
    response = client.get(BASE, query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    return response.get_json()
