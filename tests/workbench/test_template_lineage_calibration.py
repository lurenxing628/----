"""D05 end-to-end: real template copies and complete production reports."""

import pytest

from core.infrastructure.transaction import TransactionManager
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.template_lineage_support import calibration, completed, create, lineage_case, origin
from tests.workbench.template_lineage_support import ledger_fixture as _ledger_fixture

_lineage_fixture = lineage_case


@pytest.mark.parametrize("hours,expected", [([1, 2, 3, 4], None), ([1, 2, 3, 4, 100], 3), (list(range(1, 26)), 15.5)])
def test_real_ledger_five_samples_and_latest_twenty_median(lineage_case, hours, expected):
    case = lineage_case
    ids, reports = completed(case, hours)
    before = all_rows(case.conn)
    case.conn.execute("PRAGMA query_only=ON")
    facts = calibration(case)
    row = facts["rows"][0]
    assert row["suggested_unit_hours"] == expected
    assert row["sample_count"] == min(len(ids), 20)
    assert row["eligible_sample_count"] == len(ids)
    assert row["candidate_count"] == len(ids) + 1  # Legacy OP1 is not a sample.
    assert row["status"] == ("suggested" if expected is not None else "insufficient_data")
    assert row["capabilities"]["adopt"] is False and row["capabilities"]["lock"] is False
    assert all_rows(case.conn) == before
    assert len(reports) == len(ids)


def test_template_revision_change_groups_new_five_not_old_five(lineage_case):
    case = lineage_case
    old_ids, _ = completed(case, [8, 8, 8, 8, 8], prefix="OLD", version=2)
    old = origin(case, old_ids[0])
    case.conn.execute("UPDATE PartOperations SET unit_hours=2")
    case.conn.commit()
    new_ids, _ = completed(case, [1, 1, 2, 3, 3], prefix="NEW", version=3)
    facts = calibration(case)
    row = facts["rows"][0]
    assert row["sample_count"] == 5 and row["suggested_unit_hours"] == 2
    assert row["template_revision"] > old["template_revision"]
    assert set(row["sample_refs"]) == {origin(case, op_id)["operation_ref"] for op_id in new_ids}
    assert {reason["code"]: reason["count"] for reason in row["exclusion_reasons"]}["template_revision_mismatch"] == 5


def test_manual_change_revert_and_withdrawal_remove_samples_not_reports(lineage_case):
    case = lineage_case
    ids, _ = completed(case, [1, 2, 3, 4, 5, 6])
    first = origin(case, ids[0])
    reports = all_rows(case.conn)["WorkbenchProductionReports"]
    revisions = all_rows(case.conn)["WorkbenchProductionReportRevisions"]
    with TransactionManager(case.conn).transaction():
        case.conn.execute("UPDATE BatchOperations SET unit_hours=8 WHERE id=?", (ids[0],))
        case.conn.execute("UPDATE BatchOperations SET unit_hours=1 WHERE id=?", (ids[0],))
        case.lineage_writer.withdraw(origin(case, ids[1])["operation_ref"], "confirmed source mismatch")
    row = calibration(case)["rows"][0]
    assert row["sample_count"] == 4 and row["suggested_unit_hours"] is None
    assert origin(case, ids[0]) == first
    assert all_rows(case.conn)["WorkbenchProductionReports"] == reports
    assert all_rows(case.conn)["WorkbenchProductionReportRevisions"] == revisions


def test_two_template_operations_never_share_same_part_samples(lineage_case):
    case = lineage_case
    ids, _ = completed(case, [1, 2, 3, 4, 5])
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,unit_hours) VALUES ('P1',2,'T1','Same type and hours','internal',1)")
    case.conn.commit()
    facts = calibration(case)
    first, second = facts["rows"]
    assert first["sample_count"] == 5 and second["sample_count"] == 0
    assert second["suggested_unit_hours"] is None
    assert not facts["samples_by_template"][second["template_operation_ref"]]
    assert set(first["sample_refs"]) == {origin(case, op_id)["operation_ref"] for op_id in ids}


def test_delete_recreate_template_same_number_never_inherits_old_samples(lineage_case):
    case = lineage_case
    completed(case, [1, 2, 3, 4, 5])
    original_ref = calibration(case)["rows"][0]["template_operation_ref"]
    case.conn.execute("DELETE FROM PartOperations WHERE id=?", (case.template_id,))
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,unit_hours) VALUES ('P1',1,'T1','Turning','internal',1)")
    case.conn.commit()
    row = calibration(case)["rows"][0]
    assert row["template_operation_ref"] != original_ref
    assert row["sample_count"] == 0 and row["suggested_unit_hours"] is None


def test_rebuild_does_not_move_historical_reports_to_new_operation(lineage_case):
    case = lineage_case
    ids, _ = completed(case, [2, 2, 2, 2, 2])
    before = origin(case, ids[0])
    reports = all_rows(case.conn)["WorkbenchProductionReports"]
    new_id = create(case, "COPY-000", rebuild=True)
    assert origin(case, new_id)["operation_ref"] != before["operation_ref"]
    assert all_rows(case.conn)["WorkbenchProductionReports"] == reports
    assert calibration(case)["rows"][0]["sample_count"] == 4


def test_five_complete_identical_unbound_instances_are_not_samples(lineage_case):
    case = lineage_case
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=1 WHERE id=?", (case.op_id,))
    case.conn.commit()
    ids = [case.op_id]
    for index in range(4):
        code = "UNBOUND-" + str(index)
        case.batch_service.create(code, "P1", 10)
        with TransactionManager(case.conn).transaction():
            ids.append(case.lineage_writer.copy_instance(code, case.op_id))
    case.plan(2, ids)
    for op_id in ids:
        case.command("create", case.task(2, op_id), case.values(10, effective_processing_hours=2))
    facts = calibration(case)
    row = facts["rows"][0]
    assert row["candidate_count"] == 5 and row["eligible_sample_count"] == row["sample_count"] == 0
    assert row["suggested_unit_hours"] is None
    assert all(sample["template_operation_ref"] is None for sample in facts["samples_by_part"]["P1"])
