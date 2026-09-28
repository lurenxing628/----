"""Real candidate decoding respects stage dates and never splits quantities itself."""

from datetime import datetime

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
from core.services.workbench.run.compute import compute_candidate_run
from core.services.workbench.run.input import prepare_candidate_run_input
from core.services.workbench.run.preflight import PreflightService
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged


def add_requirement(case, second, arrivals):
    case.conn.execute("DELETE FROM WorkbenchCalendarDefaults")
    case.conn.execute("INSERT INTO Materials(material_id,name,unit) VALUES ('STEEL','钢材','件')")
    case.conn.commit()
    operation_ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1", (str(second),)).fetchone()[0]
    with TransactionManager(case.conn).transaction():
        WorkbenchBatchMaterialService(case.conn).apply(case.ref("batch", "B1"), {"removed_keys": [], "rows": [{
            "row_key": None, "material_ref": case.ref("material", "STEEL"), "required_quantity": 3,
            "available_quantity": 0, "operation_ref": operation_ref, "arrivals": arrivals}]})


def test_stage_arrivals_wait_at_use_operation_in_all_real_candidates(run_case):
    case = run_case
    second = case.operation(seq=2)
    add_requirement(case, second, [{"arrival_date": "2026-09-10", "quantity": 1}, {"arrival_date": "2026-09-11", "quantity": 2}])
    settings = case.settings(material_strategy="stage")
    result = unchanged(case, lambda: compute_candidate_run(case.conn, settings, case.projections()))
    assert result.state == "complete"
    for candidate in result.candidate_payloads.values():
        rows = {row.op_id: row for row in candidate.schedule_rows}
        assert rows[case.op_id].start_time == datetime(2026, 9, 9, 8, 30)
        assert rows[second].start_time == datetime(2026, 9, 11, 8, 30)
    strict = prepare_candidate_run_input(case.conn, case.settings(material_strategy="strict"), case.projections())
    assert {op.material_ready_date for op in strict.algo_ops} == {"2026-09-11"}
    assert case.conn.execute("SELECT quantity FROM Batches WHERE batch_id='B1'").fetchone()[0] == 3


def test_missing_later_material_only_allows_earlier_stage_and_quantity_change_requires_review(run_case):
    case = run_case
    second = case.operation(seq=2)
    add_requirement(case, second, [])
    data, _ = PreflightService(case.conn).evaluate(case.settings(material_strategy="stage"))
    assert [row["status"] for row in data["tasks"]] == ["eligible", "skipped"]
    prepared = prepare_candidate_run_input(case.conn, case.settings(material_strategy="stage"), case.projections())
    assert [op.id for op in prepared.algo_ops] == [case.op_id]
    with pytest.raises(CandidateRunInputError):
        prepare_candidate_run_input(case.conn, case.settings(material_strategy="strict"), case.projections())
    case.conn.execute("UPDATE Batches SET quantity=4 WHERE batch_id='B1'")
    case.conn.commit()
    with pytest.raises(CandidateRunInputError):
        prepare_candidate_run_input(case.conn, case.settings(material_strategy="stage"), case.projections())


def test_readiness_disabled_does_not_apply_dated_material_bounds(run_case):
    case = run_case
    add_requirement(case, case.op_id, [{"arrival_date": "2030-01-01", "quantity": 3}])
    prepared = prepare_candidate_run_input(case.conn, case.settings(ready_check=False), case.projections())
    assert all(op.material_ready_date is None for op in prepared.algo_ops)


def test_readiness_projection_advances_by_date_without_updating_stored_arrival(run_case):
    from core.services.material.stage_availability import MaterialAvailability
    from core.services.workbench.batch.facts import BatchFacts
    from core.services.workbench.dashboard.material_views import current_material_views

    case = run_case
    add_requirement(case, case.op_id, [{"arrival_date": "2030-01-01", "quantity": 3}])
    facts = BatchFacts(case.conn).load()
    batch = next(row for row in facts["Batches"] if row["batch_id"] == "B1")
    availability = MaterialAvailability(facts)
    assert availability.readiness_state(batch, "2029-12-31")[0] == "no"
    assert availability.readiness_state(batch, "2030-01-01")[0] == "yes"
    tables = {**facts, "SchemaVersion": [{"version": 36}]}
    current = unchanged(case, lambda: current_material_views(tables, "2030-01-01"))
    assert current[0][0]["ready_status"] == "yes" and current[1][0]["available_qty"] == 3
    assert case.conn.execute("SELECT available_qty FROM BatchMaterials").fetchone()[0] == 0


def test_merged_external_segment_waits_for_last_members_material_as_one_block(run_case):
    from core.services.scheduler.template_lineage import TemplateLineageWriter

    case = run_case
    case.conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='T1'")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','供应商','T1')")
    case.conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) VALUES ('G','P1',2,3,'merged',2,'S1')")
    copied = []
    with TransactionManager(case.conn).transaction():
        for sequence in (2, 3):
            cursor = case.conn.execute("""INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,
                supplier_id,ext_days,ext_group_id,setup_hours,unit_hours)
                VALUES ('P1',?,'T1','Turning','external','S1',2,'G',0,0)""", (sequence,))
            copied.append(TemplateLineageWriter(case.conn).copy_template("B1", cursor.lastrowid))
    case.conn.commit()
    add_requirement(case, copied[1], [{"arrival_date": "2026-09-15", "quantity": 3}])
    result = compute_candidate_run(case.conn, case.settings(material_strategy="stage"), case.projections())
    for payload in result.candidate_payloads.values():
        rows = {row.op_id: row for row in payload.schedule_rows}
        assert rows[case.op_id].end_time < datetime(2026, 9, 15)
        assert rows[copied[0]].start_time == rows[copied[1]].start_time == datetime(2026, 9, 15)
        assert rows[copied[0]].end_time == rows[copied[1]].end_time == datetime(2026, 9, 17)


def test_stage_policy_is_captured_and_revalidated_at_adoption(candidate_case):
    from core.services.workbench.facts.candidate_store import CandidateStore
    from tests.workbench.run_candidate_adoption_support import INTENT, KEY, preview, service
    from tests.workbench.run_candidate_support import compute

    case = candidate_case
    second = case.operation(seq=2)
    add_requirement(case, second, [{"arrival_date": "2026-09-11", "quantity": 3}])
    run_ref, candidates = compute(case, case.settings(material_strategy="stage"))
    assert CandidateStore(case.conn).capture(run_ref)["input"]["material_strategy"] == "stage"
    token = preview(case, candidates[0])
    result = service(case.conn).adopt(candidates[0], token, KEY, INTENT)
    assert result["result"] == "committed"
    times = dict(case.conn.execute("SELECT op_id,start_time FROM Schedule"))
    assert times[case.op_id] < "2026-09-10" and times[second] >= "2026-09-11"
    from core.services.workbench.trial.base import prepare_base
    from core.services.workbench.trial.materials import run_policy
    from core.services.workbench.trial.validation import TrialValidator

    admission, rows, live = prepare_base(case.conn, {"base": {"plan_ref": result["data"]["official_plan"]["plan_ref"]}})
    assert run_policy(admission)["material_strategy"] == "stage"
    assert not TrialValidator(case.conn, admission, rows, live).evaluate()["issues"]
