"""Production get_connection on real temporary files, not a plain sqlite substitute."""

import json
import sqlite3
from datetime import date

import pytest

from core.infrastructure.database import get_connection
from data.repositories.workbench_dashboard_source_repo import DashboardSourceRepository
from tests.workbench.dashboard_support import api, follow, source_rows
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401

ROOT = "/api/workbench/v1/dashboard"


@pytest.mark.parametrize("due,ready", [(date(2026, 9, 8), date(2026, 9, 9)), (None, None),
                                       (b"legacy-invalid-due", b"legacy-invalid-ready")])
def test_production_connection_date_null_blob_read_transition(dashboard_case, monkeypatch, due, ready):
    case = dashboard_case
    case.conn.execute("UPDATE Batches SET due_date=?,ready_date=?,remark=?", (due, ready, b"\x00legacy\xff"))
    case.conn.commit()
    original_connect, detected = sqlite3.connect, []

    def traced(*args, **kwargs):
        detected.append(kwargs.get("detect_types"))
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", traced)
    factory = lambda path: get_connection(str(path))
    probe = factory(case.path)
    try:
        # Explicitly prove COLNAMES conversion remains enabled as well as DECLTYPES.
        assert probe.execute('SELECT ? AS "probe [date]"', ("2026-09-08",)).fetchone()[0] == date(2026, 9, 8)
        if type(due) is date:
            assert type(probe.execute("SELECT due_date FROM Batches").fetchone()[0]) is date
        raw = DashboardSourceRepository(probe).table("Batches")[0]
        assert raw["due_date"] == (due.isoformat() if type(due) is date else due)
        assert raw["remark"] == b"\x00legacy\xff"
    finally:
        probe.close()
    before = source_rows(case.conn)
    client = api(case, monkeypatch, connect_factory=factory)
    response = client.get(ROOT)
    assert response.status_code == 200, response.get_json()
    loaded = response.get_json()
    item = next(row for row in loaded["data"]["items"] if row["category"] == "material")
    path = ROOT + "/items/" + item["item_ref"]
    detail = client.get(path, query_string={"snapshot_ref": loaded["meta"]["snapshot_ref"]})
    assert detail.status_code == 200, detail.get_json()
    command = client.post(path + "/transition", json={"request_key": "dashboard-host-command-01",
                          "write_token": item["write_context"]["write_token"], "input": follow()})
    assert command.status_code == 200, command.get_json()
    assert command.get_json()["result"] == "committed"
    assert command.get_json()["data"]["item_ref"] == item["item_ref"]
    assert source_rows(case.conn) == before
    facts = json.loads(case.conn.execute("SELECT source_facts_json FROM WorkbenchDashboardHistory").fetchone()[0])
    assert facts["facts"]["batch"]["remark"] == {"storage_type": "blob", "hex": b"\x00legacy\xff".hex()}
    assert detected and set(detected) == {sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES}


def test_uninstalled_schema_read_and_write_return_explicit_503(dashboard_case, monkeypatch):
    from tests.workbench.test_dashboard_schema import remove_dashboard

    case = dashboard_case
    item = case.item()
    remove_dashboard(case.conn)
    client = api(case, monkeypatch, connect_factory=lambda path: get_connection(str(path)))
    read = client.get(ROOT)
    write = client.post(ROOT + "/items/" + item["item_ref"] + "/transition", json={
        "request_key": "dashboard-host-missing-01", "write_token": item["write_context"]["write_token"], "input": follow()})
    for response in (read, write):
        assert response.status_code == 503
        assert response.get_json()["committed"] is False
        assert response.get_json()["error"]["code"] == "dashboard_unavailable"
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 0
