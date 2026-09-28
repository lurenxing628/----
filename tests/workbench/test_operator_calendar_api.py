"""个人工作日历的真实 HTTP 合同：月视图签发写能力，单日保存与范围清除各走各的形状。"""

import sqlite3
from contextlib import closing

import pytest

BASE = "/api/workbench/v1/entities/operator/"
DAY = "2026-10-05"
OTHER = "2026-10-06"
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


def test_month_signs_the_calendar_capabilities_and_hides_nothing_extra(client):
    ref = ref_of(client, "OP001")
    data = month(client, ref)
    assert data["operator_ref"] == ref and data["year"] == 2026 and data["month"] == 10
    assert len(data["days"]) == 31 and len(data["cells"]) % 7 == 0
    assert all(day["explicit"] is False and day["shift_start"] is None for day in data["days"])
    capabilities = data["write_context"]["capabilities"]
    assert set(capabilities) == {"operator.calendar_upsert", "operator.calendar_delete",
                                 "operator.calendar_range_clear"}
    assert all(capabilities.values())


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


def test_replayed_request_key_does_not_write_twice(client):
    ref = ref_of(client, "OP001")
    token = month(client, ref)["write_context"]["write_token"]
    first = command(client, ref, "upsert", {"date": DAY, "fields": WORK}, token)
    assert first.status_code == 200 and first.get_json()["replayed"] is False
    replay = command(client, ref, "upsert", {"date": DAY, "fields": WORK}, token)
    assert replay.status_code == 200 and replay.get_json()["replayed"] is True


def test_range_clear_previews_then_removes(client):
    ref = ref_of(client, "OP001")
    for index, day in enumerate((DAY, OTHER)):
        token = month(client, ref)["write_context"]["write_token"]
        assert command(client, ref, "upsert", {"date": day, "fields": WORK}, token,
                       key="operator-calendar-seed-0000" + str(index)).status_code == 200
    prepared = client.post(BASE + ref + "/calendar/range-preview",
                           json={"input": {"start_date": "2026-10-01", "end_date": "2026-10-31"}})
    assert prepared.status_code == 200, prepared.get_data(as_text=True)
    data = prepared.get_json()["data"]
    assert data["count"] == 2 and [day["date"] for day in data["days"]] == [DAY, OTHER]

    cleared = client.post(BASE + ref + "/calendar/range-clear",
                          json={"request_key": "operator-calendar-clear-00001",
                                "write_token": data["write_context"]["write_token"],
                                "input": {"start_date": "2026-10-01", "end_date": "2026-10-31"}})
    assert cleared.status_code == 200, cleared.get_data(as_text=True)
    assert cleared.get_json()["data"]["cleared_count"] == 2
    assert stored(client, "OP001", DAY) is None and stored(client, "OP001", OTHER) is None


def test_another_operators_token_cannot_write_this_calendar(client):
    first, second = ref_of(client, "OP001"), ref_of(client, "OP002")
    token = month(client, second)["write_context"]["write_token"]
    response = command(client, first, "upsert", {"date": DAY, "fields": WORK}, token)
    assert response.status_code != 200
    assert stored(client, "OP001", DAY) is None


def test_write_token_is_bound_to_the_action(client):
    ref = ref_of(client, "OP001")
    token = month(client, ref)["write_context"]["write_token"]
    # 月视图签的是日历三个动作；拿它去改人员本身必须失败。
    response = client.post("/api/workbench/v1/entities/operator/" + ref + "/update",
                           json={"request_key": "operator-update-00001", "write_token": token,
                                 "input": {"fields": {"remark": "不该成功"}}})
    assert response.status_code != 200


@pytest.mark.parametrize("payload", (
    {"date": DAY, "fields": {"type": "work", "eff": 100}},
    {"date": DAY, "fields": {"type": "work", "shiftStart": "9:00", "eff": 100}},
    {"date": DAY, "fields": {"type": "work", "shiftStart": "09:00", "eff": 0}},
    {"date": "2026-02-30", "fields": WORK},
    {"date": DAY, "fields": WORK, "extra": 1},
))
def test_invalid_input_is_rejected_without_writing(client, payload):
    ref = ref_of(client, "OP001")
    token = month(client, ref)["write_context"]["write_token"]
    assert command(client, ref, "upsert", payload, token).status_code != 200
    assert stored(client, "OP001", DAY) is None


def test_unknown_operator_reference_is_rejected(client):
    assert client.get(BASE + "f" * 48 + "/calendar/month",
                      query_string={"year": 2026, "month": 10}).status_code != 200


def test_stale_month_cannot_overwrite_new_day_and_exact_request_replays(client):
    ref = ref_of(client, 'OP001')
    old = month(client, ref)['write_context']['write_token']
    newer = dict(WORK, shiftStart='10:00', shiftEnd='18:00', eff=80)
    first = command(client, ref, 'upsert', {'date': DAY, 'fields': newer}, old, key='calendar-newer-request-01')
    assert first.status_code == 200, first.get_json()
    replay = command(client, ref, 'upsert', {'date': DAY, 'fields': newer}, old, key='calendar-newer-request-01')
    assert replay.get_json()['replayed'] is True
    stale = command(client, ref, 'upsert', {'date': DAY, 'fields': WORK}, old, key='calendar-older-request-01')
    assert stale.status_code == 409 and stale.get_json()['error']['code'] == 'stale_write'
    assert stored(client, 'OP001', DAY)['shift_start'] == '10:00'


def test_range_clear_binds_original_range_and_concurrent_dates(client):
    ref = ref_of(client, 'OP001')
    for index, day in enumerate((DAY, OTHER)):
        token = month(client, ref)['write_context']['write_token']
        assert command(client, ref, 'upsert', {'date': day, 'fields': WORK}, token, key='range-prepare-request-0' + str(index)).status_code == 200
    scope = {'start_date': DAY, 'end_date': DAY}
    response = client.post(BASE + ref + '/calendar/range-preview', json={'input': scope})
    token = response.get_json()['data']['write_context']['write_token']
    changed = command(client, ref, 'range-clear', {'start_date': DAY, 'end_date': OTHER}, token, key='range-tampered-request-01')
    assert changed.status_code == 409
    assert stored(client, 'OP001', DAY) and stored(client, 'OP001', OTHER)
    token2 = month(client, ref)['write_context']['write_token']
    assert command(client, ref, 'upsert', {'date': DAY, 'fields': dict(WORK, note='并发修改')}, token2, key='range-change-request-01').status_code == 200
    assert command(client, ref, 'range-clear', scope, token, key='range-stale-request-01').status_code == 409
