"""Readable labels are nullable projections of verified, snapshot-local instances."""

import sqlite3

import pytest

from core.infrastructure.database import get_connection
from data.repositories.workbench_outsourcing_source_repo import _target_text
from tests.workbench.outsourcing_support import ROOT, api
from tests.workbench.outsourcing_targets_labels_support import change_origin, storage, target_rows
from tests.workbench.outsourcing_targets_labels_support import targets_case as _targets_case  # noqa: F401


def test_current_http_labels_preserve_old_fields_and_all_storage(targets_case, monkeypatch):
    case = targets_case
    before = storage(case.conn)
    response = api(case, monkeypatch).get(ROOT + "/targets")
    assert response.status_code == 200, response.get_json()
    data = response.get_json()["data"]
    assert data["page"]["total"] == 3 and data["dates_inferred"] is False
    for item in data["items"]:
        assert item["batch"] == {"ref": case.entity_ref("batch", "XB1"), "business_code": "XB1", "label": "Part"}
        assert item["supplier"] == {"ref": case.entity_ref("supplier", "XS1"), "business_code": "XS1", "label": "Supplier"}
        assert {key: value for key, value in item.items() if key not in ("batch", "supplier")} == {
            "operation_ref": case.operation_ref(item["business_code"]), "business_code": item["business_code"],
            "label": "Heat treatment", "batch_ref": item["batch"]["ref"], "supplier_ref": item["supplier"]["ref"],
            "outsourcing_ref": None, "can_register": True, "issues": []}
    assert storage(case.conn) == before


@pytest.mark.parametrize("kind", ["batch", "supplier", "operation", "origin"])
def test_missing_or_retired_identity_never_fills_labels(targets_case, kind):
    case = targets_case
    ref = case.operation_ref("XO1")
    if kind == "origin":
        change_origin(case, ref, None)
    elif kind == "operation":
        case.conn.execute("UPDATE WorkbenchPlanSourceRefs SET active=0 WHERE ref=?", (ref,))
    else:
        case.conn.execute("UPDATE WorkbenchEntityRefs SET active=0 WHERE kind=?", (kind,))
    case.conn.commit()
    before = storage(case.conn)
    item = next(row for row in target_rows(case) if row["business_code"] == "XO1")
    assert item["batch"] is None and item["supplier"] is None
    assert item["can_register"] is False and item["issues"]
    assert storage(case.conn) == before


@pytest.mark.parametrize("kind,table,column", [("batch", "Batches", "batch_id"), ("supplier", "Suppliers", "supplier_id")])
def test_active_ref_with_missing_source_is_unknown(targets_case, kind, table, column):
    case = targets_case
    name = "wb_ref_" + kind + "_delete"
    # Retain the identity while simulating a missing legacy source row.
    guard = case.conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
    assert guard is not None
    case.conn.execute("PRAGMA foreign_keys=OFF")
    case.conn.execute('DROP TRIGGER "' + name + '"')
    case.conn.execute('DELETE FROM "' + table + '" WHERE "' + column + '"=?', ("XB1" if kind == "batch" else "XS1",))
    case.conn.execute(guard[0])
    case.conn.commit()
    before = storage(case.conn)
    assert all(row[kind] is None for row in target_rows(case))
    assert storage(case.conn) == before


@pytest.mark.parametrize("kind,table", [("batch", "Batches"), ("supplier", "Suppliers")])
def test_registered_same_number_replacement_never_uses_new_entity_label(targets_case, kind, table):
    case = targets_case
    registered = case.confirm(case.preview(case.payload()))["data"]["outsourcing_ref"]
    old_ref = case.payload()["target"][kind + "_ref"]
    case.conn.execute("PRAGMA foreign_keys=OFF")
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    case.conn.execute("INSERT OR REPLACE INTO " + table + " SELECT * FROM " + table)
    case.conn.execute("UPDATE " + table + " SET " + ("part_name" if kind == "batch" else "name") + "='Replacement name'")
    case.conn.commit()
    before = storage(case.conn)
    item = next(row for row in target_rows(case) if row["outsourcing_ref"] == registered)
    assert item[kind + "_ref"] != old_ref
    assert item[kind] is None and item["can_register"] is False
    assert storage(case.conn) == before


def test_batch_replacement_without_receipt_still_requires_recorded_birth(targets_case):
    case = targets_case
    case.conn.execute("PRAGMA foreign_keys=OFF")
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    case.conn.execute("INSERT OR REPLACE INTO Batches SELECT * FROM Batches")
    case.conn.commit()
    for item in target_rows(case):
        assert item["batch"] is None and item["supplier"] is None
        assert item["can_register"] is False and item["issues"][0]["code"] == "identity_drift"


def test_operation_replacement_is_new_target_not_old_receipt(targets_case):
    case = targets_case
    old_ref = case.operation_ref("XO1")
    case.confirm(case.preview(case.payload()))
    case.conn.execute("PRAGMA foreign_keys=OFF")
    case.conn.execute("PRAGMA recursive_triggers=OFF")
    case.conn.execute("INSERT OR REPLACE INTO BatchOperations SELECT * FROM BatchOperations WHERE op_code='XO1'")
    case.conn.commit()
    item = next(row for row in target_rows(case) if row["business_code"] == "XO1")
    assert item["operation_ref"] != old_ref and item["outsourcing_ref"] is None
    assert item["batch"]["business_code"] == "XB1" and item["supplier"]["business_code"] == "XS1"


@pytest.mark.parametrize("kind,table,column,raw", [
    (kind, table, column, raw)
    for kind, table, column in [("batch", "Batches", "part_name"), ("supplier", "Suppliers", "name")]
    for raw in [None, "", " \t ", b"label\x00\xff", "bad\x00text"]
    if kind != "supplier" or raw is not None
])
def test_raw_unknown_names_remain_null_not_encoded_or_fallback(targets_case, raw, kind, table, column):
    case = targets_case
    case.conn.execute("UPDATE " + table + " SET " + column + "=?", (raw,))
    case.conn.commit()
    before = storage(case.conn)
    case.conn.execute("PRAGMA query_only=ON")
    for item in target_rows(case):
        assert item[kind]["label"] is None
        assert item[kind]["business_code"] == ("XB1" if kind == "batch" else "XS1")
    assert storage(case.conn) == before


@pytest.mark.parametrize("kind,table,column,old", [("batch", "Batches", "batch_id", "XB1"),
                                                    ("supplier", "Suppliers", "supplier_id", "XS1")])
def test_raw_blob_business_code_without_verifiable_ref_is_unknown(targets_case, kind, table, column, old):
    case = targets_case
    ref = case.entity_ref(kind, old)
    case.conn.execute("PRAGMA foreign_keys=OFF")
    case.conn.execute("UPDATE " + table + " SET " + column + "=?", (b"raw-code\xff",))
    case.conn.execute("UPDATE BatchOperations SET " + column + "=?", (b"raw-code\xff",))
    case.conn.commit()
    assert case.conn.execute("SELECT active FROM WorkbenchEntityRefs WHERE ref=?", (ref,)).fetchone()[0] == 1
    before = storage(case.conn)
    for item in target_rows(case):
        assert item[kind] is None and item[kind + "_ref"] is None
        assert item["can_register"] is False and item["issues"][0]["code"] == "identity_missing"
    assert storage(case.conn) == before


@pytest.mark.parametrize("raw", [None, 0, 42, 1.5, float("inf"), b"raw\xff", "", " \t", "bad\x00text"])
def test_raw_sqlite_nontext_values_are_never_display_strings(targets_case, raw):
    value = targets_case.conn.execute("SELECT CASE WHEN 1 THEN ? END", (raw,)).fetchone()[0]
    assert _target_text(value) is None


def test_target_labels_use_caller_snapshot_and_fingerprint(targets_case):
    case = targets_case
    case.conn.execute("PRAGMA journal_mode=WAL")
    other = get_connection(str(case.path))
    try:
        with case.reader.read_snapshot():
            first = case.reader.targets()
            other.execute("UPDATE Suppliers SET name='Concurrent supplier'")
            other.commit()
            assert case.reader.targets() == first
        with case.reader.read_snapshot():
            refreshed = case.reader.targets()
        assert refreshed["fingerprint"] != first["fingerprint"]
        assert all(item["supplier"]["label"] == "Concurrent supplier" for item in refreshed["items"])
    finally:
        other.close()


@pytest.mark.parametrize("table,column", [("Batches", "part_name"), ("Suppliers", "name")])
def test_http_pages_reject_changed_labels_and_keep_scope(targets_case, monkeypatch, table, column):
    case = targets_case
    client = api(case, monkeypatch)
    scope = {"size": 1, "batch_ref": case.entity_ref("batch", "XB1")}
    first = client.get(ROOT + "/targets", query_string=scope).get_json()
    query = {**scope, "page": 2, "snapshot_ref": first["meta"]["snapshot_ref"]}
    second = client.get(ROOT + "/targets", query_string=query)
    assert second.status_code == 200
    assert second.get_json()["data"]["items"][0]["operation_ref"] != first["data"]["items"][0]["operation_ref"]
    case.conn.execute("UPDATE " + table + " SET " + column + "='Renamed'")
    case.conn.commit()
    stale = client.get(ROOT + "/targets", query_string=query)
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"


def test_snapshot_required_and_storage_failure_not_swallowed(targets_case):
    case = targets_case
    with pytest.raises(RuntimeError, match="snapshot"):
        case.reader.targets()
    def deny_label_read(action, table, column, database, source):
        return sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and table == "Batches" else sqlite3.SQLITE_OK

    case.conn.set_authorizer(deny_label_read)
    try:
        with case.reader.read_snapshot():
            with pytest.raises(sqlite3.DatabaseError):
                case.reader.targets()
    finally:
        case.conn.set_authorizer(None)
