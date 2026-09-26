"""Real backend DTOs exercise the browser's public microsecond contracts."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from flask import Blueprint

from tests.workbench.run_candidate_support import api, compute, read
from tests.workbench.run_candidate_support import candidate_case as candidate_case
from tests.workbench.trial_support import change, create, official
from tests.workbench.trial_support import trial_case as trial_case
from web.routes.workbench.preflight import register_preflight_routes

HERE = Path(__file__).resolve().parent


def probe(tmp_path, mode, payload=None, timezone="Asia/Shanghai"):
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
    assert node, "Node is required to verify the browser time contracts"
    source = tmp_path / (mode + ".json")
    source.write_text(json.dumps(payload or {}, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run(
        [node, str(HERE / "test_time_precision_contracts.cjs"), mode, str(source)],
        cwd=str(HERE.parents[1]), env=dict(os.environ, TZ=timezone),
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("timezone", ["Asia/Shanghai", "America/New_York"])
def test_public_time_scopes_and_adoption_previews_preserve_microseconds(tmp_path, timezone):
    result = probe(tmp_path, "scopes", timezone=timezone)
    assert result["canonical_valid"] == 4
    assert result["invalid_times"] >= 15
    assert result["legacy_query_widths"] == 6
    assert result["adoption_contracts"] == 2


def test_real_candidate_and_preflight_dtos_use_exact_microsecond_contracts(candidate_case, tmp_path):
    case = candidate_case
    # Actual engine output: three pieces at .001 hours finish after 10.8 seconds.
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.001 WHERE id=?", (case.op_id,))
    case.conn.commit()
    _, refs = compute(case)
    bp = Blueprint("precision_preflight", __name__)
    register_preflight_routes(bp)
    case.app.register_blueprint(bp)
    client, _ = api(case)
    candidate = read(client, "/candidates/" + refs[0] + "/workspace")
    assert candidate["data"]["tasks"][0]["end"].endswith(".800000")
    settings = case.settings()
    response = client.post("/api/workbench/v1/scheduling/preflight", json=settings)
    assert response.status_code == 200, response.get_data(as_text=True)
    result = probe(tmp_path, "candidate", {
        "candidate": candidate, "preflight": response.get_json(), "settings": settings,
    })
    assert result["candidate_mutations_rejected"] == 7
    assert result["microsecond_interval_accepted"] is True
    assert result["preflight_invalid_times"] >= 15


def test_real_trial_change_receipt_and_request_keep_original_microseconds(trial_case, tmp_path):
    case = trial_case
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.001 WHERE id=?", (case.op_id,))
    case.conn.commit()
    start = "2026-09-09T13:00:00.123456"
    draft = create(case, official(case, start=start, end="2026-09-09T13:00:10.923456"))
    receipt = change(case, draft, start=start)
    task = receipt["data"]["tasks"][0]
    intent = {"action": "change", "draft_ref": draft["draft_ref"], "input": {
        key: task[key] for key in ("task_ref", "machine_ref", "operator_ref", "start")
    }}
    result = probe(tmp_path, "trial", {"draft": draft, "receipt": receipt, "intent": intent})
    assert result["request_start"] == start
    assert result["receipt_start"] == start
    assert result["response_rounding_rejected"] is True
