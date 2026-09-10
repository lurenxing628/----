"""Five topics and four catalog exports through the complete current main entry."""

import json
import shutil
from pathlib import Path

from tests.workbench.final_execution_cases import final_e_runtime as final_e_runtime
from tests.workbench.final_execution_support import restart_preserved, serving
from tests.workbench.live_environment import write_json
from tests.workbench.reports_review_browser_oracle import verify


def test_full_main_reports_all_download_bytes_scope_sql_and_real_restart(final_e_runtime):
    parent, built, runtime = final_e_runtime
    with serving(parent, built, runtime, "reports") as host:
        print("FINAL_REPORTS_ROOT " + str(host.root), flush=True)
        initial = host.state()
        host.browser("final_execution_reports.cjs")
        report = json.loads((host.root / "final-reports-initial.json").read_text(encoding="utf-8"))
        assert all(row["passed"] for row in report["cases"])
        assert len(report["downloads"]) == 56 and host.state() == initial
        ready = host.ready
        assert ready is not None
        directory = Path(ready["root"]) / "sessions" / ready["session"]
        host.stop()
        write_json(host.root / "ei-browser.json", report)
        for source, target in (("http.jsonl", "ei-http.jsonl"), ("streams.jsonl", "ei-streams.jsonl")):
            shutil.copyfile(str(directory / source), str(host.root / target))
        proof = verify(host.root)
        assert proof["wire_bytes_identical"] and proof["database_unchanged"]
        host.start(reuse=True)
        restarted_state = host.state()
        restart_audit = restart_preserved(initial, restarted_state)
        host.browser("final_execution_reports.cjs", "restart")
        restarted = json.loads((host.root / "final-reports-restart.json").read_text(encoding="utf-8"))
        assert len(restarted["cases"]) == 4 and all(row["passed"] for row in restarted["cases"])
        assert host.state() == restarted_state
        write_json(host.root / "final-reports-proof.json", {"initial_cases": report["cases"], "restart_cases": restarted["cases"],
            "wire_sql_proof": proof, "strict_changed_tables": [], "old_rows_preserved": True,
            "private_full_build": ready["assets"]["build_id"], "restart_audit": restart_audit})
