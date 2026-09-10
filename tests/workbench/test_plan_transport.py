"""Current-source transport VM and real isolated API DTOs; no production requests."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.workbench.plan_catalog_support import history
from tests.workbench.plan_read_support import NIGHT_END, plan_read_api

ROOT = Path(__file__).resolve().parents[2]


def run_probe(tmp_path, fixtures=None):
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
    assert node, "Plan transport tests require the build-host Node runtime"
    payload = {} if fixtures is None else {"fixtures": fixtures, "fixturesOnly": True}
    result = subprocess.run(
        [node, str(Path(__file__).with_name("plan_transport_probe.cjs"))],
        cwd=str(ROOT), input=json.dumps(payload), text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["network"] == "mock-only" and report["production"] is False
    assert report["methods"] == ["GET"]
    for source in report["sources"]:
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"]
    evidence = tmp_path / "plan-transport-evidence.json"
    evidence.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("PLAN_TRANSPORT_EVIDENCE " + str(evidence), flush=True)
    return report


def catalog_fixture(api, name, **scope):
    return {"name": name, "kind": "catalog", "scope": scope, "payload": api.read(**scope)}


def workspace_fixture(api, name, ref, **scope):
    return {"name": name, "kind": "workspace", "plan_ref": ref, "scope": scope,
            "payload": api.read("/" + ref + "/workspace", **scope)}


def test_plan_transport_strict_mock_contract(tmp_path):
    report = run_probe(tmp_path)
    assert report["checks"] >= 160
    assert len(set(report["cases"])) == report["checks"]


def test_real_api_dtos_match_frontend_contract(plan_api, tmp_path):
    before = plan_api.state()
    fixtures = [catalog_fixture(plan_api, "history first", size=1)]
    first = fixtures[0]["payload"]
    fixtures.append(catalog_fixture(plan_api, "history cursor", size=1, cursor=first["data"]["page"]["next_cursor"],
                                    snapshot_ref=first["meta"]["snapshot_ref"]))
    fixtures.append(catalog_fixture(plan_api, "scenarios", collection="scenario"))
    refs = [plan_api.ref(), plan_api.ref(role="baseline_best"), plan_api.ref(role="critical_best"),
            plan_api.ref(scenario_id="PRIVATE-ACTIVE")]
    for index, ref in enumerate(refs):
        fixtures.append(workspace_fixture(plan_api, "plan kind " + str(index), ref))
    original = fixtures[3]["payload"]
    fixtures.append(workspace_fixture(plan_api, "exact snapshot", refs[0], snapshot_ref=original["meta"]["snapshot_ref"]))
    fixtures.append(workspace_fixture(plan_api, "night overlap", refs[0], range_start="2026-09-10T00:00:00", range_end="2026-09-10T01:00:00"))
    fixtures.append(workspace_fixture(plan_api, "empty overlap", refs[0], range_start=NIGHT_END, range_end="2026-09-10T08:00:00"))
    error = plan_api.get("/" + refs[1] + "/workspace", snapshot_ref=original["meta"]["snapshot_ref"])
    fixtures.append({"name": "foreign snapshot error", "kind": "workspace", "plan_ref": refs[1],
                     "scope": {"snapshot_ref": original["meta"]["snapshot_ref"]}, "payload": error.get_json(),
                     "status": error.status_code, "error": "snapshot_stale"})
    assert plan_api.state() == before
    assert run_probe(tmp_path, fixtures)["checks"] == len(fixtures)


def test_real_disabled_catalog_null_refs_and_invalid_version(plan_api, tmp_path):
    missing = plan_api.ref(role="critical_best")
    with plan_api.db() as conn:
        conn.execute("UPDATE WorkbenchPlanSourceRefs SET active=0 WHERE ref=?", (missing,))
        conn.execute("UPDATE ScheduleAdjustmentScenario SET base_version='broken' WHERE scenario_id='PRIVATE-ACTIVE'")
    before = plan_api.state()
    fixtures = [catalog_fixture(plan_api, "missing permanent ref"), catalog_fixture(plan_api, "bad scenario version", collection="scenario")]
    assert any(row["plan_ref"] is None for row in fixtures[0]["payload"]["data"]["plans"])
    assert any(row["version"] is None for row in fixtures[1]["payload"]["data"]["plans"])
    assert plan_api.state() == before
    assert run_probe(tmp_path, fixtures)["checks"] == 2


@pytest.mark.parametrize("version", [9007199254740991, 9007199254740993, 9223372036854775807])
def test_real_int64_wire_preserves_version_and_sequence(plan_api, tmp_path, version):
    with plan_api.db() as conn:
        history(conn, version, op_id=1)
        conn.execute("UPDATE BatchOperations SET seq=? WHERE id=1", (version,))
    ref = plan_api.ref(version)
    before = plan_api.state()
    fixtures = [catalog_fixture(plan_api, "int64 catalog", size=1), workspace_fixture(plan_api, "int64 workspace", ref)]
    expected = version if version <= 9007199254740991 else str(version)
    assert fixtures[0]["payload"]["data"]["plans"][0]["version"] == expected
    assert fixtures[1]["payload"]["data"]["plan"]["version"] == expected
    assert fixtures[1]["payload"]["data"]["tasks"][0]["sequence"] == expected
    assert plan_api.state() == before
    assert run_probe(tmp_path, fixtures)["checks"] == 2
