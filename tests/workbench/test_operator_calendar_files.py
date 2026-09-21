"""个人工作日历文件的导入合同：按工号加日期增量更新、不删除、与人员详情面板同一条校验链。"""

from datetime import date, datetime, time
from uuid import uuid4

import pytest

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.calendar_files.operator_files import WorkbenchOperatorCalendarFileService
from core.services.workbench.resource.operator_calendars import WorkbenchOperatorCalendarService
from tests.workbench.calendar_file_support import file_bytes
from tests.workbench.calendar_support import NIGHT, calendar_database, seed_d06_resources  # noqa: F401

KIND = "operator_calendar"
OPERATOR = "CO"
DAY = "2026-10-05"
OTHER = "2026-10-06"
HEADERS = ("工号", "日期", "类型", "班次开始", "班次结束", "效率（%）", "允许普通件", "允许急件", "备注")


@pytest.fixture(name="file_env")
def operator_file_env(calendar_env):
    """个人日历文件要按人员编号解析，所以这套夹具要装上资源身份元数据。"""
    conn, _, clock = calendar_env
    seed_d06_resources(conn)
    return conn, clock


def service(env):
    return WorkbenchOperatorCalendarFileService(env[0], clock=env[1])


def preview(env, rows, fmt="csv", headers=HEADERS):
    return service(env).preview_import(file_bytes(rows, fmt, headers), file_format=fmt)


def confirm(env, document, rows, fmt="csv", headers=HEADERS):
    conn, content = env[0], file_bytes(rows, fmt, headers)
    return WorkbenchCommandService(conn).execute(
        request_key="operator-calendar-file-" + uuid4().hex, action=document.as_dict()["operation"],
        context_ref=document.digest, normalized_input={"preview_ref": document.digest}, guard=lambda: None,
        mutate=lambda _: service(env).confirm_import(document, content, file_format=fmt))


def stored(conn, day, operator=OPERATOR):
    row = conn.execute("SELECT * FROM OperatorCalendar WHERE operator_id=? AND date=?", (operator, day)).fetchone()
    return dict(row) if row else None


def results(document):
    return [(row["row"], row["result"]) for row in document.as_dict()["rows"]]


def test_shift_window_drives_hours_and_other_days_stay(file_env):
    conn = file_env[0]
    rows = [(OPERATOR, DAY, "工作日", "09:00", "17:30", "90", "是", "否", "早班")]
    document = preview(file_env, rows)
    assert results(document) == [(2, "new")]
    assert document.as_dict()["rows"][0]["business_code"] == OPERATOR + " / " + DAY
    assert confirm(file_env, document, rows)["result"] == "committed"
    saved = stored(conn, DAY)
    assert saved["shift_start"] == "09:00" and saved["shift_end"] == "17:30" and saved["shift_hours"] == 8.5
    assert saved["efficiency"] == 0.9 and saved["remark"] == "早班"
    # 夹具里 CO 在 2026-09-09 有一条个人日历，文件没提它就不该动。
    assert stored(conn, NIGHT)["remark"] == "personal exception"


def test_blank_cells_keep_current_values(file_env):
    conn = file_env[0]
    first = [(OPERATOR, DAY, "工作日", "09:00", "17:30", "90", "是", "否", "原备注")]
    confirm(file_env, preview(file_env, first), first)
    changed = [(OPERATOR, DAY, "", "", "18:00", "", "", "", "")]
    document = preview(file_env, changed)
    body = document.as_dict()["rows"][0]
    assert body["result"] == "update" and set(body["changes"]) == {"shift_end"}
    confirm(file_env, document, changed)
    saved = stored(conn, DAY)
    assert saved["shift_end"] == "18:00" and saved["shift_hours"] == 9.0
    assert saved["efficiency"] == 0.9 and saved["remark"] == "原备注" and saved["allow_urgent"] == "no"


def test_overnight_shift_is_supported(file_env):
    conn = file_env[0]
    rows = [(OPERATOR, DAY, "工作日", "22:00", "06:00", "100", "是", "是", "")]
    confirm(file_env, preview(file_env, rows), rows)
    saved = stored(conn, DAY)
    assert saved["shift_start"] == "22:00" and saved["shift_end"] == "06:00" and saved["shift_hours"] == 8.0


def test_holiday_row_clears_the_shift(file_env):
    conn = file_env[0]
    work = [(OPERATOR, DAY, "工作日", "09:00", "17:30", "100", "是", "是", "")]
    confirm(file_env, preview(file_env, work), work)
    rest = [(OPERATOR, DAY, "假期", "", "", "", "否", "否", "调休")]
    confirm(file_env, preview(file_env, rest), rest)
    saved = stored(conn, DAY)
    assert saved["day_type"] == "holiday" and saved["shift_hours"] == 0
    assert saved["allow_normal"] == "no" and saved["allow_urgent"] == "no"


def test_every_row_says_it_overrides_the_shift_rotation(file_env):
    document = preview(file_env, [(OPERATOR, DAY, "工作日", "09:00", "17:30", "100", "是", "是", "")])
    row = document.as_dict()["rows"][0]
    assert row["requires_confirmation"] and any("班次轮换" in note for note in row["notes"])


def test_unchanged_row_is_not_written(file_env):
    rows = [(OPERATOR, DAY, "工作日", "09:00", "17:30", "100", "是", "是", "备注")]
    confirm(file_env, preview(file_env, rows), rows)
    document = preview(file_env, rows)
    assert results(document) == [(2, "unchanged")]
    assert confirm(file_env, document, rows)["result"] == "unchanged"


def test_rows_for_other_operators_are_independent(file_env):
    conn = file_env[0]
    conn.execute("INSERT INTO Operators (operator_id, name) VALUES ('CO2', 'other')")
    conn.commit()
    rows = [(OPERATOR, DAY, "工作日", "09:00", "17:30", "100", "是", "是", ""),
            ("CO2", DAY, "工作日", "07:00", "15:00", "100", "是", "是", "")]
    document = preview(file_env, rows)
    assert results(document) == [(2, "new"), (3, "new")]
    confirm(file_env, document, rows)
    assert stored(conn, DAY)["shift_start"] == "09:00"
    assert stored(conn, DAY, "CO2")["shift_start"] == "07:00"


def test_duplicate_operator_and_date_pairs_are_rejected(file_env):
    document = preview(file_env, [(OPERATOR, DAY, "工作日", "09:00", "", "", "", "", ""),
                                  (OPERATOR, DAY, "假期", "", "", "", "", "", "")])
    assert results(document) == [(2, "rejected"), (3, "rejected")]
    assert document.as_dict()["rows"][0]["errors"][0]["code"] == "duplicate_entry"


@pytest.mark.parametrize("values", (
    ("", DAY, "工作日", "09:00", "", "", "", "", ""),
    ("NOPE", DAY, "工作日", "09:00", "", "", "", "", ""),
    (" CO", DAY, "工作日", "09:00", "", "", "", "", ""),
    (OPERATOR, "", "工作日", "09:00", "", "", "", "", ""),
    (OPERATOR, "2026-02-30", "工作日", "09:00", "", "", "", "", ""),
    (OPERATOR, DAY, "放假", "09:00", "", "", "", "", ""),
    (OPERATOR, DAY, "工作日", "9:00", "", "", "", "", ""),
    (OPERATOR, DAY, "工作日", "09:00", "17:70", "", "", "", ""),
    (OPERATOR, DAY, "工作日", "09:00", "", "0", "", "", ""),
    (OPERATOR, DAY, "工作日", "09:00", "", "300", "", "", ""),
    (OPERATOR, DAY, "工作日", "09:00", "", "", "也许", "", ""),
))
def test_bad_rows_are_rejected_without_writing(file_env, values):
    conn = file_env[0]
    document = preview(file_env, [values])
    assert results(document) == [(2, "rejected")]
    with pytest.raises(WorkbenchCommandRejected):
        confirm(file_env, document, [values])
    assert stored(conn, DAY) is None


def test_one_bad_row_blocks_the_whole_batch(file_env):
    conn = file_env[0]
    rows = [(OPERATOR, DAY, "工作日", "09:00", "", "", "", "", ""),
            (OPERATOR, OTHER, "工作日", "09:00", "", "999", "", "", "")]
    document = preview(file_env, rows)
    assert results(document) == [(2, "new"), (3, "rejected")]
    with pytest.raises(WorkbenchCommandRejected):
        confirm(file_env, document, rows)
    assert stored(conn, DAY) is None


def test_file_cannot_clear_a_day(file_env):
    """文件不做删除：整天要恢复成按班次，只能走人员详情的范围清除。"""
    conn = file_env[0]
    rows = [(OPERATOR, DAY, "工作日", "09:00", "17:30", "100", "是", "是", "")]
    confirm(file_env, preview(file_env, rows), rows)
    cleared = [(OPERATOR, DAY, "\\N", "", "", "", "", "", "")]
    document = preview(file_env, cleared)
    assert results(document) == [(2, "rejected")]
    assert stored(conn, DAY) is not None


def test_backslash_n_clears_remark_and_shift_end_only(file_env):
    conn = file_env[0]
    rows = [(OPERATOR, DAY, "工作日", "09:00", "17:30", "100", "是", "是", "要清掉")]
    confirm(file_env, preview(file_env, rows), rows)
    cleared = [(OPERATOR, DAY, "", "", "\\N", "", "", "", "\\N")]
    document = preview(file_env, cleared)
    assert document.as_dict()["rows"][0]["result"] == "update"
    confirm(file_env, document, cleared)
    saved = stored(conn, DAY)
    # 班次结束清掉后按 8 小时重推，这与界面上留空结束时刻的行为一致。
    assert saved["remark"] is None and saved["shift_hours"] == 8.0 and saved["shift_end"] == "17:00"


@pytest.mark.parametrize("fmt", ("csv", "xlsx"))
def test_export_lists_only_configured_days_and_round_trips(file_env, fmt):
    conn = file_env[0]
    rows = [(OPERATOR, DAY, "工作日", "09:00", "17:30", "90", "是", "否", "早班"),
            (OPERATOR, OTHER, "假期", "", "", "", "否", "否", "")]
    confirm(file_env, preview(file_env, rows), rows)
    with TransactionManager(conn).transaction():
        download = service(file_env).export(fmt, start_date="2026-09-01", end_date="2026-10-31")
    # 夹具里 2026-09-09 也设置过，所以是三天。
    assert download.row_count == 3
    again = service(file_env).preview_import(download.content, file_format=fmt)
    assert [row["result"] for row in again.as_dict()["rows"]] == ["unchanged"] * 3


def test_export_can_be_limited_to_selected_operators(file_env):
    conn = file_env[0]
    rows = [(OPERATOR, DAY, "工作日", "09:00", "17:30", "100", "是", "是", "")]
    confirm(file_env, preview(file_env, rows), rows)
    with TransactionManager(conn).transaction():
        _, everyone = service(file_env).preview_export(start_date="2026-10-01", end_date="2026-10-31")
        _, nobody = service(file_env).preview_export(start_date="2026-10-01", end_date="2026-10-31", selected_refs=[])
    assert everyone == 1 and nobody == 0


def test_range_wider_than_the_limit_is_rejected(file_env):
    with pytest.raises(ValidationError):
        preview(file_env, [(OPERATOR, "2026-01-01", "工作日", "09:00", "", "", "", "", ""),
                           (OPERATOR, "2030-01-01", "工作日", "09:00", "", "", "", "", "")])


def test_unknown_headers_are_rejected(file_env):
    with pytest.raises(ValidationError):
        preview(file_env, [(OPERATOR,)], headers=("随便什么",))
    with pytest.raises(ValidationError):
        preview(file_env, [(DAY,)], headers=("日期",))


def test_panel_and_file_agree_on_what_can_be_saved(file_env):
    """界面存不了的组合文件也存不了：上班的日子没有班次开始，两边都要拒绝。"""
    conn, clock = file_env
    panel = WorkbenchOperatorCalendarService(conn, OPERATOR, clock=clock)
    with pytest.raises(ValidationError):
        panel.normalize("upsert", {"date": DAY, "fields": {"type": "work", "eff": 100}})
    document = preview(file_env, [(OPERATOR, DAY, "工作日", "", "", "100", "", "", "")])
    assert results(document) == [(2, "rejected")]
    assert document.as_dict()["rows"][0]["errors"][0]["field"] == "shift_start"


def test_turning_a_holiday_back_to_work_needs_a_shift_start(file_env):
    """假期行没有班次可继承，改回上班时必须一起补上开始时刻。"""
    rest = [(OPERATOR, DAY, "假期", "", "", "", "否", "否", "")]
    confirm(file_env, preview(file_env, rest), rest)
    assert results(preview(file_env, [(OPERATOR, DAY, "工作日", "", "", "", "", "", "")])) == [(2, "rejected")]
    back = [(OPERATOR, DAY, "工作日", "08:00", "", "", "是", "是", "")]
    document = preview(file_env, back)
    assert results(document) == [(2, "update")]
    confirm(file_env, document, back)
    assert stored(file_env[0], DAY)["shift_hours"] == 8.0


# ---------------------------------------------------------------------------
# Excel 时间格子：与日期格子同一口径
# ---------------------------------------------------------------------------


def test_excel_time_cells_are_accepted_like_excel_date_cells(file_env):
    """同一份文件里日期列接受 Excel 原生格子，时刻列原来却只收文本，是两套标准。

    用户在 Excel 里把班次起止设成时间格式，界面上显示 08:00，文件却被拒。
    """
    rows = [(OPERATOR, date(2026, 10, 5), "工作日", time(8, 0), time(17, 0), 100, "是", "是", "")]
    document = preview(file_env, rows, fmt="xlsx")
    assert results(document) == [(2, "new")]
    confirm(file_env, document, rows, fmt="xlsx")
    saved = stored(file_env[0], DAY)
    assert saved["shift_start"] == "08:00" and saved["shift_end"] == "17:00" and saved["shift_hours"] == 9.0


def test_time_cell_with_seconds_is_rejected_not_truncated(file_env):
    """"分钟到分为止"是既有合同：带秒的格子要报错，不能悄悄截断。"""
    rows = [(OPERATOR, date(2026, 10, 5), "工作日", time(8, 0, 30), time(17, 0), 100, "是", "是", "")]
    document = preview(file_env, rows, fmt="xlsx")
    assert results(document) == [(2, "rejected")]
    assert document.as_dict()["rows"][0]["errors"][0]["field"] == "shift_start"


def test_time_cell_carrying_a_date_is_rejected(file_env):
    """把整个时间戳填进时刻列时要报错：默默丢掉日期属于静默改值。"""
    rows = [(OPERATOR, date(2026, 10, 5), "工作日", datetime(2026, 10, 5, 8, 0), time(17, 0), 100, "是", "是", "")]
    document = preview(file_env, rows, fmt="xlsx")
    assert results(document) == [(2, "rejected")]
    assert document.as_dict()["rows"][0]["errors"][0]["field"] == "shift_start"


def test_text_clock_still_works_after_the_codec_layer_normalises(file_env):
    """回归：文本时刻仍然走界面输入模型那条校验链，行为不变。"""
    rows = [(OPERATOR, DAY, "工作日", "08:00", "17:00", "100", "是", "是", "")]
    confirm(file_env, preview(file_env, rows), rows)
    assert stored(file_env[0], DAY)["shift_start"] == "08:00"
    assert results(preview(file_env, [(OPERATOR, DAY, "工作日", "8点", "", "", "", "", "")])) == [(2, "rejected")]
