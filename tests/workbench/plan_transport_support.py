"""Run real plan DTOs through the frontend transport contract."""

import base64
import json
import subprocess
from copy import deepcopy
from pathlib import Path

from werkzeug.http import parse_options_header

from tests._support.node_runtime_support import node_runtime

ROOT = Path(__file__).resolve().parents[2]
FOLLOW_UP_PATHS = {"baseline": "/baseline", "tasks": "/tasks", "gantt_graph": "/gantt-graph", "capacity": "/capacity"}


def run_probe(tmp_path, fixtures, boundary=None):
    """Read every real backend fixture through the real plan API path.

    ``boundary`` holds real envelopes exported by the backend (``catalog_more``, ``catalog_last``, ``workspace`` and
    its ``baseline``); with it the probe also runs its transport-boundary self-check, whose illegal inputs are built
    around those envelopes.
    """
    prepared = []
    for item in fixtures:
        entry = dict(item)
        if entry["kind"] == "baseline" and "expected" not in entry:
            entry["expected"] = deepcopy(entry["payload"])
            del entry["expected"]["data"]["page"]
        prepared.append(entry)
    payload = {"fixtures": prepared}
    if boundary is not None:
        payload["boundary"] = boundary
    result = subprocess.run(
        [node_runtime(), str(Path(__file__).with_name("plan_transport_probe.cjs"))],
        cwd=str(ROOT), input=json.dumps(payload), text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["network"] == "mock-only" and report["production"] is False
    assert report["methods"] == ["GET"]
    assert report["fixtures"] == len(fixtures)
    assert (report["boundary"] > 0) is (boundary is not None)
    evidence = tmp_path / "plan-transport-evidence.json"
    evidence.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("PLAN_TRANSPORT_EVIDENCE " + str(evidence), flush=True)
    return report

def catalog_fixture(api, name, **scope):
    return {"name": name, "kind": "catalog", "scope": scope, "payload": api.read(**scope)}

def workspace_fixture(api, name, ref, **scope):
    return {"name": name, "kind": "workspace", "plan_ref": ref, "scope": scope,
            "payload": api.read("/" + ref + "/workspace", **scope)}

def follow_up_fixture(api, name, workspace, kind, **scope):
    """A read pinned to ``workspace``'s snapshot; the probe checks it against that workspace fixture's data."""
    query = {"snapshot_ref": workspace["payload"]["meta"]["snapshot_ref"], **scope}
    return {"name": name, "kind": kind, "plan_ref": workspace["plan_ref"], "workspace": workspace["name"], "scope": query,
            "payload": api.read("/" + workspace["plan_ref"] + FOLLOW_UP_PATHS[kind], **query)}

def export_fixture(api, name, workspace, file_format, **scope):
    """The real attachment bytes and headers; the expected file name is what werkzeug reads from the header."""
    query = {"format": file_format, "snapshot_ref": workspace["payload"]["meta"]["snapshot_ref"], **scope}
    response = api.get("/" + workspace["plan_ref"] + "/export", **query)
    assert response.status_code == 200, response.get_data(as_text=True)
    disposition = response.headers["Content-Disposition"]
    return {"name": name, "kind": "export", "plan_ref": workspace["plan_ref"], "scope": query,
            "body": base64.b64encode(response.data).decode("ascii"),
            "headers": {"Content-Type": response.headers["Content-Type"], "Content-Disposition": disposition},
            "filename": parse_options_header(disposition)[1]["filename"]}
