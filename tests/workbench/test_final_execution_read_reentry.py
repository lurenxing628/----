"""Keep the same real browser alive while Field/Calibration restart on the same port."""

import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.workbench.final_execution_cases import create, sql
from tests.workbench.final_execution_cases import final_e_runtime as runtime_fixture
from tests.workbench.final_execution_support import restart_preserved, serving
from tests.workbench.live_environment import write_json

final_e_runtime = runtime_fixture


@pytest.mark.parametrize("view,profile", [("field", "execution"), ("calib", "calibration")])
def test_full_read_view_same_browser_new_pid_preserves_original_scope_page_and_refs(final_e_runtime, view, profile):
    parent, built, runtime = final_e_runtime
    with serving(parent, built, runtime, profile) as host:
        if view == "field":
            create(host, op=15)
        else:
            for sequence in range(3, 25):
                sql(host, "INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,setup_hours,unit_hours) "
                    "VALUES ('P1',?,'T1',?,'internal',0,10)", (sequence, "Read reentry " + str(sequence)))
        before = host.state()
        write_json(host.root / "read-reentry-business-before.json", before)
        restarts = []
        with ThreadPoolExecutor(max_workers=1) as pool:
            browser = pool.submit(host.browser, "final_execution_read_reentry.cjs", view)
            current = before
            for number in (1, 2):
                deadline = time.monotonic() + 120
                while not (host.root / ("read-reentry-restart-request-" + str(number) + ".json")).exists():
                    if browser.done():
                        browser.result()
                        raise AssertionError("Browser ended before the restart checkpoint")
                    assert time.monotonic() < deadline, "Read reentry browser did not reach the checkpoint"
                    time.sleep(.05)
                assert host.state() == current
                assert host.ready is not None and host.process is not None
                pid, url = host.process.pid, host.ready["url"]
                host.stop()
                host.start(reuse=True)
                assert host.process is not None and host.process.pid != pid and host.ready["url"] == url
                restarts.append({"old_pid": pid, "new_pid": host.process.pid, "same_url": url,
                                 "audit": restart_preserved(current, host.state())})
                current = host.state()
                write_json(host.root / "read-reentry-restarts.json", restarts)
                write_json(host.root / ("read-reentry-restart-complete-" + str(number) + ".json"), {"url": url, "pid": host.process.pid})
            browser.result(timeout=120)
        proof = json.loads((host.root / ("final-read-reentry-" + view + ".json")).read_text(encoding="utf-8"))
        assert all(action["passed"] for action in proof["actions"]) and proof["gaps"] == []
        assert all(request["method"] == "GET" for request in proof["requests"])
        assert host.state() == current
        write_json(host.root / "read-reentry-proof.json", {"view": view, "browser": proof, "restarts": restarts,
                   "all_business_tables_unchanged": True, "full_main": True})
