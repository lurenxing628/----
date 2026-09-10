"""Full-main nine-resource pagination and original report provenance, without UI writes."""

import json

from tests.workbench.final_execution_cases import final_e_runtime as final_e_runtime
from tests.workbench.final_execution_support import restart_preserved, serving
from tests.workbench.live_environment import write_json


def test_full_main_resource_tabs_six_group_pages_drill_and_restart(final_e_runtime):
    parent, built, runtime = final_e_runtime
    with serving(parent, built, runtime, "resources") as host:
        print("FINAL_RESOURCES_ROOT " + str(host.root), flush=True)
        before = host.state()
        host.browser("final_execution_resources.cjs")
        report = json.loads((host.root / "final-resources-initial.json").read_text(encoding="utf-8"))
        assert all(row["passed"] for row in report["actions"])
        assert report["page_errors"] == report["console_errors"] == report["gaps"] == report["external_requests"] == []
        assert host.state() == before
        host.stop()
        host.start(reuse=True)
        restarted = host.state()
        audit = restart_preserved(before, restarted)
        host.browser("final_execution_resources.cjs", "restart")
        final = json.loads((host.root / "final-resources-restart.json").read_text(encoding="utf-8"))
        assert final["resources"] == report["resources"] and host.state() == restarted
        write_json(host.root / "final-resources-proof.json", {"actions": report["actions"], "strict_changed_tables": [],
            "groups_per_type": 9, "group_page_sizes": [6, 3], "restart_audit": audit})
