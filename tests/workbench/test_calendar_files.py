"""全局工作日历文件的导入合同：按日期增量更新、不删除、与日历页走同一条领域校验。"""

from datetime import date, datetime
from uuid import uuid4

import pytest

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.calendar_period_columns import PERIOD_COLUMNS, period_column_label
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.common.excel_validators import _normalize_batch_date_cell
from core.services.scheduler.calendar.service import CalendarService
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.calendar_files.file_codec import read_date
from core.services.workbench.resource.calendar_files.files import WorkbenchCalendarFileService
from tests.workbench.calendar_file_support import HEADERS, decode, file_bytes, stored_day, stored_days
from tests.workbench.calendar_support import NIGHT, calendar_database, run_day  # noqa: F401

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
    assert body["result"] == "update" and set(body["changes"]) == {"shift_hours", "shift_end"}
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


def test_holiday_switched_to_workday_without_hours_is_flagged(calendar_env):
    """假期只把类型改成工作日、工时留空，会存成 0 工时的工作日；文件不替用户补班次，但预检要说清楚。"""
    conn = calendar_env[0]
    rest = [(DAY, "假期", "", "", "", "", "")]
    confirm(calendar_env, preview(calendar_env, rest), rest)
    rows = [(DAY, "工作日", "", "", "", "", "")]
    document = preview(calendar_env, rows)
    row = document.as_dict()["rows"][0]
    assert row["result"] == "update" and row["requires_confirmation"]
    assert any("可排工时是 0" in note for note in row["notes"]), row["notes"]
    confirm(calendar_env, document, rows)
    saved = stored_day(conn, DAY)
    assert saved["day_type"] == "workday" and saved["shift_hours"] == 0
    # 原样再导一次不再提醒，免得已确认过的行每次都要确认。
    again = preview(calendar_env, rows).as_dict()["rows"][0]
    assert again["result"] == "unchanged" and not again["requires_confirmation"]


def test_unchanged_rows_are_not_flagged_or_confirmed_again(calendar_env):
    """不写入的行不提醒、也不要求确认：假期带工时、有工时却不可排产的天原样再导一次，不必每次再勾。"""
    rows = [(DAY, "假期", "4", "80", "是", "否", "放假加班半天"), (OTHER, "工作日", "4", "100", "否", "否", "停排")]
    first = preview(calendar_env, rows)
    assert all(row["requires_confirmation"] and row["notes"] for row in first.as_dict()["rows"])
    confirm(calendar_env, first, rows)
    again = preview(calendar_env, rows).as_dict()["rows"]
    assert [(row["result"], row["requires_confirmation"], row["notes"]) for row in again] == [("unchanged", False, [])] * 2


@pytest.mark.parametrize("column,header,text,filled", (("shift_hours", "可排工时（小时）", "8", 8),
                                                       ("efficiency", "效率（%）", "100", 1.0)))
def test_legacy_blank_hours_or_efficiency_follow_the_calendar_page(calendar_env, column, header, text, filled):
    """旧库升级加列没回填，工时或效率空着：导出和预检按日历引擎的解释写出（与日历页显示一致），不再整份报错。"""
    conn = calendar_env[0]
    CalendarService(conn).upsert(DAY, shift_start="08:00", shift_end="16:00", shift_hours=8, remark="旧")
    conn.execute(f"UPDATE WorkCalendar SET {column} = NULL WHERE date = ?", (DAY,))
    conn.commit()
    with TransactionManager(conn).transaction():
        download = service(calendar_env).export("csv", start_date=DAY, end_date=DAY)
    headers, exported = decode(download, "csv")
    assert exported[0][headers.index(header)] == text
    # 原样回导：这一格和引擎的解释相同，不算改动；只填日期的行沿用原行，同样不算改动。
    again = service(calendar_env).preview_import(download.content, file_format="csv").as_dict()["rows"]
    assert [(row["result"], row["errors"]) for row in again] == [("unchanged", [])]
    blank = preview(calendar_env, [(DAY, "", "", "", "", "", "")]).as_dict()["rows"][0]
    assert (blank["result"], blank["before"][column], blank["after"][column]) == ("unchanged", text, text)
    assert stored_day(conn, DAY)[column] is None
    rows = [(DAY, "", "", "", "", "", "只改备注")]
    document = preview(calendar_env, rows)
    row = document.as_dict()["rows"][0]
    assert (row["result"], set(row["changes"]), row["before"][column]) == ("update", {"remark"}, text)
    confirm(calendar_env, document, rows)
    assert (stored_day(conn, DAY)["remark"], stored_day(conn, DAY)[column]) == ("只改备注", filled)


def test_missing_type_on_a_new_weekend_day_follows_the_default_rule(calendar_env):
    """这一天原来没配置过、类型又留空时按默认规则定；周末会算成假期。"""
    weekend = next(day for day in ("2026-10-03", "2026-10-04") if date.fromisoformat(day).weekday() >= 5)
    rows = [(weekend, "", "", "90", "", "", "")]
    document = preview(calendar_env, rows)
    assert results(document) == [(2, "new")]
    assert document.as_dict()["rows"][0]["after"]["day_type"] == "假期"


def test_night_shift_hours_change_preserves_start_and_recalculates_end(calendar_env):
    conn = calendar_env[0]
    before = stored_day(conn, NIGHT)
    rows = [(NIGHT, "", "6", "", "", "", "")]
    document = preview(calendar_env, rows)
    assert results(document) == [(2, "update")]
    confirm(calendar_env, document, rows)
    after = stored_day(conn, NIGHT)
    assert after["shift_start"] == before["shift_start"] == "22:30"
    assert after["shift_end"] == "04:30" and after["shift_hours"] == 6


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
    assert headers == list(HEADERS) + ["班次开始", "班次结束"] + [period_column_label(key) for key in PERIOD_COLUMNS]
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
    assert headers == list(HEADERS) + ["班次开始", "班次结束"] + [period_column_label(key) for key in PERIOD_COLUMNS] and rows == []


def test_unknown_headers_are_rejected(calendar_env):
    with pytest.raises(ValidationError):
        preview(calendar_env, [(DAY,)], headers=("随便什么",))
    with pytest.raises(ValidationError):
        preview(calendar_env, [("工作日",)], headers=("类型",))


@pytest.mark.parametrize("value", ("2026-10-01", "2026/10/1", "2026-1-1", "2026-02-30", "2026-13-01",
                                   "2026-10-01 08:00", "2026-10-01T08:00", "", "  ", "not a date"))
def test_date_reading_matches_the_batch_import_rule(value):
    """年月日文本与批次采用相同格式；原生非午夜 datetime 另有日历拒绝规则。"""
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


def test_only_date_on_an_unconfigured_day_reports_no_write(calendar_env):
    """只填日期、其余全空的行对没配置过的天什么都不写，回执必须照实说。

    原来预检一律判 new、回执报 committed 且 summary 里 new 计 1，而库里一行没落：
    用户被告知"导入了 1 天"，实际什么都没发生。
    """
    conn = calendar_env[0]
    before = stored_days(conn)
    rows = [(OTHER, "", "", "", "", "", "")]
    document = preview(calendar_env, rows)
    assert results(document) == [(2, "unchanged")]
    assert document.as_dict()["summary"]["new"] == 0
    outcome = confirm(calendar_env, document, rows)
    assert outcome["result"] == "unchanged"
    assert stored_days(conn) == before, "回执说没写，库里就不能有变化"


def test_only_date_on_a_configured_day_stays_unchanged(calendar_env):
    """回归：已配置过的天走的是另一条分支，本来就判 unchanged。"""
    conn = calendar_env[0]
    seed = [(DAY, "工作日", "8", "100", "是", "是", "白班")]
    confirm(calendar_env, preview(calendar_env, seed), seed)
    saved = stored_day(conn, DAY)
    rows = [(DAY, "", "", "", "", "", "")]
    document = preview(calendar_env, rows)
    assert results(document) == [(2, "unchanged")]
    assert confirm(calendar_env, document, rows)["result"] == "unchanged"
    assert stored_day(conn, DAY) == saved


SATURDAY = "2026-10-03"


def test_hours_that_can_never_be_scheduled_are_called_out(calendar_env):
    """周六只填工时会存成"假期 N 小时且不可排产"，预检必须说清楚，不能让用户自己撞。

    类型留空时按日期取默认规则，周末的默认是假期且两个优先级都为否；日历页又把
    "假期带工时"显示成工作日。用户安排了 4 小时加班，看着像工作日，排产时一道工序
    也排不进来。roadmap 4.5 要求这种情况要么定死要么显式提示。
    """
    document = preview(calendar_env, [(SATURDAY, "", "4", "", "", "", "")])
    row = document.as_dict()["rows"][0]
    assert row["result"] == "new" and row["requires_confirmation"]
    assert row["after"]["allow_normal"] == "否" and row["after"]["allow_urgent"] == "否"
    assert any("一道工序也排不进来" in note for note in row["notes"]), row["notes"]


def test_holiday_overtime_that_allows_parts_is_not_flagged_as_unschedulable(calendar_env):
    """回归：假期加班并明确允许排产，是已裁决的用法，不该报"排不进来"。"""
    document = preview(calendar_env, [("2026-10-04", "假期", "4", "100", "是", "是", "假期加班")])
    row = document.as_dict()["rows"][0]
    assert row["result"] == "new"
    assert not any("一道工序也排不进来" in note for note in row["notes"]), row["notes"]


def test_whitespace_only_cell_is_rejected_instead_of_silently_clearing(calendar_env):
    """只填空格的格子和真正的空格子在文件里长得一样，含义却相反。

    空格子是"保持原样"，纯空格原来被 strip 成 None 当作"清除"：用户多打一个空格
    就把备注清掉了，而且看不出来。
    """
    conn = calendar_env[0]
    seed = [(DAY, "工作日", "8", "100", "是", "是", "原备注")]
    confirm(calendar_env, preview(calendar_env, seed), seed)
    document = preview(calendar_env, [(DAY, "", "", "", "", "", "   ")])
    assert results(document) == [(2, "rejected")]
    assert document.as_dict()["rows"][0]["errors"][0]["field"] == "remark"
    assert stored_day(conn, DAY)["remark"] == "原备注"


def test_backslash_n_is_still_the_way_to_clear_a_remark(calendar_env):
    """回归：明确的清除标记照旧工作，拒绝纯空格不影响它。"""
    conn = calendar_env[0]
    seed = [(DAY, "工作日", "8", "100", "是", "是", "原备注")]
    confirm(calendar_env, preview(calendar_env, seed), seed)
    rows = [(DAY, "", "", "", "", "", r"\N")]
    confirm(calendar_env, preview(calendar_env, rows), rows)
    assert stored_day(conn, DAY)["remark"] is None


@pytest.mark.parametrize('fmt', ['csv', 'xlsx'])
def test_minute_hours_and_precise_efficiency_roundtrip_with_editable_window(calendar_env, fmt):
    conn = calendar_env[0]
    rows = [(DAY, '工作日', '', '87.6543219', '是', '是', '夜班', '22:30', '06:40')]
    headers = HEADERS + ('班次开始', '班次结束')
    content = file_bytes(rows, fmt, headers)
    document = service(calendar_env).preview_import(content, file_format=fmt)
    confirm(calendar_env, document, rows, fmt, headers)
    saved = stored_day(conn, DAY)
    assert saved['shift_hours'] == 8 + 1 / 6 and saved['shift_end'] == '06:40'
    with TransactionManager(conn).transaction():
        download = service(calendar_env).export(fmt, start_date=DAY, end_date=DAY)
    again = service(calendar_env).preview_import(download.content, file_format=fmt)
    assert results(again) == [(2, 'unchanged')]


@pytest.mark.parametrize('start,end', [('08:00:59', '16:00:59'), ('2026-10-01 08:00', '16:00')])
def test_global_file_rejects_time_information_loss(calendar_env, start, end):
    document = preview(calendar_env, [(DAY, start, end)], headers=('日期', '班次开始', '班次结束'))
    assert results(document) == [(2, 'rejected')]
    assert stored_day(calendar_env[0], DAY) is None


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_export_efficiency_has_no_float_tail_and_round_trips(calendar_env, fmt):
    """效率 57% 存成 0.57，乘回百分数是 56.99999999999999；导出写成 57，回导仍判不变。"""
    conn = calendar_env[0]
    for day, efficiency in ((DAY, 0.57), (OTHER, 0.29)):
        CalendarService(conn).upsert(day, shift_start="08:00", shift_end="16:00", efficiency=efficiency)
    with TransactionManager(conn).transaction():
        download = service(calendar_env).export(fmt, start_date=DAY, end_date=OTHER)
    headers, exported = decode(download, fmt)
    assert [row[headers.index("效率（%）")] for row in exported] == ["57", "29"]
    again = service(calendar_env).preview_import(download.content, file_format=fmt)
    assert results(again) == [(2, "unchanged"), (3, "unchanged")]


def test_calendar_numbers_share_the_page_number_text():
    """工时与其它文件、页面同一写法；效率只多一道 15 位收尾，很小的数也不写成 1e-05。"""
    from core.services.workbench.facts import table_cells
    from core.services.workbench.resource.calendar_files import file_writer

    assert file_writer.number_text is table_cells.number_text
    assert [file_writer.number_text(value) for value in (8.0, 7.5, 8 + 1 / 6, 1e-05, 0)] == [
        "8", "7.5", "8.166666666666666", "0.00001", "0"]
    assert [file_writer.percent_text(value) for value in (0.57, 1.0, 1e-07, 0.123456789)] == ["57", "100", "0.00001", "12.3456789"]


@pytest.mark.parametrize("headers,values", (
    (("日期", "类型", "可排工时（小时）", "允许普通件", "允许急件"), (DAY, "工作日", "8", "是", "是")),
    (("日期", "类型", "班次开始", "班次结束", "允许普通件", "允许急件"), (DAY, "工作日", "08:00", "16:00", "是", "是")),
))
def test_rest_day_saved_with_empty_periods_returns_to_work_from_single_shift_columns(calendar_env, headers, values):
    """页面把休息日存成空时段；文件只填工时或班次起止也能改回工作日，不再误报"已按多时段设置"。"""
    conn = calendar_env[0]
    run_day(calendar_env, "upsert", {"date": DAY, "fields": {"type": "rest", "periods": []}})
    assert stored_day(conn, DAY)["periods_json"] == "[]"
    document = preview(calendar_env, [values], headers=headers)
    assert results(document) == [(2, "update")], document.as_dict()["rows"][0]["errors"]
    confirm(calendar_env, document, [values], headers=headers)
    saved = stored_day(conn, DAY)
    assert (saved["day_type"], saved["shift_start"], saved["shift_end"], saved["shift_hours"]) == ("workday", "08:00", "16:00", 8)
    assert saved["periods_json"] is None


def test_day_whose_shift_runs_past_the_last_date_is_rejected_on_its_own_row(calendar_env):
    """默认工作时间跨夜时，9999-12-31 的班次会跨出系统能处理的日期：只拒这一行并说明原因，不报服务器错误。"""
    conn = calendar_env[0]
    conn.execute("INSERT INTO WorkbenchCalendarDefaults(singleton, periods_json) VALUES (1, ?)",
                 ('[{"start":"22:00","end":"06:00","day_offset":0}]',))
    conn.commit()
    document = preview(calendar_env, [("9999-12-30", "", "", "", "", "", "夜班"), ("9999-12-31", "", "", "", "", "", "夜班")])
    assert results(document) == [(2, "new"), (3, "rejected")]
    assert "超出了系统能处理的最后日期" in document.as_dict()["rows"][1]["errors"][0]["message"]


def test_file_night_shift_on_the_last_date_is_rejected_at_preview_not_at_confirm(calendar_env):
    """默认时段不跨夜、文件给 9999-12-31 排夜班：预检就只拒这一行，不会预检通过、确认时整批回滚。"""
    headers = ("日期", "类型", "班次开始", "班次结束", "允许普通件", "允许急件", "备注")
    rows = [("9999-12-30", "工作日", "08:00", "16:00", "是", "是", "白班"),
            ("9999-12-31", "工作日", "22:00", "06:00", "是", "是", "夜班")]
    document = preview(calendar_env, rows, headers=headers)
    assert results(document) == [(2, "new"), (3, "rejected")]
    error = document.as_dict()["rows"][1]["errors"][0]
    assert error["field"] == "date" and "班次在当天结束" in error["message"]


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_export_keeps_minute_hours_exact_for_open_ended_legacy_rows(calendar_env, fmt):
    """旧行只存开始和 7 小时 20 分（22/3 小时）、结束为空：工时按原值导出，回导只补出结束时刻，不会被判存不稳。"""
    conn = calendar_env[0]
    CalendarService(conn).upsert(DAY, shift_start="08:00", shift_hours=22 / 3)
    conn.execute("UPDATE WorkCalendar SET shift_end = NULL WHERE date = ?", (DAY,))
    conn.commit()
    with TransactionManager(conn).transaction():
        download = service(calendar_env).export(fmt, start_date=DAY, end_date=DAY)
    headers, exported = decode(download, fmt)
    assert exported[0][headers.index("可排工时（小时）")] == str(22 / 3)
    rows = service(calendar_env).preview_import(download.content, file_format=fmt).as_dict()["rows"]
    assert [(row["result"], row["errors"]) for row in rows] == [("update", [])]
    assert rows[0]["changes"] == {"shift_end": {"before": None, "after": "15:20"}}
