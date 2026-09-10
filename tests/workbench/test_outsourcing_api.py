"""Isolated route hook using production per-request connections."""

import pytest

from tests.workbench.outsourcing_support import ROOT, api, original_rows
from tests.workbench.outsourcing_support import outsourcing_case as _outsourcing_case  # noqa: F401


def preview(client, payload):
    response = client.post(ROOT + "/receipts/preview", json={"input": payload})
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


def confirm(client, draft, key="outsourcing-http-request-key"):
    return client.post(ROOT + "/receipts", json={"request_key": key, "input": draft["input"],
                       "write_token": draft["write_context"]["write_token"]})


def test_http_read_preview_confirm_history_replay(outsourcing_case, monkeypatch):
    case = outsourcing_case
    source = original_rows(case.conn)
    client = api(case, monkeypatch)
    targets = client.get(ROOT + "/targets")
    assert targets.status_code == 200
    assert targets.get_json()["data"]["page"]["total"] == 3
    assert targets.get_json()["data"]["dates_inferred"] is False
    empty = client.get(ROOT + "/receipts")
    assert empty.get_json()["data"]["items"] == []
    draft = preview(client, case.payload(merged=True))
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts").fetchone()[0] == 0
    response = confirm(client, draft)
    assert response.status_code == 200, response.get_json()
    first = response.get_json()
    ref = first["data"]["outsourcing_ref"]
    assert first["data"]["local_operator"] == "http-local-operator"
    assert confirm(client, draft).get_json()["receipt_ref"] == first["receipt_ref"]
    observed = client.get("/api/workbench/v1/commands/outsourcing-http-request-key").get_json()["data"]
    assert observed["receipt_ref"] == first["receipt_ref"]
    listing = client.get(ROOT + "/receipts", query_string={"status": "overdue"})
    assert listing.get_json()["data"]["page"]["total"] == 1
    detail = client.get(ROOT + "/receipts/" + ref)
    assert detail.status_code == 200, detail.get_json()
    assert detail.get_json()["data"]["item"]["execution"]["automatically_reported"] is False
    history = client.get(ROOT + "/receipts/" + ref + "/history").get_json()["data"]["history"]
    assert history["items"][0]["after"]["sent"] == draft["input"]["sent"]
    assert history["items"][0]["declared_operator"] == "Shipping clerk"
    assert original_rows(case.conn) == source


def test_http_sparse_update_and_stale_history_page(outsourcing_case, monkeypatch):
    case = outsourcing_case
    client = api(case, monkeypatch)
    ref = confirm(client, preview(client, case.payload())).get_json()["data"]["outsourcing_ref"]
    draft = preview(client, {"outsourcing_ref": ref, "returned": "2026-09-10T11:00:00", "confirmedState": "returned",
                            "reason": "Unloaded and counted", "declared_operator": "Receiver"})
    assert confirm(client, draft, "outsourcing-http-update-key").status_code == 200
    path = ROOT + "/receipts/" + ref + "/history"
    first = client.get(path, query_string={"size": 1}).get_json()
    token = first["meta"]["snapshot_ref"]
    page = client.get(path, query_string={"size": 1, "page": 2, "snapshot_ref": token})
    assert page.status_code == 200
    assert page.get_json()["data"]["history"]["items"][0]["before"] is None
    update = preview(client, {"outsourcing_ref": ref, "reason": "Rechecked", "declared_operator": "Supervisor"})
    assert confirm(client, update, "outsourcing-http-reconfirm-key").status_code == 200
    stale = client.get(path, query_string={"size": 1, "page": 2, "snapshot_ref": token})
    assert stale.status_code == 409
    assert stale.get_json()["error"]["code"] == "snapshot_stale"


@pytest.mark.parametrize("query", ["page=2", "size=0", "size=101", "page=1&page=2", "source=demo", "batch_id=XB1", "status=unknown"])
def test_http_query_contracts(outsourcing_case, monkeypatch, query):
    client = api(outsourcing_case, monkeypatch)
    response = client.get(ROOT + "/receipts?" + query)
    assert response.status_code in (400, 422)
    assert response.get_json()["committed"] is False


def test_http_unknown_fields_dates_and_preview_token_binding(outsourcing_case, monkeypatch):
    case = outsourcing_case
    client = api(case, monkeypatch)
    invalid = client.post(ROOT + "/receipts/preview", json={"input": case.payload(sent="bad")})
    assert invalid.status_code == 422
    draft = preview(client, case.payload())
    draft["input"]["reason"] = "Changed after preview"
    response = confirm(client, draft)
    assert response.status_code == 409
    assert response.get_json()["error"]["code"] == "stale_write"
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingFacts").fetchone()[0] == 0


def test_http_missing_ddl_503_and_no_install(outsourcing_case, monkeypatch):
    case = outsourcing_case
    client = api(case, monkeypatch)
    draft = preview(client, case.payload())
    case.conn.execute("DROP TRIGGER wb_outsourcing_fact_sequence")
    case.conn.commit()
    for response in (client.get(ROOT + "/receipts"), client.post(ROOT + "/receipts/preview", json={"input": case.payload()}), confirm(client, draft)):
        assert response.status_code == 503
        assert response.get_json()["error"]["code"] == "outsourcing_unavailable"
        assert response.get_json()["committed"] is False
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts").fetchone()[0] == 0


def test_http_failure_returns_shared_receipt_lookup(outsourcing_case, monkeypatch):
    case = outsourcing_case
    client = api(case, monkeypatch)
    draft = preview(client, case.payload())
    case.conn.execute("CREATE TRIGGER http_fail BEFORE INSERT ON WorkbenchOutsourcingFacts BEGIN SELECT RAISE(ABORT,'fixture'); END")
    case.conn.commit()
    response = confirm(client, draft)
    assert response.status_code == 500
    body = response.get_json()
    assert body["committed"] == "unknown"
    assert body["error"]["result_target"] == "/api/workbench/v1/commands/outsourcing-http-request-key"
    assert client.get(body["error"]["result_target"]).get_json()["data"] is None
    assert case.conn.execute("SELECT COUNT(*) FROM WorkbenchOutsourcingReceipts").fetchone()[0] == 0
