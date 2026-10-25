"""真实历史执行事实经当前 worker 与采用路径保持不变。"""

import json
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Tuple

import pytest

from core.algorithm_contracts.types import ScheduleResult
from core.algorithms.greedy.run_state_setup import prepare_run_state
from core.algorithms.greedy.scheduler import GreedyScheduler, prepare_native_schedule_inputs
from core.algorithms.greedy.seed import normalize_seed_results, seed_resource_segments, seed_result_for_output
from core.errors import AppError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.services.scheduler.execution.execution_ledger_guard import (
    ensure_ledger_execution_schedulable,
    fact_resource_segments,
    ledger_fact_changes,
)
from core.services.scheduler.run.schedule_execution_persistence_guard import (
    _schedule_resource_intervals,
    _validate_unselected_resource_overlap,
)
from core.services.scheduler.run.schedule_payload_contract import ValidatedScheduleRow
from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_result_item
from core.services.scheduler.template_lineage import TemplateLineageWriter
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.execution.production_report_validation import (
    _actual_resources_changed,
    execution_facts_changed,
)
from core.services.workbench.run.candidate_adoption_constraints import _resource_overlaps
from core.services.workbench.run.input import prepare_candidate_run_input
from core.services.workbench.run.preflight import PreflightService
from core.services.workbench.run.worker import WorkbenchRunWorker
from data.repositories.operator_machine_repo import OperatorMachineRepository
from tests.workbench.ea_zero_duration_support import adopt as adopt_point
from tests.workbench.ea_zero_duration_support import point_candidate
from tests.workbench.field_workspace_support import FieldAPI
from tests.workbench.run_candidate_adoption_support import INTENT, preview, service
from tests.workbench.run_candidate_support import candidate_case as candidate_fixture  # noqa: F401
from tests.workbench.run_candidate_support import compute
from tests.workbench.scheduler_execution_ledger_support import (
    formal_rows,
    read_facts,
)


def _saved_effort(case, run_ref):
    record = json.loads(case.conn.execute("SELECT result_json FROM WorkbenchRunReceipts WHERE run_ref=?", (run_ref,)).fetchone()[0])
    ledger = record["operation_effort"]
    assert ledger["effort_basis"] == "runtime_requirement_v1"
    ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
                            (str(case.op_id),)).fetchone()[0]
    matching = [item for item in ledger["items"] if item["operation_ref"] == ref]
    assert len(matching) == 1
    return matching[0]


def _assert_kept_worker_tasks(case, result, expected_times):
    assert result["state"] == "complete" and result["candidates"]
    for candidate in result["candidates"]:
        tasks = [json.loads(row[0]) for row in case.conn.execute(
            "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (candidate["candidate_ref"],))]
        actual = next(row for row in tasks if row["op_id"] == case.op_id)
        assert (actual["start_time"], actual["end_time"]) == expected_times
        assert (actual["machine_id"], actual["operator_id"]) == ("M1", "O1")
        artifact = json.loads(case.conn.execute("SELECT artifact_json FROM WorkbenchRunCandidates WHERE candidate_ref=?",
                                                (candidate["candidate_ref"],)).fetchone()[0])
        assert next(row for row in artifact["results"] if row["op_id"] == case.op_id)["seed_source"] == "execution_fact"


def test_normal_old_finish_can_be_supplemented_and_used_by_real_replan(candidate_case):
    case = candidate_case
    source_run, refs = compute(case)
    original_effort = _saved_effort(case, source_run)
    adopted = service(case.conn).adopt(refs[0], preview(case, refs[0]), "legacy-first-adoption-001", INTENT)
    version = adopted["data"]["official_plan"]["version"]
    schedule = case.conn.execute("SELECT id FROM Schedule WHERE version=? AND op_id=?", (version, case.op_id)).fetchone()[0]
    start_event_id = case.conn.execute("""INSERT INTO OperationExecutionEvents
        (schedule_version,schedule_id,op_id,batch_id,source_table,effective_plan_role,
         event_type,reported_status,event_time,actual_machine_id,actual_operator_id,
         created_by,idempotency_key,request_fingerprint,previous_state_revision)
        VALUES (?,?,?,'B1','schedule','adopted','start','processing','2026-09-09T08:00:00',
                'M1','O1','original-operator','legacy-normal-start-001','legacy-start-fingerprint',?)""",
        (version, schedule, case.op_id, f"{case.op_id}:0:0")).lastrowid
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    execution = next(row for row in case.projections("B1", "B2") if row.operation_ref == original_effort["operation_ref"])
    assert execution.execution_state == "started" and execution.target_quantity == 3 and execution.target_basis == "batch"
    assert execution.remaining_quantity is None
    receipt_count = case.conn.execute("SELECT count(*) FROM WorkbenchRunReceipts").fetchone()[0]
    blockers = PreflightService(case.conn).evaluate(case.settings("B1", "B2"))[0]["blockers"]
    assert [row["code"] for row in blockers] == ["execution_review_required"]
    assert case.conn.execute("SELECT count(*) FROM WorkbenchRunReceipts").fetchone()[0] == receipt_count
    case.conn.execute("""INSERT INTO OperationExecutionEvents
        (schedule_version,schedule_id,op_id,batch_id,source_table,effective_plan_role,
         event_type,reported_status,event_time,quantity_done,
         created_by,idempotency_key,request_fingerprint,previous_state_revision)
        VALUES (?,?,?,'B1','schedule','adopted','finish','completed','2026-09-09T10:00:00',
                3,'original-operator','legacy-normal-finish-001','legacy-finish-fingerprint',?)""",
        (version, schedule, case.op_id, f"{case.op_id}:1:{start_event_id}"))
    case.conn.commit()
    original = formal_rows(case.conn)["OperationExecutionEvents"]
    ensure_ledger_execution_schedulable(read_facts(case.conn, version))
    api = FieldAPI(case)
    task = api.task()
    legacy = task["execution"]["legacy_facts"][-1]
    assert legacy["actual_machine_ref"] is None and legacy["actual_operator_ref"] is None
    OperatorMachineRepository(case.conn).remove("O1", "M1")
    case.conn.commit()
    api.create(case.values(3, legacy_fact_ref=legacy["legacy_fact_ref"], reason="保留原实际，只补有效工时"), task)
    assert api.task()["execution"]["data_quality"] == "complete"
    ensure_ledger_execution_schedulable(read_facts(case.conn, version))
    OperatorMachineRepository(case.conn).add("O1", "M1", "normal", "no")
    case.conn.commit()
    accepted = case.accept(key="legacy-supplement-replan-001", settings=case.settings("B1", "B2"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    _assert_kept_worker_tasks(case, result, ("2026-09-09T08:00:00", "2026-09-09T10:00:00"))
    completed_effort = _saved_effort(case, result["run_ref"])
    assert completed_effort["requirement_role"] == "completed" and completed_effort["setup_state"] == "already_completed"
    assert completed_effort["target_quantity"] == completed_effort["execution_target_quantity"] == 3
    assert completed_effort["quantity_basis"] == completed_effort["execution_quantity_basis"] == "batch"
    assert completed_effort["remaining_quantity"] == 0
    hours = ("setup_standard_hours", "processing_standard_hours", "required_standard_hours")
    assert [completed_effort[key] for key in hours] == [original_effort[key] for key in hours] == [0, 0.75, 0.75]
    assert _saved_effort(case, source_run) == original_effort
    assert formal_rows(case.conn)["OperationExecutionEvents"] == original


def _merged_reports_in_two_parts(case):
    """合并外协组第 2、3 道各报两次：先报一段 0 件的开工，再报全部 3 件到完工；两道的实际开工、完工都相同。"""
    case.conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='T1'")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','供应商','T1')")
    case.conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
                      "VALUES ('G','P1',2,3,'merged',1,'S1')")
    copied = []
    with TransactionManager(case.conn).transaction():
        writer = TemplateLineageWriter(case.conn)
        template_rows = []
        for seq in (2, 3):
            cursor = case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,"
                                       "ext_group_id,setup_hours,unit_hours) VALUES ('P1',?,'T1','Turning','external','S1','G',0,0)", (seq,))
            template_rows.append({"id": cursor.lastrowid})
        for prepared in writer.prepare_templates(template_rows, facts=BatchFacts(case.conn).load()):
            copied.append(writer.copy_prepared_template("B1", prepared))
    case.conn.commit()
    _, refs = compute(case)
    version = service(case.conn).adopt(refs[0], preview(case, refs[0]), "merged-void-adoption-001", INTENT)["data"]["official_plan"]["version"]
    start, end = (value.replace(" ", "T") for value in case.conn.execute(
        "SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id=?", (version, case.op_id)).fetchone())
    hours = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 3600
    case.command("create", case.task(version, case.op_id), case.values(3, actual_start=start, actual_end=end,
                 effective_processing_hours=hours))
    start, end = (value.replace(" ", "T") for value in case.conn.execute(
        "SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id=?", (version, copied[0])).fetchone())
    middle = (datetime.fromisoformat(start) + timedelta(minutes=30)).isoformat()
    first = []
    for operation in copied:
        for begin, finish, quantity in ((start, middle, 0), (middle, end, 3)):
            hours = (datetime.fromisoformat(finish) - datetime.fromisoformat(begin)).total_seconds() / 3600
            row = case.command("create", case.task(version, operation), case.values(
                quantity, actual_start=begin, actual_end=finish, effective_processing_hours=hours,
                actual_machine_ref=None, actual_operator_ref=None))["data"]["rows"][0]
            if quantity == 0:
                first.append(row)
    return first


def test_void_that_parts_merged_cycle_warns_without_blocking(candidate_case):
    case = candidate_case
    first = _merged_reports_in_two_parts(case)

    def intent(row):
        return {"original_revision_ref": row["revision_ref"], "reason": "误记了其他工序的产出", "declared_operator": "现场班长"}

    # 撤掉第 2 道偏早的那条，它仍完工，但实际开工变晚，和第 3 道对不上：照常能撤销，只给提醒。
    checked = case.writer.preview("report_void", first[0]["report_ref"], intent(first[0]))
    assert checked["can_confirm"] is True and checked["downstream_impacts"] == []
    assert [row["code"] for row in checked["warnings"]] == ["external_cycle_actuals_differ"]
    assert "第 3 道工序" in checked["warnings"][0]["message"] and "排产检查会拦下" in checked["warnings"][0]["message"]
    assert case.command("report_void", first[0]["report_ref"], intent(first[0]))["result"] == "committed"
    blockers = PreflightService(case.conn).evaluate(case.settings())[0]["blockers"]
    assert "external_cycle_actuals_differ" in {row["code"] for row in blockers}
    # 第 3 道也撤掉偏早的那条，两道又对上了：不再提醒，排产检查也不再拦这一组。
    again = case.writer.preview("report_void", first[1]["report_ref"], intent(first[1]))
    assert again["can_confirm"] is True and again["warnings"] == []
    assert case.command("report_void", first[1]["report_ref"], intent(first[1]))["result"] == "committed"
    blockers = PreflightService(case.conn).evaluate(case.settings())[0]["blockers"]
    assert "external_cycle_actuals_differ" not in {row["code"] for row in blockers}


def _segmented_completion(case):
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Second lathe','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Second operator')")
    case.conn.executemany("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)",
                         (("O1", "M2"), ("O2", "M1"), ("O2", "M2")))
    case.conn.commit()
    _, refs = compute(case)
    version = service(case.conn).adopt(refs[0], preview(case, refs[0]), "segments-first-adoption", INTENT)["data"]["official_plan"]["version"]
    reports = []
    for start, end, operator in ((8, 9, "O1"), (9, 10, "O2"), (10, 11, "O1")):
        reports.append(case.command("create", case.task(version, case.op_id), case.values(
            1, actual_start=f"2026-09-09T{start:02d}:00:00", actual_end=f"2026-09-09T{end:02d}:00:00",
            effective_processing_hours=1, actual_operator_ref=case.ref("operator", operator)))["data"]["rows"][0])
    return version, reports


def test_completed_ledger_keeps_each_report_resource_pair_and_rejects_unrepresentable_segments(candidate_case):
    case = candidate_case
    version, _ = _segmented_completion(case)
    fact = read_facts(case.conn, version)[case.op_id]
    projection = case.projections("B1")[0]
    projection = replace(projection, reports=sorted(projection.reports, key=lambda report: report.actual_start or ""))
    assert fact.execution_protection_content is not None
    resources = fact.execution_protection_content["resources"]
    ensure_ledger_execution_schedulable({case.op_id: fact})
    expected = tuple((datetime(2026, 9, 9, start), datetime(2026, 9, 9, end), "M1", operator)
                     for start, end, operator in ((8, 9, "O1"), (9, 10, "O2"), (10, 11, "O1")))
    assert fact_resource_segments(fact) == expected
    assert (fact.actual_machine_id, fact.actual_operator_id) == ("M1", "O1")
    assert fact.execution_effective_intervals == tuple(segment[:2] for segment in expected)
    reversed_projection = replace(projection, reports=list(reversed(projection.reports)))
    reversed_changes = ledger_fact_changes(
        fact, reversed_projection, resources, source="internal", setup_hours=0.0, unit_hours=0.25,
    )
    assert reversed_changes is not None
    assert reversed_changes["actual_operator_id"] == "O1" and not reversed_changes["execution_protection_reasons"]
    assert fact_resource_segments(replace(fact, execution_protection_content=None)) == ()

    invalid = []
    for field in ("actual_machine_ref", "actual_operator_ref"):
        reports = list(projection.reports)
        reports[1] = replace(reports[1], **{field: None})
        invalid.append((replace(projection, reports=reports), resources,
                        "execution_ledger_actual_resource_missing_or_multiple"))
    operator_ref = case.ref("operator", "O2")
    for patch in ({"available": False}, {"kind": "machine"}):
        changed_resources = dict(resources)
        changed_resources[operator_ref] = dict(resources[operator_ref], **patch)
        invalid.append((projection, changed_resources, "execution_ledger_actual_resource_unavailable"))
    invalid.append((replace(projection, legacy_facts=[{
        "actual_machine_ref": case.ref("machine", "M2"), "actual_operator_ref": None,
    }]), resources, "execution_ledger_actual_resource_missing_or_multiple"))
    invalid.append((replace(projection, legacy_facts=[{
        "actual_machine_ref": None, "actual_machine_id": "missing-machine", "actual_operator_ref": None,
    }]), resources, "execution_ledger_actual_resource_missing_or_multiple"))
    duplicate = replace(projection.reports[-1], actual_start=projection.reports[0].actual_start,
                        actual_end=projection.reports[0].actual_end)
    invalid.append((replace(projection, reports=projection.reports[:2] + [duplicate]), resources,
                    "execution_ledger_intervals_not_representable"))
    gapped = replace(projection.reports[1], actual_start="2026-09-09T09:15:00")
    invalid.append((replace(projection, reports=[projection.reports[0], gapped, projection.reports[2]]), resources,
                    "execution_ledger_intervals_not_representable"))
    for damaged, current_resources, reason in invalid:
        changes = ledger_fact_changes(
            fact, damaged, current_resources, source="internal", setup_hours=0.0, unit_hours=0.25,
        )
        assert changes is not None
        assert reason in changes["execution_protection_reasons"]
        with pytest.raises(AppError) as exc:
            ensure_ledger_execution_schedulable({case.op_id: replace(fact, **changes)})
        assert exc.value.details is not None
        assert exc.value.details["reason"] == "execution_ledger_requires_reconciliation"
    truncated = replace(projection, completion_basis="legacy_finish_event", reports=projection.reports[:2])
    changes = ledger_fact_changes(
        fact, truncated, resources, source="internal", setup_hours=0.0, unit_hours=0.25,
    )
    assert changes is not None
    assert changes["execution_effective_intervals"] == tuple(segment[:2] for segment in expected[:2])
    with pytest.raises(AppError) as exc:
        ensure_ledger_execution_schedulable({case.op_id: replace(fact, **changes)})
    assert exc.value.details is not None
    assert "execution_ledger_actual_interval_inconsistent" in exc.value.details["data_gaps"]


def test_segment_metadata_survives_seed_coercion_and_occupies_only_its_actual_resources(candidate_case):
    case = candidate_case
    _segmented_completion(case)
    case.batch("B2")
    case.operation(batch="B2")
    case.conn.commit()
    prepared = prepare_candidate_run_input(case.conn, case.settings("B1", "B2"), case.projections("B1", "B2"))
    seed = prepared.execution_seed_results[0]
    fact = prepared.execution_facts[case.op_id]
    segments: Tuple[Tuple[datetime, datetime, str, str], ...] = fact_resource_segments(fact)
    assert len(segments) == 3
    assert seed["_resource_segments"] == segments
    coerced = coerce_seed_result_item(seed, idx=0)
    normalized, op_ids, warnings = normalize_seed_results(seed_results=[coerced], operations=prepared.algo_ops)
    assert op_ids == {case.op_id} and warnings == []
    assert seed_resource_segments(normalized[0]) == segments
    assert type(seed_result_for_output(normalized[0])) is ScheduleResult
    native = prepare_native_schedule_inputs({}, scheduler=GreedyScheduler(prepared.cal_svc),
        operations=prepared.algo_ops, batches=prepared.batches, seed_results=normalized)
    state = prepare_run_state(prepared_inputs=native, params=SimpleNamespace(base_time=datetime(2026, 9, 9, 8)),
        warnings=[], algo_stats={}, readiness_gate_enabled=False, strict_mode=True)
    assert state.machine_timeline["M1"] == [segment[:2] for segment in segments]
    assert state.operator_timeline["O1"] == [segments[0][:2], segments[2][:2]]
    assert state.operator_timeline["O2"] == [segments[1][:2]]
    assert len(state.results) == state.seed_count == 1
    assert type(state.results[0]) is ScheduleResult and not hasattr(state.results[0], "_resource_segments")

    def busy(selected):
        return sum((end - start).total_seconds() / 3600.0 for start, end, _machine, _operator in selected)

    # Busy hours and machine type neighbors follow each segment's actual resources, not the plan row's first pair.
    assert state.machine_busy_hours == {"M1": pytest.approx(busy(segments))}
    assert state.operator_busy_hours == {"O1": pytest.approx(busy([segments[0], segments[2]])),
                                         "O2": pytest.approx(busy([segments[1]]))}
    assert state.last_op_type_by_machine.neighbor_witness("M1")[0] == len(segments)

    actual = ValidatedScheduleRow(case.op_id, "M1", "O1", datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 11), "internal")
    concurrent = ValidatedScheduleRow(case.op_id + 100, "M2", "O2",
                                      datetime(2026, 9, 9, 9, 15), datetime(2026, 9, 9, 9, 45), "internal")
    with pytest.raises(CandidateAdoptionBlocked) as exc:
        _resource_overlaps([actual, concurrent], prepared.execution_facts)
    assert exc.value.code == "candidate_resource_overlap"
    concurrent = replace(concurrent, operator_id="O1")
    _resource_overlaps([actual, concurrent], prepared.execution_facts)
    intervals = _schedule_resource_intervals([actual], prepared.execution_facts)
    assert intervals["operator", "O2"] == ([segments[1][0]], [segments[1][1]])
    reservation = SimpleNamespace(op_id=concurrent.op_id, machine_id="M2", operator_id="O2",
                                  start_time=concurrent.start_time, end_time=concurrent.end_time)
    with pytest.raises(AppError) as exc:
        _validate_unselected_resource_overlap(payload=SimpleNamespace(schedule_rows=[actual]),
            reservations=[reservation], execution_facts=prepared.execution_facts)
    assert exc.value.details is not None
    assert exc.value.details["reason"] == "unselected_execution_resource_overlap"
    reservation.operator_id = "O1"
    _validate_unselected_resource_overlap(payload=SimpleNamespace(schedule_rows=[actual]),
        reservations=[reservation], execution_facts=prepared.execution_facts)
    point_event = ValidatedScheduleRow(case.op_id + 101, "M2", "O2",
                                       datetime(2026, 9, 9, 9, 30), datetime(2026, 9, 9, 9, 30), "internal")
    _validate_unselected_resource_overlap(payload=SimpleNamespace(schedule_rows=[point_event]),
        reservations=[SimpleNamespace(op_id=concurrent.op_id, machine_id="M2", operator_id="O2",
                                      start_time=concurrent.start_time, end_time=concurrent.end_time)],
        execution_facts=prepared.execution_facts)


def test_segmented_completion_runs_and_adopts_with_full_scope_then_protects_resource_interval_binding(candidate_case):
    case = candidate_case
    _, reports = _segmented_completion(case)
    case.batch("B2")
    new_op = case.operation("B2", machine_id="M2", operator_id="O1")
    case.conn.commit()
    only_new = case.accept(key="segments-partial-scope-run", settings=case.settings("B2"))
    partial = WorkbenchRunWorker(case.conn).execute(only_new["run_ref"])
    assert partial["state"] == "complete" and partial["candidates"]
    blocked = service(case.conn).preview(partial["candidates"][0]["candidate_ref"])
    assert blocked["validation"]["can_adopt"] is False
    assert "official_scope_not_covered" in {issue["code"] for issue in blocked["validation"]["issues"]}
    accepted = case.accept(key="segments-full-scope-run", settings=case.settings("B1", "B2"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    _assert_kept_worker_tasks(case, result, ("2026-09-09T08:00:00", "2026-09-09T11:00:00"))
    ref = result["candidates"][0]["candidate_ref"]
    tasks = [json.loads(row[0]) for row in case.conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,))]
    new_task = next(row for row in tasks if row["op_id"] == new_op)
    assert (new_task["machine_id"], new_task["operator_id"]) == ("M2", "O1")
    assert (new_task["start_time"], new_task["end_time"]) == ("2026-09-09T09:00:00", "2026-09-09T09:45:00")
    adopted = service(case.conn).adopt(ref, preview(case, ref), "segments-full-adoption", INTENT)
    assert adopted["result"] == "committed"
    projection = case.ledger.get_task(case.task(adopted["data"]["official_plan"]["version"], case.op_id))
    changed_reports = list(projection.reports)
    last = next(index for index, report in enumerate(changed_reports) if report.report_ref == reports[-1]["report_ref"])
    changed_reports[last] = replace(changed_reports[last], actual_operator_ref=case.ref("operator", "O2"))
    changed = replace(projection, reports=changed_reports)
    assert execution_facts_changed(projection, changed)
    assert _actual_resources_changed(projection, changed, "internal")
    with pytest.raises(WorkbenchCommandRejected) as exc:
        case.command("correct", reports[-1]["report_ref"], {
            "original_revision_ref": reports[-1]["revision_ref"], "actual_operator_ref": case.ref("operator", "O2"),
            "reason": "不能偷换已采用的分段人员",
        })
    assert "adopted_actual_resource_changed" in {item["code"] for item in exc.value.conflicts}
    maintained = case.command("correct", reports[-1]["report_ref"], {
        "original_revision_ref": reports[-1]["revision_ref"], "remark": "只维护备注，不改实际占用",
        "reason": "补充说明",
    })
    assert maintained["result"] == "committed"


def test_completed_zero_duration_point_report_can_replan_and_adopt(candidate_case):
    case = candidate_case
    first_ref = point_candidate(case, setup=0, unit=0, quantity=3)
    version = adopt_point(case, first_ref, key="point-first-adoption")["version"]
    created = case.command("create", case.task(version, case.op_id), case.values(
        3, actual_start="2026-09-09T08:00:00", actual_end="2026-09-09T08:00:00", effective_processing_hours=0.0))
    assert created["result"] == "committed"
    facts = read_facts(case.conn, version)
    fact = facts[case.op_id]
    ensure_ledger_execution_schedulable(facts)
    assert fact.execution_effective_intervals == ((datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 8)),)
    assert fact_resource_segments(fact) == ()

    # Non-point operations must still reject zero-length actual report intervals.
    projection = case.projections("B1")[0]
    assert fact.execution_protection_content is not None
    resources = fact.execution_protection_content["resources"]
    non_point_changes = ledger_fact_changes(
        fact, projection, resources, source="internal", setup_hours=0.0, unit_hours=0.25,
    )
    assert non_point_changes is not None
    assert "execution_ledger_actual_interval_missing" in non_point_changes["execution_protection_reasons"]

    # Zero-norm operations that actually took positive time must remain valid.
    positive_report = replace(projection.reports[0], actual_end="2026-09-09T09:00:00", effective_processing_hours=1.0)
    positive_projection = replace(projection, confirmed_finish="2026-09-09T09:00:00", reports=[positive_report])
    positive_changes = ledger_fact_changes(
        fact, positive_projection, resources, source="internal", setup_hours=0.0, unit_hours=0.0,
    )
    assert positive_changes is not None
    assert not positive_changes["execution_protection_reasons"]
    assert positive_changes["execution_effective_intervals"] == ((datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 9)),)
    ensure_ledger_execution_schedulable({case.op_id: replace(fact, **positive_changes)})

    case.batch("B2")
    new_op = case.operation("B2")
    case.conn.commit()
    preflight_data, _ = PreflightService(case.conn).evaluate(case.settings("B1", "B2"))
    assert preflight_data["blockers"] == []
    accepted = case.accept(key="point-full-scope-replan", settings=case.settings("B1", "B2"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    _assert_kept_worker_tasks(case, result, ("2026-09-09T08:00:00", "2026-09-09T08:00:00"))
    ref = result["candidates"][0]["candidate_ref"]
    tasks = [json.loads(row[0]) for row in case.conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,))]
    new_task = next(row for row in tasks if row["op_id"] == new_op)
    assert (new_task["start_time"], new_task["end_time"]) == ("2026-09-09T08:00:00", "2026-09-09T08:45:00")
    replan_plan = adopt_point(case, ref, key="point-replan-adoption")
    assert replan_plan["version"] == version + 1


def test_mixed_zero_and_positive_duration_point_reports_replan_and_adopt(candidate_case):
    case = candidate_case
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Second lathe','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Second operator')")
    case.conn.executemany("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)",
                         (("O1", "M2"), ("O2", "M1"), ("O2", "M2")))
    case.conn.commit()
    first_ref = point_candidate(case, setup=0, unit=0, quantity=3)
    version = adopt_point(case, first_ref, key="mixed-point-first-adoption")["version"]
    task_ref = case.task(version, case.op_id)
    m2_ref, o2_ref = case.ref("machine", "M2"), case.ref("operator", "O2")
    case.command("create", task_ref, case.values(0, actual_start="2026-09-09T08:00:00",
        actual_end="2026-09-09T08:00:00", effective_processing_hours=0.0,
        actual_machine_ref=m2_ref, actual_operator_ref=o2_ref))
    second = case.command("create", task_ref, case.values(3, actual_start="2026-09-09T08:00:00",
        actual_end="2026-09-09T09:00:00", effective_processing_hours=1.0))["data"]["rows"][0]
    case.batch("B2")
    new_op = case.operation("B2", machine_id="M2", operator_id="O2")
    case.conn.commit()

    fact_two = read_facts(case.conn, version)[case.op_id]
    assert (fact_two.actual_machine_id, fact_two.actual_operator_id) == ("M1", "O1")
    assert fact_resource_segments(fact_two) == ()
    prepared_two = prepare_candidate_run_input(case.conn, case.settings("B1", "B2"), case.projections("B1", "B2"))
    assert "_resource_segments" not in prepared_two.execution_seed_results[0]
    accepted_two = case.accept(key="mixed-point-two-seg-replan", settings=case.settings("B1", "B2"))
    result_two = WorkbenchRunWorker(case.conn).execute(accepted_two["run_ref"])
    _assert_kept_worker_tasks(case, result_two, ("2026-09-09T08:00:00", "2026-09-09T09:00:00"))
    ref_two = result_two["candidates"][0]["candidate_ref"]
    tasks_two = [json.loads(row[0]) for row in case.conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref_two,))]
    new_task_two = next(row for row in tasks_two if row["op_id"] == new_op)
    assert (new_task_two["machine_id"], new_task_two["operator_id"]) == ("M2", "O2")
    assert (new_task_two["start_time"], new_task_two["end_time"]) == ("2026-09-09T08:00:00", "2026-09-09T08:45:00")
    snapshot = sqlite3.connect(":memory:")
    case.conn.backup(snapshot)
    adopted_two = service(case.conn).adopt(ref_two, preview(case, ref_two), "mixed-point-two-seg-adoption", INTENT)
    assert adopted_two["result"] == "committed"
    snapshot.backup(case.conn)

    # 落在正时长报工内部的零时长点报工只是证据，不打断实际占用，也不改变实际开工、完工。
    case.command("correct", second["report_ref"], {"original_revision_ref": second["revision_ref"],
        "completed_quantity": 2, "reason": "拆出一件按内部时间点报工"})
    case.command("create", task_ref, case.values(1, actual_start="2026-09-09T08:30:00",
        actual_end="2026-09-09T08:30:00", effective_processing_hours=0.0,
        actual_machine_ref=m2_ref, actual_operator_ref=o2_ref))
    facts_inner = read_facts(case.conn, version)
    fact_inner = facts_inner[case.op_id]
    assert fact_inner.execution_effective_intervals == (
        (datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 8)),
        (datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 9)),
        (datetime(2026, 9, 9, 8, 30), datetime(2026, 9, 9, 8, 30)),
    )
    ensure_ledger_execution_schedulable(facts_inner)
    assert fact_resource_segments(fact_inner) == ()
    accepted_inner = case.accept(key="mixed-point-inner-replan", settings=case.settings("B1", "B2"))
    result_inner = WorkbenchRunWorker(case.conn).execute(accepted_inner["run_ref"])
    _assert_kept_worker_tasks(case, result_inner, ("2026-09-09T08:00:00", "2026-09-09T09:00:00"))
    ref_inner = result_inner["candidates"][0]["candidate_ref"]
    tasks_inner = [json.loads(row[0]) for row in case.conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref_inner,))]
    new_task_inner = next(row for row in tasks_inner if row["op_id"] == new_op)
    assert (new_task_inner["machine_id"], new_task_inner["operator_id"]) == ("M2", "O2")
    assert (new_task_inner["start_time"], new_task_inner["end_time"]) == ("2026-09-09T08:00:00", "2026-09-09T08:45:00")
    adopted_inner = service(case.conn).adopt(ref_inner, preview(case, ref_inner), "mixed-point-inner-adoption", INTENT)
    assert adopted_inner["result"] == "committed"
    snapshot.backup(case.conn)
    snapshot.close()

    case.command("correct", second["report_ref"], {"original_revision_ref": second["revision_ref"],
        "completed_quantity": 1, "reason": "拆分为两段正时长报工"})
    case.command("create", task_ref, case.values(0, actual_start="2026-09-09T09:00:00",
        actual_end="2026-09-09T09:00:00", effective_processing_hours=0.0,
        actual_machine_ref=m2_ref, actual_operator_ref=o2_ref))
    case.command("create", task_ref, case.values(2, actual_start="2026-09-09T09:00:00",
        actual_end="2026-09-09T10:00:00", effective_processing_hours=1.0))
    expected_segments = (
        (datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 9), "M1", "O1"),
        (datetime(2026, 9, 9, 9), datetime(2026, 9, 9, 10), "M1", "O1"),
    )
    fact = read_facts(case.conn, version)[case.op_id]
    assert (fact.actual_machine_id, fact.actual_operator_id) == ("M1", "O1")
    assert fact_resource_segments(fact) == expected_segments
    accepted = case.accept(key="mixed-point-full-scope-replan", settings=case.settings("B1", "B2"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    _assert_kept_worker_tasks(case, result, ("2026-09-09T08:00:00", "2026-09-09T10:00:00"))
    ref = result["candidates"][0]["candidate_ref"]
    tasks = [json.loads(row[0]) for row in case.conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,))]
    new_task = next(row for row in tasks if row["op_id"] == new_op)
    assert (new_task["machine_id"], new_task["operator_id"]) == ("M2", "O2")
    assert (new_task["start_time"], new_task["end_time"]) == ("2026-09-09T08:00:00", "2026-09-09T08:45:00")
    adopted = service(case.conn).adopt(ref, preview(case, ref), "mixed-point-replan-adoption", INTENT)
    assert adopted["result"] == "committed"


def test_completed_zero_duration_legacy_finish_point_can_replan_and_adopt(candidate_case):
    case = candidate_case
    first_ref = point_candidate(case, setup=0, unit=0, quantity=3)
    version = adopt_point(case, first_ref, key="legacy-point-first-adoption")["version"]
    schedule = case.conn.execute(
        "SELECT id FROM Schedule WHERE version=? AND op_id=?", (version, case.op_id),
    ).fetchone()[0]
    start_event_id = case.conn.execute("""INSERT INTO OperationExecutionEvents
        (schedule_version,schedule_id,op_id,batch_id,source_table,effective_plan_role,
         event_type,reported_status,event_time,actual_machine_id,actual_operator_id,
         created_by,idempotency_key,request_fingerprint,previous_state_revision)
        VALUES (?,?,?,'B1','schedule','adopted','start','processing','2026-09-09T08:00:00',
                'M1','O1','original-operator','legacy-point-start-001','legacy-point-start-fp',?)""",
        (version, schedule, case.op_id, f"{case.op_id}:0:0")).lastrowid
    case.conn.execute("""INSERT INTO OperationExecutionEvents
        (schedule_version,schedule_id,op_id,batch_id,source_table,effective_plan_role,
         event_type,reported_status,event_time,quantity_done,
         created_by,idempotency_key,request_fingerprint,previous_state_revision)
        VALUES (?,?,?,'B1','schedule','adopted','finish','completed','2026-09-09T08:00:00',
                3,'original-operator','legacy-point-finish-001','legacy-point-finish-fp',?)""",
        (version, schedule, case.op_id, f"{case.op_id}:1:{start_event_id}"))
    case.conn.commit()

    projection = case.projections("B1")[0]
    assert not projection.reports and projection.completion_basis == "legacy_finish_event"
    facts = read_facts(case.conn, version)
    fact = facts[case.op_id]
    ensure_ledger_execution_schedulable(facts)
    assert fact.execution_effective_intervals == ((datetime(2026, 9, 9, 8), datetime(2026, 9, 9, 8)),)

    case.batch("B2")
    new_op = case.operation("B2")
    case.conn.commit()
    accepted = case.accept(key="legacy-point-full-scope-replan", settings=case.settings("B1", "B2"))
    result = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])
    _assert_kept_worker_tasks(case, result, ("2026-09-09T08:00:00", "2026-09-09T08:00:00"))
    ref = result["candidates"][0]["candidate_ref"]
    tasks = [json.loads(row[0]) for row in case.conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,))]
    new_task = next(row for row in tasks if row["op_id"] == new_op)
    assert (new_task["start_time"], new_task["end_time"]) == ("2026-09-09T08:00:00", "2026-09-09T08:45:00")
    replan_plan = adopt_point(case, ref, key="legacy-point-replan-adoption")
    assert replan_plan["version"] == version + 1
