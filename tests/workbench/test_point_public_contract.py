"""Real worker and HTTP results cross both live candidate JavaScript validators."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.workbench.ea_zero_duration_support import point_candidate
from tests.workbench.test_run_candidate_baseline_support import api, original_plan
from tests.workbench.test_run_candidate_support import candidate_case as _candidate_case  # noqa: F401
from tests.workbench.test_run_candidate_support import read, retained


@pytest.mark.parametrize("has_baseline", [False, True])
@pytest.mark.parametrize("mixed", [False, True])
def test_point_candidate_and_initial_comparison_use_live_validators(candidate_case, has_baseline, mixed):
    case = candidate_case
    if has_baseline:
        original_plan(case)
    if mixed:
        case.operation(seq=2, setup_hours=0, unit_hours=0.25)
        case.conn.commit()
    candidate_ref = point_candidate(case)
    client, _ = api(case)
    path = "/candidates/" + candidate_ref
    fixtures = []
    scopes = ({}, {"range_start": "2026-09-09T08:00:00", "range_end": "2026-09-09T08:00:01"},
              {"range_start": "2026-09-09T07:00:00", "range_end": "2026-09-09T08:00:00"})
    with retained(case.conn):
        for scope in scopes:
            fixtures.append({"scope": scope, "workspace": read(client, path + "/workspace", **scope),
                             "baseline": read(client, path + "/baseline", **scope)})
        value = {"fixtures": fixtures, "candidate_ref": candidate_ref, "has_baseline": has_baseline,
                 "run_ref": fixtures[0]["workspace"]["data"]["candidate"]["run_ref"], "all_points": not mixed}
        node = shutil.which("node")
        assert node, "Node is required to verify the shipped JavaScript contract"
        probe = Path(__file__).with_name("point_public_contract_probe.cjs")
        result = subprocess.run([node, str(probe)], input=json.dumps(value), text=True,
                                capture_output=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        report = json.loads(result.stdout)
        assert report["read_only"] and report["checks"] >= 25
