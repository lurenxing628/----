"""BE-only DTO replay: private fixture DB, real read routes, no shared asset build."""

import hashlib
import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path

from tests.workbench.plan_read_support import add_tasks
from tests.workbench.test_actual_gantt_support import BASE, connect, prepare, seed_report
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_preflight_support import BASE as PREFLIGHT_BASE
from tests.workbench.test_preflight_support import create_app, snapshot

ROOT = Path(__file__).resolve().parents[2]


def dto(response):
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def actual_scope(api):
    first = dto(api.client.get(BASE, query_string={"plan_ref": api.ref()}))["data"]["items"][0]["task"]
    return {"plan_ref": api.ref(), "source": "production", "resource_type": "machine", "resource_ref": first["machine_ref"],
            "range_start": "2026-09-08T22:00:00", "range_end": "2026-09-09T06:00:00",
            "plan_finish_date_from": "2026-09-09", "plan_finish_date_to": "2026-09-09", "batch_ids": ["CAT-B"]}


def transport(scope):
    return dict(scope, batch_ids=json.dumps(scope["batch_ids"]))


def seed_unbound_report(conn, task):
    report, request = secrets.token_hex(24), "be-only-" + secrets.token_hex(12)
    values = {"actual_start": "2026-09-08T22:00:00", "actual_end": "2026-09-08T23:00:00", "completed_quantity": 2,
              "effective_processing_hours": 1, "actual_machine_ref": None, "actual_operator_ref": None, "remark": "BE unbound fixture"}
    conn.execute("INSERT INTO WorkbenchCommandReceipts(request_key,receipt_ref,action,context_ref,input_hash,outcome_json) VALUES (?,?,?,?,?,?)",
                 (request, secrets.token_hex(16), "fixture", task["task_ref"], "0" * 64, "{}"))
    conn.execute("INSERT INTO WorkbenchProductionReports(report_ref,report_no,operation_ref,recorded_against_task_ref,recorded_against_plan_ref,source,recorded_at) VALUES (?,?,?,?,?,'manual',?)",
                 (report, "BG-00000001", task["operation_ref"], task["task_ref"], task["plan_ref"], "2026-09-09T08:00:00"))
    conn.execute("INSERT INTO WorkbenchProductionReportRevisions(revision_ref,report_ref,sequence,action,values_json,reason,local_operator,declared_operator,recorded_at,request_key) VALUES (?,?,1,'create',?,'','fixture','fixture',?,?)",
                 (secrets.token_hex(24), report, json.dumps(values), "2026-09-09T08:00:00", request))


def prepare_dtos(output):
    database = output / "be-only.sqlite"
    api = prepare(database, reports=False)
    scope = actual_scope(api)
    first = dto(api.client.get(BASE, query_string=transport(scope)))["data"]["items"][0]["task"]
    with api.db() as conn:
        seed_unbound_report(conn, first)
    before_actual = api.state()
    actual = dto(api.client.get(BASE, query_string=transport(scope)))
    export_scope = dict(scope, snapshot_ref=actual["meta"]["snapshot_ref"], format="csv", local_query="BG-00000001", late_filter="all", selected_task_ref=first["task_ref"])
    exported = api.client.get(BASE + "/export", query_string=transport(export_scope))
    assert exported.status_code == 200, exported.get_data(as_text=True)
    assert "BG-00000001" in exported.get_data(as_text=True)
    assert api.state() == before_actual
    (output / "actual.csv").write_bytes(exported.data)

    with api.db() as conn:
        add_tasks(conn, 22, start="2026-09-08 22:00:00", end="2026-09-09 06:00:00")
        conn.execute("UPDATE Schedule SET machine_id='PRIVATE-M1',operator_id='PRIVATE-O1' WHERE version=3")
    tasks = dto(api.client.get(BASE, query_string=transport(scope)))["data"]["items"]
    with api.db() as conn:
        for index, item in enumerate(tasks[1:4], 2):
            seed_report(conn, item["task"], f"BE-{index:03d}", quantity=2 if index == 2 else 10)
    conn = connect(database)
    try:
        batch = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key='CAT-B' AND active=1").fetchone()[0]
        preflight_input = {"batch_refs": [batch], "start_date": "2026-09-09", "end_date": "2026-09-09", "ready_check": True,
                           "missing_resource_policy": "auto_assign", "completed_policy": "preserve_actuals"}
        before = snapshot(conn)
        changes = conn.total_changes
        conn.execute("PRAGMA query_only=ON")
        preflight = dto(create_app(conn).test_client().post(PREFLIGHT_BASE, json=preflight_input))
        assert snapshot(conn) == before and conn.total_changes == changes
    finally:
        conn.close()
    counts = preflight["data"]["counts"]
    assert (counts["selected_tasks"], counts["blocked_tasks"], counts["protected_tasks"]) == (23, 19, 4), counts
    assert sum(row["code"] == "execution_review_required" for row in preflight["data"]["run_blocked_reasons"]) == 2
    packet = {"actual": actual, "scope": scope, "export_scope": export_scope, "preflight": preflight, "preflight_input": preflight_input,
              "csv_headers": {"contentType": exported.content_type, "disposition": exported.headers["Content-Disposition"]}}
    (output / "dto.json").write_text(json.dumps(packet, ensure_ascii=False), encoding="utf-8")
    (output / "dto-evidence.json").write_text(json.dumps({"source": "private SQLite real Flask read DTO replay", "database": str(database),
        "actual_reads_unchanged": True, "preflight_read_unchanged": True, "counts": counts, "main_database_accessed": False,
        "production_database_accessed": False, "real_http_server_started": False}, indent=2), encoding="utf-8")


def test_be_preflight_actual_surfaces():
    output = Path(tempfile.mkdtemp(prefix="aps-be-surfaces-"))
    print("BE_SURFACE_ARTIFACTS " + str(output), flush=True)
    manifest_path = ROOT / "static/workbench/asset-manifest.json"
    manifest_before = manifest_path.read_bytes()
    prepare_dtos(output)
    node, browser, modules = runtime_tools()
    run = subprocess.run([node, str(ROOT / "tests/workbench/be_surface_browser.cjs"), str(output)], cwd=str(ROOT),
                         env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser), capture_output=True, text=True, timeout=240)
    assert manifest_path.read_bytes() == manifest_before, "Shared build manifest changed during BE replay"
    assert run.returncode == 0, run.stdout + run.stderr + "\n" + str(output)
    report = json.loads((output / "be-surfaces.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.") and report["target"] == "chrome109"
    assert report["errors"] == [] and report["external"] == [] and len(report["variants"]) == 4
    assert all(row["passed"] for row in report["variants"])
    for source in report["sources"]:
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"]
