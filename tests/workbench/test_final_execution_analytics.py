"""Full-main review primitives and explicit migration gaps are not blanket passes."""

import json

from tests.workbench.final_execution_artifacts import verify_downloads
from tests.workbench.final_execution_cases import final_e_runtime as final_e_runtime
from tests.workbench.final_execution_support import serving
from tests.workbench.live_environment import write_json


def test_full_main_review_filters_keyboard_drill_and_csv(final_e_runtime):
    parent, built, runtime = final_e_runtime
    with serving(parent, built, runtime, "reports") as host:
        print("FINAL_ANALYTICS_ROOT " + str(host.root), flush=True)
        before = host.state()
        host.browser("final_execution_analytics.cjs")
        report = json.loads((host.root / "final-analytics-initial.json").read_text(encoding="utf-8"))
        assert all(row["passed"] for row in report["actions"])
        assert report["page_errors"] == report["console_errors"] == report["external_requests"] == []
        assert host.state() == before
        host.stop()
        artifacts = verify_downloads(host.root, report)
        write_json(host.root / "final-analytics-proof.json", {"actions": report["actions"], "gaps": report["gaps"],
            "strict_changed_tables": [], "artifact_checks": artifacts, "screenshots": report["screenshots"]})
        assert report["gaps"] == [], report["gaps"]
