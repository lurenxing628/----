"""True shipment lifecycle, retained facts, grouping and date contracts."""

import json
from datetime import date

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.outsourcing_support import original_rows
from tests.workbench.outsourcing_support import outsourcing_case as _outsourcing_case  # noqa: F401


def test_preview_readonly_then_send_return_correct_reconfirm(outsourcing_case):
    case = outsourcing_case
    source = original_rows(case.conn)
    before = case.conn.total_changes
    preview = case.preview(case.payload())
    assert case.conn.total_changes == before
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts").fetchone()[0] == 0
    first = case.confirm(preview)
    ref = first["data"]["outsourcing_ref"]
    assert first["data"]["local_operator"] == "local-operator"
    assert first["data"]["declared_operator"] == "Shipping clerk"
    assert case.detail(ref)["overdue"] is True
    returned = case.preview({"outsourcing_ref": ref, "returned": "2026-09-10T10:00:00", "confirmedState": "returned",
                             "declared_operator": "Receiving clerk", "reason": "Checked receipt sheet 02"})
    second = case.confirm(returned)
    assert second["data"]["sent"] == preview["after"]["sent"]
    assert second["data"]["execution"]["automatically_reported"] is False
    correction = case.preview({"outsourcing_ref": ref, "returned": "2026-09-10T10:30:00",
                               "declared_operator": "Supervisor", "reason": "Corrected unloading time"})
    case.confirm(correction)
    case.confirm(case.preview({"outsourcing_ref": ref, "declared_operator": "Supervisor", "reason": "Rechecked receipt"}))
    with case.reader.read_snapshot():
        result = case.reader.history(ref)
    facts = result["history"]["items"]
    assert len(facts) == 4
    assert facts[0]["before"] == facts[0]["after"]
    assert facts[1]["before"]["returned"] == "2026-09-10T10:00:00"
    assert facts[2]["before"]["returned"] is None
    assert facts[3]["before"] is None
    assert result["item"]["overdue"] is False
    assert original_rows(case.conn) == source
    assert case.conn.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("patch", [
    {"sent": None}, {"planned": ""}, {"sent": "2026-02-30T00:00:00"}, {"sent": True},
    {"sent": "2026-09-07T09:00"}, {"sent": "2026-09-07T09:00:00Z"},
    {"planned": "2026-09-06T09:00:00"}, {"returned": "2026-09-06T09:00:00", "confirmedState": "returned"},
    {"sent": "2026-09-11T09:00:00", "planned": "2026-09-12T09:00:00"},
    {"returned": "2026-09-11T00:00:00", "confirmedState": "returned"},
    {"returned": "2026-09-10T09:00:00"}, {"confirmedState": "returned"},
    {"confirmedState": "unknown"}, {"confirmedState": {}}, {"returned": ""},
    {"declared_operator": " "}, {"reason": ""}, {"local_operator": "client-forged"},
])
def test_invalid_facts_never_write(outsourcing_case, patch):
    case = outsourcing_case
    before = case.conn.total_changes
    with pytest.raises(WorkbenchCommandRejected):
        case.preview(case.payload(**patch))
    assert case.conn.total_changes == before


@pytest.mark.parametrize("missing", ["sent", "planned", "returned", "confirmedState", "declared_operator", "reason"])
def test_create_missing_fields_rejected(outsourcing_case, missing):
    payload = outsourcing_case.payload()
    del payload[missing]
    with pytest.raises(WorkbenchCommandRejected):
        outsourcing_case.preview(payload)


def test_explicit_merged_mapping_not_template_cycle_inference(outsourcing_case):
    case = outsourcing_case
    case.conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
                     "VALUES ('XG1','XP1',1,3,'merged',999,'XS1')")
    case.conn.commit()
    preview = case.preview(case.payload(merged=True))
    result = case.confirm(preview)
    ref = result["data"]["outsourcing_ref"]
    item = case.detail(ref)
    assert item["target"]["grouping_basis"] == "explicit_receipt_membership"
    assert len(item["target"]["operation_refs"]) == 2
    assert item["planned"] == "2026-09-09T12:00:00"
    with pytest.raises(WorkbenchCommandRejected, match="已有外协登记"):
        case.preview(case.payload())
    with case.reader.read_snapshot():
        targets = case.reader.targets()["items"]
    assert sum(item["can_register"] for item in targets) == 1
    assert sum(item["outsourcing_ref"] == ref for item in targets) == 2


@pytest.mark.parametrize("change", ["mixed_batch", "different_supplier", "internal", "different_piece", "duplicate", "single_many"])
def test_merged_members_invalid(outsourcing_case, change):
    case = outsourcing_case
    payload = case.payload(merged=True)
    if change == "mixed_batch":
        case.conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('XB2','XP1',10)")
        case.conn.execute("UPDATE BatchOperations SET batch_id='XB2' WHERE op_code='XO2'")
    elif change == "different_supplier":
        case.conn.execute("UPDATE BatchOperations SET supplier_id=NULL WHERE op_code='XO2'")
    elif change == "internal":
        case.conn.execute("UPDATE BatchOperations SET source='internal' WHERE op_code='XO2'")
    elif change == "different_piece":
        case.conn.execute("UPDATE BatchOperations SET piece_id='piece2' WHERE op_code='XO2'")
    elif change == "duplicate":
        payload["target"]["operation_refs"][1] = payload["target"]["operation_refs"][0]
    else:
        payload["target"]["kind"] = "single"
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected):
        case.preview(payload)


@pytest.mark.parametrize("due", [date(2026, 9, 11), None, b"invalid-date\x00\xff", 42])
def test_real_connection_raw_date_blob_integer_preserved(outsourcing_case, due):
    case = outsourcing_case
    assert case.conn.execute('SELECT ? AS "sample [date]"', ("2026-09-11",)).fetchone()[0] == date(2026, 9, 11)
    case.conn.execute("UPDATE Batches SET due_date=?,remark=?", (due, b"\x00raw\xff"))
    case.conn.commit()
    source = original_rows(case.conn)
    result = case.confirm(case.preview(case.payload()))
    facts = json.loads(case.conn.execute("SELECT source_facts_json FROM WorkbenchOutsourcingFacts").fetchone()[0])
    assert facts["batch"]["row"]["remark"] == {"storage_type": "blob", "hex": b"\x00raw\xff".hex()}
    if type(due) is date:
        assert type(case.conn.execute("SELECT due_date FROM Batches").fetchone()[0]) is date
        assert facts["batch"]["row"]["due_date"] == due.isoformat()
    assert result["data"]["sent"] == "2026-09-07T09:00:00"
    assert original_rows(case.conn) == source
