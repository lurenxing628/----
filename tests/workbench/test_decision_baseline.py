"""Decision baselines use captured last-per-operation arrangements and identities."""

import json
from copy import deepcopy
from datetime import date, datetime

import pytest

from core.infrastructure.connection_guards import query_only
from core.infrastructure.transaction import TransactionManager
from core.models.enums import ADOPTION_SOURCE_KIND_VALUES
from core.models.workbench_batch_material import normalize_material_changes
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
from core.services.workbench.batch.scope import BatchFactScope
from core.services.workbench.facts.candidate_facts import admit_generation_facts
from core.services.workbench.facts.candidate_read_source import read_candidate_source
from core.services.workbench.facts.candidate_store import CandidateStore
from core.services.workbench.facts.decision_baseline import (
    _last_official_rows,
    read_decision_baseline,
)
from core.services.workbench.facts.production_capture import CORRUPT_ARCHIVE, validate_production_archive
from core.services.workbench.run.worker import WorkbenchRunWorker
from core.shared.strict_parse import TIME_US_MAX
from tests.workbench.execution_ledger_support import publish_official_plan
from tests.workbench.run_candidate_adoption_support import INTENT, service
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401


def _run(case, key, *batches, _expected_state="complete", **settings):
    accepted = case.accept(key="decision-baseline-run-" + key, settings=case.settings(*batches, **settings))
    run = WorkbenchRunWorker(case.conn, clock=datetime.now).execute(accepted["run_ref"])
    assert run["state"] == _expected_state, run
    return read_candidate_source(CandidateStore(case.conn), run["candidates"][0]["candidate_ref"])


def _adopt(case, key, *batches, **settings):
    source = _run(case, key, *batches, **settings)
    ref = source.candidate["candidate_ref"]
    adopter = service(case.conn)
    adopter.point_rendering_enabled = True
    checked = adopter.preview(ref)
    assert checked["validation"]["can_adopt"], checked
    outcome = adopter.adopt(ref, checked["write_context"]["write_token"], "decision-baseline-adopt-" + key, INTENT)
    assert outcome["result"] == "committed", outcome
    return outcome["data"]["official_plan"], source


def _read(source):
    return read_decision_baseline(
        source.capture,
        source.facts,
        source.disposition,
    )


def test_absent_official_baseline_keeps_original_capture(candidate_case):
    source = _run(candidate_case, "absent")
    original = deepcopy(source.capture)
    data = _read(source)
    assert data["identity"]["state"] == "absent"
    assert data["identity"]["plan_ref"] is None
    assert data["tasks"] == [] and data["source_states"] == []
    assert data["deferred_operation_ids"] == []
    assert source.capture == original


def test_latest_adopted_version_keeps_saved_identities(candidate_case):
    case = candidate_case
    case.batch("B2")
    case.operation("B2")
    case.conn.commit()
    first, _original_first = _adopt(case, "first", "B1", "B2")
    second, original_second = _adopt(case, "second", "B1", "B2")
    assert second["version"] == first["version"] + 1
    current = _run(case, "compare", "B1", "B2")
    assert len(current.capture["baseline"]["rows"]) == 2
    before = deepcopy(current.capture)
    data = _read(current)
    tasks = {row["batch_label"]: row for row in data["tasks"]}
    assert set(tasks) == {"B1", "B2"}
    assert {row["official_version"] for row in tasks.values()} == {second["version"]}
    assert {row["plan_ref"] for row in tasks.values()} == {second["plan_ref"]}
    assert len({row["task_ref"] for row in tasks.values()}) == 2
    assert data["identity"]["source_candidate_ref"] == original_second.candidate["candidate_ref"]
    assert data["identity"]["source_run_ref"] == original_second.run["run_ref"]
    assert [row["version"] for row in data["source_states"]] == [second["version"]]
    assert data["source_states"][0]["available"] is True
    assert {row["source"] for row in tasks.values()} == {"internal"}
    assert all(row["locked"] is False for row in tasks.values())
    assert current.capture == before


def test_saved_baseline_rows_are_admitted_once_per_operation_with_stored_instants(candidate_case):
    _adopt(candidate_case, "instants")
    current = _run(candidate_case, "instants-read")
    assert len(current.capture["baseline"]["rows"]) == 1
    # baseline_json 是 Schedule 行的 JSON 副本，表的 CHECK 与唯一索引都不随它走：
    # 起止不是存储微秒、结束早于开始，或同一工序出现两行，就拒收这份对照。
    broken = []
    for column in ("start_us", "end_us"):
        for value in ("2026-09-09 08:00:00", 1.5, True, None, TIME_US_MAX + 1):
            capture = deepcopy(current.capture)
            capture["baseline"]["rows"][0][column] = value
            broken.append(capture)
    capture = deepcopy(current.capture)
    (row,) = capture["baseline"]["rows"]
    row["end_us"] = row["start_us"] - 1
    broken.append(capture)
    capture = deepcopy(current.capture)
    (row,) = capture["baseline"]["rows"]
    capture["baseline"]["rows"].append({**row, "id": row["id"] + 1, "task_ref": "f" * 48})
    broken.append(capture)
    # 点事件标志须与起止相同一致（Schedule 的 CHECK）：正时长行标成点事件、或标志不是整数，都拒收。
    for value in (1, True, None):
        capture = deepcopy(current.capture)
        capture["baseline"]["rows"][0]["is_point_event"] = value
        broken.append(capture)
    capture = deepcopy(current.capture)
    (row,) = capture["baseline"]["rows"]
    row["end_us"] = row["start_us"]
    broken.append(capture)
    # 每行恰是 Schedule 的全部列：缺一列、多一列都拒收；对照直接报出的自制外协按同一值域准入，两个合法值照收。
    for value in ("internal", "external"):
        capture = deepcopy(current.capture)
        capture["baseline"]["rows"][0]["source"] = value
        read_decision_baseline(capture, current.facts, current.disposition)
    for value in ("unexpected", None, 1):
        capture = deepcopy(current.capture)
        capture["baseline"]["rows"][0]["source"] = value
        broken.append(capture)
    capture = deepcopy(current.capture)
    del capture["baseline"]["rows"][0]["machine_label"]
    broken.append(capture)
    capture = deepcopy(current.capture)
    capture["baseline"]["rows"][0]["status"] = "scheduled"
    broken.append(capture)
    for capture in broken:
        with pytest.raises(WorkbenchCommandRejected) as rejected:
            read_decision_baseline(capture, current.facts, current.disposition)
        assert (rejected.value.code, rejected.value.status) == ("candidate_baseline_invalid", 500)


def test_archived_schedule_rows_are_admitted_with_their_table_checks(candidate_case):
    # 归档里的 Schedule 是 JSON 副本，表的 CHECK 与 (version, op_id) 唯一索引都不随它走；
    # 基线按这些不变量换算起止与点事件，坏一格整份归档按损坏拒收。
    _adopt(candidate_case, "archive")
    current = _run(candidate_case, "archive-read")
    stored = current.capture["facts"]
    validate_production_archive(stored)
    columns = stored["columns"]["Schedule"]
    (row,) = stored["tables"]["Schedule"]
    at = {name: columns.index(name) for name in ("version", "op_id", "id", "start_us", "end_us", "is_point_event",
                                                 "source", "lock_status")}
    assert row[at["start_us"]] < row[at["end_us"]] and row[at["is_point_event"]] == 0
    # 基线把原安排的自制外协与锁定直接带进对照；两个值域里的每个值都收。
    for name, values in (("source", ("internal", "external")), ("lock_status", ("unlocked", "locked"))):
        for value in values:
            kept = deepcopy(stored)
            kept["tables"]["Schedule"][0][at[name]] = value
            validate_production_archive(kept)
    # 版本的采纳来源决定基线按候选还是试调取来源编号：两个值都收，值域外整份拒收。
    kind = stored["columns"]["ScheduleHistory"].index("source_kind")
    for value in ADOPTION_SOURCE_KIND_VALUES:
        kept = deepcopy(stored)
        kept["tables"]["ScheduleHistory"][0][kind] = value
        validate_production_archive(kept)

    def tampered(**cells):
        broken = deepcopy(stored)
        for name, value in cells.items():
            broken["tables"]["Schedule"][0][at[name]] = value
        return broken

    broken = [tampered(**{column: value}) for column in ("start_us", "end_us")
              for value in ("2026-09-09 08:00:00", 1.5, True, None, TIME_US_MAX + 1)]
    broken += [tampered(end_us=row[at["start_us"]] - 1), tampered(end_us=row[at["start_us"]]),
               tampered(is_point_event=1), tampered(is_point_event=True), tampered(version="1"), tampered(op_id=True)]
    broken += [tampered(**{column: value}) for column in ("source", "lock_status") for value in ("unexpected", None, 1)]
    for value in ("run", "unexpected", None, 1):
        history = deepcopy(stored)
        history["tables"]["ScheduleHistory"][0][kind] = value
        broken.append(history)
    duplicate = deepcopy(stored)
    duplicate["tables"]["Schedule"].append(list(row))
    duplicate["tables"]["Schedule"][1][at["id"]] = row[at["id"]] + 1
    broken.append(duplicate)
    for value in broken:
        with pytest.raises(ValueError, match=CORRUPT_ARCHIVE):
            validate_production_archive(value)
        with pytest.raises(WorkbenchCommandRejected) as rejected:
            admit_generation_facts({"facts": value, "execution": []})
        assert (rejected.value.code, rejected.value.status) == ("candidate_artifact_invalid", 500)


def test_last_version_selection_keeps_segments_and_excludes_superseded_and_future_rows():
    rows = [{"id": key, "op_id": op, "version": version} for key, op, version in (
        (1, 1, 1), (2, 1, 2), (3, 2, 1), (4, 2, 3), (5, 3, 2))]
    assert [row["id"] for row in _last_official_rows(rows, 2)] == [2, 3, 5]


def test_immutable_zero_point_work_survives_current_operation_edits(candidate_case):
    case = candidate_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0 WHERE id=?", (case.op_id,))
    case.conn.commit()
    official, original = _adopt(case, "point")
    current = _run(case, "point-compare")
    # Changes made after admission cannot replace either saved generation.
    case.conn.execute("UPDATE BatchOperations SET unit_hours=10 WHERE id=?", (case.op_id,))
    case.conn.execute("UPDATE Machines SET name='Changed live lathe' WHERE machine_id='M1'")
    case.conn.commit()
    statements = []
    case.conn.set_trace_callback(statements.append)
    case.conn.execute("PRAGMA query_only=ON")
    try:
        data = _read(current)
    finally:
        case.conn.set_trace_callback(None)
        case.conn.execute("PRAGMA query_only=OFF")
    task = data["tasks"][0]
    assert task["plan_ref"] == official["plan_ref"]
    assert task["event_kind"] == "point" and task["duration_seconds"] == 0
    assert task["occupies_resources"] is False
    assert task["machine"]["label"] == "Original lathe"
    assert not any("FROM SCHEDULE " in statement.upper() or "JOIN SCHEDULE " in statement.upper()
                   for statement in statements)
    assert task["start"] == original.tasks[0]["start"]


def test_formal_deferred_ids_use_original_stage_source_independently_of_current_run(candidate_case):
    case = candidate_case
    second = case.operation(seq=2)
    case.conn.execute("INSERT INTO Materials(material_id,name,unit) VALUES ('STEEL','钢材','件')")
    case.conn.commit()
    operation_ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
                                      (str(second),)).fetchone()[0]
    with TransactionManager(case.conn).transaction():
        batch_ref = case.ref("batch", "B1")
        scope = BatchFactScope(BatchFacts(case.conn, material_day=date.today().isoformat()), command=True, mode="single_instance", target_ref=batch_ref)
        WorkbenchBatchMaterialService(case.conn).apply_normalized(scope, batch_ref, normalize_material_changes({"removed_keys": [], "rows": [{
            "row_key": None, "material_ref": case.ref("material", "STEEL"), "required_quantity": 3,
            "available_quantity": 0, "operation_ref": operation_ref, "arrivals": []}]}))
    _adopt(case, "stage", _expected_state="partial", material_strategy="stage")
    current = _run(case, "strict-current", ready_check=False, material_strategy="strict")
    assert current.disposition[operation_ref]["status"] == "eligible"
    data = _read(current)
    assert data["deferred_operation_ids"] == [second]


def test_baseline_only_resources_keep_frozen_labels_while_active_candidate_resources_use_admission_labels(
    candidate_case,
):
    from core.services.workbench.run.decision_session import decision_read

    case = candidate_case
    case.conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M2','Initial M2')")
    case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M2','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Initial O2')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O2','M2')")
    case.batch("B2")
    case.operation("B2", machine_id="M2", operator_id="O2")
    case.conn.execute("UPDATE BatchOperations SET machine_id='M1', operator_id='O1' WHERE id=?", (case.op_id,))
    case.conn.commit()

    _adopt(case, "frozen-v1", "B1", "B2")

    case.conn.execute("UPDATE Machines SET name='Renamed M1' WHERE machine_id='M1'")
    case.conn.execute("UPDATE Operators SET name='Renamed O1' WHERE operator_id='O1'")
    case.conn.execute("UPDATE Machines SET name='Active M2' WHERE machine_id='M2'")
    case.conn.execute("UPDATE Operators SET name='Active O2' WHERE operator_id='O2'")
    case.conn.execute("UPDATE BatchOperations SET machine_id='M2', operator_id='O2' WHERE id=?", (case.op_id,))
    case.conn.commit()

    current = _run(case, "frozen-v2", "B1", "B2")
    data = _read(current)
    by_batch = {row["batch_label"]: row for row in data["tasks"]}
    assert by_batch["B1"]["machine"]["label"] == "Original lathe"
    assert by_batch["B1"]["operator"]["label"] == "Original operator"
    assert by_batch["B2"]["machine"]["label"] == "Initial M2"
    assert by_batch["B2"]["operator"]["label"] == "Initial O2"

    with decision_read(
        case.conn,
        current.run["run_ref"],
        selected_candidate_ref=current.candidate["candidate_ref"],
        comparison_mode="admission_official",
    ) as source:
        cohort = {(row["kind"], row["ref"]): row["label"] for row in source.resource_cohort["resources"]}
    assert cohort[("machine", case.ref("machine", "M1"))] == "Original lathe"
    assert cohort[("operator", case.ref("operator", "O1"))] == "Original operator"
    assert cohort[("machine", case.ref("machine", "M2"))] == "Active M2"
    assert cohort[("operator", case.ref("operator", "O2"))] == "Active O2"


def test_candidate_metadata_scopes_to_arranged_members_across_partial_and_full_versions(candidate_case):
    case = candidate_case
    case.batch("B2")
    op_b = case.operation("B2")
    case.batch("B3")
    case.operation("B3")
    case.conn.commit()

    def op_ref_for(op_id):
        return case.conn.execute(
            "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
            (str(op_id),),
        ).fetchone()[0]

    ref_a, ref_b = op_ref_for(case.op_id), op_ref_for(op_b)

    official_v1, source_ab = _adopt(case, "ab-only", "B1", "B2")
    assert set(source_ab.facts.operations) == {ref_a, ref_b}
    full_compare = _run(case, "full-v1", "B1", "B2")

    case.command(
        "create",
        case.task(official_v1["version"], case.op_id),
        case.values(3, actual_end="2026-09-09T08:45:00", effective_processing_hours=0.75),
    )
    seeded_out_of_window = _run(
        case, "seed-a-out-of-window", "B1", "B2", start_date="2026-09-10", completed_policy="preserve_actuals"
    )
    assert {row["op_id"] for row in seeded_out_of_window.raw_tasks} == {case.op_id, op_b}

    # v2 仅重排 B2（不记录原候选），使 A 的最后正式安排仍在 v1：subset 与 full 均准确映射各自所属版本的工序元数据。
    publish_official_plan(
        case.conn,
        2,
        [{"op_id": op_b, "machine_id": "M1", "operator_id": "O1",
          "start_time": "2026-09-09T10:00:00", "end_time": "2026-09-09T10:45:00"}],
        record_source=False,
    )
    case.conn.commit()
    subset_compare = _run(case, "subset-v2", "B1", "B2", completed_policy="preserve_actuals")

    with TransactionManager(case.conn).transaction(), query_only(case.conn):
        subset_baseline = read_decision_baseline(
            subset_compare.capture, subset_compare.facts, subset_compare.disposition
        )
        subset_by_ref = {row["operation_ref"]: row for row in subset_baseline["tasks"]}
        assert set(subset_by_ref) == {ref_a, ref_b}
        assert subset_by_ref[ref_a]["process_type_ref"] is not None

        full_baseline = read_decision_baseline(
            full_compare.capture, full_compare.facts, full_compare.disposition
        )
        full_by_ref = {row["operation_ref"]: row for row in full_baseline["tasks"]}
        assert set(full_by_ref) == {ref_a, ref_b}
        assert all(row["process_type_ref"] is not None for row in full_by_ref.values())
        assert set(full_baseline["operation_standards"]) == {ref_a, ref_b}
        assert set(full_baseline["operation_efforts"]) == {ref_a, ref_b}


def test_large_archived_sequences_sort_numerically_across_workspace_baseline_reference_and_completion(
    candidate_case, monkeypatch
):
    from core.models.workbench_run_candidate import RunCandidateReadScope
    from core.services.workbench.facts.completion_scope import project_completion_summary
    from core.services.workbench.run.candidate_baseline import WorkbenchRunCandidateBaselineQueryService
    from core.services.workbench.run.candidates import WorkbenchRunCandidateQueryService
    from core.services.workbench.run.decision_session import decision_read
    from core.services.workbench.run.decision_workspace import read_reference_workspace
    from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository

    case = candidate_case
    _adopt(case, "seq-official", "B1")

    op_2 = case.operation("B1", seq=2, unit_hours=1)
    op_3 = case.operation("B1", seq=3, unit_hours=1)
    op_4 = case.operation("B1", seq=4, unit_hours=1)
    op_5 = case.operation("B1", seq=5, unit_hours=1)
    op_6 = case.operation("B1", seq=6, unit_hours=1)
    material_rows = []
    for idx, deferred_op in enumerate((op_3, op_4, op_5, op_6), start=3):
        mat_code = f"MAT_{idx}"
        case.conn.execute("INSERT INTO Materials(material_id,name,unit) VALUES (?,?,'件')", (mat_code, mat_code))
        op_ref = case.conn.execute(
            "SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
            (str(deferred_op),),
        ).fetchone()[0]
        material_rows.append(
            {
                "row_key": None,
                "material_ref": case.ref("material", mat_code),
                "required_quantity": 2,
                "available_quantity": 0,
                "operation_ref": op_ref,
                "arrivals": [],
            }
        )
    case.conn.commit()
    with TransactionManager(case.conn).transaction():
        batch_ref = case.ref("batch", "B1")
        scope = BatchFactScope(BatchFacts(case.conn, material_day=date.today().isoformat()), command=True, mode="single_instance", target_ref=batch_ref)
        WorkbenchBatchMaterialService(case.conn).apply_normalized(
            scope,
            batch_ref,
            normalize_material_changes({"removed_keys": [], "rows": material_rows}),
        )

    current = _run(case, "seq-stage", "B1", _expected_state="partial", material_strategy="stage")
    run_ref = current.run["run_ref"]
    cand_ref = current.candidate["candidate_ref"]

    seq_overrides = {
        case.op_id: 10,
        op_2: (1 << 53) + 5,
        op_3: 10_000_000_000_000_000,
        op_4: 1 << 53,
        op_5: 2,
        op_6: None,
    }
    original_capture = WorkbenchRunCandidateRepository.job_capture

    def capture_with_large_sequences(repo_self, target_run_ref):
        row = original_capture(repo_self, target_run_ref)
        if row is None or target_run_ref != run_ref:
            return row
        facts = json.loads(row["conditions_archive_json"])
        cols = facts["columns"]["BatchOperations"]
        id_idx, seq_idx = cols.index("id"), cols.index("seq")
        for op_row in facts["tables"]["BatchOperations"]:
            if isinstance(op_row, list) and op_row[id_idx] in seq_overrides:
                op_row[seq_idx] = seq_overrides[op_row[id_idx]]
            elif isinstance(op_row, dict) and op_row["id"] in seq_overrides:
                op_row["seq"] = seq_overrides[op_row["id"]]
        patched_text = json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
        return {
            **row,
            "conditions_archive_json": patched_text,
            "conditions_archive_bytes": len(patched_text.encode("utf-8")),
        }

    monkeypatch.setattr(WorkbenchRunCandidateRepository, "job_capture", capture_with_large_sequences)
    noop_bind = lambda scope, state: state  # noqa: E731

    ws_asc, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(
        RunCandidateReadScope(cand_ref, sort="sequence", order="asc"), bind_snapshot=noop_bind
    )
    ws_desc, _ = WorkbenchRunCandidateQueryService(case.conn).workspace(
        RunCandidateReadScope(cand_ref, sort="sequence", order="desc"), bind_snapshot=noop_bind
    )
    assert [row["sequence"] for row in ws_asc["tasks"]] == [10, str((1 << 53) + 5)]
    assert [row["sequence"] for row in ws_desc["tasks"]] == [str((1 << 53) + 5), 10]
    expected_unplanned_asc = [2, str(1 << 53), "10000000000000000", None]
    assert [row["sequence"] for row in ws_asc["unplanned_operations"]] == expected_unplanned_asc
    assert [row["sequence"] for row in ws_desc["unplanned_operations"]] == list(reversed(expected_unplanned_asc))

    base_asc, _ = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(
        RunCandidateReadScope(cand_ref, sort="sequence", order="asc"), bind_snapshot=noop_bind
    )
    base_desc, _ = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(
        RunCandidateReadScope(cand_ref, sort="sequence", order="desc"), bind_snapshot=noop_bind
    )
    expected_all_asc = [2, 10, str(1 << 53), str((1 << 53) + 5), "10000000000000000", None]
    assert [row["sequence"] for row in base_asc["comparisons"]] == expected_all_asc
    assert [row["sequence"] for row in base_desc["comparisons"]] == list(reversed(expected_all_asc))

    ref_ws, _ = read_reference_workspace(
        case.conn, run_ref, bind_snapshot=noop_bind, selected_candidate_ref=cand_ref, comparison_mode="admission_official"
    )
    assert [row["sequence"] for row in ref_ws["unplanned_operations"]] == [
        2,
        str(1 << 53),
        str((1 << 53) + 5),
        "10000000000000000",
        None,
    ]

    with decision_read(case.conn, run_ref, selected_candidate_ref=cand_ref) as source:
        detailed_scope = source.completion.scope(cand_ref, details=True)
        recomputed_scope = project_completion_summary(
            source.completion.delivery(cand_ref), source.completion.work_items(cand_ref)
        )
    assert [row["sequence"] for row in detailed_scope["remaining_batches"][0]["operations"]] == expected_unplanned_asc
    assert recomputed_scope["deferred_operation_refs"] == detailed_scope["deferred_operation_refs"]
