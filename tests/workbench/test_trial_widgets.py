"""CN slice: source-compiled Chrome109, real API and persisted trial row evidence."""

import ast
import hashlib
import json
import os
import subprocess
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.trial_export_widgets_support import public_snapshot, verify_download
from tests.workbench.trial_widgets_support import TRIAL_WIDGET_SOURCES, TrialWidgetServer


def test_short_task_fixture_uses_real_duration_and_adjacent_sql_rows(tmp_path):
    backend = TrialWidgetServer(tmp_path)
    client = backend.app.test_client()
    url = "/api/workbench/v1/trial/drafts/" + backend.refs["drafts"][2]
    response = client.get(url)
    assert response.status_code == 200
    data = response.get_json()["data"]
    tasks = sorted((row for row in data["tasks"] if row["batch_id"] == "B1"), key=lambda row: row["sequence"])
    assert [row["sequence"] for row in tasks] == [1, 2, 3]
    for previous, task in zip(tasks, tasks[1:]):
        assert previous["end"] == task["start"] and previous["task_ref"] in task["predecessor_refs"]
        assert task["hours"]["basis"] == "effective_processing_hours" and task["duration_reason"] is None
        assert task["hours"]["quantity"] == 3 and task["hours"]["setup_hours"] == 0
        assert task["hours"]["unit_hours"] * 3600 == pytest.approx(10)
        assert task["hours"]["total_hours"] * 3600 == pytest.approx(30)
        assert (datetime.fromisoformat(task["end"]) - datetime.fromisoformat(task["start"])).total_seconds() == 30
        with backend.connect() as conn:
            rows = conn.execute("""SELECT s.version,s.start_time,s.end_time,bo.setup_hours,bo.unit_hours,b.quantity
                FROM Schedule s JOIN BatchOperations bo ON bo.id=s.op_id JOIN Batches b ON b.batch_id=bo.batch_id
                WHERE bo.batch_id='B1' AND bo.seq=? ORDER BY s.version""", (task["sequence"],)).fetchall()
            assert [row[0] for row in rows] == list(range(1, 13))
            assert all((row[1], row[2]) == (task["start"], task["end"]) for row in rows)
            assert all((row[3] + row[4] * row[5]) * 3600 == pytest.approx(30) for row in rows)
        start = "2026-09-09T13:00:" + ("00" if task["sequence"] == 2 else "30")
        response = client.post(url + "/change", json={"request_key": "DF-short-duration-0000000" + str(task["sequence"]),
            "write_token": data["write_context"]["write_token"], "input": {"task_ref": task["task_ref"],
                "machine_ref": task["machine_ref"], "operator_ref": task["operator_ref"], "start": start}})
        assert response.status_code == 200, response.get_json()
        data = response.get_json()["data"]
        updated = next(row for row in data["tasks"] if row["task_ref"] == task["task_ref"])
        assert updated["start"] == start and updated["original"] == task["original"]
        assert (datetime.fromisoformat(updated["end"]) - datetime.fromisoformat(start)).total_seconds() == 30
        with backend.connect() as conn:
            stored = conn.execute("SELECT current_json FROM WorkbenchTrialRows WHERE task_ref=?", (task["task_ref"],)).fetchone()
            assert all(json.loads(stored[0])[key] == updated[key] for key in ("start", "end", "machine_ref", "operator_ref"))
    proof = backend.proof()
    assert proof["request_connection"] == "core.infrastructure.database.get_connection"
    assert proof["all_connections_isolated"] and all(row["legacy_rows_and_types_retained"] for row in proof["databases"])


@pytest.mark.parametrize("probe_scope", ("full", "exports"))
def test_trial_widgets_real_browser(probe_scope):
    node, browser, modules = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    output = Path(tempfile.mkdtemp(prefix="aps-cn-trial-widgets-"))
    print("TRIAL_WIDGET_ARTIFACTS " + probe_scope + " " + str(output), flush=True)
    backend = TrialWidgetServer(output)
    server = make_server("127.0.0.1", 0, backend.app, threaded=True)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        result = subprocess.run([node, str(root / "tests/workbench/trial_widgets_probe.cjs"), str(output),
                                 "http://127.0.0.1:" + str(server.server_port), json.dumps(TRIAL_WIDGET_SOURCES), probe_scope], cwd=str(root),
                                env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                                capture_output=True, text=True, timeout=480)
    finally:
        backend.release.set()
        server.shutdown()
        thread.join(timeout=15)
        server.server_close()
        proof = backend.proof()
        (output / "sqlite-proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "probe-output.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, (result.stdout + result.stderr)[-10000:] + "\n" + str(output)
    report = json.loads((output / "trial-widgets.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    expected_variants = 1 if probe_scope == "full" and os.environ.get("TRIAL_WIDGET_TARGET_ONLY") == "1" else 4
    assert len(report["variants"]) == expected_variants and all(r["passed"] for r in report["variants"])
    assert not report["errors"] and not report["external"] and not report["dialogs"]
    assert proof["all_connections_isolated"] and not proof["business_results_mocked"]
    assert proof["request_connection"] == "core.infrastructure.database.get_connection"
    assert all(row["legacy_rows_and_types_retained"] and row["receipt_task_counts_match_sqlite"] for row in proof["databases"])
    if expected_variants == 4:
        assert [(row["width"], row["height"], row["variant"]) for row in report["variants"]] == [
            (1920, 1080, "1920-light"), (1920, 1080, "1920-dark"),
            (1392, 924, "1392-light"), (1392, 924, "1392-dark"),
        ]
        if probe_scope == "full":
            assert [(row["variant"], row["name"]) for row in report["shortTasks"]] == [
                (row["variant"], name) for row in report["variants"] for name in ("gantt-original", "person-gantt", "batch-gantt")]
            for row in report["shortTasks"]:
                assert len(row["tasks"]) == len(row["boundaries"]) == 2
                assert all(0 < task["width"] < 5 and task["seconds"] == 30 and task["real_hit_and_click"] for task in row["tasks"])
                assert all(abs(pair["pixel_gap"]) < 0.05 and pair["separate_rows"] for pair in row["boundaries"])
        expected_downloads = [(row["variant"], entry, button) for row in report["variants"]
                              for entry in ("editing", "saved") for button in ("导出对比", "导出原始数据")]
        expected_downloads.extend(("1392-dark", "1000-tasks-last-page", button) for button in ("导出对比", "导出原始数据"))
        assert [(item["variant"], item["entry"], item["button"]) for item in report["downloads"]] == expected_downloads
        fields = []
        for item in report["downloads"]:
            if item["button"] == "导出对比":
                fields.append(verify_download(item))
                continue
            actual = json.loads(Path(item["path"]).read_text(encoding="utf-8"))
            expected = json.loads(Path(item["dto"]).read_text(encoding="utf-8"))
            assert actual == expected == public_snapshot(actual)
            assert "write_context" not in actual and item["no_write_context"]
            assert item["complete_task_count"] and actual["task_count"] == len(actual["tasks"]) == item["task_count"]
            assert item["task_count"] == (1000 if item["entry"] == "1000-tasks-last-page" else 5)
        assert len(fields) == 9 and all(item["columns"] == 22 and item["every_cell_matches_dto"] for item in fields)
        (output / "csv-field-proof.json").write_text(json.dumps(fields, ensure_ascii=False, indent=2), encoding="utf-8")
    style_names = json.loads((root / "scripts/workbench/build-order.json").read_text(encoding="utf-8"))["styles"]
    assert [Path(item["path"]).name for item in report["sources"]] == list(TRIAL_WIDGET_SOURCES) + style_names
    assert TRIAL_WIDGET_SOURCES.index("TrialContract.js") < TRIAL_WIDGET_SOURCES.index("TrialExport.js") < TRIAL_WIDGET_SOURCES.index("TrialControls.jsx")
    for item in report["sources"]:
        assert hashlib.sha256((root / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    for name in ("test_trial_widgets.py", "trial_widgets_support.py"):
        ast.parse((root / "tests/workbench" / name).read_text(encoding="utf-8"), feature_version=(3, 8))
    print(result.stdout, flush=True)
