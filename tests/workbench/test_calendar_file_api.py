"""全局工作日历导入预检保持只读，确认写入一次并复用回执。"""

import json
import sqlite3
from contextlib import closing
from io import BytesIO

import pytest

from tests.workbench.calendar_file_support import HEADERS, file_bytes

BASE = "/api/workbench/v1/calendar-files"
PERIOD_HEADERS = ["工作时段数"] + ["第" + str(index) + "段" + field for index in range(2, 9) for field in ("开始", "结束", "开始日期")]
KIND = "work_calendar"
DAY = "2026-10-01"
OTHER = "2026-10-02"


@pytest.fixture(name="client")
def calendar_file_client(db_env):
    from app import create_app

    app = create_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert BASE + "/<kind>/preview" in rules and BASE + "/<kind>/export-preview" in rules
    client = app.test_client()
    # 第一次读库的请求会补写排产配置等默认行。先跑一次只读的预检把这些补完，之后的整库快照才有可比性。
    preview_ok(client, [(DAY, "工作日", "08:00", "16:00", "", "", "", "")])
    return client


def database(client):
    conn = sqlite3.connect(client.application.config["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    return closing(conn)


def snapshot(client):
    with database(client) as conn:
        return [line for line in conn.iterdump() if not line.startswith('INSERT INTO "OperationLogs"')]


def days(client):
    from core.models.calendar_periods import decode_periods, period_hours

    with database(client) as conn:
        return {row["date"]: (row["day_type"], period_hours(decode_periods(row["periods_json"])))
                for row in conn.execute("SELECT * FROM WorkCalendar")}


def preview_ok(client, rows, fmt="csv", headers=HEADERS):
    fields = {"file": (BytesIO(file_bytes(rows, fmt, headers=headers)), "calendar." + fmt), "format": fmt, "mode": "upsert"}
    response = client.post(BASE + "/" + KIND + "/preview", data=fields, content_type="multipart/form-data")
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def confirm(client, preview, key="calendar-file-request-00001"):
    return client.post(BASE + "/" + KIND + "/confirm", json={
        "request_key": key, "write_token": preview["write_context"]["write_token"],
        "input": {"preview_ref": preview["preview_ref"]}})


def test_preview_does_not_write_and_confirm_commits_once(client, monkeypatch):
    preview = preview_ok(client, [(DAY, "工作日", "08:00", "16:00", "100", "是", "是", "调休"),
                                  (OTHER, "假期", "", "", "", "否", "否", "")])
    # 只比日历表：应用启动后还会陆续补建与本功能无关的表和触发器，整库快照在首几次请求间本来就会变。
    assert days(client) == {}
    assert preview["operation"] == KIND + ".import" and preview["commit_policy"] == "atomic"
    assert preview["can_confirm"] and preview["mode"] == "upsert"
    assert [row["result"] for row in preview["rows"]] == ["new", "new"]
    assert [item["label"] for item in preview["columns"]] == list(HEADERS) + PERIOD_HEADERS + ["可排工时（小时）（只读）"]
    assert "entity_key" not in json.dumps(preview) and "revision" not in json.dumps(preview)

    from core.services.scheduler.calendar.admin import CalendarAdmin
    from data.repositories.workbench_calendar_query_repo import WorkbenchCalendarQueryRepository

    built, build = [], CalendarAdmin._build_work_calendar

    def build_once(self, *args, **kwargs):
        model = build(self, *args, **kwargs)
        built.append(model)
        return model

    def no_receipt_refs(*args):
        raise AssertionError("File receipts do not consume permanent calendar refs")

    monkeypatch.setattr(CalendarAdmin, "_build_work_calendar", build_once)
    monkeypatch.setattr(WorkbenchCalendarQueryRepository, "created_refs", no_receipt_refs)
    first = confirm(client, preview)
    assert len(built) == 2
    assert first.status_code == 200, first.get_data(as_text=True)
    assert first.get_json()["result"] == "committed"
    assert days(client) == {DAY: ("workday", 8.0), OTHER: ("holiday", 0.0)}

    after = snapshot(client)
    replay = confirm(client, preview)
    assert replay.status_code == 200 and replay.get_json()["replayed"] is True
    assert snapshot(client) == after


def test_zero_hour_workday_preview_notes_the_fact_and_requires_confirmation(client):
    row, = preview_ok(
        client,
        [(OTHER, "工作日", "", "", "", "是", "是", "", "0")],
        headers=HEADERS + ("工作时段数",),
    )["rows"]
    assert row["result"] == "new" and row["requires_confirmation"] is True
    assert [note for note in row["notes"] if "可排工时是 0" in note] == [
        "这一天是工作日，但可排工时是 0，排产时一道工序也排不进来。要上班请填班次起止或工作时段；要休息请把类型填成「假期」。"]
    worked, = preview_ok(client, [(OTHER, "工作日", "08:00", "16:00", "", "是", "是", "")])["rows"]
    assert not any("可排工时是 0" in note for note in worked["notes"])


def test_holiday_turned_workday_must_state_periods_in_global_file(client):
    preview = preview_ok(client, [(DAY, "假期", "", "", "", "否", "否", "国庆")])
    assert confirm(client, preview, key="calendar-file-holiday-setup").status_code == 200

    # 只改类型、工作时段留空：这一行不导入，错误落在该填的班次开始列。
    omitted = preview_ok(client, [(DAY, "工作日", "", "", "", "", "", "")])
    row, = omitted["rows"]
    assert omitted["can_confirm"] is False and row["result"] == "rejected"
    assert [(err["field"], err["message"]) for err in row["errors"]] == [
        ("shift_start", DAY + " 原来是假期或休息日，改成工作日时请填写工作时段。")]

    # 类型留空仍是假期，不算改回工作日；只改备注照常。
    kept, = preview_ok(client, [(DAY, "", "", "", "", "", "", "只改备注")])["rows"]
    assert kept["result"] == "update" and kept["after"]["day_type"] == "假期"

    # 工作时段数填 0 是明确的零工时工作日，放行并提醒确认。
    zero, = preview_ok(client, [(DAY, "工作日", "", "", "", "", "", "", "0")], headers=HEADERS + ("工作时段数",))["rows"]
    assert zero["result"] == "update" and zero["after"]["shift_hours"] == "0" and zero["requires_confirmation"] is True
    assert any("可排工时是 0" in note for note in zero["notes"])

    # 填了班次起止就按所填保存；没存过的日期留空仍取默认时段。
    filled, = preview_ok(client, [(DAY, "工作日", "09:00", "17:00", "", "是", "是", "")])["rows"]
    assert filled["result"] == "update" and filled["after"]["shift_hours"] == "8"
    fresh, = preview_ok(client, [(OTHER, "工作日", "", "", "", "", "", "")])["rows"]
    assert fresh["result"] == "new" and fresh["after"]["period_count"] == "2"


def test_broken_default_periods_reject_on_date_column_not_unfilled_shift_columns(client):
    # 库里的默认工作时间坏了，只填日期和备注的行取默认时段失败：错误落在日期列，
    # 不落在这一行没填的班次开始列。
    with database(client) as conn:
        conn.execute("INSERT OR REPLACE INTO WorkbenchCalendarDefaults(singleton,periods_json) VALUES (1,'[]')")
        conn.commit()
    before = snapshot(client)
    row, = preview_ok(client, [(OTHER, "", "", "", "", "", "", "只写备注")])["rows"]
    assert row["result"] == "rejected"
    assert [(err["field"], err["message"]) for err in row["errors"]] == [
        ("date", "默认工作时间至少需要一个工作时段，请重新维护。")]
    assert snapshot(client) == before


def test_stored_calendar_csv_roundtrip_without_false_diff(client):
    preview = preview_ok(client, [(DAY, "工作日", "08:00", "16:00", "100", "是", "是", "初值")])
    assert confirm(client, preview, key="calendar-file-roundtrip-setup").status_code == 200

    export_prev = client.post(
        BASE + "/" + KIND + "/export-preview",
        json={"range": {"start_date": DAY, "end_date": DAY}},
    )
    assert export_prev.status_code == 200, export_prev.get_data(as_text=True)
    export_ref = export_prev.get_json()["data"]["export_ref"]
    exported = client.get(
        BASE + "/" + KIND + "/export",
        query_string={"export_ref": export_ref, "format": "csv"},
    )
    assert exported.status_code == 200, exported.get_data(as_text=True)

    roundtrip_resp = client.post(
        BASE + "/" + KIND + "/preview",
        data={"file": (BytesIO(exported.data), "calendar.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data",
    )
    assert roundtrip_resp.status_code == 200, roundtrip_resp.get_data(as_text=True)
    roundtrip = roundtrip_resp.get_json()["data"]
    row, = roundtrip["rows"]
    assert row["errors"] == [] and row["result"] == "unchanged" and row["changes"] == {}
    assert roundtrip["can_confirm"] is True
    assert row["before"]["shift_start"] == row["after"]["shift_start"] == "08:00"

    same_defaults = preview_ok(client, [(DAY, "工作日", "08:00", "16:00", "100", "是", "是", "带默认同值改备注")])
    assert same_defaults["can_confirm"] is True
    same_defaults_row, = same_defaults["rows"]
    assert same_defaults_row["errors"] == [] and same_defaults_row["result"] == "update"
    assert same_defaults_row["before"]["shift_start"] == same_defaults_row["after"]["shift_start"] == "08:00"
    assert same_defaults_row["changes"] == {"remark": {"before": "初值", "after": "带默认同值改备注"}}

    remark_only = preview_ok(client, [(DAY, "", "", "", "", "", "", "只改备注")])
    assert remark_only["can_confirm"] is True
    updated_row, = remark_only["rows"]
    assert updated_row["errors"] == [] and updated_row["result"] == "update"
    assert updated_row["before"]["shift_start"] == updated_row["after"]["shift_start"] == "08:00"
    assert updated_row["changes"] == {"remark": {"before": "初值", "after": "只改备注"}}

    hours_and_eff = preview_ok(client, [(DAY, "", "08:00", "12:00", "80", "", "", "")])
    assert hours_and_eff["can_confirm"] is True
    hours_row, = hours_and_eff["rows"]
    assert hours_row["errors"] == [] and hours_row["result"] == "update"
    assert hours_row["after"]["shift_hours"] == "4" and hours_row["after"]["efficiency"] == "80"

    with database(client) as conn:
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('OP-CSV','张三')")
        conn.execute(
            "INSERT INTO OperatorCalendar(operator_id,date,day_type,efficiency,allow_normal,allow_urgent,remark,periods_json) "
            "VALUES ('OP-CSV',?,'workday',1,'yes','yes',NULL,'[{\"start\":\"08:00\",\"end\":\"12:00\",\"day_offset\":0}]')",
            (DAY,),
        )
        conn.commit()
        from core.infrastructure.transaction import TransactionManager
        from core.services.workbench.resource.operator_calendars import WorkbenchOperatorCalendarService

        with TransactionManager(conn).transaction():
            assert WorkbenchOperatorCalendarService(conn, "OP-CSV").month(2026, 10)["stats"]["work_days"] == 1
    op_export_prev = client.post(
        BASE + "/operator_calendar/export-preview",
        json={"range": {"start_date": DAY, "end_date": DAY}},
    )
    assert op_export_prev.status_code == 200, op_export_prev.get_data(as_text=True)
    op_exported = client.get(
        BASE + "/operator_calendar/export",
        query_string={"export_ref": op_export_prev.get_json()["data"]["export_ref"], "format": "csv"},
    )
    assert op_exported.status_code == 200, op_exported.get_data(as_text=True)
    op_roundtrip_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={"file": (BytesIO(op_exported.data), "operator_calendar.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data",
    )
    assert op_roundtrip_resp.status_code == 200, op_roundtrip_resp.get_data(as_text=True)
    op_roundtrip = op_roundtrip_resp.get_json()["data"]
    op_row, = op_roundtrip["rows"]
    assert op_roundtrip["can_confirm"] is True
    assert op_row["errors"] == [] and op_row["result"] == "unchanged"
    assert op_row["changes"] == {} and op_row["requires_confirmation"] is False
    assert op_row["before"]["shift_end"] == op_row["after"]["shift_end"] == "12:00"
    op_remark_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={
            "file": (BytesIO(file_bytes([("OP-CSV", DAY, "仅改备注")], headers=("工号", "日期", "备注"))), "operator_calendar.csv"),
            "format": "csv",
            "mode": "upsert",
        },
        content_type="multipart/form-data",
    )
    assert op_remark_resp.status_code == 200, op_remark_resp.get_data(as_text=True)
    op_remark = op_remark_resp.get_json()["data"]
    assert op_remark["can_confirm"] is True
    assert op_remark["rows"][0]["result"] == "update"
    assert op_remark["rows"][0]["changes"] == {"remark": {"before": None, "after": "仅改备注"}}


def test_operator_zero_hour_workday_roundtrip_and_fullwidth_clock_rejected(client):
    from core.errors import ValidationError
    from core.models.calendar_periods import normalize_periods

    with pytest.raises(ValidationError):
        normalize_periods([{"start": "1０:00", "end": "11:00", "day_offset": 0}])

    with database(client) as conn:
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('OP-ZERO','李四')")
        conn.commit()

    create_bytes = file_bytes(
        [("OP-ZERO", DAY, "工作日", "0", "零工时工作日")],
        headers=("工号", "日期", "类型", "工作时段数", "备注"),
    )
    create_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={"file": (BytesIO(create_bytes), "operator_calendar.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data",
    )
    assert create_resp.status_code == 200, create_resp.get_data(as_text=True)
    create_prev = create_resp.get_json()["data"]
    assert create_prev["can_confirm"] is True
    assert create_prev["rows"][0]["after"]["shift_hours"] == "0"
    assert create_prev["rows"][0]["requires_confirmation"] is True
    assert [note for note in create_prev["rows"][0]["notes"] if "可排工时是 0" in note] == [
        "这一天是工作日，但可排工时是 0，排产时这个人一道工序也排不进来。要上班请填班次起止或工作时段；要休息请把类型填成「假期」。"]
    confirmed_create = client.post(
        BASE + "/operator_calendar/confirm",
        json={
            "request_key": "op-zero-create-00001",
            "write_token": create_prev["write_context"]["write_token"],
            "input": {"preview_ref": create_prev["preview_ref"]},
        },
    )
    assert confirmed_create.status_code == 200, confirmed_create.get_data(as_text=True)

    remark_bytes = file_bytes(
        [("OP-ZERO", DAY, "零工时仅改备注")],
        headers=("工号", "日期", "备注"),
    )
    remark_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={"file": (BytesIO(remark_bytes), "operator_calendar.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data",
    )
    assert remark_resp.status_code == 200, remark_resp.get_data(as_text=True)
    remark_prev = remark_resp.get_json()["data"]
    remark_row, = remark_prev["rows"]
    assert remark_prev["can_confirm"] is True and remark_row["result"] == "update"
    assert remark_row["after"]["shift_hours"] == "0"
    assert remark_row["changes"] == {"remark": {"before": "零工时工作日", "after": "零工时仅改备注"}}
    confirmed_remark = client.post(
        BASE + "/operator_calendar/confirm",
        json={
            "request_key": "op-zero-remark-00002",
            "write_token": remark_prev["write_context"]["write_token"],
            "input": {"preview_ref": remark_prev["preview_ref"]},
        },
    )
    assert confirmed_remark.status_code == 200, confirmed_remark.get_data(as_text=True)
    with database(client) as conn:
        stored = conn.execute(
            "SELECT periods_json, remark FROM OperatorCalendar WHERE operator_id='OP-ZERO' AND date=?",
            (DAY,),
        ).fetchone()
    assert (stored["periods_json"], stored["remark"]) == ("[]", "零工时仅改备注")

    export_prev = client.post(
        BASE + "/operator_calendar/export-preview",
        json={"range": {"start_date": DAY, "end_date": DAY}},
    )
    assert export_prev.status_code == 200
    exported_zero = client.get(
        BASE + "/operator_calendar/export",
        query_string={"export_ref": export_prev.get_json()["data"]["export_ref"], "format": "csv"},
    )
    assert exported_zero.status_code == 200
    zero_roundtrip_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={"file": (BytesIO(exported_zero.data), "operator_calendar.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data",
    )
    assert zero_roundtrip_resp.status_code == 200
    zero_roundtrip = zero_roundtrip_resp.get_json()["data"]
    assert zero_roundtrip["can_confirm"] is True
    assert zero_roundtrip["rows"][0]["result"] == "unchanged" and zero_roundtrip["rows"][0]["changes"] == {}

    with database(client) as conn:
        conn.execute(
            "INSERT INTO OperatorCalendar(operator_id,date,day_type,efficiency,allow_normal,allow_urgent,remark,periods_json) "
            "VALUES ('OP-ZERO',?,'holiday',1,'no','no',NULL,'[]')",
            (OTHER,),
        )
        conn.commit()
    holiday_to_work_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={
            "file": (BytesIO(file_bytes([("OP-ZERO", OTHER, "工作日")], headers=("工号", "日期", "类型"))), "operator_calendar.csv"),
            "format": "csv",
            "mode": "upsert",
        },
        content_type="multipart/form-data",
    )
    assert holiday_to_work_resp.status_code == 200, holiday_to_work_resp.get_data(as_text=True)
    holiday_to_work = holiday_to_work_resp.get_json()["data"]
    holiday_row, = holiday_to_work["rows"]
    assert holiday_to_work["can_confirm"] is False and holiday_row["result"] == "rejected"
    assert [(err["field"], err["message"]) for err in holiday_row["errors"]] == [
        ("shift_start", OTHER + " 原来是假期或休息日，改成工作日时请填写工作时段。")]

    # 工作时段数填 0 是明确的零工时工作日；填了时段就按所填保存。
    explicit_zero_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={
            "file": (BytesIO(file_bytes([("OP-ZERO", OTHER, "工作日", "0")], headers=("工号", "日期", "类型", "工作时段数"))),
                     "operator_calendar.csv"),
            "format": "csv",
            "mode": "upsert",
        },
        content_type="multipart/form-data",
    )
    explicit_zero_row, = explicit_zero_resp.get_json()["data"]["rows"]
    assert explicit_zero_row["result"] == "update" and explicit_zero_row["after"]["shift_hours"] == "0"
    assert any("可排工时是 0" in note for note in explicit_zero_row["notes"])
    filled_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={
            "file": (BytesIO(file_bytes([("OP-ZERO", OTHER, "工作日", "09:00", "17:00")],
                                        headers=("工号", "日期", "类型", "班次开始", "班次结束"))),
                     "operator_calendar.csv"),
            "format": "csv",
            "mode": "upsert",
        },
        content_type="multipart/form-data",
    )
    filled_row, = filled_resp.get_json()["data"]["rows"]
    assert filled_row["result"] == "update" and filled_row["after"]["shift_hours"] == "8"

    new_work_without_periods_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={
            "file": (BytesIO(file_bytes([("OP-ZERO", "2026-10-03", "工作日")], headers=("工号", "日期", "类型"))), "operator_calendar.csv"),
            "format": "csv",
            "mode": "upsert",
        },
        content_type="multipart/form-data",
    )
    assert new_work_without_periods_resp.status_code == 200, new_work_without_periods_resp.get_data(as_text=True)
    new_work_without_periods = new_work_without_periods_resp.get_json()["data"]
    rejected_row, = new_work_without_periods["rows"]
    assert new_work_without_periods["can_confirm"] is False and rejected_row["result"] == "rejected"
    assert [err["field"] for err in rejected_row["errors"]] == ["shift_start"]


def test_operator_calendar_identity_binding_readonly_formula_and_xlsx_crlf_roundtrip(client, monkeypatch):
    import openpyxl.xml

    insert_operator = ("INSERT INTO Operators(operator_id,name,created_at,updated_at) "
                       "VALUES ('OP-REF','王五','2026-01-01 08:00:00','2026-01-01 08:00:00')")
    with database(client) as conn:
        conn.execute(insert_operator)
        conn.commit()

    preview_bytes = file_bytes(
        [("OP-REF", DAY, "工作日", "08:00", "16:00", "多行\r\n备注")],
        headers=("工号", "日期", "类型", "班次开始", "班次结束", "备注"),
    )
    prev_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={"file": (BytesIO(preview_bytes), "operator_calendar.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data",
    )
    assert prev_resp.status_code == 200, prev_resp.get_data(as_text=True)
    prev_data = prev_resp.get_json()["data"]
    assert prev_data["can_confirm"] is True

    # 删除后按同编号同字段重建人员（永久 ref 改变、Operators 行逐字段相同），旧预检确认必须 stale_write
    with database(client) as conn:
        conn.execute("DELETE FROM Operators WHERE operator_id='OP-REF'")
        conn.execute(insert_operator)
        conn.commit()
    stale = client.post(
        BASE + "/operator_calendar/confirm",
        json={
            "request_key": "op-ref-stale-00001",
            "write_token": prev_data["write_context"]["write_token"],
            "input": {"preview_ref": prev_data["preview_ref"]},
        },
    )
    assert stale.status_code == 409 and stale.get_json()["error"]["code"] == "stale_write"
    with database(client) as conn:
        assert not conn.execute("SELECT 1 FROM OperatorCalendar WHERE operator_id='OP-REF'").fetchall()

    # 只读参考列填 Excel 公式（=1+1）时，预检跳过只读列的公式报错并正常通过
    xlsx_with_readonly_formula = file_bytes(
        [("OP-REF", "=1+1", DAY, "工作日", "08:00", "16:00", "=1+1", "多行\r\n备注")],
        fmt="xlsx",
        headers=("工号", "人员姓名（只读）", "日期", "类型", "班次开始", "班次结束", "可排工时（小时）（只读）", "备注"),
    )
    formula_prev_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={"file": (BytesIO(xlsx_with_readonly_formula), "operator_calendar.xlsx"), "format": "xlsx", "mode": "upsert"},
        content_type="multipart/form-data",
    )
    assert formula_prev_resp.status_code == 200, formula_prev_resp.get_data(as_text=True)
    formula_prev = formula_prev_resp.get_json()["data"]
    assert formula_prev["can_confirm"] is True
    assert formula_prev["rows"][0]["errors"] == []
    confirmed_formula = client.post(
        BASE + "/operator_calendar/confirm",
        json={
            "request_key": "op-ref-formula-00002",
            "write_token": formula_prev["write_context"]["write_token"],
            "input": {"preview_ref": formula_prev["preview_ref"]},
        },
    )
    assert confirmed_formula.status_code == 200, confirmed_formula.get_data(as_text=True)

    # LXML=False 下含 \r\n 备注的日历 XLSX 导出再回导保持 unchanged
    with database(client) as conn:
        conn.execute(
            "UPDATE OperatorCalendar SET remark=? WHERE operator_id='OP-REF' AND date=?",
            ("多行\r\n备注", DAY),
        )
        conn.commit()
    monkeypatch.setattr(openpyxl.xml, "LXML", False)
    export_prev = client.post(
        BASE + "/operator_calendar/export-preview",
        json={"range": {"start_date": DAY, "end_date": DAY}},
    )
    assert export_prev.status_code == 200, export_prev.get_data(as_text=True)
    exported_xlsx = client.get(
        BASE + "/operator_calendar/export",
        query_string={"export_ref": export_prev.get_json()["data"]["export_ref"], "format": "xlsx"},
    )
    assert exported_xlsx.status_code == 200, exported_xlsx.get_data(as_text=True)
    roundtrip_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={"file": (BytesIO(exported_xlsx.data), "operator_calendar.xlsx"), "format": "xlsx", "mode": "upsert"},
        content_type="multipart/form-data",
    )
    assert roundtrip_resp.status_code == 200, roundtrip_resp.get_data(as_text=True)
    roundtrip_data = roundtrip_resp.get_json()["data"]
    assert roundtrip_data["can_confirm"] is True
    target_row, = roundtrip_data["rows"]
    assert target_row["result"] == "unchanged" and target_row["changes"] == {}
    assert target_row["after"]["remark"] == "多行\r\n备注"

    # D11: export-preview 传非法假值 snapshot_ref 时直接 400 拒绝，不静默降级为无令牌
    bad_snapshot = client.post(
        BASE + "/operator_calendar/export-preview",
        json={"range": {"start_date": DAY, "end_date": DAY}, "snapshot_ref": ""},
    )
    assert bad_snapshot.status_code == 400 and bad_snapshot.get_json()["error"]["code"] == "invalid_input"

    # D08: 预检时被工号不存在挡住的超长日期跨度，确认时人员已补建后触发 ValidationError(422) 而非 stale_write(409)
    span_bytes = file_bytes(
        [("OP-REF", "2020-01-01", "工作日", "08:00", "16:00"), ("OP-LATE", "2026-10-01", "工作日", "08:00", "16:00")],
        headers=("工号", "日期", "类型", "班次开始", "班次结束"),
    )
    span_prev = client.post(
        BASE + "/operator_calendar/preview",
        data={"file": (BytesIO(span_bytes), "operator_calendar.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data",
    ).get_json()["data"]
    with database(client) as conn:
        conn.execute("INSERT INTO Operators(operator_id,name,created_at,updated_at) VALUES ('OP-LATE','赵六','2026-01-01 08:00:00','2026-01-01 08:00:00')")
        conn.commit()
    span_confirm = client.post(
        BASE + "/operator_calendar/confirm",
        json={
            "request_key": "op-span-validation-00003",
            "write_token": span_prev["write_context"]["write_token"],
            "input": {"preview_ref": span_prev["preview_ref"]},
        },
    )
    assert span_confirm.status_code == 422 and span_confirm.get_json()["error"]["code"] == "invalid_input"

    # SRC-23: 导出绑定保存 row_count，下载在选中人员解析与快照核验后立即检查 XLSX 容量，早于 _public 投影；来源变化时超限下载优先返回 snapshot_stale
    from core.services.workbench.facts import file_writer
    from core.services.workbench.resource.calendar_files.operator_files import WorkbenchOperatorCalendarFileService

    op_ref = client.get("/api/workbench/v1/entities/operator", query_string={"query": "OP-REF"}).get_json()["data"]["entities"][0]["ref"]
    scoped_prev = client.post(
        BASE + "/operator_calendar/export-preview",
        json={"range": {"start_date": DAY, "end_date": DAY}, "scope": {"operator_refs": [op_ref]}},
    )
    assert scoped_prev.status_code == 200 and scoped_prev.get_json()["data"]["row_count"] == 1
    scoped_export_ref = scoped_prev.get_json()["data"]["export_ref"]

    monkeypatch.setattr(file_writer, "XLSX_MAX_ROWS", 2)
    boundary_xlsx = client.get(
        BASE + "/operator_calendar/export",
        query_string={"export_ref": scoped_export_ref, "format": "xlsx"},
    )
    assert boundary_xlsx.status_code == 200

    public_calls, orig_public = [], WorkbenchOperatorCalendarFileService._public

    def tracked_public(self, *args, **kwargs):
        public_calls.append(True)
        return orig_public(self, *args, **kwargs)

    monkeypatch.setattr(WorkbenchOperatorCalendarFileService, "_public", tracked_public)
    monkeypatch.setattr(file_writer, "XLSX_MAX_ROWS", 1)
    over_xlsx = client.get(
        BASE + "/operator_calendar/export",
        query_string={"export_ref": scoped_export_ref, "format": "xlsx"},
    )
    assert over_xlsx.status_code == 422 and over_xlsx.get_json()["error"]["code"] == "invalid_input"
    assert public_calls == []

    csv_ok = client.get(
        BASE + "/operator_calendar/export",
        query_string={"export_ref": scoped_export_ref, "format": "csv"},
    )
    assert csv_ok.status_code == 200 and len(public_calls) == 1

    public_calls.clear()
    with database(client) as conn:
        conn.execute("UPDATE OperatorCalendar SET efficiency=0.5 WHERE operator_id='OP-REF' AND date=?", (DAY,))
        conn.commit()
    stale_xlsx = client.get(
        BASE + "/operator_calendar/export",
        query_string={"export_ref": scoped_export_ref, "format": "xlsx"},
    )
    assert stale_xlsx.status_code == 409 and stale_xlsx.get_json()["error"]["code"] == "snapshot_stale"
    assert public_calls == []


def test_operator_calendar_import_batch_shares_period_decoding_across_rows(client, monkeypatch):
    from core.models import calendar as calendar_model
    from core.models import calendar_period_columns, calendar_periods
    from core.services.scheduler.calendar import defaults as defaults_module
    from core.services.scheduler.calendar import engine as engine_module

    assert not hasattr(calendar_period_columns, "decode_periods") and not hasattr(calendar_model, "decode_periods")
    with database(client) as conn:
        conn.executemany(
            "INSERT INTO Operators(operator_id,name) VALUES (?,?)",
            [("OP-B1", "甲"), ("OP-B2", "乙")],
        )
        conn.commit()

    decoded = []
    real_decode = calendar_periods.decode_periods

    def counted_decode(raw):
        decoded.append(raw)
        return real_decode(raw)

    for module in (
        calendar_periods,
        defaults_module,
        engine_module,
    ):
        monkeypatch.setattr(module, "decode_periods", counted_decode)

    shared_json = calendar_periods.encode_periods([{"start": "08:00", "end": "16:00", "day_offset": 0}])
    batch_bytes = file_bytes(
        [
            ("OP-B1", DAY, "工作日", "08:00", "16:00"),
            ("OP-B1", OTHER, "工作日", "08:00", "16:00"),
            ("OP-B2", DAY, "工作日", "08:00", "16:00"),
        ],
        headers=("工号", "日期", "类型", "班次开始", "班次结束"),
    )
    resp = client.post(
        BASE + "/operator_calendar/preview",
        data={"file": (BytesIO(batch_bytes), "operator_calendar.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["can_confirm"] is True
    assert [row["result"] for row in data["rows"]] == ["new", "new", "new"]
    assert all(
        row["after"]["period_count"] == "1"
        and row["after"]["shift_start"] == "08:00"
        and row["after"]["shift_end"] == "16:00"
        for row in data["rows"]
    )
    assert decoded.count(shared_json) == 1

    decoded.clear()
    global_data = preview_ok(
        client,
        [
            (DAY, "工作日", "08:00", "16:00", "", "", "", ""),
            (OTHER, "工作日", "08:00", "16:00", "", "", "", ""),
            ("2026-10-03", "工作日", "08:00", "16:00", "", "", "", ""),
        ],
    )
    assert global_data["can_confirm"] is True
    assert [row["result"] for row in global_data["rows"]] == ["new", "new", "new"]
    assert all(
        row["after"]["period_count"] == "1"
        and row["after"]["shift_start"] == "08:00"
        and row["after"]["shift_end"] == "16:00"
        for row in global_data["rows"]
    )
    assert decoded.count(shared_json) == 1


def test_overlong_period_count_strings_return_row_errors_instead_of_500(client):
    expected_error = [("period_count", "分段时间须同时填写工作时段数（0 至 8）；0 表示没有工作时段。")]
    preview = preview_ok(
        client,
        [
            (DAY, "工作日", "08:00", "16:00", "", "是", "是", "", "9" * 5000),
            (OTHER, "工作日", "08:00", "16:00", "", "是", "是", "", "0" * 5000 + "9"),
        ],
        headers=HEADERS + ("工作时段数",),
    )
    assert preview["can_confirm"] is False
    assert [row["result"] for row in preview["rows"]] == ["rejected", "rejected"]
    for row in preview["rows"]:
        assert [(err["field"], err["message"]) for err in row["errors"]] == expected_error

    with database(client) as conn:
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('OP-LONG','丙')")
        conn.commit()
    op_bytes = file_bytes(
        [
            ("OP-LONG", DAY, "工作日", "08:00", "16:00", "9" * 5000),
            ("OP-LONG", OTHER, "工作日", "08:00", "16:00", "0" * 5000 + "9"),
        ],
        headers=("工号", "日期", "类型", "班次开始", "班次结束", "工作时段数"),
    )
    op_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={"file": (BytesIO(op_bytes), "operator_calendar.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data",
    )
    assert op_resp.status_code == 200, op_resp.get_data(as_text=True)
    op_preview = op_resp.get_json()["data"]
    assert op_preview["can_confirm"] is False
    assert [row["result"] for row in op_preview["rows"]] == ["rejected", "rejected"]
    for row in op_preview["rows"]:
        assert [(err["field"], err["message"]) for err in row["errors"]] == expected_error
