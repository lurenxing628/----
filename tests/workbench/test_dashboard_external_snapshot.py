"""Host GETs are read-only and include full external evidence in the snapshot."""

import sqlite3
from datetime import date, datetime

import pytest

from core.infrastructure.database import get_connection
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.dashboard import WorkbenchDashboardService
from tests.workbench.dashboard_external_support import external_case as _external_case  # noqa: F401
from tests.workbench.dashboard_external_support import storage
from tests.workbench.dashboard_support import NOW, api
from tests.workbench.dashboard_support import dashboard_case as _dashboard_case  # noqa: F401
from tests.workbench.outsourcing_support import api as outsourcing_api

ROOT = "/api/workbench/v1/dashboard"


@pytest.mark.parametrize("due", [date(2026, 9, 11), None, b"invalid-date\x00\xff", 42])
def test_host_get_is_query_only_and_preserves_typedraw(external_case, monkeypatch, due):
    case = external_case
    case.register()
    case.conn.execute("UPDATE Batches SET due_date=?,remark=? WHERE batch_id='XB1'", (due, b"\x00raw\xff"))
    case.conn.commit()
    before = storage(case.conn)
    connections, detected = [], []
    original = sqlite3.connect

    def connect(*args, **kwargs):
        detected.append(kwargs.get("detect_types"))
        return original(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", connect)

    def factory(path):
        conn = get_connection(str(path))
        assert conn.execute('SELECT ? AS "sample [date]"', ("2026-09-11",)).fetchone()[0] == date(2026, 9, 11)
        conn.execute("PRAGMA query_only=ON")
        connections.append(conn)
        return conn

    client = api(case, monkeypatch, connect_factory=factory)
    response = client.get(ROOT)
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["categories"]["external"]["known_risk_count"] == 1
    assert response.headers["Cache-Control"] == "no-store"
    assert storage(case.conn) == before
    assert detected and set(detected) == {sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES}
    assert connections


@pytest.mark.parametrize("change", ["register", "return", "unknown_source", "unregistered_supplier"])
def test_external_changes_invalidate_dashboard_pagination_snapshot(external_case, monkeypatch, change):
    case = external_case
    ref = case.register() if change == "return" else None
    client = api(case, monkeypatch, connect_factory=lambda path: get_connection(str(path)))
    first = client.get(ROOT, query_string={"size": 1}).get_json()
    assert first["ok"] is True and first["data"]["page"]["total"] > 1
    query = {"size": 1, "page": 2, "snapshot_ref": first["meta"]["snapshot_ref"]}
    second = client.get(ROOT, query_string=query)
    assert second.status_code == 200, second.get_json()
    assert second.get_json()["data"]["categories"]["external"] == first["data"]["categories"]["external"]
    if change == "register":
        case.register()
    elif change == "return":
        case.returned(ref)
    elif change == "unknown_source":
        case.conn.execute("PRAGMA ignore_check_constraints=ON")
        case.conn.execute("UPDATE BatchOperations SET source=? WHERE op_code='XO1'", (b"external",))
        case.conn.commit()
    else:
        case.conn.execute("UPDATE Suppliers SET remark=? WHERE supplier_id='XS1'", (b"changed\x00\xff",))
        case.conn.commit()
    stale = client.get(ROOT, query_string=query)
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"
    assert client.get(ROOT).status_code == 200


def test_snapshot_keeps_factory_time_at_overdue_boundary(external_case, monkeypatch):
    case = external_case
    for index in range(1, 4):
        case.register(index, planned="2026-09-10T12:00:00")
    client = api(case, monkeypatch, connect_factory=lambda path: get_connection(str(path)))
    first = client.get(ROOT, query_string={"size": 1}).get_json()
    assert first["data"]["categories"]["external"]["risk_count"] == 0
    import web.routes.workbench.dashboard as module

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 9, 10, 12, 0, 1)

    monkeypatch.setattr(module, "datetime", Later)
    old = client.get(ROOT, query_string={"size": 1, "page": 2, "snapshot_ref": first["meta"]["snapshot_ref"]})
    assert old.status_code == 200, old.get_json()
    assert old.get_json()["data"]["categories"]["external"]["risk_count"] == 0
    fresh = client.get(ROOT).get_json()
    assert fresh["data"]["categories"]["external"]["risk_count"] == 3
    assert fresh["meta"]["as_of"] != first["meta"]["as_of"]


def test_independent_receipt_pages_history_and_execution_boundary(external_case, monkeypatch):
    case = external_case
    refs = [case.register(index) for index in range(1, 4)]
    client = outsourcing_api(case.shipments, monkeypatch)
    path = "/api/workbench/v1/outsourcing/receipts"
    first = client.get(path, query_string={"size": 1}).get_json()
    token = first["meta"]["snapshot_ref"]
    second = client.get(path, query_string={"size": 1, "page": 2, "snapshot_ref": token}).get_json()
    assert first["data"]["page"]["total"] == second["data"]["page"]["total"] == 3
    assert first["data"]["items"][0]["outsourcing_ref"] != second["data"]["items"][0]["outsourcing_ref"]
    assert first["data"]["items"][0]["execution"]["automatically_reported"] is False
    case.returned(refs[0])
    assert client.get(path, query_string={"size": 1, "page": 2, "snapshot_ref": token}).status_code == 409
    history = client.get(path + "/" + refs[0] + "/history").get_json()
    assert history["data"]["history"]["page"]["total"] == 2
    assert history["data"]["item"]["outsourcing_ref"] == refs[0]
    assert history["data"]["item"]["overdue"] is False


def test_complete_external_source_limit_never_truncates_to_zero(external_case, monkeypatch):
    import data.repositories.workbench_outsourcing_repo as repo

    case = external_case
    for index in range(1, 4):
        case.register(index)
    monkeypatch.setattr(repo, "MAX_ROWS", 2)
    reader = WorkbenchDashboardService(case.conn)
    with reader.read_snapshot(), pytest.raises(WorkbenchCommandRejected) as error:
        reader.read(NOW)
    assert error.value.code == "query_too_large"


def test_storage_read_error_is_not_disguised_as_unknown(external_case, monkeypatch):
    from data.repositories.workbench_outsourcing_repo import WorkbenchOutsourcingRepository

    def broken(self, batch_ref=None):
        raise sqlite3.OperationalError("injected read failure")

    monkeypatch.setattr(WorkbenchOutsourcingRepository, "refs", broken)
    with pytest.raises(sqlite3.OperationalError, match="injected read failure"):
        external_case.read()
