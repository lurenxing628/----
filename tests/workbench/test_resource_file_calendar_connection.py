"""Exercise resource files through factory connections with typed calendar dates."""

from io import BytesIO

import pytest

from tests.workbench.identity_metadata_support import business_snapshot
from tests.workbench.material_actions_api_support import database
from tests.workbench.test_resource_file_api import command, context, registered

BASE = "/api/workbench/v1"


@pytest.fixture
def native_client(db_env):
    from app import create_app

    client = registered(create_app())
    with database(client) as conn:
        conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('DATE-T','Date type','internal')")
        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('DATE-M','Date machine','DATE-T')")
        conn.execute("INSERT INTO Operators(operator_id,name,status,remark) VALUES ('DATE-O','Date operator','active','Keep note')")
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id,skill_level,is_primary) VALUES ('DATE-O','DATE-M','expert','yes')")
        conn.execute("INSERT INTO OperatorCalendar(operator_id,date,shift_start,shift_end,shift_hours,efficiency,remark) "
                     "VALUES ('DATE-O','2026-09-09','23:15','07:45',8.5,.625,'Keep personal night')")
        conn.commit()
    return client


def facts(client):
    with database(client) as conn:
        return business_snapshot(conn)


@pytest.mark.parametrize("fmt", ["csv", "xlsx"])
def test_native_calendar_export_roundtrip_and_blocked_bulk_are_readonly(native_client, fmt):
    client = native_client
    original = facts(client)
    bound = context(client, "operator")
    preview = client.post(BASE + "/exports/operator/preview", json={"selection": "all", **bound})
    assert preview.status_code == 200
    data = preview.get_json()["data"]
    downloaded = client.get(BASE + "/exports/operator", query_string={"export_ref": data["export_ref"], "format": fmt})
    assert downloaded.status_code == 200, downloaded.get_data(as_text=True)
    imported = client.post(BASE + "/imports/operator/preview", data={"file": (BytesIO(downloaded.data), "roundtrip." + fmt),
                           "format": fmt, "mode": "upsert"}, content_type="multipart/form-data")
    assert imported.status_code == 200, imported.get_data(as_text=True)
    result = imported.get_json()["data"]
    assert result["summary"]["unchanged"] == 1 and result["summary"]["rejected"] == 0
    assert facts(client) == original
    saved = command(client, "operator", result, key="native-calendar-roundtrip-" + fmt)
    assert saved.status_code == 200 and saved.get_json()["result"] == "unchanged"
    assert facts(client) == original
    bound = context(client, "operator")
    ref = client.get(BASE + "/entities/operator").get_json()["data"]["entities"][0]["ref"]
    removed = client.post(BASE + "/entities/operator/bulk-preview", json={"action": "delete", "refs": [ref], **bound})
    assert removed.status_code == 200, removed.get_data(as_text=True)
    result = removed.get_json()["data"]
    assert result["summary"]["rejected"] == 1 and result["rows"][0]["reference_count"] == 2
    assert result["can_confirm"] is False
    rejected = command(client, "operator", result, key="native-calendar-protected-" + fmt, operation="bulk")
    assert rejected.status_code == 409 and rejected.get_json()["committed"] is False
    assert facts(client) == original


def test_native_personal_calendar_change_invalidates_resource_import(native_client):
    client = native_client
    data = b'business_code,label\nDATE-O,Updated label\n'
    imported = client.post(BASE + "/imports/operator/preview", data={"file": (BytesIO(data), "update.csv"),
                           "format": "csv", "mode": "upsert"}, content_type="multipart/form-data")
    assert imported.status_code == 200, imported.get_data(as_text=True)
    result = imported.get_json()["data"]
    assert result["summary"]["update"] == 1
    with database(client) as conn:
        conn.execute("UPDATE OperatorCalendar SET efficiency=.5 WHERE operator_id='DATE-O'")
        conn.commit()
    before = facts(client)
    saved = command(client, "operator", result, key="native-calendar-stale-import")
    assert saved.status_code == 409 and saved.get_json()["error"]["code"] == "stale_write"
    assert facts(client) == before
