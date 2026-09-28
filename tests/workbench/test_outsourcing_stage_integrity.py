"""Shipment membership follows real route stages, with old receipt facts retained."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.outsourcing.source import WorkbenchOutsourcingSourceService
from tests.workbench.outsourcing_support import ROOT, api
from tests.workbench.outsourcing_support import outsourcing_case as _outsourcing_case  # noqa: F401
from tests.workbench.test_outsourcing_api import confirm, preview


def spaced_route(case):
    case.conn.execute("UPDATE BatchOperations SET seq=seq*10")
    case.conn.commit()


def separated_payload(case):
    payload = case.payload(merged=True)
    payload["target"]["operation_refs"] = [case.operation_ref("XO1"), case.operation_ref("XO3")]
    return payload


@pytest.mark.parametrize("middle_source", ["internal", "external"])
def test_new_shipment_cannot_cross_or_omit_middle_operation(outsourcing_case, monkeypatch, middle_source):
    case = outsourcing_case
    spaced_route(case)
    case.conn.execute("UPDATE BatchOperations SET source=? WHERE op_code='XO2'", (middle_source,))
    case.conn.commit()
    response = api(case, monkeypatch).post(ROOT + "/receipts/preview", json={"input": separated_payload(case)})
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "constraint_conflict"
    assert "连续工序" in response.get_json()["error"]["message"]
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts").fetchone()[0] == 0


def test_real_adjacent_operations_need_not_have_consecutive_sequence_numbers(outsourcing_case, monkeypatch):
    case = outsourcing_case
    spaced_route(case)
    client = api(case, monkeypatch)
    result = confirm(client, preview(client, case.payload(merged=True)))
    assert result.status_code == 200, result.get_json()
    assert result.get_json()["result"] == "committed"


def test_shared_internal_operation_separates_piece_shipments(outsourcing_case):
    case = outsourcing_case
    spaced_route(case)
    case.conn.execute("UPDATE BatchOperations SET piece_id='A' WHERE op_code IN ('XO1','XO3')")
    case.conn.execute("UPDATE BatchOperations SET source='internal' WHERE op_code='XO2'")
    case.conn.commit()
    with pytest.raises(WorkbenchCommandRejected, match="连续工序"):
        case.preview(separated_payload(case))


def test_middle_operation_inserted_after_preview_cannot_slip_into_confirm(outsourcing_case, monkeypatch):
    case = outsourcing_case
    spaced_route(case)
    client = api(case, monkeypatch)
    draft = preview(client, case.payload(merged=True))
    case.conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source) "
                      "VALUES ('XMID','XB1',15,'XT1','Internal middle','internal')")
    case.conn.commit()
    result = confirm(client, draft)
    assert result.status_code == 409
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts").fetchone()[0] == 0


def test_preexisting_noncontiguous_receipt_stays_readable_and_can_record_return(outsourcing_case, monkeypatch):
    case = outsourcing_case
    spaced_route(case)
    case.conn.execute("UPDATE BatchOperations SET source='internal' WHERE op_code='XO2'")
    case.conn.commit()
    # Build the exact membership an older version allowed; no rewriting of retained facts.
    with monkeypatch.context() as old:
        old.setattr(WorkbenchOutsourcingSourceService, "require_contiguous", lambda self, operations: None)
        receipt = case.confirm(case.preview(separated_payload(case)))
    ref = receipt["data"]["outsourcing_ref"]
    original_members = case.detail(ref)["target"]["operation_refs"]
    assert case.detail(ref)["can_preview"]
    returned = case.confirm(case.preview({"outsourcing_ref": ref, "returned": "2026-09-10T10:00:00",
        "confirmedState": "returned", "declared_operator": "Receiving clerk", "reason": "Verified original return"}))
    assert returned["result"] == "committed"
    detail = case.detail(ref)
    assert detail["target"]["operation_refs"] == original_members
    assert detail["history_count"] == 2 and detail["confirmedState"] == "returned"
