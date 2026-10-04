"""不重排时段（hold_window）的前端合同：排产检查输入三态、检查结果一致性、排产任务和排产记录的可选回显；
真实后端返回的排产检查结果（不带 / null / 本次填写）也要原样通过页面校验。"""

import json
import os
import shutil
import subprocess
from pathlib import Path

from flask import Blueprint

from tests.workbench.run_candidate_support import api
from tests.workbench.run_candidate_support import candidate_case as candidate_case  # noqa: F401
from web.routes.workbench.preflight import register_preflight_routes

HERE = Path(__file__).resolve().parent


def probe(*args):
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
    assert node, "Node is required for pure UI contracts; browser tooling is not needed"
    result = subprocess.run(
        [node, str(HERE / "hold_window_contract.cjs"), *args], cwd=str(HERE.parents[1]),
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_hold_window_frontend_contracts():
    summary = probe()
    assert summary["invalid_inputs"] >= 14
    assert summary["rejected_results"] >= 16


def test_real_preflight_results_with_hold_window_pass_page_validation(candidate_case, tmp_path):
    case = candidate_case
    case.plan(7, [case.op_id], start="2026-09-09T09:00:00", end="2026-09-09T10:00:00")
    bp = Blueprint("hold_window_preflight", __name__)
    register_preflight_routes(bp)
    case.app.register_blueprint(bp)
    client, _ = api(case)
    base = case.settings()
    payloads = []
    for patch in ({}, {"hold_window": None}, {"hold_window": {"start": "2026-09-09T08:00", "end": "2026-09-09T12:00"}}):
        settings = {**base, **patch}
        response = client.post("/api/workbench/v1/scheduling/preflight", json=settings)
        assert response.status_code == 200, response.get_data(as_text=True)
        payloads.append({"settings": settings, "response": response.get_json()})
    source = tmp_path / "hold-window-preflight.json"
    source.write_text(json.dumps(payloads, ensure_ascii=False), encoding="utf-8")
    default, unset, explicit = probe("real", str(source))["cases"]
    assert (default["source"], default["hold_window"]) == ("default", None)
    assert (unset["source"], unset["hold_window"], unset["hold_window_tasks"]) == ("explicit", None, 0)
    assert explicit["source"] == "explicit"
    assert explicit["hold_window"] == {"start": "2026-09-09T08:00", "end": "2026-09-09T12:00"}
    assert explicit["hold_window_tasks"] == 1 and explicit["bases"] == ["hold_window"]
