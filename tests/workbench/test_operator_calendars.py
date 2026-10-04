"""个人工作日历的写入合同：以班次起止为准、只动这一个人、范围清除是唯一的批量出路。"""

from uuid import uuid4

import pytest

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.operator_calendars import WorkbenchOperatorCalendarService
from tests.workbench.calendar_support import NIGHT, calendar_database  # noqa: F401

OPERATOR = "CO"
DAY = "2026-10-05"
OTHER = "2026-10-06"
WORK = {"type": "work", "shiftStart": "09:00", "shiftEnd": "17:30", "eff": 90,
        "allowNormal": "yes", "allowUrgent": "no", "note": "早班"}


def service(env):
    return WorkbenchOperatorCalendarService(env[0], OPERATOR, clock=env[2])


def stored(conn, day, operator=OPERATOR):
    row = conn.execute("SELECT * FROM OperatorCalendar WHERE operator_id=? AND date=?", (operator, day)).fetchone()
    return dict(row) if row else None


def run(env, action, payload, key=None):
    conn = env[0]
    domain = service(env)
    normalized = domain.normalize(action, payload)
    return WorkbenchCommandService(conn).execute(
        request_key=key or "operator-calendar-" + uuid4().hex, action="operator.calendar_" + action,
        context_ref="operator:" + OPERATOR, normalized_input=normalized,
        guard=lambda: domain.snapshot(normalized["date"]) if action != "range_clear" else None,
        mutate=lambda checked: domain.apply(action, normalized, checked))


def test_shift_window_drives_hours(calendar_env):
    conn = calendar_env[0]
    assert run(calendar_env, "upsert", {"date": DAY, "fields": WORK})["result"] == "committed"
    saved = stored(conn, DAY)
    assert saved["shift_start"] == "09:00" and saved["shift_end"] == "17:30"
    assert saved["shift_hours"] == 8.5 and saved["efficiency"] == 0.9
    assert saved["allow_normal"] == "yes" and saved["allow_urgent"] == "no" and saved["remark"] == "早班"


def test_note_only_patch_preserves_legacy_duration_then_rest_clears_it(calendar_env):
    conn = calendar_env[0]
    conn.execute("INSERT INTO OperatorCalendar(operator_id,date,shift_start,shift_hours,remark) VALUES (?,?,?,4,?)",
                 (OPERATOR, DAY, "09:00", "原备注"))
    conn.commit()
    proposed = service(calendar_env).proposed_row({"note": "只改备注"}, service(calendar_env).snapshot(DAY))
    assert proposed["shift_hours"] == 4
    run(calendar_env, "upsert", {"date": DAY, "fields": {"type": "work", "shiftStart": "09:00", "note": "只改备注"}})
    saved = stored(conn, DAY)
    assert saved["shift_hours"] == 4 and saved["shift_end"] == "13:00" and saved["remark"] == "只改备注"
    run(calendar_env, "upsert", {"date": DAY, "fields": {"type": "rest"}})
    assert stored(conn, DAY)["shift_hours"] == 0


def test_overnight_shift_is_supported(calendar_env):
    conn = calendar_env[0]
    run(calendar_env, "upsert", {"date": DAY, "fields": {**WORK, "shiftStart": "22:00", "shiftEnd": "06:00"}})
    saved = stored(conn, DAY)
    assert saved["shift_start"] == "22:00" and saved["shift_end"] == "06:00" and saved["shift_hours"] == 8.0


def test_rest_day_has_no_shift_and_no_priorities(calendar_env):
    conn = calendar_env[0]
    run(calendar_env, "upsert", {"date": DAY, "fields": {"type": "rest", "eff": 100,
                                                         "allowNormal": "no", "allowUrgent": "no"}})
    saved = stored(conn, DAY)
    assert saved["day_type"] == "holiday" and saved["shift_hours"] == 0
    assert saved["allow_normal"] == "no" and saved["allow_urgent"] == "no"


def test_repeated_save_of_the_same_values_is_unchanged(calendar_env):
    run(calendar_env, "upsert", {"date": DAY, "fields": WORK})
    assert run(calendar_env, "upsert", {"date": DAY, "fields": WORK})["result"] == "unchanged"


def test_single_day_delete_removes_only_that_day(calendar_env):
    conn = calendar_env[0]
    run(calendar_env, "upsert", {"date": DAY, "fields": WORK})
    run(calendar_env, "upsert", {"date": OTHER, "fields": WORK})
    assert run(calendar_env, "delete", {"date": DAY})["result"] == "committed"
    assert stored(conn, DAY) is None and stored(conn, OTHER) is not None
    # 夹具里 CO 在 2026-09-09 有一条个人日历，不该受影响。
    assert stored(conn, NIGHT) is not None


def test_range_clear_removes_every_configured_day_in_range(calendar_env):
    conn = calendar_env[0]
    for day in (DAY, OTHER):
        run(calendar_env, "upsert", {"date": day, "fields": WORK})
    preview = service(calendar_env).preview_range_clear({"start_date": "2026-10-01", "end_date": "2026-10-31"})
    assert preview["count"] == 2 and [day["date"] for day in preview["days"]] == [DAY, OTHER]
    outcome = run(calendar_env, "range_clear", {"start_date": "2026-10-01", "end_date": "2026-10-31"})
    assert outcome["result"] == "committed" and outcome["data"]["cleared_count"] == 2
    assert stored(conn, DAY) is None and stored(conn, OTHER) is None
    assert stored(conn, NIGHT) is not None


def test_range_clear_on_an_empty_range_is_unchanged(calendar_env):
    outcome = run(calendar_env, "range_clear", {"start_date": "2026-10-01", "end_date": "2026-10-31"})
    assert outcome["result"] == "unchanged" and outcome["data"]["cleared_count"] == 0


def test_range_clear_never_touches_the_global_calendar(calendar_env):
    conn = calendar_env[0]
    before = dict(conn.execute("SELECT * FROM WorkCalendar WHERE date=?", (NIGHT,)).fetchone())
    run(calendar_env, "range_clear", {"start_date": "2026-01-01", "end_date": "2026-12-31"})
    assert dict(conn.execute("SELECT * FROM WorkCalendar WHERE date=?", (NIGHT,)).fetchone()) == before


def test_range_clear_only_touches_this_operator(calendar_env):
    conn = calendar_env[0]
    conn.execute("INSERT INTO Operators (operator_id, name) VALUES ('CO2', 'other')")
    conn.commit()
    other = WorkbenchOperatorCalendarService(conn, "CO2", clock=calendar_env[2])
    normalized = other.normalize("upsert", {"date": DAY, "fields": WORK})
    WorkbenchCommandService(conn).execute(
        request_key="other-" + uuid4().hex, action="operator.calendar_upsert", context_ref="operator:CO2",
        normalized_input=normalized, guard=lambda: other.snapshot(DAY),
        mutate=lambda checked: other.apply("upsert", normalized, checked))
    run(calendar_env, "range_clear", {"start_date": "2026-01-01", "end_date": "2026-12-31"})
    assert stored(conn, DAY, "CO2") is not None


def test_stale_range_clear_points_to_the_existing_preview_button(calendar_env):
    """预检之后这段日期又被改过：不清除任何一天，提示要点的是页面上现有的「预检要清除的日期」按钮。"""
    conn, domain = calendar_env[0], service(calendar_env)
    run(calendar_env, "upsert", {"date": DAY, "fields": WORK})
    payload = domain.normalize("range_clear", {"start_date": "2026-10-01", "end_date": "2026-10-31"})
    checked = domain.preview_range_clear(payload)
    run(calendar_env, "upsert", {"date": OTHER, "fields": WORK})
    with pytest.raises(WorkbenchCommandRejected, match="请重新点「预检要清除的日期」"):
        WorkbenchCommandService(conn).execute(
            request_key="stale-range-" + uuid4().hex, action="operator.calendar_range_clear",
            context_ref="operator:" + OPERATOR, normalized_input=payload, guard=lambda: checked,
            mutate=lambda current: domain.apply("range_clear", payload, current))
    assert stored(conn, DAY) is not None and stored(conn, OTHER) is not None


def test_month_reports_only_configured_days(calendar_env):
    run(calendar_env, "upsert", {"date": DAY, "fields": WORK})
    month = service(calendar_env).month(2026, 10)
    configured = [day for day in month["days"] if day["explicit"]]
    assert [day["date"] for day in configured] == [DAY]
    assert month["stats"]["configured"] == 1 and month["stats"]["work_days"] == 1
    assert all(day["row"] is None for day in month["days"] if not day["explicit"])


def test_stale_snapshot_rejects_the_write(calendar_env):
    conn, domain = calendar_env[0], service(calendar_env)
    normalized = domain.normalize("upsert", {"date": DAY, "fields": WORK})
    stale = domain.snapshot(DAY)
    run(calendar_env, "upsert", {"date": DAY, "fields": {**WORK, "note": "别人先改了"}})
    with pytest.raises(WorkbenchCommandRejected):
        WorkbenchCommandService(conn).execute(
            request_key="stale-" + uuid4().hex, action="operator.calendar_upsert", context_ref="operator:" + OPERATOR,
            normalized_input=normalized, guard=lambda: stale,
            mutate=lambda checked: domain.apply("upsert", normalized, checked))
    assert stored(conn, DAY)["remark"] == "别人先改了"


@pytest.mark.parametrize("fields", (
    {"type": "work", "eff": 100},
    {"type": "work", "shiftStart": "9:00", "eff": 100},
    {"type": "work", "shiftStart": "09:00", "shiftEnd": "17:00:00", "eff": 100},
    {"type": "work", "shiftStart": "24:00", "eff": 100},
    {"type": "work", "shiftStart": "09:00", "eff": 0},
    {"type": "work", "shiftStart": "09:00", "eff": 300},
    {"type": "rest", "shiftStart": "09:00", "allowNormal": "yes"},
    {"shiftStart": "09:00", "eff": 100},
    {"type": "maybe", "shiftStart": "09:00"},
    {"type": "work", "shiftStart": "09:00", "hours": 8},
))
def test_invalid_field_shapes_are_rejected(calendar_env, fields):
    with pytest.raises(ValidationError):
        service(calendar_env).normalize("upsert", {"date": DAY, "fields": fields})


@pytest.mark.parametrize("payload", (
    {"start_date": "2026-10-31", "end_date": "2026-10-01"},
    {"start_date": "2026-01-01", "end_date": "2030-01-01"},
    {"start_date": "bad", "end_date": "2026-10-01"},
    {"start_date": "2026-10-01"},
))
def test_invalid_ranges_are_rejected(calendar_env, payload):
    with pytest.raises(ValidationError):
        service(calendar_env).normalize("range_clear", payload)


@pytest.mark.parametrize("action", (None, "", "confirm", "preview", "calendar_upsert"))
def test_unknown_actions_are_rejected(action):
    with pytest.raises(ValidationError):
        WorkbenchOperatorCalendarService.normalize(action, {})


def test_writes_require_an_outer_transaction(calendar_env):
    domain = service(calendar_env)
    with pytest.raises(RuntimeError):
        domain.apply("upsert", {"date": DAY, "fields": WORK}, None)
