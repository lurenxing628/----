"""EN: real SQLite/EA adoption and unmodified PlanGantt DenseRow in Chrome 109."""

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from tests.workbench.ea_zero_duration_support import adopt
from tests.workbench.point_frontend_support import app_for, serve
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_run_candidate_support import compute
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401

HERE = Path(__file__).resolve().parent
COUNT = 144


def invoke(script, value, output, timeout=180):
    node, browser, modules = runtime_tools()
    result = subprocess.run(
        [node, str(HERE / script)], input=json.dumps(value), text=True,
        capture_output=True, timeout=timeout,
        env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
    )
    (output / (script + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr + "\n" + str(output)


def digest_sql(conn):
    return hashlib.sha256("\n".join(conn.iterdump()).encode("utf-8")).hexdigest()


def seed(case):
    case.conn.execute("UPDATE Batches SET quantity=1 WHERE batch_id='B1'")
    case.conn.execute("UPDATE BatchOperations SET setup_hours=0,unit_hours=0,op_type_name='Dense point 000'")
    for index in range(COUNT):
        if index:
            case.operation(seq=2 * index + 1, setup_hours=0, unit_hours=0,
                           op_type_name=f"Dense point {index:03d}")
        case.operation(seq=2 * index + 2, setup_hours=0, unit_hours=1 / 60,
                       op_type_name=f"Normal interval {index:03d}")
    case.conn.commit()
    run, candidates = compute(case)
    assert candidates, "Actual scheduler must persist a candidate"
    official = adopt(case, candidates[0], key="en-dense-point-adopt-01")
    rows = case.conn.execute("SELECT start_time,end_time FROM Schedule ORDER BY start_time,end_time").fetchall()
    assert len(rows) == COUNT * 2
    assert sum(row[0] == row[1] for row in rows) == COUNT
    seconds = sum((datetime.fromisoformat(row[1]) - datetime.fromisoformat(row[0])).total_seconds() for row in rows)
    assert seconds == COUNT * 60, "Only normal intervals consume scheduling time"
    return {"run_ref": run, "candidate_ref": candidates[0], "plan_ref": official["plan_ref"]}


def test_real_point_dense_canvas_chromium109(trial_case, tmp_path):
    identity = seed(trial_case)
    output = tmp_path / "en-point-dense-canvas"
    output.mkdir()
    # EE builder/host are read-only dependencies; all compiled output is EN-private.
    invoke("point_browser_build.cjs", {"output": str(output)}, output)
    app = app_for(trial_case, output)
    before = digest_sql(trial_case.conn)
    client = app.test_client()
    paths = {"candidate": "/api/workbench/v1/scheduling/candidates/" + identity["candidate_ref"] + "/workspace",
             "plan": "/api/workbench/v1/plans/" + identity["plan_ref"] + "/workspace"}
    fixtures = {}
    for kind, url in paths.items():
        response = client.get(url)
        assert response.status_code == 200, response.get_data(as_text=True)
        payload = response.get_json()
        assert payload["ok"] and payload["meta"]["source"] == "production"
        tasks = payload["data"]["tasks"]
        points = [row for row in tasks if row.get("event_kind") == "point"]
        normal = [row for row in tasks if row.get("event_kind") != "point"]
        assert len(points) == len(normal) == COUNT
        assert all(row["start"] == row["end"] and row["duration_seconds"] == 0 and
                   row["occupies_resources"] is False for row in points)
        assert {row["start"] for row in points} == {row["start"] for row in normal}
        assert all((datetime.fromisoformat(row["end"]) - datetime.fromisoformat(row["start"])).total_seconds() == 60 for row in normal)
        fixtures[kind] = payload
    for row in fixtures["plan"]["data"]["projections"]["occupancy"]["resources"]:
        assert row["occupied_hours"] == pytest.approx(COUNT / 60)
        assert row["arranged_hours"] == pytest.approx(COUNT / 60)
        assert row["overlap_hours"] == 0 and not row["has_overlap"]
        assert all(segment["concurrent_operations"] == 1 for segment in row["segments"])
    (output / "dto-evidence.json").write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding="utf-8")
    with serve(app) as base:
        invoke("point_dense_canvas_probe.cjs", {"base": base, "path": paths["plan"], "output": str(output)}, output)
    report = json.loads((output / "browser-result.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.")
    assert not report["errors"] and not report["external"]
    assert len(report["variants"]) == 4 and all(row["passed"] for row in report["variants"])
    assert len(report["boundaries"]) == 2 and all(row["dense_point_rows"] == 0 for row in report["boundaries"])
    assert len(report["screenshots"]) == 14
    for image in report["screenshots"]:
        assert Path(image).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert all(row["method"] == "GET" and row["status"] == 200 for row in report["requests"])
    assert digest_sql(trial_case.conn) == before, "All browser reads preserve the adopted SQLite database"
    build = json.loads((output / "build-evidence.json").read_text(encoding="utf-8"))
    sources = []
    for row in build["sources"]:
        source = HERE / row["path"] if row["path"] == "point_browser_host.jsx" else HERE.parents[1] / "frontend/workbench" / row["path"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row["sha256"], "Source changed during browser run: " + str(source)
        sources.append({"path": str(source), "sha256": row["sha256"]})
    for name in ("test_point_dense_canvas.py", "point_dense_canvas_probe.cjs", "point_browser_build.cjs", "point_frontend_support.py"):
        source = HERE / name
        sources.append({"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    proof = {"identity": identity, "sqlite": str(trial_case.path), "before_sql_sha256": before,
             "after_sql_sha256": digest_sql(trial_case.conn), "point_count": COUNT, "normal_count": COUNT,
             "normal_seconds": COUNT * 60, "global_build": False, "production_database": False, "sources": sources}
    (output / "sqlite-proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    print("EN_DENSE_CANVAS_EVIDENCE " + str(output), flush=True)
