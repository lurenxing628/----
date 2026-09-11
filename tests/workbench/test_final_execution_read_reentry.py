"""Keep the same real browser alive while Field/Calibration restart on the same port."""

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from zipfile import ZipFile, ZipInfo

import pytest

from tests.workbench.final_execution_cases import create, sql
from tests.workbench.final_execution_cases import final_e_runtime as runtime_fixture
from tests.workbench.final_execution_support import restart_preserved, serving
from tests.workbench.live_environment import write_json

final_e_runtime = runtime_fixture


def verify_original_read_download(root, browser):
    root = Path(root).resolve()
    exported = browser["export"]

    def key(url):
        parsed = urlsplit(url)
        return parsed.path, parse_qs(parsed.query)

    expected = key(exported["url"])
    requests = [row for row in browser["requests"] if key(row["url"]) == expected]
    assert len(requests) == 1 and requests[0]["method"] == "GET"
    records = {}
    for name in ("http", "streams"):
        records[name] = [row for path in (root / "sessions").glob("*/" + name + ".jsonl")
                         for row in map(json.loads, path.read_text(encoding="utf-8").splitlines())
                         if key(row["url"]) == expected]
        assert len(records[name]) == 1, "Export must bind to one original response, not a refetch"
    response, wire = records["http"][0], records["streams"][0]
    assert response["method"] == "GET" and response["status"] == 200
    headers = {name.lower(): value for name, value in response["headers"].items()}
    for name in ("content-type", "content-disposition", "content-length"):
        assert headers[name] == exported["headers"][name]
    assert len(browser["downloads"]) == 1
    download = browser["downloads"][0]
    assert download["path"] == exported["path"]
    saved, original = Path(download["path"]).resolve(), Path(wire["path"]).resolve()
    assert root in saved.parents and root in original.parents
    content, emitted = saved.read_bytes(), original.read_bytes()
    assert content == emitted, "Download differs from the original response bytes"
    digest = hashlib.sha256(content).hexdigest()
    assert digest == download["sha256"] == wire["sha256"]
    assert len(content) == download["bytes"] == wire["bytes"] == int(headers["content-length"])
    return {"url": exported["url"], "download_path": str(saved), "original_response_path": str(original),
            "sha256": digest, "bytes": len(content), "page_requests": 1, "host_responses": 1,
            "original_wire_bytes_identical": True}


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
        download_proof = verify_original_read_download(host.root, proof)
        write_json(host.root / "read-reentry-proof.json", {"view": view, "browser": proof, "restarts": restarts,
                   "all_business_tables_unchanged": True, "full_main": True, "download_proof": download_proof})


@pytest.mark.parametrize("case", ["original", "zip-time-only", "duplicate-http", "duplicate-wire",
                                  "missing-wire", "wrong-snapshot", "wrong-digest"])
def test_read_download_oracle_requires_one_original_response_and_every_byte(tmp_path, case):
    def archive(second):
        output = BytesIO()
        with ZipFile(output, "w") as zipped:
            zipped.writestr(ZipInfo("member.xml", date_time=(2026, 9, 11, 15, 44, second)), b"<same-content/>")
        return output.getvalue()

    original, later = archive(32), archive(34)
    assert original != later and len(original) == len(later)
    with ZipFile(BytesIO(original)) as first, ZipFile(BytesIO(later)) as second:
        assert first.read("member.xml") == second.read("member.xml")
    content = later if case == "zip-time-only" else original
    saved, emitted = tmp_path / "download.xlsx", tmp_path / "wire.bin"
    saved.write_bytes(content)
    emitted.write_bytes(original)
    url = "http://127.0.0.1:12345/api/workbench/v1/execution/files/export?snapshot_ref=-fixed&query=B1"
    headers = {"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
               "content-disposition": "attachment; filename=export.xlsx", "content-length": str(len(original))}
    browser = {"requests": [{"url": url, "method": "GET"}], "export": {"url": url, "path": str(saved), "headers": headers},
               "downloads": [{"path": str(saved), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}]}
    http = [{"url": url, "method": "GET", "status": 200, "headers": headers}]
    wire = [{"url": url, "path": str(emitted), "bytes": len(original), "sha256": hashlib.sha256(original).hexdigest()}]
    if case == "duplicate-http":
        http *= 2
    elif case == "duplicate-wire":
        wire *= 2
    elif case == "missing-wire":
        wire = []
    elif case == "wrong-snapshot":
        wire[0]["url"] = url.replace("-fixed", "-different")
    elif case == "wrong-digest":
        wire[0]["sha256"] = "0" * 64
    session = tmp_path / "sessions/original"
    session.mkdir(parents=True)
    for name, rows in (("http", http), ("streams", wire)):
        (session / (name + ".jsonl")).write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    write_json(tmp_path / "download-evidence.json", browser)
    if case == "original":
        assert verify_original_read_download(tmp_path, browser)["original_wire_bytes_identical"]
    else:
        with pytest.raises(AssertionError):
            verify_original_read_download(tmp_path, browser)
