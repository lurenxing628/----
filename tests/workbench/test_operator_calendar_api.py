"""个人工作日历月视图签发能力，单日保存后清除实际记录。"""

import sqlite3
from contextlib import closing

import pytest

from tests.workbench.calendar_api_support import assert_read_failure, deny_table_reads

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
    assert row is not None
    assert row["shift_start"] == "09:00" and row["shift_end"] == "17:30" and row["shift_hours"] == 8.5

    after = month(client, ref)
    configured = [day for day in after["days"] if day["explicit"]]
    assert len(configured) == 1 and configured[0]["date"] == DAY and configured[0]["shift_hours"] == 8.5

    periods = [{"start": "08:00", "end": "12:00", "day_offset": 0},
               {"start": "13:00", "end": "17:00", "day_offset": 0}]
    split_saved = command(client, ref, "upsert",
                          {"date": DAY, "fields": {"type": "work", "periods": periods, "eff": 100}},
                          after["write_context"]["write_token"], key="operator-calendar-request-00002")
    assert split_saved.status_code == 200 and split_saved.get_json()["result"] == "committed"
    split_row = stored(client, "OP001", DAY)
    assert split_row is not None
    assert (split_row["shift_start"], split_row["shift_end"], split_row["shift_hours"]) == ("08:00", "17:00", 8.0)

    after_split = month(client, ref)
    reverted = command(client, ref, "upsert",
                       {"date": DAY, "fields": {"type": "work", "periods": None, "shiftStart": "08:00", "eff": 100}},
                       after_split["write_context"]["write_token"], key="operator-calendar-request-00003")
    assert reverted.status_code == 200 and reverted.get_json()["result"] == "committed"
    single_row = stored(client, "OP001", DAY)
    assert single_row is not None and single_row["periods_json"] is None
    assert (single_row["shift_start"], single_row["shift_end"], single_row["shift_hours"]) == ("08:00", "16:00", 8.0)

    after_reverted = month(client, ref)
    cleared = command(client, ref, "delete", {"date": DAY}, after_reverted["write_context"]["write_token"],
                      key="operator-calendar-request-00004")
    assert cleared.status_code == 200 and cleared.get_json()["result"] == "committed"
    assert stored(client, "OP001", DAY) is None


def test_blank_legacy_columns_read_the_way_scheduling_does(client):
    """旧行的班次开始、工时、效率被明确写成空：月视图统计、这一天的显示、导出都按排产引擎的解释，不再报错；库里的行不动。"""
    ref = ref_of(client, "OP001")
    token = month(client, ref)["write_context"]["write_token"]
    assert command(client, ref, "upsert", {"date": DAY, "fields": WORK}, token).status_code == 200
    with database(client) as conn:
        conn.execute("UPDATE OperatorCalendar SET shift_hours=NULL, efficiency=NULL, shift_start=NULL, shift_end=NULL "
                     "WHERE operator_id='OP001' AND date=?", (DAY,))
        conn.commit()
    data = month(client, ref)
    shown = next(day for day in data["days"] if day["date"] == DAY)
    assert data["stats"] == {"configured": 1, "work_days": 1}
    assert (shown["shift_start"], shown["shift_hours"], shown["efficiency"]) == ("08:00", 8.0, 1.0)
    raw = stored(client, "OP001", DAY)
    assert raw is not None and raw["shift_hours"] is None


@pytest.mark.parametrize("operator_code", ["OP:1", "OP%1"])
def test_new_day_receipt_uses_escaped_operator_identity(client, operator_code):
    from core.infrastructure.workbench_metadata_schema import entity_key

    day = "2026-10-15"
    with database(client) as conn:
        conn.execute("INSERT INTO Operators(operator_id,name,status) VALUES (?,?,'active')",
                     (operator_code, "特殊工号"))
        conn.commit()
    ref = ref_of(client, operator_code)
    token = month(client, ref)["write_context"]["write_token"]
    saved = command(client, ref, "upsert", {"date": day, "fields": WORK}, token)
    assert saved.status_code == 200, saved.get_data(as_text=True)
    receipt = saved.get_json()
    assert receipt["result"] == "committed"
    with database(client) as conn:
        identity = conn.execute(
            "SELECT ref FROM WorkbenchEntityRefs WHERE kind='operator_calendar' AND entity_key=? AND active=1",
            (entity_key(operator_code, day),)).fetchone()
    assert identity is not None and receipt["data"]["calendar_ref"] == identity["ref"]
    row = stored(client, operator_code, day)
    assert row is not None and row["shift_hours"] == 8.5
    shown = next(item for item in month(client, ref)["days"] if item["date"] == day)
    assert shown["calendar_ref"] == identity["ref"] and shown["explicit"]


def test_operator_calendar_with_surrounding_whitespace_does_not_touch_trimmed_sibling(client):
    day = "2026-10-16"
    with database(client) as conn:
        conn.executemany(
            "INSERT INTO Operators(operator_id,name,status) VALUES (?,?,'active')",
            [("OP1", "正常工号"), (" OP1 ", "带空格工号")],
        )
        conn.commit()
    normal_ref = ref_of(client, "OP1")
    spaced_ref = ref_of(client, " OP1 ")

    normal_token = month(client, normal_ref)["write_context"]["write_token"]
    normal_saved = command(
        client, normal_ref, "upsert",
        {"date": day, "fields": {**WORK, "shiftStart": "08:00", "shiftEnd": "16:00", "note": "OP1原记录"}},
        normal_token, key="operator-calendar-trimmed-001",
    )
    assert normal_saved.status_code == 200 and normal_saved.get_json()["result"] == "committed"

    spaced_token = month(client, spaced_ref)["write_context"]["write_token"]
    spaced_saved = command(
        client, spaced_ref, "upsert",
        {"date": day, "fields": WORK},
        spaced_token, key="operator-calendar-spaced-001",
    )
    assert spaced_saved.status_code == 200 and spaced_saved.get_json()["result"] == "committed"
    spaced_row = stored(client, " OP1 ", day)
    normal_row = stored(client, "OP1", day)
    assert spaced_row is not None and spaced_row["remark"] == "早班"
    assert normal_row is not None and normal_row["remark"] == "OP1原记录"

    spaced_after = month(client, spaced_ref)
    spaced_updated = command(
        client, spaced_ref, "upsert",
        {"date": day, "fields": {**WORK, "note": "更新带空格工号"}},
        spaced_after["write_context"]["write_token"], key="operator-calendar-spaced-002",
    )
    assert spaced_updated.status_code == 200 and spaced_updated.get_json()["result"] == "committed"
    spaced_row = stored(client, " OP1 ", day)
    normal_row = stored(client, "OP1", day)
    assert spaced_row is not None and spaced_row["remark"] == "更新带空格工号"
    assert normal_row is not None and normal_row["remark"] == "OP1原记录"

    spaced_after_update = month(client, spaced_ref)
    spaced_deleted = command(
        client, spaced_ref, "delete",
        {"date": day},
        spaced_after_update["write_context"]["write_token"], key="operator-calendar-spaced-003",
    )
    assert spaced_deleted.status_code == 200 and spaced_deleted.get_json()["result"] == "committed"
    normal_row = stored(client, "OP1", day)
    assert stored(client, " OP1 ", day) is None
    assert normal_row is not None and normal_row["remark"] == "OP1原记录"


def test_range_preview_read_failure_reports_nothing_committed(client):
    ref = ref_of(client, "OP001")
    deny_table_reads(client.application, "OperatorCalendar")
    response = client.post(BASE + ref + "/calendar/range-preview",
                           json={"input": {"start_date": "2026-10-01", "end_date": "2026-10-07"}})
    assert_read_failure(response)
