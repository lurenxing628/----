"""Real Flask read/preview routes, stale references and zero-write boundaries."""

import sqlite3

import pytest

from core.services.workbench.process_queries import WorkbenchProcessQueryService
from tests.workbench.process_query_support import process_read_application, ref_for, stored

BASE = "/api/workbench/v1/entities/part"


def detail(client, code="PROC-001"):
    with sqlite3.connect(client.application.config["DATABASE_PATH"]) as conn:
        ref = ref_for(conn, code=code)
    response = client.get(BASE + "/" + ref)
    assert response.status_code == 200, response.get_json()
    return ref, response.get_json()


def preview(client, ref, body):
    return client.post("/api/workbench/v1/process/" + ref + "/route-preview", json=body)


def test_real_envelopes_list_navigation_and_preview_never_write(process_read_client):
    client = process_read_client
    path = client.application.config["DATABASE_PATH"]
    with sqlite3.connect(path) as conn:
        before = stored(conn)
    first = client.get(BASE, query_string={"size": 2})
    assert first.status_code == 200
    body = first.get_json()
    assert first.headers["Cache-Control"] == "no-store"
    assert body["data"]["page"]["total"] == 5
    assert body["meta"]["source"] == "production"
    second = client.get(BASE, query_string={"size": 2, "page": 2, "snapshot_ref": body["meta"]["snapshot_ref"]})
    assert second.status_code == 200 and len(second.get_json()["data"]["entities"]) == 2
    ref, current = detail(client)
    result = preview(client, ref, {"mode": "text", "route_raw": "10车削;20热处理;40未建工种", "snapshot_ref": current["meta"]["snapshot_ref"]})
    assert result.status_code == 200, result.get_json()
    payload = result.get_json()["data"]
    assert payload["part_ref"] == ref and payload["can_confirm_route"] is True
    assert payload["counts"] == {"operations": 3, "recognized": 2, "unknown": 1}
    assert payload["changes"] == {"added": [40], "removed": [30], "retained": [10, 20], "same_sequence_changed": []}
    assert payload["operations"][2]["source_suggestion"] is None
    assert payload["write_context"]["capabilities"]["process.route_confirm"] is True
    assert payload["baseline"]["external_group_count"] == 1
    assert current["data"]["capabilities"]["stage_confirm"] is True
    assert client.post(BASE + "/" + ref + "/stage-confirm", json={}).status_code in (404, 405)
    with sqlite3.connect(path) as conn:
        assert stored(conn) == before


@pytest.mark.parametrize("query", ["page=0", "page=2", "size=201", "sort=id", "stage=done", "page=1&page=2", "unknown=1"])
def test_bad_or_unbound_list_scope_rejects(process_read_client, query):
    response = process_read_client.get(BASE + "?" + query)
    assert response.status_code in (400, 409)
    assert response.get_json()["committed"] is False


@pytest.mark.parametrize("mutate", [
    "UPDATE Parts SET part_name='新名称' WHERE part_no='PROC-001'",
    "UPDATE PartOperations SET unit_hours=.75 WHERE part_no='PROC-001' AND seq=10",
    "UPDATE ExternalGroups SET total_days=9 WHERE group_id='PROC-G'",
    "UPDATE OpTypes SET name='精车' WHERE op_type_id='PROC-IN'",
    "UPDATE Suppliers SET default_days=4 WHERE supplier_id='PROC-S'",
    "DELETE FROM WorkbenchSupplierOpTypes WHERE supplier_id='PROC-S'",
    "INSERT INTO WorkbenchSupplierProfiles(supplier_id,inactive_reason) VALUES ('PROC-S','pending_review')",
    "INSERT INTO WorkbenchOpTypePolicies(op_type_id,default_merge_mode) VALUES ('PROC-EX','merged')",
])
def test_each_reference_fact_change_rejects_original_preview_context(process_read_client, mutate):
    client = process_read_client
    ref, current = detail(client)
    with sqlite3.connect(client.application.config["DATABASE_PATH"]) as conn:
        conn.execute(mutate)
        conn.commit()
        before = stored(conn)
    response = preview(client, ref, {"mode": "text", "route_raw": "10车削", "snapshot_ref": current["meta"]["snapshot_ref"]})
    assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"
    with sqlite3.connect(client.application.config["DATABASE_PATH"]) as conn:
        assert stored(conn) == before


def test_list_snapshot_cannot_be_used_as_detail_or_preview_context(process_read_client):
    client = process_read_client
    listing = client.get(BASE).get_json()
    ref, current = detail(client)
    response = preview(client, ref, {"mode": "rows", "rows": [{"seq": 10, "op_type_name": "车削"}], "snapshot_ref": listing["meta"]["snapshot_ref"]})
    assert response.status_code == 409
    response = preview(client, ref, {"mode": "rows", "rows": [{"seq": 10, "op_type_name": "检验"}], "snapshot_ref": current["meta"]["snapshot_ref"]})
    assert response.status_code == 200
    assert response.get_json()["data"]["changes"]["same_sequence_changed"] == [10]


@pytest.mark.parametrize("raw", ['{"mode":"text","mode":"rows","route_raw":"10车削"}', '[]', '{',
                                  '{"mode":"rows","rows":[{"seq":10,"seq":20,"op_type_name":"车削"}]}'])
def test_malformed_and_duplicate_json_fields_fail_without_writing(process_read_client, raw):
    client = process_read_client
    ref, _ = detail(client)
    response = client.post("/api/workbench/v1/process/" + ref + "/route-preview", data=raw, content_type="application/json")
    assert response.status_code == 400 and response.get_json()["committed"] is False


def test_preview_storage_failure_is_not_an_uncertain_save(process_read_client, monkeypatch):
    client = process_read_client
    ref, _ = detail(client)

    def broken(_self):
        raise RuntimeError("read fixture failed")

    monkeypatch.setattr(WorkbenchProcessQueryService, "facts", broken)
    response = preview(client, ref, {"mode": "text", "route_raw": "10车削"})
    assert response.status_code == 500 and response.get_json()["committed"] is False
    assert "request_key" not in response.get_json()["error"]


def test_full_sqlite_sequence_is_displayed_exactly_and_unsafe_row_number_rejected(process_read_client):
    client = process_read_client
    maximum = (1 << 63) - 1
    with sqlite3.connect(client.application.config["DATABASE_PATH"]) as conn:
        conn.execute("UPDATE PartOperations SET seq=? WHERE part_no='PROC-001' AND seq=10", (maximum,))
        conn.commit()
    ref, result = detail(client)
    assert result["data"]["operations"][-1]["sequence"] == str(maximum)
    response = preview(client, ref, {"mode": "text", "route_raw": str(maximum) + "车削"})
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["operations"][0]["sequence"] == str(maximum)
    assert data["changes"]["retained"] == [str(maximum)]
    response = preview(client, ref, {"mode": "rows", "rows": [{"seq": maximum, "op_type_name": "车削"}]})
    assert response.status_code == 422 and response.get_json()["committed"] is False


def test_oversized_preview_body_is_explicitly_rejected(process_read_client):
    client = process_read_client
    ref, _ = detail(client)
    response = client.post("/api/workbench/v1/process/" + ref + "/route-preview", data=' ' * (1024 * 1024 + 1), content_type="application/json")
    assert response.status_code == 413 and response.get_json()["committed"] is False


@pytest.mark.parametrize("sequence", [0, -10, "bad", 1.5])
def test_bad_legacy_sequence_remains_visible_and_blocks_automatic_replacement(process_read_client, sequence):
    client = process_read_client
    with sqlite3.connect(client.application.config["DATABASE_PATH"]) as conn:
        conn.execute("UPDATE PartOperations SET seq=? WHERE part_no='PROC-001' AND seq=10", (sequence,))
        conn.commit()
        before = stored(conn)
    ref, current = detail(client)
    bad = [row for row in current["data"]["operations"] if any(item["code"] == "sequence_invalid" for item in row["issues"])]
    assert len(bad) == 1 and str(bad[0]["sequence"]) == str(sequence)
    response = preview(client, ref, {"mode": "text", "route_raw": "10车削"})
    assert response.status_code == 200
    assert not response.get_json()["data"]["can_confirm_route"]
    assert any(item["code"] == "legacy_sequence_invalid" for item in response.get_json()["data"]["diagnostics"])
    with sqlite3.connect(client.application.config["DATABASE_PATH"]) as conn:
        assert stored(conn) == before


@pytest.mark.parametrize("value", ["bad hours", -1, float("inf")])
def test_bad_legacy_hours_are_readable_as_unknown_not_zero(process_read_client, value):
    client = process_read_client
    with sqlite3.connect(client.application.config["DATABASE_PATH"]) as conn:
        conn.execute("UPDATE PartOperations SET unit_hours=? WHERE part_no='PROC-001' AND seq=10", (value,))
        conn.commit()
        before = stored(conn)
    _, current = detail(client)
    row = current["data"]["operations"][0]
    assert row["unit_hours"] is None and any(item["code"] == "value_invalid" for item in row["issues"])
    with sqlite3.connect(client.application.config["DATABASE_PATH"]) as conn:
        assert stored(conn) == before
