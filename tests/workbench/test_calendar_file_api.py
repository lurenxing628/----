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
    preview_ok(client, [(DAY, "工作日", "8", "", "", "", "")])
    return client


def database(client):
    conn = sqlite3.connect(client.application.config["DATABASE_PATH"])
    conn.row_factory = sqlite3.Row
    return closing(conn)


def snapshot(client):
    with database(client) as conn:
        return [line for line in conn.iterdump() if not line.startswith('INSERT INTO "OperationLogs"')]


def days(client):
    with database(client) as conn:
        return {row["date"]: (row["day_type"], row["shift_hours"]) for row in conn.execute("SELECT * FROM WorkCalendar")}


def preview_ok(client, rows, fmt="csv"):
    fields = {"file": (BytesIO(file_bytes(rows, fmt)), "calendar." + fmt), "format": fmt, "mode": "upsert"}
    response = client.post(BASE + "/" + KIND + "/preview", data=fields, content_type="multipart/form-data")
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["data"]


def confirm(client, preview, key="calendar-file-request-00001"):
    return client.post(BASE + "/" + KIND + "/confirm", json={
        "request_key": key, "write_token": preview["write_context"]["write_token"],
        "input": {"preview_ref": preview["preview_ref"]}})


def test_preview_does_not_write_and_confirm_commits_once(client, monkeypatch):
    preview = preview_ok(client, [(DAY, "工作日", "8", "100", "是", "是", "调休"),
                                  (OTHER, "假期", "0", "", "否", "否", "")])
    # 只比日历表：应用启动后还会陆续补建与本功能无关的表和触发器，整库快照在首几次请求间本来就会变。
    assert days(client) == {}
    assert preview["operation"] == KIND + ".import" and preview["commit_policy"] == "atomic"
    assert preview["can_confirm"] and preview["mode"] == "upsert"
    assert [row["result"] for row in preview["rows"]] == ["new", "new"]
    assert [item["label"] for item in preview["columns"]] == list(HEADERS) + ["班次开始", "班次结束"] + PERIOD_HEADERS
    assert "entity_key" not in json.dumps(preview) and "revision" not in json.dumps(preview)

    from core.services.scheduler.calendar.admin import CalendarAdmin
    from data.repositories.workbench_calendar_query_repo import WorkbenchCalendarQueryRepository

    built, build = [], CalendarAdmin._build_work_calendar

    def build_once(self, **kwargs):
        model = build(self, **kwargs)
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


def test_legacy_null_shift_start_and_empty_remark_csv_roundtrip_without_false_diff(client):
    preview = preview_ok(client, [(DAY, "工作日", "8", "100", "是", "是", "初值")])
    assert confirm(client, preview, key="calendar-file-legacy-setup").status_code == 200
    with database(client) as conn:
        conn.execute(
            "UPDATE WorkCalendar SET shift_start=NULL, shift_end=NULL, shift_hours=NULL, efficiency=NULL, "
            "allow_normal=NULL, allow_urgent=NULL WHERE date=?",
            (DAY,),
        )
        conn.commit()

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

    same_defaults = preview_ok(client, [(DAY, "工作日", "8", "100", "是", "是", "带默认同值改备注")])
    assert same_defaults["can_confirm"] is True
    same_defaults_row, = same_defaults["rows"]
    assert same_defaults_row["errors"] == [] and same_defaults_row["result"] == "update"
    assert same_defaults_row["before"]["shift_start"] == same_defaults_row["after"]["shift_start"] == "08:00"
    assert same_defaults_row["changes"] == {"remark": {"before": "初值", "after": "带默认同值改备注"}}

    remark_only = preview_ok(client, [(DAY, "", "", "", "", "", "只改备注")])
    assert remark_only["can_confirm"] is True
    updated_row, = remark_only["rows"]
    assert updated_row["errors"] == [] and updated_row["result"] == "update"
    assert updated_row["before"]["shift_start"] == updated_row["after"]["shift_start"] == "08:00"
    assert updated_row["changes"] == {"remark": {"before": "初值", "after": "只改备注"}}

    hours_and_eff = preview_ok(client, [(DAY, "", "4", "80", "", "", "")])
    assert hours_and_eff["can_confirm"] is True
    hours_row, = hours_and_eff["rows"]
    assert hours_row["errors"] == [] and hours_row["result"] == "update"
    assert hours_row["after"]["shift_hours"] == "4" and hours_row["after"]["efficiency"] == "80"

    with database(client) as conn:
        conn.execute("UPDATE WorkCalendar SET remark='' WHERE date=?", (DAY,))
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('OP-CSV','张三')")
        conn.execute(
            "INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_start,shift_end,shift_hours,efficiency,allow_normal,allow_urgent,remark) "
            "VALUES ('OP-CSV',?,'workday','08:00','16:00',8,1,'yes','yes','')",
            (DAY,),
        )
        conn.commit()

    empty_remark_prev = client.post(
        BASE + "/" + KIND + "/export-preview",
        json={"range": {"start_date": DAY, "end_date": DAY}},
    )
    assert empty_remark_prev.status_code == 200
    empty_remark_csv = client.get(
        BASE + "/" + KIND + "/export",
        query_string={"export_ref": empty_remark_prev.get_json()["data"]["export_ref"], "format": "csv"},
    )
    assert empty_remark_csv.status_code == 200

    work_csv_reimport = client.post(
        BASE + "/" + KIND + "/preview",
        data={"file": (BytesIO(empty_remark_csv.data), "calendar.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data",
    )
    assert work_csv_reimport.status_code == 200, work_csv_reimport.get_data(as_text=True)
    work_reimport_data = work_csv_reimport.get_json()["data"]
    assert work_reimport_data["can_confirm"] is True
    assert work_reimport_data["rows"][0]["errors"] == [] and work_reimport_data["rows"][0]["result"] == "unchanged"
    assert work_reimport_data["rows"][0]["changes"] == {}

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
    assert op_roundtrip["can_confirm"] is True
    assert op_roundtrip["rows"][0]["errors"] == [] and op_roundtrip["rows"][0]["result"] == "unchanged"
    assert op_roundtrip["rows"][0]["changes"] == {}

    with database(client) as conn:
        conn.execute(
            "UPDATE OperatorCalendar SET shift_start='08:00', shift_end=NULL, shift_hours=4, "
            "allow_normal=NULL, allow_urgent=NULL WHERE operator_id='OP-CSV' AND date=?",
            (DAY,),
        )
        conn.commit()
        from core.services.workbench.resource.operator_calendars import WorkbenchOperatorCalendarService

        assert WorkbenchOperatorCalendarService(conn, "OP-CSV").month(2026, 10)["stats"]["work_days"] == 1
    legacy_op_export_prev = client.post(
        BASE + "/operator_calendar/export-preview",
        json={"range": {"start_date": DAY, "end_date": DAY}},
    )
    assert legacy_op_export_prev.status_code == 200, legacy_op_export_prev.get_data(as_text=True)
    legacy_op_exported = client.get(
        BASE + "/operator_calendar/export",
        query_string={"export_ref": legacy_op_export_prev.get_json()["data"]["export_ref"], "format": "csv"},
    )
    assert legacy_op_exported.status_code == 200, legacy_op_exported.get_data(as_text=True)
    legacy_op_roundtrip_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={"file": (BytesIO(legacy_op_exported.data), "operator_calendar.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data",
    )
    assert legacy_op_roundtrip_resp.status_code == 200, legacy_op_roundtrip_resp.get_data(as_text=True)
    legacy_op_roundtrip = legacy_op_roundtrip_resp.get_json()["data"]
    legacy_op_row, = legacy_op_roundtrip["rows"]
    assert legacy_op_roundtrip["can_confirm"] is True
    assert legacy_op_row["errors"] == [] and legacy_op_row["result"] == "unchanged"
    assert legacy_op_row["changes"] == {} and legacy_op_row["requires_confirmation"] is False
    assert legacy_op_row["before"]["shift_end"] == legacy_op_row["after"]["shift_end"] == "12:00"
    legacy_op_remark_resp = client.post(
        BASE + "/operator_calendar/preview",
        data={
            "file": (BytesIO(file_bytes([("OP-CSV", DAY, "仅改备注")], headers=("工号", "日期", "备注"))), "operator_calendar.csv"),
            "format": "csv",
            "mode": "upsert",
        },
        content_type="multipart/form-data",
    )
    assert legacy_op_remark_resp.status_code == 200, legacy_op_remark_resp.get_data(as_text=True)
    legacy_op_remark = legacy_op_remark_resp.get_json()["data"]
    assert legacy_op_remark["can_confirm"] is True
    assert legacy_op_remark["rows"][0]["result"] == "update"
    assert legacy_op_remark["rows"][0]["changes"] == {"remark": {"before": None, "after": "仅改备注"}}


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
            "SELECT shift_hours, periods_json, remark FROM OperatorCalendar WHERE operator_id='OP-ZERO' AND date=?",
            (DAY,),
        ).fetchone()
    assert (stored["shift_hours"], stored["periods_json"], stored["remark"]) == (0.0, "[]", "零工时仅改备注")

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
            "UPDATE OperatorCalendar SET day_type='workday', shift_start='08:00', shift_end=NULL, shift_hours=0.0, "
            "periods_json=NULL, remark='旧零工时' WHERE operator_id='OP-ZERO' AND date=?",
            (DAY,),
        )
        conn.commit()
    legacy_zero_prev = client.post(
        BASE + "/operator_calendar/export-preview",
        json={"range": {"start_date": DAY, "end_date": DAY}},
    )
    assert legacy_zero_prev.status_code == 200
    legacy_zero_csv = client.get(
        BASE + "/operator_calendar/export",
        query_string={"export_ref": legacy_zero_prev.get_json()["data"]["export_ref"], "format": "csv"},
    )
    assert legacy_zero_csv.status_code == 200
    legacy_zero_rt = client.post(
        BASE + "/operator_calendar/preview",
        data={"file": (BytesIO(legacy_zero_csv.data), "operator_calendar.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data",
    ).get_json()["data"]
    assert legacy_zero_rt["can_confirm"] is True
    assert legacy_zero_rt["rows"][0]["result"] == "unchanged"
    assert legacy_zero_rt["rows"][0]["after"]["shift_hours"] == "0"

    legacy_remark_bytes = file_bytes(
        [("OP-ZERO", DAY, "旧零工时改备注")],
        headers=("工号", "日期", "备注"),
    )
    legacy_remark_prev = client.post(
        BASE + "/operator_calendar/preview",
        data={"file": (BytesIO(legacy_remark_bytes), "operator_calendar.csv"), "format": "csv", "mode": "upsert"},
        content_type="multipart/form-data",
    ).get_json()["data"]
    assert legacy_remark_prev["can_confirm"] is True
    assert legacy_remark_prev["rows"][0]["result"] == "update"
    assert legacy_remark_prev["rows"][0]["after"]["shift_hours"] == "0"
    assert legacy_remark_prev["rows"][0]["changes"] == {"remark": {"before": "旧零工时", "after": "旧零工时改备注"}}


def test_operator_calendar_identity_binding_readonly_formula_and_xlsx_crlf_roundtrip(client, monkeypatch):
    import openpyxl.xml

    with database(client) as conn:
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('OP-REF','王五')")
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

    # 同秒重建同名同工号人员（永久身份 ref 改变，Operators 行不变）后，confirm 必须拒绝 stale_write
    with database(client) as conn:
        conn.execute(
            "UPDATE WorkbenchEntityRefs SET active=0 WHERE kind='operator' AND entity_key='OP-REF' AND active=1"
        )
        conn.execute(
            "INSERT INTO WorkbenchEntityRefs(ref, kind, entity_key, revision, active) "
            "VALUES (?, 'operator', 'OP-REF', 1, 1)",
            ("f" * 48,),
        )
        conn.commit()

    stale_confirm = client.post(
        BASE + "/operator_calendar/confirm",
        json={
            "request_key": "op-ref-stale-00001",
            "write_token": prev_data["write_context"]["write_token"],
            "input": {"preview_ref": prev_data["preview_ref"]},
        },
    )
    assert stale_confirm.status_code == 409, stale_confirm.get_data(as_text=True)
    assert stale_confirm.get_json()["error"]["code"] == "stale_write"

    # 只读参考列填 Excel 公式（=1+1）时，预检跳过只读列的公式报错并正常通过
    xlsx_with_readonly_formula = file_bytes(
        [("OP-REF", "=1+1", DAY, "工作日", "08:00", "16:00", "=1+1", "多行\r\n备注")],
        fmt="xlsx",
        headers=("operator_code", "operator_label", "date", "day_type", "shift_start", "shift_end", "shift_hours", "remark"),
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
