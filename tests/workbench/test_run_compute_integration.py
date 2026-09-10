"""Real resource, readiness, calendar and external-precedence integration."""

from datetime import datetime

import pytest

from core.models.workbench_run_compute import CandidateRunInputError
from core.services.workbench.run_compute import compute_candidate_run
from tests.workbench.identity_metadata_support import insert_row
from tests.workbench.run_compute_support import run_case as _run_case  # noqa: F401
from tests.workbench.run_compute_support import unchanged


def test_auto_assignment_uses_qualified_pair_without_writing_operation(run_case):
    case = run_case
    case.conn.execute("UPDATE BatchOperations SET machine_id=NULL,operator_id=NULL")
    case.conn.commit()
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), case.projections()))
    assert result.schedule_input.operations[0].machine_id is None
    assert result.schedule_input.operations[0].operator_id is None
    for payload in result.candidate_payloads.values():
        row = payload.schedule_rows[0]
        assert (row.machine_id, row.operator_id) == ("M1", "O1")


def test_excluding_predecessor_excludes_successor_without_scope_expansion(run_case):
    case = run_case
    case.conn.execute("UPDATE BatchOperations SET machine_id=NULL")
    second = case.operation(seq=2)
    case.batch("B2")
    eligible = case.operation("B2")
    case.batch("NEVER-SELECTED")
    case.operation("NEVER-SELECTED")
    case.conn.commit()
    result = unchanged(case, lambda: compute_candidate_run(
        case.conn, case.settings("B1", "B2", missing_resource_policy="exclude"), case.projections("B1", "B2"),
    ))
    assert set(result.schedule_input.normalized_batch_ids) == {"B1", "B2"}
    assert result.state == "partial"
    assert all(payload.scheduled_op_ids == {eligible} for payload in result.candidate_payloads.values())
    row = next(item for item in result.dispositions if item["op_id"] == second)
    assert row["status"] == "skipped"
    assert "predecessor_excluded" in {item["code"] for item in row["issues"]}


def test_readiness_override_applies_to_materials_and_ready_date(run_case):
    case = run_case
    case.conn.execute("UPDATE Batches SET ready_status='no',ready_date='2027-01-01'")
    case.conn.execute("INSERT INTO Materials(material_id,name) VALUES ('MAT','Material')")
    case.conn.execute("""INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty,ready_status)
        VALUES ('B1','MAT',3,1,'no')""")
    case.conn.commit()
    with pytest.raises(CandidateRunInputError) as error:
        unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(), case.projections()))
    assert error.value.reason == "no_eligible_operations"
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(ready_check=False), case.projections()))
    assert result.state == "complete"


def test_night_operator_calendar_efficiency_and_downtime_are_real(run_case):
    case = run_case
    insert_row(case.conn, "WorkCalendar", dict(date="2026-09-09", day_type="workday", shift_start="22:30",
               shift_end="06:30", shift_hours=8, efficiency=1, allow_normal="yes", allow_urgent="yes"))
    insert_row(case.conn, "OperatorCalendar", dict(operator_id="O1", date="2026-09-09", day_type="workday",
               shift_start="23:00", shift_end="07:00", shift_hours=8, efficiency=0.5, allow_normal="yes", allow_urgent="yes"))
    insert_row(case.conn, "MachineDowntimes", dict(machine_id="M1", scope_type="machine", scope_value="M1",
               start_time="2026-09-09 22:00:00", end_time="2026-09-10 00:00:00", reason_code="maintenance", status="active"))
    case.conn.commit()
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings(end_date="2026-09-10"), case.projections()))
    for payload in result.candidate_payloads.values():
        row = payload.schedule_rows[0]
        assert row.start_time == datetime(2026, 9, 10)
        assert row.end_time == datetime(2026, 9, 10, 1, 30)


def test_complex_merged_external_chain_and_shared_resource_competition(run_case):
    case = run_case
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('EXT','Heat treatment','external')")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','Supplier','EXT')")
    insert_row(case.conn, "ExternalGroups", dict(group_id="EG", part_no="P1", start_seq=2, end_seq=3,
               merge_mode="merged", total_days=0.25, supplier_id="S1"))
    external_ids = []
    for seq in (2, 3):
        insert_row(case.conn, "PartOperations", dict(part_no="P1", seq=seq, op_type_id="EXT", op_type_name="Heat treatment",
                   source="external", supplier_id="S1", ext_group_id="EG", setup_hours=0, unit_hours=0, status="active"))
        external_ids.append(case.operation(seq=seq, op_type_id="EXT", source="external", supplier_id="S1",
                                          machine_id=None, operator_id=None, setup_hours=0, unit_hours=0, ext_days=None))
    last = case.operation(seq=4)
    case.batch("B2", priority="urgent")
    competing = case.operation("B2", unit_hours=1)
    case.conn.commit()
    result = unchanged(case, lambda: compute_candidate_run(case.conn, case.settings("B1", "B2"), case.projections()))
    expected = {case.op_id, last, competing} | set(external_ids)
    for payload in result.candidate_payloads.values():
        assert payload.scheduled_op_ids == expected
        rows = {row.op_id: row for row in payload.schedule_rows}
        first, second = (rows[op_id] for op_id in external_ids)
        assert first.start_time >= rows[case.op_id].end_time
        assert first.end_time == second.end_time
        assert first.start_time == second.start_time
        assert (first.end_time - first.start_time).total_seconds() == 6 * 3600
        assert rows[last].start_time >= second.end_time
        internal = sorted((row for row in rows.values() if row.source == "internal"), key=lambda row: row.start_time)
        assert all(left.end_time <= right.start_time for left, right in zip(internal, internal[1:]))
