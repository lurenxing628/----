"""Real candidate decoding respects stage dates and never splits quantities itself."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.material import stage_availability
from core.services.material.stage_availability import MaterialAvailability, covers_quantity
from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
from core.services.workbench.run.compute import compute_candidate_run
from core.services.workbench.run.input import prepare_candidate_run_input
from core.services.workbench.run.preflight import PreflightService
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


def material_tables(case):
    return {name: [dict(row) for row in case.conn.execute("SELECT * FROM " + name)] for name in (
        "BatchMaterials", "BatchMaterialReviews", "BatchMaterialArrivals", "BatchMaterialStages",
        "BatchOperations", "BatchExternalContexts")}


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
    availability = MaterialAvailability(material_tables(case))
    batch = dict(case.conn.execute("SELECT * FROM Batches WHERE batch_id='B1'").fetchone())
    requirement = availability.requirements["B1"][0]
    with patch.object(stage_availability, "arrival_day", wraps=stage_availability.arrival_day) as parse_day, \
            patch.object(stage_availability, "quantity", wraps=stage_availability.quantity) as parse_quantity, \
            patch.object(stage_availability, "sorted", wraps=sorted, create=True) as sort_rows:
        assert [availability.operation_release(batch, {"seq": sequence}, "stage") for sequence in (2, 1, 2, 1)] == [
            "2026-09-11", "1900-01-01", "2026-09-11", "1900-01-01"]
        assert availability.operation_release(batch, {"seq": 1}, "strict") == "2026-09-11"
        assert availability.operation_release(batch, {"seq": 2}, "strict") == "2026-09-11"
        assert availability.readiness_state(batch, "2026-09-10") == ("partial", [])
        assert availability.available(requirement, "2026-09-10") == Decimal(1)
        assert availability.available(requirement, "2026-09-11") == Decimal(3)
        assert availability.splittable_quantity(batch, "2026-09-10") == 1
        assert parse_day.call_count == 2
        assert parse_quantity.call_count == 5  # two arrivals, required/base amounts, batch quantity
        assert sum(not call.kwargs for call in sort_rows.call_args_list) == 1


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
    tables = material_tables(case)
    requirement = tables["BatchMaterials"][0]
    tables["BatchMaterialArrivals"] = [{"requirement_id": requirement["id"], "arrival_date": "bad-day", "quantity": 1}]
    availability = MaterialAvailability(tables)
    batch = {"batch_id": "B1", "quantity": 3}
    assert availability.operation_release(batch, {"seq": 1}, "stage") == "1900-01-01"
    with pytest.raises(WorkbenchCommandRejected, match="到料日期"):
        availability.operation_release(batch, {"seq": 2}, "stage")
    assert availability.operation_release(batch, {"seq": 1}, "stage") == "1900-01-01"
    earlier = dict(requirement, id=requirement["id"] + 1)
    tables["BatchMaterials"] = [earlier, requirement]
    tables["BatchMaterialReviews"].append({"requirement_id": earlier["id"], "batch_quantity": 3})
    with pytest.raises(WorkbenchCommandRejected, match="到料日期"):
        MaterialAvailability(tables).operation_release(batch, {"seq": 1}, "strict")
    tables["BatchMaterials"] = [dict(requirement, available_qty=3)]
    stocked = MaterialAvailability(tables)
    assert stocked.release(tables["BatchMaterials"][0]) == "1900-01-01"
    with pytest.raises(WorkbenchCommandRejected, match="到料日期"):
        stocked.available(tables["BatchMaterials"][0], "2026-09-10")
    case.conn.execute("UPDATE Batches SET quantity=4 WHERE batch_id='B1'")
    case.conn.commit()
    with pytest.raises(CandidateRunInputError):
        prepare_candidate_run_input(case.conn, case.settings(material_strategy="stage"), case.projections())


def test_merged_material_facts_keep_cross_piece_sequence_and_decimal_boundaries():
    batch = {"batch_id": "B1", "quantity": 3}
    first = {"id": 1, "batch_id": "B1", "required_qty": 0.1 + 0.2, "available_qty": 0, "ready_status": "no"}
    second = dict(first, id=2, required_qty=0.3)
    context = {"group_id": 1, "group_ref": "group-one", "group_part_no": "P1", "start_sequence": 3,
               "end_sequence": 6, "merge_mode": "merged", "supplier_id": "S1", "total_days": 2}
    tables = {
        "BatchMaterials": [first, second],
        "BatchMaterialReviews": [{"requirement_id": row["id"], "batch_quantity": 3} for row in (first, second)],
        "BatchMaterialStages": [{"requirement_id": 1, "operation_id": 5}, {"requirement_id": 2, "operation_id": 6}],
        "BatchMaterialArrivals": [
            {"requirement_id": 1, "arrival_date": "2026-09-10", "quantity": 0.1},
            {"requirement_id": 1, "arrival_date": "2026-09-10", "quantity": 0.2},
            {"requirement_id": 2, "arrival_date": "2026-09-11", "quantity": 0.3}],
        "BatchOperations": [{"id": number, "batch_id": "B1", "seq": number, "piece_id": 7 if number == 3 else None}
                            for number in (5, 3, 6)] + [{"id": 99, "batch_id": "OTHER", "seq": 1}],
        "BatchExternalContexts": [dict(context, operation_id=number, group_id=number) for number in (5, 3, 6)]
                                 + [{"operation_id": 99, "merge_mode": "merged"}],
    }
    availability = MaterialAvailability(tables)
    with patch.object(stage_availability, "context_group_key", wraps=stage_availability.context_group_key) as group_key:
        assert availability.use_sequence(first) == availability.use_sequence(second) == 3
        assert [availability.operation_release(batch, {"seq": sequence}, "stage") for sequence in (6, 2, 3)] == [
            "2026-09-11", "1900-01-01", "2026-09-11"]
        assert availability.operation_release(batch, {"seq": 1}, "strict") == "2026-09-11"
        assert availability.splittable_quantity(batch, "2026-09-11") == 3
        assert group_key.call_count == 3  # once per current-batch member; OTHER stays unconsumed
    assert availability.available(first, "2026-09-10") == Decimal("0.3")
    assert covers_quantity(Decimal("0.3"), Decimal(str(0.1 + 0.2)))
    assert not covers_quantity(Decimal(9999999999999999), Decimal(10000000000000000))
    large = dict(first, required_qty=1.0000000000000002e28, available_qty=1e28)
    large_arrivals = [{"requirement_id": 1, "arrival_date": day, "quantity": 999999999997.0}
                      for day in ("2026-09-10", "2026-09-11")]
    assert MaterialAvailability({"BatchMaterialArrivals": large_arrivals}).release(large) == "2026-09-11"
    tables["BatchMaterialStages"][0] = {"requirement_id": 1, "operation_id": 3}
    with pytest.raises(WorkbenchCommandRejected, match="单件分支"):
        MaterialAvailability(tables).use_sequence(first)
    assert MaterialAvailability({}).operation_release(batch, {"seq": 1}, "stage") == "1900-01-01"
