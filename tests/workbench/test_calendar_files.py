"""全局工作日历文件的导入合同：按日期增量更新、不删除、与日历页走同一条领域校验。"""

from datetime import date, datetime
from uuid import uuid4

import pytest

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.common.excel_validators import _normalize_batch_date_cell
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.calendar_files.file_codec import read_date
from core.services.workbench.resource.calendar_files.files import WorkbenchCalendarFileService
from tests.workbench.calendar_file_support import HEADERS, decode, file_bytes, stored_day, stored_days
from tests.workbench.calendar_support import NIGHT, calendar_database  # noqa: F401

KIND = "work_calendar"
DAY = "2026-10-01"
OTHER = "2026-10-02"


def service(env):
    return WorkbenchCalendarFileService(env[0], KIND, clock=env[2])


def preview(env, rows, fmt="csv", headers=HEADERS):
    return service(env).preview_import(file_bytes(rows, fmt, headers), file_format=fmt)


def confirm(env, document, rows, fmt="csv", headers=HEADERS):
    conn, content = env[0], file_bytes(rows, fmt, headers)
    return WorkbenchCommandService(conn).execute(
        request_key="calendar-file-" + uuid4().hex, action=document.as_dict()["operation"],
        context_ref=document.digest, normalized_input={"preview_ref": document.digest}, guard=lambda: None,
        mutate=lambda _: service(env).confirm_import(document, content, file_format=fmt))


def results(document):
    return [(row["row"], row["result"]) for row in document.as_dict()["rows"]]


def test_new_day_is_created_and_other_days_stay(calendar_env):
    conn = calendar_env[0]
    before = stored_days(conn)
    rows = [(DAY, "工作日", "8", "100", "是", "是", "国庆调休")]
    document = preview(calendar_env, rows)
    assert results(document) == [(2, "new")]
    assert document.as_dict()["rows"][0]["before"] is None
    assert confirm(calendar_env, document, rows)["result"] == "committed"
    saved = stored_day(conn, DAY)
    assert saved["day_type"] == "workday" and saved["shift_hours"] == 8 and saved["efficiency"] == 1.0
    assert saved["allow_normal"] == "yes" and saved["remark"] == "国庆调休"
    # 文件里没写的日期完全不动，包括夹具里那天真实的跨夜班表。
    assert {day: row for day, row in stored_days(conn).items() if day != DAY} == before


def test_blank_cells_keep_current_values(calendar_env):
    conn = calendar_env[0]
    first = [(DAY, "工作日", "8", "80", "是", "否", "原备注")]
    confirm(calendar_env, preview(calendar_env, first), first)
    changed = [(DAY, "", "6", "", "", "", "")]
    document = preview(calendar_env, changed)
    body = document.as_dict()["rows"][0]
    assert body["result"] == "update" and set(body["changes"]) == {"shift_hours"}
    confirm(calendar_env, document, changed)
    saved = stored_day(conn, DAY)
    assert saved["shift_hours"] == 6 and saved["efficiency"] == 0.8
    assert saved["allow_urgent"] == "no" and saved["remark"] == "原备注"


def test_backslash_n_clears_remark_only(calendar_env):
    conn = calendar_env[0]
    first = [(DAY, "工作日", "8", "100", "是", "是", "要清掉")]
    confirm(calendar_env, preview(calendar_env, first), first)
    cleared = [(DAY, "", "", "", "", "", "\\N")]
    document = preview(calendar_env, cleared)
    assert document.as_dict()["rows"][0]["changes"]["remark"] == {"before": "要清掉", "after": None}
    confirm(calendar_env, document, cleared)
    assert stored_day(conn, DAY)["remark"] is None


@pytest.mark.parametrize("column,index", (("类型", 1), ("可排工时（小时）", 2), ("效率（%）", 3), ("允许普通件", 4)))
def test_other_columns_cannot_be_cleared(calendar_env, column, index):
    values = [DAY, "", "", "", "", "", ""]
    values[index] = "\\N"
    document = preview(calendar_env, [tuple(values)])
    assert results(document) == [(2, "rejected")]
    assert "不能清除" in document.as_dict()["rows"][0]["errors"][0]["message"]


def test_unchanged_row_is_not_written(calendar_env):
    rows = [(DAY, "工作日", "8", "100", "是", "是", "备注")]
    confirm(calendar_env, preview(calendar_env, rows), rows)
    document = preview(calendar_env, rows)
    assert results(document) == [(2, "unchanged")]
    assert confirm(calendar_env, document, rows)["result"] == "unchanged"


def test_holiday_with_hours_is_allowed_and_flagged(calendar_env):
    """界面的输入模型禁止假期带工时，文件放行，但必须在预检里讲清楚它会怎么显示。"""
    conn = calendar_env[0]
    rows = [(DAY, "假期", "4", "80", "是", "否", "放假加班半天")]
    document = preview(calendar_env, rows)
    row = document.as_dict()["rows"][0]
    assert row["result"] == "new" and row["requires_confirmation"]
    assert any("假期" in note and "工作日" in note for note in row["notes"])
    confirm(calendar_env, document, rows)
    saved = stored_day(conn, DAY)
    assert saved["day_type"] == "holiday" and saved["shift_hours"] == 4


def test_holiday_without_hours_is_a_plain_rest_day(calendar_env):
    conn = calendar_env[0]
    rows = [(DAY, "假期", "0", "", "否", "否", "国庆")]
    document = preview(calendar_env, rows)
    assert results(document) == [(2, "new")]
    assert not document.as_dict()["rows"][0]["notes"]
    confirm(calendar_env, document, rows)
    saved = stored_day(conn, DAY)
    assert saved["day_type"] == "holiday" and saved["shift_hours"] == 0


def test_missing_type_on_a_new_weekend_day_follows_the_default_rule(calendar_env):
    """这一天原来没配置过、类型又留空时按默认规则定；周末会算成假期。"""
    weekend = next(day for day in ("2026-10-03", "2026-10-04") if date.fromisoformat(day).weekday() >= 5)
    rows = [(weekend, "", "", "90", "", "", "")]
    document = preview(calendar_env, rows)
    assert results(document) == [(2, "new")]
    assert document.as_dict()["rows"][0]["after"]["day_type"] == "假期"


def test_real_night_shift_still_rejects_hours_only_change(calendar_env):
    """夹具里那天是用户设过的跨夜班表，只填工时与它对不上，必须拒绝而不是悄悄改成白班。"""
    conn = calendar_env[0]
    before = stored_day(conn, NIGHT)
    rows = [(NIGHT, "", "6", "", "", "", "")]
    document = preview(calendar_env, rows)
    assert results(document) == [(2, "rejected")]
    with pytest.raises(WorkbenchCommandRejected):
        confirm(calendar_env, document, rows)
    assert stored_day(conn, NIGHT) == before


def test_duplicate_dates_are_rejected(calendar_env):
    document = preview(calendar_env, [(DAY, "工作日", "8", "", "", "", ""), (DAY, "假期", "0", "", "", "", "")])
    assert results(document) == [(2, "rejected"), (3, "rejected")]
    assert document.as_dict()["rows"][0]["errors"][0]["code"] == "duplicate_entry"


@pytest.mark.parametrize("values", (
    ("", "工作日", "8", "", "", "", ""),
    ("2026-13-01", "工作日", "8", "", "", "", ""),
    ("2026-02-30", "工作日", "8", "", "", "", ""),
    ("2026-10-01 08:00", "工作日", "8", "", "", "", ""),
    (DAY, "放假", "8", "", "", "", ""),
    (DAY, "工作日", "25", "", "", "", ""),
    (DAY, "工作日", "很多", "", "", "", ""),
    (DAY, "工作日", "8", "0", "", "", ""),
    (DAY, "工作日", "8", "300", "", "", ""),
    (DAY, "工作日", "8", "", "也许", "", ""),
))
def test_bad_rows_are_rejected_without_writing(calendar_env, values):
    conn = calendar_env[0]
    before = stored_days(conn)
    document = preview(calendar_env, [values])
    assert results(document) == [(2, "rejected")]
    with pytest.raises(WorkbenchCommandRejected):
        confirm(calendar_env, document, [values])
    assert stored_days(conn) == before


def test_one_bad_row_blocks_the_whole_batch(calendar_env):
    conn = calendar_env[0]
    rows = [(DAY, "工作日", "8", "", "", "", ""), (OTHER, "工作日", "99", "", "", "", "")]
    document = preview(calendar_env, rows)
    assert results(document) == [(2, "new"), (3, "rejected")]
    with pytest.raises(WorkbenchCommandRejected):
        confirm(calendar_env, document, rows)
    assert stored_day(conn, DAY) is None


def test_range_wider_than_the_limit_is_rejected(calendar_env):
    with pytest.raises(ValidationError):
        preview(calendar_env, [("2026-01-01", "工作日", "8", "", "", "", ""),
                               ("2030-01-01", "工作日", "8", "", "", "", "")])


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_export_lists_only_configured_days_and_round_trips(calendar_env, fmt):
    conn = calendar_env[0]
    rows = [(DAY, "工作日", "8", "100", "是", "是", "配置过"), (OTHER, "假期", "0", "", "否", "否", "")]
    confirm(calendar_env, preview(calendar_env, rows), rows)
    with TransactionManager(conn).transaction():
        download = service(calendar_env).export(fmt, start_date="2026-09-01", end_date="2026-10-31")
    # 夹具里的 2026-09-09 也配置过，所以是三天；没配置过的日子一行都不该出现。
    assert download.row_count == 3
    headers, exported = decode(download, fmt)
    assert headers == list(HEADERS)
    assert [row[0] for row in exported] == [NIGHT, DAY, OTHER]
    again = service(calendar_env).preview_import(download.content, file_format=fmt)
    assert [row["result"] for row in again.as_dict()["rows"]] == ["unchanged"] * 3


def test_export_preview_counts_configured_days(calendar_env):
    conn = calendar_env[0]
    with TransactionManager(conn).transaction():
        arguments, count = service(calendar_env).preview_export(start_date="2026-10-01", end_date="2026-10-31")
    assert arguments == {"start_date": "2026-10-01", "end_date": "2026-10-31"} and count == 0


@pytest.mark.parametrize("bounds", (("2026-10-31", "2026-10-01"), ("2026-01-01", "2030-01-01"), ("bad", "2026-10-01")))
def test_bad_export_range_is_rejected(calendar_env, bounds):
    conn = calendar_env[0]
    with pytest.raises(WorkbenchCommandRejected), TransactionManager(conn).transaction():
        service(calendar_env).preview_export(start_date=bounds[0], end_date=bounds[1])


def test_range_snapshot_changes_only_when_the_range_changes(calendar_env):
    conn = calendar_env[0]
    with TransactionManager(conn).transaction():
        first = service(calendar_env).range_snapshot("2026-10-01", "2026-10-31")
    rows = [(DAY, "工作日", "8", "", "", "", "")]
    confirm(calendar_env, preview(calendar_env, rows), rows)
    with TransactionManager(conn).transaction():
        second = service(calendar_env).range_snapshot("2026-10-01", "2026-10-31")
        elsewhere = service(calendar_env).range_snapshot("2026-11-01", "2026-11-30")
    assert first != second and elsewhere != second


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_template_has_headers_and_no_rows(calendar_env, fmt):
    download = WorkbenchCalendarFileService.template(KIND, fmt)
    assert download.row_count == 0 and download.filename == "工作日历导入模板." + fmt
    headers, rows = decode(download, fmt)
    assert headers == list(HEADERS) and rows == []


def test_unknown_headers_are_rejected(calendar_env):
    with pytest.raises(ValidationError):
        preview(calendar_env, [(DAY,)], headers=("随便什么",))
    with pytest.raises(ValidationError):
        preview(calendar_env, [("工作日",)], headers=("类型",))


@pytest.mark.parametrize("value", ("2026-10-01", "2026/10/1", "2026-1-1", "2026-02-30", "2026-13-01",
                                   "2026-10-01 08:00", "2026-10-01T08:00", "", "  ", "not a date"))
def test_date_reading_matches_the_batch_import_rule(value):
    """日期口径必须与批次导入一致；那边的错误文案带停用词，所以只比判定不比文案。"""
    expected = _normalize_batch_date_cell(value, "日期")
    try:
        assert read_date(value) == expected["value"]
    except ValidationError:
        assert expected["error"] is not None or expected["value"] is None


@pytest.mark.parametrize("value", (date(2026, 10, 1), datetime(2026, 10, 1, 0, 0)))
def test_excel_date_cells_are_accepted(value):
    assert read_date(value) == "2026-10-01"


def test_excel_datetime_with_a_time_is_rejected():
    with pytest.raises(ValidationError):
        read_date(datetime(2026, 10, 1, 8, 30))
