"""DU: real cold entrypoint and warm stopped reads must leave SQLite and journal alone."""

import json
import sqlite3
from pathlib import Path
from urllib.parse import urlencode

import pytest

from core.services.workbench.system_journal import file_fingerprint
from tests.workbench.system_restore_entrypoint_support import BASE, KEY, ProcessHost, seed_database
from tests.workbench.system_restore_host_support import restore_host as _restore_host  # noqa: F401


@pytest.mark.parametrize("damage", ["pending", "corrupt", "mixed", "missing-database"])
def test_true_cold_readonly_page_and_diagnostic_never_open_database(tmp_path, damage):
    host = ProcessHost(tmp_path, "no-database")
    source = seed_database(host)
    row, _ = host.journal().begin(KEY, "restore", {})
    host.journal().record(row, "verifying", target={"filename": source.name, "sha256": file_fingerprint(str(source))})
    if damage == "corrupt":
        next(host.journal_dir.glob("*.json")).write_text("{broken", encoding="utf-8")
    if damage == "mixed":
        (host.journal_dir / "broken.json").write_text("{broken", encoding="utf-8")
    if damage == "missing-database":
        host.path.unlink()
    before = host.hashes()
    try:
        host.start()
        assert host.ready["runtime_ready"] is False
        for path in ("/", "/workbench", "/workbench?view=system", "/workbench/trial"):
            status, body = host.request(path)
            assert status == 503 and isinstance(body, bytes)
            page = body.decode("utf-8")
            assert 'data-restore-maintenance="cold"' in page and "系统已暂停" in page
            assert 'src="/static/' not in page and "nonce" not in page
            assert '<a href="/workbench?view=system">返回工作台</a>' in page
            assert '返回入口会重新查询维护状态' in page
        query = "/workbench?" + urlencode({"kind": "request", "reference": KEY})
        status, page = host.request(query)
        assert status == 503 and KEY in page.decode("utf-8")
        assert ("维护记录损坏" in page.decode("utf-8")) == (damage == "corrupt")
        status, diagnostic = host.request(query + "&download=diagnostic")
        assert status == 200 and diagnostic["database_checked_by_page"] is False
        assert diagnostic["result_source"] == "external_maintenance_journal"
        if damage != "corrupt":
            assert diagnostic["result"]["operation"]["job_ref"] == row["job_ref"]
            assert host.request(BASE + "/results/" + KEY)[1]["data"]["operation"]["state"] == "verifying"
            assert host.request(BASE + "/jobs/" + row["job_ref"])[0] == (503 if damage == "mixed" else 200)
        for path in (BASE + "/backups", BASE + "/config", "/system/health", "/static/missing.css"):
            assert host.request(path)[0] == 503
        assert host.request("/workbench", {}, "POST")[0] == 503
        for suffix in ("?kind=unknown", "?reference=bad", "?reference=a&reference=b", "?resume=yes"):
            assert host.request("/workbench" + suffix)[0] == 400
        host.locked()
        assert host.hashes() == before
        host.stop()
        assert host.hashes() == before
    finally:
        host.close()


def test_warm_page_and_original_receipt_are_readonly_even_when_all_db_connects_forbidden(restore_host, monkeypatch):
    case = restore_host
    operation = case.client.post(BASE + "/backups/restore", json=case.intent(), buffered=True).json["data"]["operation"]
    paths = [Path(case.path)] + list(case.backups.glob("*.db")) + list(Path(case.journal.directory).glob("*.json"))
    before = {str(path): file_fingerprint(str(path)) for path in paths}
    def forbidden(*args, **kwargs):
        raise AssertionError("DU read-only maintenance view opened SQLite")
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    for suffix in ("", "?view=system", "?reference=" + operation["request_key"], "?kind=job&reference=" + operation["job_ref"]):
        response = case.client.get("/workbench" + suffix, buffered=True)
        assert response.status_code == 503 and response.mimetype == "text/html"
        assert "重启整个软件" in response.get_data(as_text=True)
        assert operation["protection_filename"] in response.get_data(as_text=True)
        page = response.get_data(as_text=True)
        details = page.split('<summary>维护阶段与核对信息</summary>', 1)[1].split('</details>', 1)[0]
        assert operation["code"] in details and operation["request_key"] in details
        assert '<th scope="col">维护状态</th>' in page
    for suffix in ("/results/" + operation["request_key"], "/jobs/" + operation["job_ref"]):
        value = case.client.get(BASE + suffix, buffered=True).json
        assert value["data"]["operation"]["job_ref"] == operation["job_ref"]
        assert value["meta"]["result_source"] == "external_maintenance_journal"
    response = case.client.get("/workbench?download=diagnostic", buffered=True)
    assert response.status_code == 200 and response.mimetype == "application/json"
    assert json.loads(response.data)["result"]["operation"]["state"] == "succeeded"
    assert {str(path): file_fingerprint(str(path)) for path in paths} == before
