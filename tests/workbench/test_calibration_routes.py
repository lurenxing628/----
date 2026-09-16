"""Real Flask transport plus real SQLite: production lineage is never fabricated."""

import csv
import io
import json
from datetime import timedelta

import openpyxl
import pytest

from tests.workbench.calibration_support import (
    BASE,
    assert_failure,
    assert_no_writes,
    complete_reports,
    ledger_fixture,
    query_only,
    scope_token,
)
from tests.workbench.calibration_support import calibration_api as api_fixture
from tests.workbench.calibration_support import calibration_case as case_fixture
from tests.workbench.execution_ledger_support import NOW


def test_real_complete_reports_still_require_persisted_template_lineage(calibration_api):
    case = calibration_api
    _, reports = complete_reports(case, [.1] * 5)
    query_only(case)
    payload = scope_token(case)
    row = payload["data"]["items"][0]
    assert row["sample_count"] == 0 and row["candidate_count"] == 5
    assert row["old_unit_hours"] == 1 and row["suggested_unit_hours"] is None
    assert row["status"] == "insufficient_data" and row["sample_refs"] == []
    assert row["template_operation_ref"] == case.template.operation_ref
    response = case.client.get(BASE + "/" + row["suggestion_ref"], query_string={"snapshot_ref": payload["meta"]["snapshot_ref"]})
    detail = response.get_json()["data"]
    assert detail["candidate_scope_basis"] == "template_ref_and_same_part_unbound"
    assert len(detail["samples"]) == 5
    sample = detail["samples"][0]
    assert sample["template_operation_ref"] is None and sample["template_revision"] is None
    assert sample["report_refs"][0] in {report["report_ref"] for report in reports}
    assert sample["reports"][0]["correction_history"]
    assert_no_writes(case)


def test_pagination_search_literal_and_scope_boundaries(calibration_api):
    case = calibration_api
    case.conn.executemany("INSERT INTO PartOperations(part_no,seq,op_type_name,source,unit_hours) VALUES ('P1',?,?,'internal',?)",
                         [(2, "Alpha", 0), (3, "BETA%_", None)])
    case.conn.commit()
    payload = scope_token(case, size=1, sort="operation_label")
    token = payload["meta"]["snapshot_ref"]
    assert payload["data"]["page"]["total"] == 3
    second = case.client.get(BASE, query_string={"size": 1, "sort": "operation_label", "page": 2, "snapshot_ref": token}).get_json()
    assert second["data"]["items"][0]["operation_label"] == "BETA%_"
    assert_failure(case.client.get(BASE, query_string={"size": 2, "sort": "operation_label", "snapshot_ref": token}), "snapshot_stale", 409)
    assert scope_token(case, query="%_")["data"]["page"]["total"] == 1
    assert scope_token(case, query="beta")["data"]["page"]["total"] == 1
    assert scope_token(case, deviation="over_20_percent")["data"]["page"]["total"] == 0
    assert scope_token(case, status="suggested")["data"]["page"]["total"] == 0
    assert scope_token(case, source="external")["data"]["page"]["total"] == 0
    search = scope_token(case, query="Alpha")
    assert_failure(case.client.get(BASE + "/" + case.template.operation_ref,
        query_string={"query": "Alpha", "snapshot_ref": search["meta"]["snapshot_ref"]}), "entity_not_found", 404)


@pytest.mark.parametrize("query", [{"page": "-1"}, {"size": 201}, {"page": "2"}, {"unknown": "x"},
    {"query": "x" * 201}, {"part_ref": "P1"}, {"source": "legacy"}, {"deviation": "20"},
    {"sort": "sql"}, {"snapshot_ref": "expired"}])
def test_invalid_arguments_not_ignored(calibration_api, query):
    response = calibration_api.client.get(BASE, query_string=query)
    assert response.status_code in (400, 409)
    assert response.get_json()["ok"] is False


def test_snapshot_required_and_no_adopt_alias(calibration_api):
    case = calibration_api
    assert_failure(case.client.get(BASE + "/export"), "snapshot_required", 400)
    assert_failure(case.client.get(BASE + "/" + case.template.operation_ref), "snapshot_required", 400)
    assert_failure(case.client.get(BASE + "?query=a&query=b"), "invalid_input", 400)
    for suffix in ("/adopt", "/lock", ""):
        response = case.client.post(BASE + "/" + case.template.operation_ref + suffix, json={"unit_hours": 1})
        assert response.status_code in (404, 405)


@pytest.mark.parametrize("change", ["template", "report", "instance", "identity"])
def test_changed_sources_explicitly_stale(calibration_api, change):
    case = calibration_api
    _, reports = complete_reports(case, [.1])
    token = scope_token(case)["meta"]["snapshot_ref"]
    if change == "template":
        case.conn.execute("UPDATE PartOperations SET unit_hours=0 WHERE part_no='P1'")
    elif change == "report":
        case.command("correct", reports[0]["report_ref"], {"original_revision_ref": reports[0]["revision_ref"],
                     "reason": "confirmed hours", "effective_processing_hours": 0})
    elif change == "instance":
        case.conn.execute("UPDATE BatchOperations SET unit_hours=999 WHERE id=?", (case.op_id,))
    else:
        case.conn.execute("DELETE FROM PartOperations WHERE part_no='P1'")
        case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,unit_hours) VALUES ('P1',1,'Turning',1)")
    case.conn.commit()
    assert_failure(case.client.get(BASE, query_string={"snapshot_ref": token}), "snapshot_stale", 409)


@pytest.mark.parametrize("format_name", ["csv", "xlsx"])
def test_export_full_scope_snapshot_injection_and_unknown(calibration_api, format_name):
    case = calibration_api
    case.conn.execute("UPDATE Parts SET part_name=' =1+1' WHERE part_no='P1'")
    case.conn.execute("UPDATE PartOperations SET op_type_name='@SUM(1,2)',unit_hours=0")
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,unit_hours) VALUES ('P1',2,'+1+1',NULL)")
    case.conn.commit()
    query_only(case)
    payload = scope_token(case, size=1)
    token = payload["meta"]["snapshot_ref"]
    response = case.client.get(BASE + "/export", query_string={"size": 1, "snapshot_ref": token, "format": format_name})
    assert response.status_code == 200, response.get_json()
    assert response.headers["X-Workbench-Snapshot"] == token
    assert response.headers["X-Workbench-Row-Count"] == "2"
    if format_name == "csv":
        rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))
    else:
        workbook = openpyxl.load_workbook(io.BytesIO(response.data), data_only=False)
        assert all(cell.data_type != "f" for sheet in workbook for row in sheet for cell in row)
        rows = list(workbook["校准建议"].values)
        metadata = dict(workbook["范围与计算方式"].values)
        assert metadata["采用与锁定"] == "请在工时校准页面预检并采用；采用后更新并锁定模板定额，已有批次不随之更改。"
        workbook.close()
    assert len(rows) == 3
    assert all(row[1].startswith("'") and row[3].startswith("'") for row in rows[1:])
    assert {str(row[7]) for row in rows[1:]} == {"0" if format_name == "xlsx" else "0.0", "暂无数据"}
    assert all(row[-2].lstrip("'") == token and json.loads(row[-1])["size"] == 1 for row in rows[1:])
    assert_no_writes(case)


def test_read_requires_preflight_instead_of_claiming_adoption_unavailable(calibration_api):
    data = scope_token(calibration_api)["data"]
    expected = {"code": "adoption_preflight_required", "message": "请先预检所选模板；通过后可采用建议定额并锁定。"}
    assert data["blocked_reasons"] == [expected]
    row = data["items"][0]
    assert expected in row["blocked_reasons"]
    assert row["write_context"]["blocked_reasons"] == row["blocked_reasons"]
    assert data["capabilities"]["adopt"] is False and row["capabilities"]["adopt"] is False
    assert row["write_context"]["write_token"] is None


def test_repeated_snapshot_keeps_generated_at_and_data(calibration_api):
    case = calibration_api
    first = scope_token(case)
    second = scope_token(case, snapshot_ref=first["meta"]["snapshot_ref"])
    assert first["data"] == second["data"]
    row = second["data"]["items"][0]
    assert row["as_of"] == row["generated_at"] == first["meta"]["as_of"]


@pytest.mark.parametrize("text", ["=1+1", "+1+1", "-1+1", "@SUM(1)", "\t=1+1", "\r=1+1", "\n=1+1", "  =1+1"])
def test_csv_formula_prefixes_are_text(calibration_api, text):
    case = calibration_api
    case.conn.execute("UPDATE Parts SET part_name=?", (text,))
    case.conn.commit()
    token = scope_token(case)["meta"]["snapshot_ref"]
    response = case.client.get(BASE + "/export", query_string={"snapshot_ref": token})
    rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))
    assert rows[1][1] == "'" + text


def test_export_rejects_empty_format_and_changed_scope(calibration_api):
    case = calibration_api
    first = scope_token(case)
    token = first["meta"]["snapshot_ref"]
    assert_failure(case.client.get(BASE + "/export", query_string={"snapshot_ref": token, "format": "xls"}), "invalid_input", 400)
    assert_failure(case.client.get(BASE + "/export", query_string={"snapshot_ref": token, "query": "none"}), "snapshot_stale", 409)
    empty = scope_token(case, query="none")
    assert_failure(case.client.get(BASE + "/export", query_string={"snapshot_ref": empty["meta"]["snapshot_ref"], "query": "none"}), "empty_export", 422)


def test_new_actual_after_snapshot_returns_stale_not_false_corruption(calibration_api):
    case = calibration_api
    token = scope_token(case)["meta"]["snapshot_ref"]
    case.writer.ledger.clock = lambda: NOW + timedelta(hours=2)
    case.command("create", case.task(1, case.op_id), case.values(10,
        actual_start=NOW.isoformat(), actual_end=(NOW + timedelta(hours=1)).isoformat(), effective_processing_hours=1))
    assert_failure(case.client.get(BASE + "/export", query_string={"snapshot_ref": token}), "snapshot_stale", 409)


def test_cross_plan_same_execution_is_one_candidate_with_original_report_ref(calibration_api):
    case = calibration_api
    _, reports = complete_reports(case, [.1])
    original_plan = case.ledger.get_report(reports[0]["report_ref"]).recorded_against_plan_ref
    case.plan(3, [case.op_id])
    payload = scope_token(case)
    assert payload["data"]["items"][0]["candidate_count"] == 1
    detail = case.client.get(BASE + "/" + case.template.operation_ref,
        query_string={"snapshot_ref": payload["meta"]["snapshot_ref"]}).get_json()["data"]
    assert detail["samples"][0]["reports"][0]["recorded_against_plan_ref"] == original_plan


def test_initial_clock_captured_after_database_snapshot_starts(calibration_api, monkeypatch):
    case = calibration_api
    case.command("create", case.task(1, case.op_id), case.values(10, effective_processing_hours=.5,
        actual_start=(NOW - timedelta(hours=2)).isoformat(), actual_end=(NOW - timedelta(hours=1)).isoformat()))
    clocks = iter((NOW - timedelta(hours=3), NOW))
    monkeypatch.setattr("web.routes.workbench.calibration._as_of", lambda token: next(clocks))
    payload = scope_token(case)
    assert payload["meta"]["as_of"] == NOW.isoformat()
    assert payload["data"]["items"][0]["generated_at"] == NOW.isoformat()
