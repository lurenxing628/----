"""Batch ordinals agree across reads/writes and remain bound to their write snapshot."""

import pytest

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
from core.services.workbench.batch.projection import BatchProjection
from tests.workbench.batch_support import assert_error, batch_database, detail, post, ref_for

_batch_fixture = batch_database


def _seed_requirements(client):
    conn = client.batch_conn
    conn.execute("""INSERT INTO Materials(material_id,name,unit,status) VALUES
        ('MAT2','第二种物料','件','active'),('MAT3','第三种物料','件','active')""")
    conn.execute("""INSERT INTO BatchMaterials(id,batch_id,material_id,required_qty,available_qty,ready_status) VALUES
        (90002,'FREE-001','MAT1',10,2,'partial'),(90011,'FREE-001','MAT2',10,3,'partial')""")
    conn.commit()


def _requirements(conn):
    return [tuple(row) for row in conn.execute("""SELECT id,material_id,required_qty,available_qty
        FROM BatchMaterials WHERE batch_id='FREE-001' ORDER BY id""")]


def test_projection_and_proposal_share_ordinals_for_unordered_sparse_requirement_ids(batch_client):
    client = batch_client
    _seed_requirements(client)
    ref = ref_for(client)
    reader = BatchFacts(client.batch_conn)
    facts = reader.load()
    facts["BatchMaterials"] = list(reversed(facts["BatchMaterials"]))
    batch = next(row for row in facts["Batches"] if row["batch_id"] == "FREE-001")
    projected = BatchProjection(facts).materials(batch)["requirements"]
    old, final = WorkbenchBatchMaterialService(client.batch_conn, reader=reader)._proposed(
        ref, {"rows": [], "removed_keys": []}, batch, facts,
    )
    expected = [ref + "0000000000000001", ref + "0000000000000002"]
    assert [row["row_key"] for row in projected] == list(old) == list(final) == expected
    assert [old[key]["id"] for key in expected] == [90002, 90011]
    assert [row["business_code"] for row in projected] == ["MAT1", "MAT2"]
    assert all(len(row["row_key"]) == 64 and "id" not in row for row in projected)
    assert _requirements(client.batch_conn) == [(90002, "MAT1", 10.0, 2.0), (90011, "MAT2", 10.0, 3.0)]


def test_reused_ordinal_rejects_old_snapshot_and_fresh_keys_modify_remove_the_right_requirement(batch_client):
    client = batch_client
    _seed_requirements(client)
    ref = ref_for(client)
    original = detail(client)["data"]
    previous_second = original["materials"]["requirements"][1]
    conn = client.batch_conn
    conn.execute("DELETE FROM BatchMaterials WHERE id=90002")
    conn.execute("""INSERT INTO BatchMaterials(id,batch_id,material_id,required_qty,available_qty,ready_status)
        VALUES (90019,'FREE-001','MAT3',10,4,'partial')""")
    conn.commit()
    before = _requirements(conn)
    response = post(client, "materials_update", {"removed_keys": [], "rows": [{
        "row_key": previous_second["row_key"], "material_ref": previous_second["material_ref"],
        "required_quantity": 10, "available_quantity": 9,
    }]}, context=original["write_context"], key="material-old-ordinal-snapshot-001")
    assert_error(response, "stale_write")
    assert _requirements(conn) == before

    current = detail(client)["data"]
    first, second = current["materials"]["requirements"]
    assert first["business_code"] == "MAT2" and first["row_key"] == ref + "0000000000000001"
    assert second["business_code"] == "MAT3" and second["row_key"] == previous_second["row_key"]
    response = post(client, "materials_update", {"removed_keys": [], "rows": [{
        "row_key": first["row_key"], "material_ref": first["material_ref"],
        "required_quantity": 10, "available_quantity": 9,
    }]}, context=current["write_context"], key="material-fresh-ordinal-update-001")
    assert response.status_code == 200, response.get_json()
    assert _requirements(conn) == [(90011, "MAT2", 10.0, 9.0), (90019, "MAT3", 10.0, 4.0)]
    response = post(client, "materials_update", {"rows": [], "removed_keys": [first["row_key"]]},
                    key="material-fresh-ordinal-remove-001")
    assert response.status_code == 200, response.get_json()
    remaining = detail(client)["data"]["materials"]["requirements"]
    assert _requirements(conn) == [(90019, "MAT3", 10.0, 4.0)]
    assert len(remaining) == 1 and remaining[0]["business_code"] == "MAT3"
    assert remaining[0]["row_key"] == ref + "0000000000000001"



def test_saving_requirements_rejects_stored_arrival_with_invalid_date(batch_client):
    client = batch_client
    _seed_requirements(client)
    conn = client.batch_conn
    # 库里遗留的坏到料日期不能按字符串大小算成已到料，整次保存按物料资料无效拒绝。
    conn.execute("INSERT INTO BatchMaterialArrivals(requirement_id,arrival_date,quantity) VALUES (90002,'2026-00-99',8)")
    conn.commit()
    before = _requirements(conn)
    other = detail(client)["data"]["materials"]["requirements"][1]
    response = post(client, "materials_update", {"removed_keys": [], "rows": [{
        "row_key": other["row_key"], "material_ref": other["material_ref"],
        "required_quantity": 10, "available_quantity": 9,
    }]}, key="material-invalid-arrival-date-001")
    assert_error(response, "material_unknown")
    assert _requirements(conn) == before


def test_requirement_readiness_rejects_blob_arrival_date_without_comparing_storage_types(batch_client):
    client = batch_client
    _seed_requirements(client)
    conn = client.batch_conn
    conn.execute("INSERT INTO BatchMaterialArrivals(requirement_id,arrival_date,quantity) VALUES (90002,?,8)", (b"2026-01-01",))
    conn.commit()
    with TransactionManager(conn).transaction():
        with pytest.raises(WorkbenchCommandRejected) as error:
            WorkbenchBatchMaterialService(conn).apply_normalized(ref_for(client), {"removed_keys": [], "rows": []})
    assert error.value.code == "material_unknown"


def test_saving_requirements_rejects_future_arrival_with_invalid_quantity(batch_client):
    client = batch_client
    _seed_requirements(client)
    conn = client.batch_conn
    # 齐套日之后的到料也要和排产读取同一口径先校验，坏数量不能因日期在后被跳过而保存成功。
    conn.execute("INSERT INTO BatchMaterialArrivals(requirement_id,arrival_date,quantity) VALUES (90002,'9999-12-31','bad')")
    conn.commit()
    before = _requirements(conn)
    other = detail(client)["data"]["materials"]["requirements"][1]
    response = post(client, "materials_update", {"removed_keys": [], "rows": [{
        "row_key": other["row_key"], "material_ref": other["material_ref"],
        "required_quantity": 10, "available_quantity": 9,
    }]}, key="material-future-invalid-quantity-001")
    assert_error(response, "material_unknown")
    assert _requirements(conn) == before


def test_detail_projects_blob_arrival_date_and_invalid_quantity_as_issues(batch_client):
    client = batch_client
    _seed_requirements(client)
    conn = client.batch_conn
    conn.execute("INSERT INTO BatchMaterialArrivals(requirement_id,arrival_date,quantity) VALUES (90002,?,8),(90002,'2026-01-02','bad')",
                 (b"2026-01-01",))
    conn.commit()
    first = detail(client)["data"]["materials"]["requirements"][0]
    assert first["business_code"] == "MAT1"
    assert first["arrivals"] == [{"arrival_date": "b'2026-01-01'", "quantity": 8.0},
                                 {"arrival_date": "2026-01-02", "quantity": None}]
    messages = [item["message"] for item in first["issues"]]
    assert "到料日期原值不合法，请核对。" in messages
    assert "分批到料数量原值不合法，请核对。" in messages
