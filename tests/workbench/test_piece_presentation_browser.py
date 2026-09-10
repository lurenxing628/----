"""Real read-only HTTP DTOs and shipped components; EQ owns main-page acceptance."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from flask import Blueprint, g

from tests.workbench.point_frontend_support import app_for, serve
from tests.workbench.test_live_browser import runtime_tools
from tests.workbench.test_piece_chain_support import adopt_candidate, adopt_trial, saved_trial
from tests.workbench.test_piece_presentation import PIECES, real_case
from tests.workbench.trial_support import create, snapshot
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401
from web.routes.workbench.run_candidate_baseline import register_run_candidate_baseline_routes

HERE = Path(__file__).resolve().parent


def invoke(script, value, timeout=90):
    node, browser, modules = runtime_tools()
    result = subprocess.run([node, str(HERE / script)], input=json.dumps(value), text=True, capture_output=True,
                            timeout=timeout, env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser))
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_real_piece_http_contract_and_long_chinese_labels(trial_case):
    case = trial_case
    ids, (_, refs) = real_case(case)
    first = adopt_candidate(case, refs[0])["data"]["official_plan"]
    _, _, saved = saved_trial(case, {"plan_ref": first["plan_ref"]}, op_id=ids[None, 40])
    second = adopt_trial(case, saved)["data"]["official_plan"]
    draft = create(case, {"base": {"plan_ref": second["plan_ref"]}}, key="es-long-piece-draft")
    output = Path(tempfile.mkdtemp(prefix="aps-piece-presentation-"))
    print("ES_PIECE_EVIDENCE " + str(output), flush=True)
    invoke("piece_presentation_build.cjs", {"output": str(output)}, timeout=180)
    app = app_for(case, output)
    bp = Blueprint("es_piece_baseline", __name__)
    register_run_candidate_baseline_routes(bp)
    app.register_blueprint(bp)

    @app.before_request
    def read_only():
        g.db.execute("PRAGMA query_only=ON")

    paths = {"candidate": "/api/workbench/v1/scheduling/candidates/" + refs[0] + "/workspace",
             "baseline": "/api/workbench/v1/scheduling/candidates/" + refs[0] + "/baseline",
             "plan": "/api/workbench/v1/plans/" + second["plan_ref"] + "/workspace",
             "old": "/api/workbench/v1/plans/" + case.plan_ref(4) + "/workspace",
             "trial": "/api/workbench/v1/trial/drafts/" + draft["draft_ref"]}
    before, changes = snapshot(case.conn), case.conn.total_changes
    client = app.test_client()
    fixtures = {}
    for kind, path in paths.items():
        response = client.get(path)
        assert response.status_code == 200, response.get_data(as_text=True)
        fixtures[kind] = response.get_json()
    report = json.loads(invoke("piece_presentation_contract.cjs", {"fixtures": fixtures, "candidate_ref": refs[0], "pieces": PIECES}))
    assert report["checks"] >= 50 and report["physical_geometry_unchanged"]
    report["trial_and_readonly"] = True
    (output / "contract-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    fixtures["trial"]["data"]["write_context"]["write_token"] = "<redacted transient test token>"
    (output / "dto-evidence.json").write_text(json.dumps(fixtures, ensure_ascii=False, indent=2), encoding="utf-8")
    with serve(app) as base:
        print(invoke("piece_presentation_browser.cjs", {"base": base, "paths": paths, "pieces": PIECES, "output": str(output)}, timeout=180), flush=True)
    browser = json.loads((output / "browser-report.json").read_text(encoding="utf-8"))
    assert browser["browser"].startswith("109.") and not browser["errors"] and not browser["external"]
    assert len(browser["screenshots"]) == 8
    assert snapshot(case.conn) == before and case.conn.total_changes == changes
    assert all(row["method"] == "GET" for row in browser["requests"])
