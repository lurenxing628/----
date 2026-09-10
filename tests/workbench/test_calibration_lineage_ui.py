"""Strict template grouping from CE writes through the public API and Chrome 109."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.workbench.calibration_lineage_ui_support import calibration_case as _calibration_case
from tests.workbench.calibration_lineage_ui_support import prepare, serve, verify_export
from tests.workbench.test_calibration_support import (
    BASE,
    assert_failure,
    assert_no_writes,
    query_only,
    scope_token,
)
from tests.workbench.test_calibration_support import calibration_api as _calibration_api
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_template_lineage_support import completed, origin
from tests.workbench.test_template_lineage_support import ledger_fixture as _ledger_fixture
from tests.workbench.test_template_lineage_support import lineage_case as _lineage_case

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def detail(case, payload, ref=None, **scope):
    ref = ref or payload["data"]["items"][0]["suggestion_ref"]
    response = case.client.get(BASE + "/" + ref, query_string={**scope, "snapshot_ref": payload["meta"]["snapshot_ref"]})
    assert response.status_code == 200, response.get_json()
    return response.get_json()


@pytest.mark.parametrize("hours,expected", [([1, 2, 3, 4], None), ([0] * 5, 0), ([0, 1, 3, 4, 100], 3), (list(range(1, 26)), 15.5)])
def test_ce_real_samples_reach_api_with_backend_median(calibration_api, hours, expected):
    case = calibration_api
    ids, reports = completed(case, hours)
    query_only(case)
    payload = scope_token(case)
    result = detail(case, payload)["data"]
    row = result["suggestion"]
    assert result["lineage_available"] is True
    assert result["candidate_scope_basis"] == "template_ref_and_same_part_unbound"
    assert row["suggested_unit_hours"] == expected and row["sample_count"] == min(20, len(ids))
    assert row["capabilities"]["adopt"] is row["capabilities"]["lock"] is False
    assert {sample["sample_ref"] for sample in result["samples"] if sample["template_operation_ref"] is not None} == {
        origin(case, op_id)["operation_ref"] for op_id in ids}
    selected = [sample for sample in result["samples"] if sample["selected"]]
    assert {sample["sample_ref"] for sample in selected} == set(row["sample_refs"])
    assert {ref for sample in result["samples"] for ref in sample["report_refs"]} == {report["report_ref"] for report in reports}
    assert len([sample for sample in result["samples"] if sample["template_operation_ref"] is None]) == 1
    assert_no_writes(case)


def test_no_missing_source_warning_when_all_candidates_are_bound(calibration_api):
    case = calibration_api
    completed(case, [1, 2, 3, 4, 5])
    case.conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P2','Other part')")
    case.conn.execute("UPDATE Batches SET part_no='P2' WHERE batch_id='B1'")
    case.conn.commit()
    query_only(case)
    payload = scope_token(case)
    data = detail(case, payload)["data"]
    assert data["lineage_available"] is True and data["source_constraints"] == []
    assert data["suggestion"]["candidate_count"] == data["suggestion"]["sample_count"] == 5
    assert_no_writes(case)


def test_mixed_sources_and_exclusions_stay_separate(calibration_api):
    case = calibration_api
    config = prepare(case)
    query_only(case)
    payload = scope_token(case, query="Turning-01")
    data = detail(case, payload, query="Turning-01")["data"]
    row, samples = data["suggestion"], data["samples"]
    assert row["suggested_unit_hours"] == 3 and row["sample_count"] == 5
    assert row["candidate_count"] == 14 and row["excluded_count"] == 9
    assert set(row["sample_refs"]) == set(config["selected_refs"])
    assert not set(config["other_refs"] + config["recent_refs"]) & {sample["sample_ref"] for sample in samples}
    excluded = [sample for sample in samples if sample["template_operation_ref"] and not sample["selected"]]
    assert {sample["sample_ref"] for sample in excluded} == set(config["excluded_refs"])
    codes = {reason["code"] for sample in excluded for reason in sample["exclusion_reasons"]}
    assert {"template_revision_mismatch", "operation_not_complete", "processing_hours_unknown", "template_lineage_withdrawn", "template_instance_modified"} <= codes
    assert_no_writes(case)


def test_real_gaps_and_report_corrections_are_preserved(calibration_api):
    case = calibration_api
    config = prepare(case)
    query_only(case)
    payload = scope_token(case, query="Turning-01")
    samples = detail(case, payload, query="Turning-01")["data"]["samples"]
    unknown = next(sample for sample in samples if sample["sample_ref"] == config["unknown_ref"])
    assert unknown["template_operation_ref"] is None and unknown["selected"] is unknown["eligible"] is False
    assert unknown["unknown_record_count"] == 1 and unknown["effective_processing_hours"] is None and unknown["data_gaps"]
    correction = next(sample for sample in samples if sample["sample_ref"] == config["correction_sample_ref"])["reports"][0]
    assert correction["report_ref"] == config["report_ref"] and len(correction["correction_history"]) == 2
    assert correction["correction_history"][-1]["before"]["effective_processing_hours"] == 900
    assert correction["correction_history"][-1]["after"]["effective_processing_hours"] == 1000
    assert_no_writes(case)


def test_recreated_template_ref_does_not_inherit_or_relabel_history(calibration_api):
    case = calibration_api
    completed(case, [1, 2, 3, 4, 5])
    payload = scope_token(case)
    old_ref = payload["data"]["items"][0]["template_operation_ref"]
    case.conn.execute("DELETE FROM PartOperations WHERE id=?", (case.template_id,))
    case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source,unit_hours) VALUES ('P1',1,'Turning','internal',1)")
    case.conn.commit()
    assert_failure(case.client.get(BASE + "/" + old_ref, query_string={"snapshot_ref": payload["meta"]["snapshot_ref"]}), "snapshot_stale", 409)
    fresh = scope_token(case)
    data = detail(case, fresh)["data"]
    assert data["suggestion"]["template_operation_ref"] != old_ref
    assert data["suggestion"]["suggested_unit_hours"] is None and data["suggestion"]["sample_count"] == 0
    assert len(data["samples"]) == 1 and data["samples"][0]["template_operation_ref"] is None
    assert_failure(case.client.get(BASE + "/" + old_ref, query_string={"snapshot_ref": fresh["meta"]["snapshot_ref"]}), "entity_not_found", 404)


@pytest.mark.parametrize("scope", [{"source": "internal", "size": 1, "sort": "suggested_unit_hours", "direction": "desc"},
    {"status": "suggested", "size": 1}, {"deviation": "over_20_percent", "size": 1}, {"query": "Turning-02"}, {"query": "Turning-03"}])
def test_all_filtered_json_csv_xlsx_match(calibration_api, scope):
    case = calibration_api
    prepare(case)
    query_only(case)
    payload = scope_token(case, **scope)
    rows = []
    for page in range(1, payload["data"]["page"]["total_pages"] + 1):
        rows.extend(scope_token(case, **scope, page=page, snapshot_ref=payload["meta"]["snapshot_ref"])["data"]["items"])
    for format_name in ("csv", "xlsx"):
        response = case.client.get(BASE + "/export", query_string={**scope, "page": payload["data"]["page"]["total_pages"],
            "snapshot_ref": payload["meta"]["snapshot_ref"], "format": format_name})
        assert response.status_code == 200, response.get_json()
        assert int(response.headers["X-Workbench-Row-Count"]) == len(rows) == payload["data"]["summary"]["total"]
        assert response.headers["X-Workbench-Snapshot"] == payload["meta"]["snapshot_ref"]
        verify_export(response.data, format_name, rows, payload["data"]["scope"], payload["meta"]["snapshot_ref"], payload["meta"]["as_of"])
    assert_no_writes(case)


def test_chrome109_real_lineage_ui(calibration_api, tmp_path):
    config = prepare(calibration_api)
    output = Path(os.environ.get("CALIBRATION_LINEAGE_UI_OUTPUT", str(tmp_path / "browser-evidence"))).resolve()
    assert ROOT not in output.parents and output != ROOT
    output.mkdir(parents=True, exist_ok=True)
    node, browser, modules = runtime_tools()
    print("CALIBRATION_LINEAGE_UI_ARTIFACTS " + str(output), flush=True)
    with serve(calibration_api, output, config) as settings:
        result = subprocess.run([node, str(HERE / "calibration_lineage_ui_probe.cjs"), str(output)],
            input=json.dumps(settings), text=True, capture_output=True, timeout=300,
            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser))
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)
    report = json.loads((output / "calibration-lineage-ui.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.") and report["compile_global_build"] is False
    assert len(report["cases"]) == 4 and len(report["downloads"]) == 8
    assert report["errors"] == report["external"] == [] and report["contract_rejections"] >= 8
    assert report["recreated_ref_not_retargeted"]
    for source in report["sources"]:
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"]
    for download in report["downloads"]:
        content = Path(download["path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == download["sha256"]
        assert download["page"] == 2 and len(download["expected_rows"]) == 22
        verify_export(content, download["format"], download["expected_rows"], download["scope"], download["snapshot"], download["as_of"])
    server = json.loads((output / "calibration-lineage-server.json").read_text(encoding="utf-8"))
    assert server["violations"] == [] and server["server_stopped"] and len(server["mutations"]) == 1
    assert all(row["method"] == "GET" and row["unchanged"] and row["writes"] == [] for row in server["journal"])
    print("CALIBRATION_LINEAGE_UI_VERIFIED " + json.dumps({"cases": 4, "downloads": 8, "output": str(output)}), flush=True)
