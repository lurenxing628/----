"""Main-entrypoint evidence, not component-only API or rendered fixtures."""

import json
from pathlib import Path

from tests.workbench.final_operations_actions import FAMILIES, actions
from tests.workbench.final_operations_seed import seed
from tests.workbench.final_operations_support import REPO, OperationsHost
from tests.workbench.test_system_restore_entrypoint_support import wait_for


def test_final_operations_action_denominator_matches_all_planning_families():
    planning = json.loads((REPO / ".codestable/roadmap/workbench-prototype-migration/workbench-capabilities.json").read_text())
    expected = {row["id"] for row in planning["capabilities"] if row["workstream"] in ("dashboard", "system")}
    assert set(FAMILIES) == expected and len(expected) == 33
    rows = actions()
    assert len(rows) == 228 and len({row["action_id"] for row in rows}) == 228
    assert planning["phase"] == "planning" and planning["summary"]["exact_count"] == 206


def test_final_operations_real_host_worker_readonly_and_owned_stop(tmp_path):
    host = OperationsHost(tmp_path / "operations-host")
    seed(host.root)
    try:
        host.start()
        assert host.ready["runtime_ready"] and host.ready["guard_is_controller"]
        wait_for(lambda: host.stored("SELECT state FROM WorkbenchRunJobs WHERE request_key='final-operations-worker-000001'")[0]["state"] == "complete", timeout=60)
        status, html = host.request("/workbench?view=dashboard")
        assert status == 200 and b"workbench/app/main.js" in html
        status, data = host.request("/api/workbench/v1/dashboard")
        assert status == 200, data
        assert all(data["data"]["categories"][kind]["known_risk_count"] > 0 for kind in ("delivery", "actual", "material", "downtime"))
        assert data["data"]["candidate_catalog"]["runs"][0]["candidate_count"] == 4
        host.locked()
        host.stop()
        evidence = json.loads((host.root / "process-evidence.json").read_text())
        assert not evidence["violations"]
        assert evidence["sqlite_connections"]
        for filename in evidence["sqlite_connections"]:
            if filename != ":memory:":
                Path(filename).resolve().relative_to(host.root)
        assert host.marker() == "current"
        assert "skip" in (host.root / "process.log").read_text().lower() or "跳过" in (host.root / "process.log").read_text()
    finally:
        host.close()
