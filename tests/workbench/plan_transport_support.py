"""Run real plan DTOs through the frontend transport contract."""

import json
import subprocess
from pathlib import Path

from tests._support.node_runtime_support import node_runtime

ROOT = Path(__file__).resolve().parents[2]


def run_probe(tmp_path, fixtures=None):
    node = node_runtime()
    if fixtures is not None:
        workspaces = {
            item["plan_ref"]: item["payload"]["data"]
            for item in fixtures
            if item.get("kind") == "workspace"
            and not item.get("contract_error")
            and not item.get("error")
            and isinstance(item.get("payload"), dict)
            and isinstance(item["payload"].get("data"), dict)
        }
        prepared = []
        for item in fixtures:
            entry = dict(item)
            if entry.get("kind") in ("baseline", "tasks", "gantt_graph", "capacity") and entry.get("workspace_data") is None:
                entry["workspace_data"] = workspaces.get(entry.get("plan_ref"))
            if entry.get("kind") == "baseline" and "expected" not in entry and isinstance(entry.get("payload"), dict) and isinstance(entry["payload"].get("data"), dict):
                expected = json.loads(json.dumps(entry["payload"]))
                expected["data"].pop("page", None)
                ws_data = entry.get("workspace_data")
                if isinstance(ws_data, dict) and isinstance(ws_data.get("tasks"), list):
                    by_ref = {row["task_ref"]: row for row in ws_data["tasks"] if isinstance(row, dict) and "task_ref" in row}
                    for row in expected["data"].get("items") or []:
                        if row.get("after_in_scope") is True and isinstance(row.get("after"), dict) and set(row["after"]) == {"task_ref"}:
                            row["after"] = by_ref.get(row["after"]["task_ref"], row["after"])
                entry["expected"] = expected
            prepared.append(entry)
        payload = {"fixtures": prepared, "fixturesOnly": True}
    else:
        payload = {}
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

def baseline_fixture(api, name, ref, snapshot_ref, workspace_data=None, **scope):
    query = {"snapshot_ref": snapshot_ref, **scope}
    return {"name": name, "kind": "baseline", "plan_ref": ref, "scope": query,
            "workspace_data": workspace_data, "payload": api.read("/" + ref + "/baseline", **query)}

def tasks_fixture(api, name, ref, snapshot_ref, workspace_data=None, **scope):
    query = {"snapshot_ref": snapshot_ref, "page": 1, **scope}
    return {"name": name, "kind": "tasks", "plan_ref": ref, "scope": query,
            "workspace_data": workspace_data, "payload": api.read("/" + ref + "/tasks", **query)}

def gantt_graph_fixture(api, name, ref, snapshot_ref, workspace_data=None, **scope):
    query = {"snapshot_ref": snapshot_ref, **scope}
    return {"name": name, "kind": "gantt_graph", "plan_ref": ref, "scope": query,
            "workspace_data": workspace_data, "payload": api.read("/" + ref + "/gantt-graph", **query)}

def capacity_fixture(api, name, ref, snapshot_ref, workspace_data=None, **scope):
    query = {"snapshot_ref": snapshot_ref, **scope}
    return {"name": name, "kind": "capacity", "plan_ref": ref, "scope": query,
            "workspace_data": workspace_data, "payload": api.read("/" + ref + "/capacity", **query)}
