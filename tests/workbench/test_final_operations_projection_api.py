"""Real route payloads validate in the actual JS clients; no browser overlay."""

import json
import os
import subprocess
from pathlib import Path

from flask import Blueprint

from tests.workbench.final_operations_support import REPO
from tests.workbench.run_candidate_baseline_support import api, original_plan
from tests.workbench.run_candidate_support import candidate_case as _candidate_case
from tests.workbench.run_candidate_support import compute
from tests.workbench.test_live_browser import runtime_tools
from web.routes.workbench.dashboard_analysis import dashboard_analysis, dashboard_candidate_comparison


def test_final_operations_projection_api_and_strict_clients(candidate_case, tmp_path):
    case = candidate_case
    original_plan(case)
    _, refs = compute(case)
    client, statements = api(case)
    bp = Blueprint("final_operations_analysis", __name__)
    bp.add_url_rule("/api/workbench/v1/dashboard/analysis", view_func=dashboard_analysis)
    bp.add_url_rule("/api/workbench/v1/dashboard/candidates/<candidate_ref>/comparison", view_func=dashboard_candidate_comparison)
    case.app.register_blueprint(bp)
    scope = {"range_start": "2026-09-09T00:00:00", "range_end": "2026-09-26T00:00:00"}
    base = "/api/workbench/v1/scheduling/candidates/" + refs[0]
    urls = {"analysis": ("/api/workbench/v1/dashboard/analysis", {}), "workspace": (base + "/workspace", scope),
            "baseline": (base + "/baseline", scope),
            "comparison": ("/api/workbench/v1/dashboard/candidates/" + refs[0] + "/comparison", scope)}
    payloads = {"scope": scope}
    for name, (url, query) in urls.items():
        response = client.get(url, query_string=query)
        assert response.status_code == 200, response.get_json()
        assert response.headers["Cache-Control"] == "no-store"
        payloads[name] = response.get_json()
    assert all(not sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE")) for sql in statements)
    (tmp_path / "api-payloads.json").write_text(json.dumps(payloads, ensure_ascii=False), encoding="utf-8")
    node, _, modules = runtime_tools()
    result = subprocess.run([node, str(REPO / "tests/workbench/final_operations_projection_contract.cjs")],
                            input=json.dumps(payloads), text=True, capture_output=True, timeout=30, cwd=str(REPO),
                            env=dict(os.environ, NODE_PATH=modules))
    (tmp_path / "client-contract.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["rejected"] == 14
    assert Path(tmp_path / "api-payloads.json").stat().st_size > 0
