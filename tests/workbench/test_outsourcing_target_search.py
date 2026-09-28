"""Business order and literal keyword filtering remain bound to the read snapshot."""

import pytest

from tests.workbench.outsourcing_support import ROOT, api
from tests.workbench.outsourcing_support import outsourcing_case as _outsourcing_case  # noqa: F401


def test_targets_expose_sequence_piece_and_sort_by_business_route(outsourcing_case, monkeypatch):
    case = outsourcing_case
    case.conn.execute("UPDATE BatchOperations SET seq=40 WHERE op_code='XO1'")
    case.conn.execute("UPDATE BatchOperations SET seq=10 WHERE op_code='XO2'")
    case.conn.execute("UPDATE BatchOperations SET piece_id='B',seq=5 WHERE op_code='XO3'")
    case.conn.commit()
    response = api(case, monkeypatch).get(ROOT + "/targets")
    assert response.status_code == 200, response.get_json()
    rows = response.get_json()["data"]["items"]
    assert [(row["business_code"], row["sequence"], row["piece"]) for row in rows] == [
        ("XO2", 10, None), ("XO1", 40, None), ("XO3", 5, "B")]


@pytest.mark.parametrize("query,count", [("xb1", 3), ("XP1", 3), ("Part", 3), ("Supplier", 3),
                                        ("Heat treatment", 3), ("XO2", 1), ("%", 0), ("not-found", 0)])
def test_keyword_search_uses_batch_part_operation_supplier_and_literal_text(outsourcing_case, monkeypatch, query, count):
    response = api(outsourcing_case, monkeypatch).get(ROOT + "/targets", query_string={"query": query})
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["page"]["total"] == count


def test_search_applies_before_row_cap(outsourcing_case, monkeypatch):
    import core.services.workbench.outsourcing.source as source

    monkeypatch.setattr(source, "MAX_ROWS", 2)
    client = api(outsourcing_case, monkeypatch)
    assert client.get(ROOT + "/targets").status_code == 413
    filtered = client.get(ROOT + "/targets", query_string={"query": "XO1"})
    assert filtered.status_code == 200 and filtered.get_json()["data"]["page"]["total"] == 1


def test_search_paging_scope_and_data_drift_are_rejected(outsourcing_case, monkeypatch):
    case = outsourcing_case
    client = api(case, monkeypatch)
    scope = {"query": "heat", "size": 1, "batch_ref": case.entity_ref("batch", "XB1")}
    first = client.get(ROOT + "/targets", query_string=scope).get_json()
    page = {**scope, "page": 2, "snapshot_ref": first["meta"]["snapshot_ref"]}
    second = client.get(ROOT + "/targets", query_string=page)
    assert second.status_code == 200 and second.get_json()["data"]["items"][0]["business_code"] == "XO2"
    changed_scope = client.get(ROOT + "/targets", query_string={**page, "query": "supplier"})
    assert changed_scope.status_code == 409 and changed_scope.get_json()["error"]["code"] == "snapshot_stale"
    case.conn.execute("UPDATE BatchOperations SET piece_id='A' WHERE op_code='XO2'")
    case.conn.commit()
    changed_rows = client.get(ROOT + "/targets", query_string=page)
    assert changed_rows.status_code == 409 and changed_rows.get_json()["error"]["code"] == "snapshot_stale"


@pytest.mark.parametrize("query", ["x" * 201, "bad\x00query"])
def test_search_invalid_text_is_explicitly_rejected(outsourcing_case, monkeypatch, query):
    response = api(outsourcing_case, monkeypatch).get(ROOT + "/targets", query_string={"query": query})
    assert response.status_code == 400 and response.get_json()["committed"] is False
