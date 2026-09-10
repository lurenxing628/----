"""Damaged sources fail explicitly; sparse facts remain honest data gaps."""

import json

import pytest

from tests.workbench.calibration_support import (
    BASE,
    assert_failure,
    complete_reports,
    inject_revision_damage,
    ledger_fixture,
    scope_token,
)
from tests.workbench.calibration_support import calibration_api as api_fixture
from tests.workbench.calibration_support import calibration_case as case_fixture


@pytest.mark.parametrize("damage", ["json", "missing_revision", "chain", "hours", "quantity", "extra_field", "time"])
def test_broken_report_is_not_insufficient_data(calibration_api, damage):
    case = calibration_api
    _, reports = complete_reports(case, [.1])
    revision = reports[0]["revision_ref"]
    with inject_revision_damage(case.conn):
        if damage == "json":
            case.conn.execute("UPDATE WorkbenchProductionReportRevisions SET values_json='{' WHERE revision_ref=?", (revision,))
        elif damage == "missing_revision":
            case.conn.execute("DELETE FROM WorkbenchProductionReportRevisions WHERE revision_ref=?", (revision,))
        elif damage == "chain":
            case.conn.execute("UPDATE WorkbenchProductionReportRevisions SET sequence=2 WHERE revision_ref=?", (revision,))
        else:
            values = json.loads(case.conn.execute("SELECT values_json FROM WorkbenchProductionReportRevisions WHERE revision_ref=?", (revision,)).fetchone()[0])
            key, value = {"hours": ("effective_processing_hours", "unknown"), "quantity": ("completed_quantity", True),
                          "extra_field": ("guessed_template_ref", "x"), "time": ("actual_end", "damaged")}[damage]
            values[key] = value
            case.conn.execute("UPDATE WorkbenchProductionReportRevisions SET values_json=? WHERE revision_ref=?", (json.dumps(values), revision))
    case.conn.commit()
    assert_failure(case.client.get(BASE), "storage_failure", 500)


@pytest.mark.parametrize("damage", ["template_identity", "instance_identity", "template_hours", "template_trigger", "ledger_table"])
def test_missing_or_invalid_sources_never_repaired(calibration_api, damage):
    case = calibration_api
    if damage == "template_identity":
        case.conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind='template_operation'")
    elif damage == "instance_identity":
        case.conn.execute("UPDATE WorkbenchPlanSourceRefs SET active=0 WHERE kind='operation'")
    elif damage == "template_hours":
        case.conn.execute("UPDATE PartOperations SET unit_hours=-1")
    elif damage == "template_trigger":
        case.conn.execute("DROP TRIGGER wb_ref_template_operation_update")
    else:
        case.conn.execute("DROP TABLE WorkbenchProductionReportRevisions")
    case.conn.commit()
    changes = case.conn.total_changes
    response = case.client.get(BASE)
    assert response.status_code in (409, 500)
    assert response.get_json()["ok"] is False
    assert case.conn.total_changes == changes


def test_legacy_source_change_is_explicit_failure(calibration_api):
    case = calibration_api
    case.event(case.op_id, "start")
    case.event(case.op_id, "finish", quantity=10)
    assert scope_token(case)["data"]["items"][0]["sample_count"] == 0
    case.conn.execute("UPDATE OperationExecutionEvents SET remark='changed after archive'")
    case.conn.commit()
    assert_failure(case.client.get(BASE), "calibration_source_changed", 409)


def test_unknown_hours_correction_and_retired_template_identity(calibration_api):
    case = calibration_api
    _, reports = complete_reports(case, [.1])
    old = scope_token(case)
    report = reports[0]
    case.command("correct", report["report_ref"], {"original_revision_ref": report["revision_ref"],
                                                 "effective_processing_hours": None, "reason": "unknown after review"})
    assert_failure(case.client.get(BASE + "/export", query_string={"snapshot_ref": old["meta"]["snapshot_ref"]}), "snapshot_stale", 409)
    fresh = scope_token(case)
    detail = case.client.get(BASE + "/" + case.template.operation_ref,
        query_string={"snapshot_ref": fresh["meta"]["snapshot_ref"]}).get_json()["data"]
    sample = detail["samples"][0]
    assert sample["effective_processing_hours"] is None
    assert len(sample["reports"][0]["correction_history"]) == 2
    assert "processing_hours_unknown" in {reason["code"] for reason in sample["exclusion_reasons"]}
