"""Production date conversion and fractional material allocation over HTTP."""

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from core.services.material.stage_availability import MaterialAvailability, covers_quantity
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.batch.file_preview import BatchImportPreview
from tests.workbench.batch_support import (
    BASE,
    assert_error,
    create_batch_client,
    create_input,
    detail,
    list_data,
    post,
    ref_for,
    state,
)
from tests.workbench.test_batch_actions import confirm
from tests.workbench.test_batch_quantity_split import prepare, preview


@pytest.fixture
def split_client():
    conn = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
    try:
        yield create_batch_client(conn)
    finally:
        conn.close()


def split_confirm(client, proposal):
    response = confirm(client, proposal, path="/" + ref_for(client) + "/split-confirm", key="split-regression-confirm-01")
    assert response.status_code == 200, response.get_json()
    return detail(client, response.get_json()["data"]["child_ref"])["data"]


@pytest.mark.parametrize("ready_day,expected", [("2026-09-20", "2026-09-28"), ("2026-10-02", "2026-10-02")])
def test_split_ready_date_uses_real_sqlite_date_conversion(split_client, ready_day, expected):
    client = split_client
    prepare(client)
    client.batch_conn.execute("UPDATE Batches SET ready_date=? WHERE batch_id='FREE-001'", (ready_day,))
    client.batch_conn.commit()
    assert type(client.batch_conn.execute("SELECT ready_date FROM Batches WHERE batch_id='FREE-001'").fetchone()[0]) is date
    child = split_confirm(client, preview(client))
    assert child["fields"]["quantity"] == 40 and child["fields"]["ready_date"] == expected


@pytest.mark.parametrize("total,required,initial,arrival,expected", [
    (7, 1, .2, .6, 5), (9, 1, .1, .5, 5), (13, .7, .12, .3, 7),
])
def test_fractional_split_stays_ready_without_inventing_stock(split_client, total, required, initial, arrival, expected):
    client, conn = split_client, split_client.batch_conn
    conn.execute("UPDATE Materials SET status='active' WHERE material_id='MAT1'")
    conn.execute("UPDATE Batches SET quantity=? WHERE batch_id='FREE-001'", (total,))
    conn.commit()
    response = post(client, "materials_update", {"removed_keys": [], "rows": [{"row_key": None,
        "material_ref": ref_for(client, "material", "MAT1"), "required_quantity": required,
        "available_quantity": initial, "arrivals": [{"arrival_date": "2026-09-28", "quantity": arrival}]}]})
    assert response.status_code == 200, response.get_json()
    child = split_confirm(client, preview(client))
    facts = BatchFacts(conn).load()
    batch = next(row for row in facts["Batches"] if row["batch_id"] == child["business_code"])
    availability = MaterialAvailability(facts)
    assert child["fields"]["quantity"] == expected
    assert availability.readiness_state(batch, "2026-09-28")[0] == "yes"
    assert availability.release(availability.requirements[batch["batch_id"]][0]) == "2026-09-28"
    required_sum, stock_sum = conn.execute("SELECT sum(required_qty),sum(available_qty) FROM BatchMaterials WHERE batch_id IN (?,?)",
                                          ("FREE-001", child["business_code"])).fetchone()
    assert required_sum == pytest.approx(required, rel=1e-15, abs=0)
    assert stock_sum == pytest.approx(initial, rel=1e-15, abs=0)
    assert conn.execute("SELECT sum(quantity) FROM BatchMaterialArrivals").fetchone()[0] == pytest.approx(arrival, rel=1e-15, abs=0)


@pytest.mark.parametrize("available,required", [("0.714285714284", "0.714285714285"), ("0", "0.00000000000001"),
                                             ("9007199254740990", "9007199254740991")])
def test_real_shortages_are_not_rounded_into_stock(available, required):
    assert not covers_quantity(Decimal(available), Decimal(required))


@pytest.mark.parametrize("owner", ["source", "child"])
def test_split_history_blocks_delete_in_ui_command_and_file_preview(split_client, owner):
    client = split_client
    prepare(client)
    child = split_confirm(client, preview(client))
    ref = child["ref"] if owner == "child" else ref_for(client)
    entity = detail(client, ref)["data"]
    response = post(client, "materials_update", {"rows": [], "removed_keys": [row["row_key"] for row in entity["materials"]["requirements"]]},
                    ref=ref, key="clear-split-regression-01")
    assert response.status_code == 200
    entity = detail(client, ref)["data"]
    assert not entity["write_context"]["capabilities"].get("batch.delete", False)
    assert any("数量拆分" in reason["message"] for reason in entity["write_context"]["blocked_reasons"])
    before = state(client)
    response = post(client, "delete", {}, ref=ref, key="delete-split-regression-01")
    assert 400 <= response.status_code < 500 and response.get_json()["committed"] is False
    facts = BatchFacts(client.batch_conn).load()
    deleted = BatchImportPreview(facts, "replace").deleted()
    assert any("数量拆分" in error for row in deleted if row["entity_ref"] == ref for error in row["errors"])
    assert state(client) == before
    assert post(client, "create", create_input(client, "UNSPLIT-001"), key="unsplit-control-create-01").status_code == 200
    normal = ref_for(client, key="UNSPLIT-001")
    before = state(client)
    for refs in ([ref], [normal, ref]):
        response = client.post(BASE + "/bulk-preview", json={"scope": {},
            "snapshot_ref": list_data(client)["meta"]["snapshot_ref"],
            "input": {"action": "delete", "refs": refs, "patch": {}}})
        error = assert_error(response, "constraint_conflict", 409)
        assert "数量拆分" in error["error"]["message"]
        assert state(client) == before
