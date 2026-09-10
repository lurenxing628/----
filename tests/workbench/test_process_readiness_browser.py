"""Lightweight source-only rail probe; does not build or publish workbench assets."""

import json
import os
import subprocess
from pathlib import Path

from tests.workbench.process_readiness_support import enroll, summary
from tests.workbench.process_workflow_support import seed_workflow


def test_process_summary_chromium109_refresh_and_states(schema_conn, tmp_path):
    from tests.workbench.test_live_browser import runtime_tools

    fixtures = {"empty": summary(schema_conn)}
    seed_workflow(schema_conn)
    fixtures["legacy"] = summary(schema_conn)
    enroll(schema_conn)
    fixtures["route"] = summary(schema_conn)
    for stage, name in (("route", "source"), ("source", "hours"), ("hours", "ready")):
        enroll(schema_conn, stages=(stage,))
        fixtures[name] = summary(schema_conn)
    seed_workflow(schema_conn, "OTHER", catalog=False)
    fixtures["mixed"] = summary(schema_conn)
    schema_conn.execute("UPDATE PartOperations SET unit_hours=3 WHERE part_no='P1' AND seq=1")
    schema_conn.commit()
    fixtures["stale"] = summary(schema_conn)
    schema_conn.execute("PRAGMA foreign_keys=OFF")
    schema_conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind='template_operation'")
    schema_conn.commit()
    fixtures["unavailable"] = summary(schema_conn)
    fixture_path = tmp_path / "process-summary-facts.json"
    fixture_path.write_text(json.dumps(fixtures, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    node, browser, modules = runtime_tools()
    output = tmp_path / "process-rail-artifacts"
    result = subprocess.run([node, str(Path(__file__).with_name("process_readiness_probe.cjs")), str(output), str(fixture_path)],
                            env=dict(os.environ, NODE_PATH=modules, WORKBENCH_BROWSER=browser),
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((output / "component-result.json").read_text(encoding="utf-8"))
    assert report["browser"].startswith("109.") and len(report["cases"]) == 4
    assert report["checks"] >= 100 and not report["errors"] and not report["external"]
    assert report["scope"] == "source-only-ResourceLive-callback-mock-with-service-facts"
    print(result.stdout)
