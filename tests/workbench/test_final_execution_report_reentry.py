"""Report and review read views survive re-entry without replaying process-local tokens."""

import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.workbench.final_execution_cases import final_e_runtime as runtime_fixture
from tests.workbench.final_execution_support import restart_preserved, serving
from tests.workbench.live_environment import write_json

final_e_runtime = runtime_fixture


@pytest.mark.parametrize("view", ["reports", "review"])
def test_full_report_read_view_reentry_reload_and_new_pid_same_port(final_e_runtime, view):
    parent, built, runtime = final_e_runtime
    with serving(parent, built, runtime, "reports") as host:
        before = host.state()
        restarts = []
        with ThreadPoolExecutor(max_workers=1) as pool:
            browser = pool.submit(host.browser, "final_execution_report_reentry.cjs", view)
            restarted = before
            for number in (1, 2):
                deadline = time.monotonic() + 120
                while not (host.root / ("report-reentry-restart-request-" + str(number) + ".json")).exists():
                    if browser.done():
                        browser.result()
                        raise AssertionError("Browser ended before the restart checkpoint")
                    assert time.monotonic() < deadline, "Report browser did not reach the restart checkpoint"
                    time.sleep(.05)
                assert host.state() == restarted
                assert host.ready is not None and host.process is not None
                previous_pid = host.process.pid
                host.stop()
                host.start(reuse=True)
                assert host.process is not None and host.process.pid != previous_pid
                audit = restart_preserved(restarted, host.state())
                restarted = host.state()
                restarts.append({"old_pid": previous_pid, "new_pid": host.process.pid, "audit": audit})
                write_json(host.root / ("report-reentry-restart-complete-" + str(number) + ".json"), {"url": host.ready["url"], "pid": host.process.pid})
            browser.result(timeout=120)
        proof = json.loads((host.root / ("final-report-reentry-" + view + ".json")).read_text(encoding="utf-8"))
        assert all(action["passed"] for action in proof["actions"]) and proof["gaps"] == []
        assert all(request["method"] == "GET" for request in proof["requests"])
        assert host.state() == restarted
        write_json(host.root / "report-reentry-proof.json", {"view": view, "browser": proof,
            "restarts": restarts,
            "all_business_tables_unchanged": True, "full_main": True})
