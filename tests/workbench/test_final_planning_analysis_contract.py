"""Frontend validation consumes real API envelopes, not mocked browser responses."""

import json
import subprocess
from pathlib import Path

import pytest

from tests.workbench.run_candidate_adoption_support import INTENT, KEY, preview, service
from tests.workbench.run_candidate_support import api, compute
from tests.workbench.run_candidate_support import candidate_case as _case  # noqa: F401
from tests.workbench.test_live_browser import runtime_tools


@pytest.mark.parametrize("adopted", [False, True])
def test_analysis_transport_rejects_wrong_identity_unknown_zero_and_scope_claims(candidate_case, tmp_path, adopted):
    case = candidate_case
    if adopted:
        case.plan(7, [case.op_id], start="2026-09-12T08:00:00", end="2026-09-12T10:00:00")
    _, refs = compute(case)
    if adopted:
        service(case.conn).adopt(refs[0], preview(case, refs[0]), KEY, INTENT)
    client, _ = api(case)
    fixtures = []
    for ref in refs:
        item = {}
        for name, leaf in (("analysis", "analysis"), ("history", "adoptions")):
            response = client.get("/api/workbench/v1/scheduling/candidates/" + ref + "/" + leaf)
            assert response.status_code == 200, response.get_data(as_text=True)
            item[name] = response.get_json()
        fixtures.append(item)
    source = tmp_path / "actual-analysis-envelopes.json"
    source.write_text(json.dumps(fixtures, ensure_ascii=False), encoding="utf-8")
    node, _, _ = runtime_tools()
    result = subprocess.run([node, str(Path(__file__).with_name("final_planning_analysis_contract.cjs")), str(source)],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["cases"] == 4
