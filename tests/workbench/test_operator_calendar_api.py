"""个人工作日历月视图签发能力，单日保存后清除实际记录；选人导出只在预检准入一次。"""

import sqlite3
from contextlib import closing

import pytest

from core.models.calendar_periods import decode_periods
from tests.workbench.calendar_api_support import assert_read_failure, deny_table_reads

BASE = "/api/workbench/v1/entities/operator/"
DAY = "2026-10-05"
WORK = {
    "type": "work",
    "periods": [{"start": "09:00", "end": "17:30", "day_offset": 0}],
    "eff": 90,
    "allowNormal": "yes",
    "allowUrgent": "no",
    "note": "早班",
}


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
    initial_resp = client.get(BASE + ref + "/calendar/month", query_string={"year": 2026, "month": 10}).get_json()
    token = initial_resp["data"]["write_context"]["write_token"]
    snapshot_ref = initial_resp["meta"]["snapshot_ref"]
    repeated = client.get(BASE + ref + "/calendar/month", query_string={"year": 2026, "month": 10, "snapshot_ref": snapshot_ref})
    assert repeated.status_code == 200
    saved = command(client, ref, "upsert", {"date": DAY, "fields": WORK}, token)
    assert saved.status_code == 200, saved.get_data(as_text=True)
    assert saved.get_json()["result"] == "committed"
    stale = client.get(BASE + ref + "/calendar/month", query_string={"year": 2026, "month": 10, "snapshot_ref": snapshot_ref})
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"
    row = stored(client, "OP001", DAY)
    assert row is not None
    assert decode_periods(row["periods_json"]) == WORK["periods"]

    after = month(client, ref)
    configured = [day for day in after["days"] if day["explicit"]]
    assert len(configured) == 1 and configured[0]["date"] == DAY and configured[0]["periods"] == WORK["periods"]

    periods = [{"start": "08:00", "end": "12:00", "day_offset": 0},
               {"start": "13:00", "end": "17:00", "day_offset": 0}]
    split_saved = command(client, ref, "upsert",
                          {"date": DAY, "fields": {"type": "work", "periods": periods, "eff": 100}},
                          after["write_context"]["write_token"], key="operator-calendar-request-00002")
    assert split_saved.status_code == 200 and split_saved.get_json()["result"] == "committed"
    split_row = stored(client, "OP001", DAY)
    assert split_row is not None
    assert decode_periods(split_row["periods_json"]) == periods

    after_split = month(client, ref)
    rejected = command(client, ref, "upsert",
                       {"date": DAY, "fields": {"type": "work", "periods": None, "eff": 100}},
                       after_split["write_context"]["write_token"], key="operator-calendar-request-00003")
    assert rejected.status_code == 422 and rejected.get_json()["error"]["code"] == "invalid_input"

    cleared = command(client, ref, "delete", {"date": DAY}, after_split["write_context"]["write_token"],
                      key="operator-calendar-request-00004")
    assert cleared.status_code == 200 and cleared.get_json()["result"] == "committed"
    assert stored(client, "OP001", DAY) is None


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
    assert row is not None and decode_periods(row["periods_json"]) == WORK["periods"]
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
        {"date": day, "fields": {**WORK, "periods": [{"start": "08:00", "end": "16:00", "day_offset": 0}], "note": "OP1原记录"}},
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


def test_month_and_range_preview_avoid_resource_dependency_queries_and_prebind_stale_token(client, monkeypatch):
    from core.services.workbench.resource.operator_calendars import WorkbenchOperatorCalendarService
    from core.services.workbench.resource.table_facts import capture_change_facts

    monkeypatch.setattr(
        "core.services.workbench.resource.queries.capture_change_facts",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("operator calendar should not capture resource change facts")),
    )
    ref = ref_of(client, "OP001")
    initial = client.get(BASE + ref + "/calendar/month", query_string={"year": 2026, "month": 10}).get_json()
    snapshot_ref = initial["meta"]["snapshot_ref"]
    token = initial["data"]["write_context"]["write_token"]
    assert command(client, ref, "upsert", {"date": DAY, "fields": WORK}, token).status_code == 200
    assert capture_change_facts is not None

    monkeypatch.setattr(
        WorkbenchOperatorCalendarService,
        "month",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("stale month token should fail before reading month")),
    )
    stale = client.get(BASE + ref + "/calendar/month", query_string={"year": 2026, "month": 10, "snapshot_ref": snapshot_ref})
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"


def test_selected_operator_calendar_export_admits_refs_once_and_resolves_them_per_download(client, monkeypatch):
    from core.services.workbench.resource.queries import WorkbenchResourceQueryService
    from web.routes.workbench import calendar_files

    files = "/api/workbench/v1/calendar-files/operator_calendar/"
    with database(client) as conn:
        conn.executemany(
            "INSERT INTO OperatorCalendar(operator_id,date,day_type,efficiency,allow_normal,allow_urgent,periods_json) "
            "VALUES (?,?,'workday',1,'yes','yes','[{\"start\":\"09:00\",\"end\":\"17:00\",\"day_offset\":0}]')",
            [("OP001", DAY), ("OP002", DAY)],
        )
        conn.commit()
    selected = [ref_of(client, "OP001")]

    def export_ref():
        response = client.post(files + "export-preview", json={"range": {"start_date": DAY, "end_date": DAY},
                                                              "scope": {"operator_refs": selected}})
        assert response.status_code == 200, response.get_data(as_text=True)
        data = response.get_json()["data"]
        assert data["range"]["selected_refs"] == selected
        return data["export_ref"]

    def download(ref):
        return client.get(files + "export", query_string={"export_ref": ref, "format": "csv"})

    ref, resolved, resolve_refs = export_ref(), [], WorkbenchResourceQueryService.resolve_refs
    with monkeypatch.context() as patch:
        for name in ("check_range", "resource_refs"):
            patch.setattr(calendar_files, name, lambda *args, **kwargs: pytest.fail("下载不该再准入预检已存的范围"))
        patch.setattr(WorkbenchResourceQueryService, "resolve_refs",
                      lambda self, refs: resolved.append(refs) or resolve_refs(self, refs))
        exported = download(ref)
    assert exported.status_code == 200, exported.get_data(as_text=True)
    text = exported.data.decode("utf-8-sig")
    assert "OP001" in text and "OP002" not in text
    assert resolved == [selected]
    ref = export_ref()
    with database(client) as conn:
        conn.execute("UPDATE Operators SET name='改名' WHERE operator_id='OP002'")
        conn.commit()
    stale = download(ref)
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "snapshot_stale"
    ref = export_ref()
    with database(client) as conn:
        conn.execute("DELETE FROM Operators WHERE operator_id='OP001'")
        conn.commit()
    # 先解析选中人员、后绑快照：选中的人已删除时报 404，而不是 409。
    missing = download(ref)
    assert missing.status_code == 404 and missing.get_json()["error"]["code"] == "entity_not_found"
