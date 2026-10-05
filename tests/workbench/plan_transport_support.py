"""Run real plan DTOs through the frontend transport contract."""

import json
import subprocess
from pathlib import Path

from tests.workbench.node_runtime_support import node_runtime

ROOT = Path(__file__).resolve().parents[2]


def run_probe(tmp_path, fixtures=None):
    node = node_runtime()
    payload = {} if fixtures is None else {"fixtures": fixtures, "fixturesOnly": True}
    result = subprocess.run(
        [node, str(Path(__file__).with_name("plan_transport_probe.cjs"))],
        cwd=str(ROOT), input=json.dumps(payload), text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["network"] == "mock-only" and report["production"] is False
    assert report["methods"] == ["GET"]
    evidence = tmp_path / "plan-transport-evidence.json"
    evidence.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("PLAN_TRANSPORT_EVIDENCE " + str(evidence), flush=True)
    return report

def catalog_fixture(api, name, **scope):
    return {"name": name, "kind": "catalog", "scope": scope, "payload": api.read(**scope)}

def workspace_fixture(api, name, ref, **scope):
    return {"name": name, "kind": "workspace", "plan_ref": ref, "scope": scope,
            "payload": api.read("/" + ref + "/workspace", **scope)}
