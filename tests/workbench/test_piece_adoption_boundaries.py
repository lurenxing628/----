"""Calendar/resource drift, quantity edges and per-piece external merge boundaries."""

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.services.scheduler.run.schedule_payload_contract import build_validated_schedule_payload
from core.services.workbench.run_compute import compute_candidate_run
from tests.workbench.piece_adoption_support import START, lower_input, payload, slot_payload, split
from tests.workbench.piece_adoption_support import candidate_case as candidate_case  # noqa: F401
from tests.workbench.test_piece_adoption import check


@pytest.mark.parametrize("change", ["efficiency", "downtime", "operator_inactive"])
def test_fresh_resource_calendar_facts_override_stale_prepared_caches(candidate_case, change):
    case = candidate_case
    split(case)
    prepared = lower_input(case)
    value = slot_payload(prepared)
    if change == "efficiency":
        case.conn.execute("INSERT INTO WorkCalendar(date,day_type,shift_hours,shift_start,efficiency,allow_normal,allow_urgent) "
                          "VALUES ('2026-09-09','workday',8,'08:00',0.5,'yes','yes')")
    elif change == "downtime":
        case.conn.execute("INSERT INTO MachineDowntimes(machine_id,start_time,end_time,reason_code,status) "
                          "VALUES ('M1','2026-09-09 08:00:00','2026-09-09 09:00:00','repair','active')")
    else:
        case.conn.execute("UPDATE Operators SET status='inactive' WHERE operator_id='O1'")
    case.conn.commit()
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, value)
    assert caught.value.code in ("piece_calendar_duration_conflict", "piece_resource_invalid")


def test_execution_projection_target_cannot_be_replaced_by_batch_multiplier(candidate_case):
    case = candidate_case
    split(case)
    prepared = lower_input(case)
    value = slot_payload(prepared)
    row = next(row for row in prepared.dispositions if row["piece_id"] is not None)
    row["execution"]["target_quantity"] = 3
    row["execution"]["remaining_quantity"] = 3
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, value)
    assert caught.value.code == "piece_execution_changed"


def test_piece_point_requires_its_own_witness_and_missing_dto_does_not_pass(candidate_case):
    case = candidate_case
    ids = split(case, common=False)
    prepared = lower_input(case)
    value = slot_payload(prepared)
    first = next(row for row in value.schedule_rows if row.op_id == ids["item-A", 20])
    altered = replace(value, schedule_rows=[replace(row, end_time=row.start_time) if row == first else row
                                            for row in value.schedule_rows])
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, altered)
    assert caught.value.code == "point_duration_nonzero"
    prepared.dispositions[0].pop("execution")
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, value)
    assert caught.value.code == "piece_evidence_incomplete"


def test_zero_piece_payload_is_proven_by_original_work_not_equal_interval(candidate_case):
    case = candidate_case
    ids = split(case, common=False, unit=0)
    result = compute_candidate_run(case.conn, case.settings(), case.projections())
    assert result.state == "complete"
    prepared = result.schedule_input
    for value in result.candidate_payloads.values():
        proof = check(case, prepared, value)
        assert {work.op_id for work in proof.scope.operations} == set(ids.values())
        assert all(work.target_quantity == 1 for work in proof.scope.operations)
        assert all(row.start_time == row.end_time for row in value.schedule_rows)
        with pytest.raises(ValidationError):
            build_validated_schedule_payload(list(value.schedule_rows), allowed_op_ids=set(ids.values()),
                                             operations=prepared.operations)


@pytest.mark.parametrize("merged", [False, True])
def test_real_external_periods_and_merged_intervals_remain_piece_local(candidate_case, merged):
    case = candidate_case
    ids = split(case, common=False, quantity=2)
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','Supplier','T1')")
    case.conn.execute("UPDATE BatchOperations SET source='external',supplier_id='S1',ext_days=1,"
                      "machine_id=NULL,operator_id=NULL")
    group = "G1" if merged else None
    if merged:
        case.conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
                          "VALUES ('G1','P1',20,30,'merged',2,'S1')")
    for seq in (20, 30):
        case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,ext_days,ext_group_id) "
                          "VALUES ('P1',?,'T1','Turning','external','S1',1,?)", (seq, group))
    case.conn.commit()
    prepared = lower_input(case)
    results = []
    for piece, offset in (("item-A", 0), ("item-B", 3)):
        for seq in (20, 30):
            start = START + timedelta(days=offset + (0 if merged or seq == 20 else 1))
            end = prepared.cal_svc.add_calendar_days(start, 2 if merged else 1)
            results.append(SimpleNamespace(op_id=ids[piece, seq], source="external", machine_id=None,
                                            operator_id=None, start_time=start, end_time=end))
    good = payload(prepared, results)
    check(case, prepared, good)
    if merged:
        moved_id = ids["item-B", 30]
        bad = payload(prepared, [replace(row, start_time=row.start_time + timedelta(days=1),
                                        end_time=row.end_time + timedelta(days=1))
                                 if row.op_id == moved_id else row for row in good.schedule_rows])
        with pytest.raises(PieceAdoptionBlocked) as caught:
            check(case, prepared, bad)
        assert caught.value.code == "piece_merged_group_split"
    else:
        bad = payload(prepared, [replace(row, end_time=row.end_time - timedelta(hours=1)) for row in good.schedule_rows])
        with pytest.raises(PieceAdoptionBlocked) as caught:
            check(case, prepared, bad)
        assert caught.value.code == "piece_external_duration_conflict"


def test_same_piece_label_in_different_batches_is_not_a_shared_identity(candidate_case):
    case = candidate_case
    ids = split(case, common=False, quantity=1)
    case.batch("B2", quantity=1)
    second = case.operation("B2", seq=20, piece_id="item-A")
    case.conn.commit()
    prepared = lower_input(case, "B1", "B2")
    value = slot_payload(prepared)
    proof = check(case, prepared, value)
    refs = dict(proof.operation_refs)
    assert refs[second] != refs[ids["item-A", 20]]
    assert next(work.predecessor_op_ids for work in proof.scope.operations if work.op_id == second) == ()


def test_real_legacy_quantity_above_one_piece_is_rejected_without_rewriting_finish(candidate_case):
    case = candidate_case
    ids = split(case, common=False)
    first = ids["item-A", 20]
    case.plan(1, [first])
    case.event(first, "start")
    case.event(first, "finish", quantity=2)
    prepared = lower_input(case)
    value = slot_payload(prepared)
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, value)
    assert caught.value.code == "piece_execution_quantity_unproven"


def test_disposition_boolean_id_is_not_an_integer_identity(candidate_case):
    case = candidate_case
    split(case, common=False, quantity=1)
    prepared = lower_input(case)
    value = slot_payload(prepared)
    assert prepared.dispositions[0]["op_id"] == 1
    prepared.dispositions[0]["op_id"] = True
    with pytest.raises(PieceAdoptionBlocked) as caught:
        check(case, prepared, value)
    assert caught.value.code == "piece_identity_invalid"
