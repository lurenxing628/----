"""个人工作日历月视图签发能力，单日保存后清除实际记录。"""

import sqlite3
from contextlib import closing

import pytest

BASE = "/api/workbench/v1/entities/operator/"
DAY = "2026-10-05"
WORK = {"type": "work", "shiftStart": "09:00", "shiftEnd": "17:30", "eff": 90,
        "allowNormal": "yes", "allowUrgent": "no", "note": "早班"}


@pytest.fixture(name="client")
def operator_calendar_client(db_env):
    from app import create_app

    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert BASE + "<ref>/calendar/month" in rules and BASE + "<ref>/calendar/range-clear" in rules
    client = app.test_client()
    with database(client) as conn:
        conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('OT1','车','internal')")
        conn.executemany("INSERT INTO Operators(operator_id,name,status) VALUES (?,?,'active')",
                         [("OP001", "张三"), ("OP002", "李四")])
        conn.commit()
    return client


def database(client):
    conn = sqlite3.connect(client.application.config["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    return closing(conn)


def ref_of(client, code):
    with database(client) as conn:
        row = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='operator' AND entity_key=? AND active=1",
                           (code,)).fetchone()
        assert row is not None, code
        return row["ref"]


def stored(client, code, day):
    with database(client) as conn:
        row = conn.execute("SELECT * FROM OperatorCalendar WHERE operator_id=? AND date=?", (code, day)).fetchone()
        return dict(row) if row else None


def month(client, ref, year=2026, number=10):
    response = client.get(BASE + ref + "/calendar/month", query_string={"year": year, "month": number})
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def command(client, ref, action, payload, token, key="operator-calendar-request-00001"):
    return client.post(BASE + ref + "/calendar/" + action,
                       json={"request_key": key, "write_token": token, "input": payload})


def test_save_one_day_then_clear_it(client):
    ref = ref_of(client, "OP001")
    token = month(client, ref)["write_context"]["write_token"]
    saved = command(client, ref, "upsert", {"date": DAY, "fields": WORK}, token)
    assert saved.status_code == 200, saved.get_data(as_text=True)
    assert saved.get_json()["result"] == "committed"
    row = stored(client, "OP001", DAY)
    assert row["shift_start"] == "09:00" and row["shift_end"] == "17:30" and row["shift_hours"] == 8.5

    after = month(client, ref)
    configured = [day for day in after["days"] if day["explicit"]]
    assert len(configured) == 1 and configured[0]["date"] == DAY and configured[0]["shift_hours"] == 8.5

    cleared = command(client, ref, "delete", {"date": DAY}, after["write_context"]["write_token"],
                      key="operator-calendar-request-00002")
    assert cleared.status_code == 200 and cleared.get_json()["result"] == "committed"
    assert stored(client, "OP001", DAY) is None
