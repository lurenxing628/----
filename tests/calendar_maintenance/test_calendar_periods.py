"""生产日历保留午休与跨午夜分段。"""

from datetime import date, datetime

import pytest

from core.services.capacity.plan_calendar_engine import SnapshotCalendarEngine
from core.services.capacity.plan_calendar_windows import available_intervals, policy_projection
from core.services.scheduler.calendar.service import CalendarService

DAY = "2026-10-05"
LUNCH = [{"start": "08:00", "end": "12:00", "day_offset": 0},
         {"start": "13:00", "end": "17:00", "day_offset": 0}]


def dt(clock, day=DAY):
    return datetime.fromisoformat(day + "T" + clock)


def _upsert_work_calendar(service: CalendarService, date_value: str, **kwargs):
    context = kwargs.pop("context", None) or service.normalization_context()
    model = service._admin._build_work_calendar(date_value=date_value, context=context, **kwargs)
    service._admin.repo.upsert_many([model])
    service.conn.commit()
    service._engine.clear_policy_cache()
    return model


def test_lunch_is_neither_processing_nor_capacity_and_native_slot_stops_at_noon(schema_conn):
    service = CalendarService(schema_conn)
    _upsert_work_calendar(service, DAY, periods=LUNCH, efficiency=.8)
    assert service.add_working_hours(dt("11:00"), 2) == dt("14:00")
    assert service.adjust_to_working_time(dt("12:15")) == dt("13:00")
    assert service.working_hours_between(dt("08:00"), dt("17:00")) == 8
    assert service.certified_slot_window(dt("11:00")) == (dt("08:00"), dt("12:00"))
    assert service.certified_slot_window(dt("12:30")) is None
    row = service._admin.repo.get(DAY)
    assert row is not None
    engine = SnapshotCalendarEngine({"global": [row.to_dict()], "personal": [], "profiles": [], "patterns": []})
    projected = policy_projection(engine, date.fromisoformat(DAY), date.fromisoformat(DAY), dt("00:00"), dt("23:59"))
    assert projected["available_hours"] == 8 and projected["effective_hours"] == 6.4
    assert len(projected["windows"]) == 2
    assert available_intervals(projected) == [(dt("08:00"), dt("12:00")), (dt("13:00"), dt("17:00"))]


def test_split_night_uses_explicit_next_day_without_filling_the_break(schema_conn):
    service = CalendarService(schema_conn)
    periods = [{"start": "22:00", "end": "01:00", "day_offset": 0},
               {"start": "02:00", "end": "06:00", "day_offset": 1}]
    _upsert_work_calendar(service, DAY, periods=periods)
    start, end = dt("23:00"), dt("04:00", "2026-10-06")
    assert service.add_working_hours(start, 4) == end
    assert service.working_hours_between(start, end) == 4
    assert service.adjust_to_working_time(dt("01:30", "2026-10-06")) == dt("02:00", "2026-10-06")


def test_calendar_range_builds_once_per_day_and_only_reads_new_receipt_refs(schema_conn, monkeypatch):
    from core.infrastructure.transaction import TransactionManager
    from core.models.calendar import WorkCalendar
    from core.services.workbench.resource.calendars import WorkbenchCalendarService

    _upsert_work_calendar(
        CalendarService(schema_conn),
        "2026-10-12",
        periods=[{"start": "08:00", "end": "16:00", "day_offset": 0}],
    )
    domain = WorkbenchCalendarService(schema_conn)
    built, persisted, ref_reads = [], [], []
    build = domain._calendar._admin._build_work_calendar
    save = domain._calendar._admin.repo.upsert_many
    refs = domain._query.created_refs

    def counted_build(*args, **kwargs):
        model = build(*args, **kwargs)
        built.append(model)
        return model

    def save_models(models):
        models = list(models)
        assert all(isinstance(model, WorkCalendar) for model in models)
        persisted.extend(models)
        return save(models)

    def read_refs(kind, keys):
        keys = list(keys)
        ref_reads.append((kind, keys))
        return refs(kind, keys)

    def no_snapshot(*args):
        raise AssertionError("Prepared batch writes must not re-read day snapshots")

    monkeypatch.setattr(domain._calendar._admin, "_build_work_calendar", counted_build)
    monkeypatch.setattr(domain._calendar._admin.repo, "upsert_many", save_models)
    monkeypatch.setattr(domain._query, "created_refs", read_refs)
    monkeypatch.setattr(domain, "snapshot", no_snapshot)
    request = {"start_date": "2026-10-12", "end_date": "2026-10-14", "scope": "all",
               "operation": "upsert", "fields": {"note": "一起调整"}}
    preview = domain.preview(request)
    assert len(built) == 3
    with TransactionManager(schema_conn).transaction(begin_immediate=True):
        outcome = domain.confirm({"preview_ref": preview.preview_ref}, preview)
    assert len(built) == 6 and all(left is right for left, right in zip(persisted, built[3:]))
    assert ref_reads == [("calendar", ["2026-10-13", "2026-10-14"])]
    assert outcome.result == "committed" and all(item["calendar_ref"] for item in outcome.data["dates"])
    preview = domain.preview({**request, "fields": {"note": "再次调整"}})
    with TransactionManager(schema_conn).transaction(begin_immediate=True):
        domain.confirm({"preview_ref": preview.preview_ref}, preview)
    assert len(ref_reads) == 1


def test_calendar_range_preserves_lock_time_facts_ttl_and_minute_conflicts(schema_conn):
    from datetime import timedelta

    import pytest

    from core.errors import ValidationError
    from core.infrastructure.transaction import TransactionManager
    from core.models.calendar_periods import decode_periods
    from core.models.workbench_command import WorkbenchCommandRejected
    from core.services.workbench.resource.calendars import WorkbenchCalendarService

    now = [datetime(2026, 10, 12, 9)]
    domain = WorkbenchCalendarService(schema_conn, clock=lambda: now[0])
    eight_hours = [{"start": "08:00", "end": "16:00", "day_offset": 0}]
    request = {"start_date": DAY, "end_date": DAY, "fields": {"periods": eight_hours}, "scope": "all", "operation": "upsert"}
    preview = domain.preview(request)
    _upsert_work_calendar(
        CalendarService(schema_conn),
        DAY,
        periods=[{"start": "08:00", "end": "15:00", "day_offset": 0}],
    )
    with TransactionManager(schema_conn).transaction(begin_immediate=True):
        with pytest.raises(WorkbenchCommandRejected, match="范围里的日历已经变了"):
            domain.confirm({"preview_ref": preview.preview_ref}, preview)
    preview = domain.preview({**request, "fields": {"note": "核对"}})
    now[0] += timedelta(minutes=15)
    with TransactionManager(schema_conn).transaction(begin_immediate=True):
        with pytest.raises(WorkbenchCommandRejected, match="已过期"):
            domain.confirm({"preview_ref": preview.preview_ref}, preview)
    for fields in (
        {"periods": None},
        {"periods": [{"start": "08:00", "end": "12:00", "day_offset": 0},
                     {"start": "11:00", "end": "15:00", "day_offset": 0}]},
        {"periods": [{"start": "08:00", "end": "08:00", "day_offset": 0},
                     {"start": "09:00", "end": "10:00", "day_offset": 1}]},
    ):
        with pytest.raises(ValidationError) as error:
            domain.preview({**request, "fields": fields})
        assert error.value.field == "fields.periods"
    saved_day = CalendarService(schema_conn)._admin.repo.get(DAY)
    assert saved_day is not None and decode_periods(saved_day.periods_json) == [{"start": "08:00", "end": "15:00", "day_offset": 0}]


def test_zero_and_full_day_hours_keep_their_windows_through_confirmation(schema_conn):
    from core.infrastructure.transaction import TransactionManager
    from core.models.calendar_periods import decode_periods, period_hours
    from core.services.workbench.resource.calendars import WorkbenchCalendarService

    domain = WorkbenchCalendarService(schema_conn)
    for hours, periods in ((24, [{"start": "08:00", "end": "08:00", "day_offset": 0}]), (0, [])):
        preview = domain.preview({"start_date": DAY, "end_date": DAY, "scope": "all",
                                  "operation": "upsert", "fields": {"periods": periods}})
        assert preview.days[0]["after"]["effective"]["hours"] == hours
        with TransactionManager(schema_conn).transaction(begin_immediate=True):
            result = domain.confirm({"preview_ref": preview.preview_ref}, preview)
        assert result.result == "committed"
        service = CalendarService(schema_conn)
        row = service._admin.repo.get(DAY)
        assert row is not None
        assert period_hours(decode_periods(row.periods_json)) == hours
        policy = service._engine._policy_for_date(DAY)
        assert policy.hours == hours and bool(policy.work_windows()) == bool(hours)


@pytest.mark.parametrize("personal", [False, True], ids=["global", "personal"])
def test_explicit_periods_replace_stored_periods_and_omitted_periods_keep_them(schema_conn, personal):
    from core.errors import ValidationError
    from core.infrastructure.transaction import TransactionManager
    from core.models.calendar_period_columns import parse_period_columns
    from core.models.calendar_periods import decode_periods, period_hours
    from core.services.workbench.resource.calendar_reading import CalendarProjection
    from core.services.workbench.resource.calendars import WorkbenchCalendarService
    from core.services.workbench.resource.operator_calendars import WorkbenchOperatorCalendarService

    initial_periods = '[{"start":"08:00","end":"09:15","day_offset":0}]'
    if personal:
        schema_conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
        schema_conn.execute(
            "INSERT INTO OperatorCalendar(operator_id,date,day_type,efficiency,allow_normal,allow_urgent,periods_json) "
            "VALUES ('O1',?,'workday',1,'yes','yes',?)",
            (DAY, initial_periods),
        )
        schema_conn.commit()
        op_domain = WorkbenchOperatorCalendarService(schema_conn, "O1")
        before = op_domain.day_state(DAY, op_domain.range_states(DAY, DAY))
        proposed = op_domain.proposed_row(
            {"periods": LUNCH},
            before,
            context=op_domain._calendar.normalization_context(),
            projection=CalendarProjection({}, engine=op_domain._calendar._engine),
        )
        assert period_hours(decode_periods(proposed.periods_json)) == 8
        with TransactionManager(schema_conn).transaction(begin_immediate=True):
            normalized = op_domain.normalize("upsert", {"date": DAY, "fields": {"type": "work", "periods": LUNCH}})
            result = op_domain._apply_checked("upsert", normalized, op_domain.day_state(DAY, op_domain.range_states(DAY, DAY)))
    else:
        schema_conn.execute(
            "INSERT INTO WorkCalendar(date,day_type,efficiency,allow_normal,allow_urgent,periods_json) "
            "VALUES (?,'workday',1,'yes','yes',?)",
            (DAY, initial_periods),
        )
        schema_conn.commit()
        cal_domain = WorkbenchCalendarService(schema_conn)
        preview = cal_domain.preview({"start_date": DAY, "end_date": DAY, "scope": "all",
                                      "operation": "upsert", "fields": {"periods": LUNCH}})
        assert preview.days[0]["after"]["effective"]["hours"] == 8
        with TransactionManager(schema_conn).transaction(begin_immediate=True):
            result = cal_domain.confirm({"preview_ref": preview.preview_ref}, preview)
    assert result.result == "committed"
    service = CalendarService(schema_conn)
    row = service._admin.operator_calendar_repo.get("O1", DAY) if personal else service._admin.repo.get(DAY)
    assert row is not None
    assert decode_periods(row.periods_json) == LUNCH
    assert service._engine._policy_for_date(DAY, "O1" if personal else None).hours == 8

    if personal:
        op_domain = WorkbenchOperatorCalendarService(schema_conn, "O1")
        with pytest.raises(ValidationError) as exc_info:
            op_domain.normalize("upsert", {"date": DAY, "fields": {"type": "work", "periods": None}})
        assert exc_info.value.field == "fields.periods"
        with TransactionManager(schema_conn).transaction(begin_immediate=True):
            normalized = op_domain.normalize("upsert", {"date": DAY, "fields": {"type": "work", "note": "仅改备注"}})
            note_only = op_domain._apply_checked(
                "upsert", normalized, op_domain.day_state(DAY, op_domain.range_states(DAY, DAY))
            )
    else:
        cal_domain = WorkbenchCalendarService(schema_conn)
        with pytest.raises(ValidationError) as exc_info:
            cal_domain.preview({"start_date": DAY, "end_date": DAY, "scope": "all",
                                "operation": "upsert", "fields": {"periods": None}})
        assert exc_info.value.field == "fields.periods"
        preview = cal_domain.preview({"start_date": DAY, "end_date": DAY, "scope": "all",
                                      "operation": "upsert", "fields": {"note": "仅改备注"}})
        with TransactionManager(schema_conn).transaction(begin_immediate=True):
            note_only = cal_domain.confirm({"preview_ref": preview.preview_ref}, preview)
    assert note_only.result == "committed"
    service = CalendarService(schema_conn)
    updated = service._admin.operator_calendar_repo.get("O1", DAY) if personal else service._admin.repo.get(DAY)
    assert updated is not None and updated.remark == "仅改备注"
    assert decode_periods(updated.periods_json) == LUNCH

    with pytest.raises(ValidationError):
        parse_period_columns({"period_count": "²"})


REST_TO_WORK = DAY + " 原来是假期或休息日，改成工作日时请填写工作时段。"


def _holiday_row(conn, personal):
    table_columns = "date,day_type,efficiency,allow_normal,allow_urgent,periods_json"
    if personal:
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
        conn.execute(f"INSERT INTO OperatorCalendar(operator_id,{table_columns}) VALUES ('O1',?,'holiday',1,'no','no','[]')", (DAY,))
    else:
        conn.execute(f"INSERT INTO WorkCalendar({table_columns}) VALUES (?,'holiday',1,'no','no','[]')", (DAY,))
    conn.commit()


def _apply_upsert(domain, conn, fields, personal):
    from core.infrastructure.transaction import TransactionManager

    with TransactionManager(conn).transaction(begin_immediate=True):
        normalized = domain.normalize("upsert", {"date": DAY, "fields": fields})
        before = domain.day_state(DAY, domain.range_states(DAY, DAY)) if personal else domain.snapshot(DAY)
        return domain._apply_checked("upsert", normalized, before)


@pytest.mark.parametrize("personal", [False, True], ids=["global", "personal"])
def test_holiday_switched_to_work_without_periods_is_rejected(schema_conn, personal):
    from core.errors import ValidationError
    from core.models.calendar_periods import encode_periods
    from core.services.workbench.resource.calendars import WorkbenchCalendarService
    from core.services.workbench.resource.operator_calendars import WorkbenchOperatorCalendarService

    _holiday_row(schema_conn, personal)
    domain = WorkbenchOperatorCalendarService(schema_conn, "O1") if personal else WorkbenchCalendarService(schema_conn)
    stored = (lambda: CalendarService(schema_conn)._admin.operator_calendar_repo.get("O1", DAY)) if personal else (
        lambda: CalendarService(schema_conn)._admin.repo.get(DAY))

    with pytest.raises(ValidationError) as rejected:
        _apply_upsert(domain, schema_conn, {"type": "work"}, personal)
    assert rejected.value.field == "fields.periods" and rejected.value.message == REST_TO_WORK
    assert stored().day_type == "holiday"

    # 显式空数组是明确的零工时工作日，不算没填。
    assert _apply_upsert(domain, schema_conn, {"type": "work", "periods": []}, personal).result == "committed"
    zero = stored()
    assert zero.day_type == "workday" and zero.periods_json == "[]"

    # 已是工作日的行省略时段表示不改。
    assert _apply_upsert(domain, schema_conn, {"type": "work", "note": "只改备注"}, personal).result == "committed"
    assert stored().periods_json == "[]" and stored().remark == "只改备注"

    # 给了时段就按所填保存。
    assert _apply_upsert(domain, schema_conn, {"type": "work", "periods": LUNCH}, personal).result == "committed"
    assert stored().periods_json == encode_periods(LUNCH)


@pytest.mark.parametrize("entry", ["global_day", "global_range", "personal_day"])
def test_form_keeps_non_form_field_of_domain_error_unprefixed(schema_conn, entry):
    # 跨出 9999-12-31 的班次报的是 date，不是表单里的字段：表单入口不给它造 fields.date 这条路径。
    from core.errors import ValidationError
    from core.infrastructure.transaction import TransactionManager
    from core.services.workbench.resource.calendars import WorkbenchCalendarService
    from core.services.workbench.resource.operator_calendars import WorkbenchOperatorCalendarService

    last, overnight = "9999-12-31", [{"start": "22:00", "end": "06:00", "day_offset": 0}]
    fields = {"type": "work", "periods": overnight}
    if entry == "personal_day":
        schema_conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
        schema_conn.commit()
    domain = WorkbenchOperatorCalendarService(schema_conn, "O1") if entry == "personal_day" else WorkbenchCalendarService(schema_conn)
    with pytest.raises(ValidationError) as rejected:
        if entry == "global_range":
            domain.preview({"start_date": last, "end_date": last, "scope": "all", "operation": "upsert", "fields": fields})
        else:
            with TransactionManager(schema_conn).transaction(begin_immediate=True):
                normalized = domain.normalize("upsert", {"date": last, "fields": fields})
                before = (domain.day_state(last, domain.range_states(last, last)) if entry == "personal_day"
                          else domain.snapshot(last))
                domain._apply_checked("upsert", normalized, before)
    assert rejected.value.field == "date" and "9999-12-31" in rejected.value.message


def test_global_range_rejects_holiday_turned_work_but_fresh_dates_take_defaults(schema_conn):
    from core.errors import ValidationError
    from core.infrastructure.transaction import TransactionManager
    from core.models.calendar_periods import encode_periods, period_hours
    from core.services.workbench.resource.calendars import WorkbenchCalendarService

    _holiday_row(schema_conn, False)
    domain = WorkbenchCalendarService(schema_conn)
    work_only = {"scope": "all", "operation": "upsert", "fields": {"type": "work"}}
    with pytest.raises(ValidationError) as rejected:
        domain.preview({**work_only, "start_date": DAY, "end_date": "2026-10-06"})
    assert rejected.value.field == "fields.periods" and rejected.value.message == REST_TO_WORK

    # 从未存过的日期只改类型：取当前默认时段。
    preview = domain.preview({**work_only, "start_date": "2026-10-06", "end_date": "2026-10-06"})
    default_periods = domain._calendar._engine.default_periods()
    assert preview.days[0]["after"]["row"]["periods_json"] == encode_periods(default_periods)
    assert preview.days[0]["after"]["effective"]["hours"] == period_hours(default_periods)
    with TransactionManager(schema_conn).transaction(begin_immediate=True):
        assert domain.confirm({"preview_ref": preview.preview_ref}, preview).result == "committed"

    # 范围里显式给空数组：假期也可明确改成零工时工作日。
    explicit = domain.preview({"scope": "all", "operation": "upsert", "start_date": DAY, "end_date": DAY,
                               "fields": {"type": "work", "periods": []}})
    assert explicit.days[0]["after"]["row"]["day_type"] == "workday"
    assert explicit.days[0]["after"]["row"]["periods_json"] == "[]" and explicit.days[0]["after"]["effective"]["hours"] == 0.0


def test_zero_period_day_window_is_midnight_whatever_path_wrote_it(schema_conn):
    from core.services.workbench.resource.calendar_reading import CalendarProjection, effective_calendar_day

    service = CalendarService(schema_conn)
    context = service.normalization_context()
    for day, day_type in ((DAY, "workday"), ("2026-10-06", "holiday")):
        _upsert_work_calendar(service, day, day_type=day_type, periods=[], efficiency=1, context=context)
        expected = day + "T00:00:00"
        policy = service._engine._policy_for_date(day)
        assert policy.work_windows() == () and policy.work_window() == (dt("00:00:00", day), dt("00:00:00", day))
        effective = effective_calendar_day(day, service._admin.repo.get(day),
                                           projection=CalendarProjection({}, engine=service._engine))
        assert (effective["window_start"], effective["window_end"], effective["windows"]) == (expected, expected, [])


def test_snapshot_engine_reports_bad_stored_efficiency_in_plain_words():
    from core.errors import ValidationError

    row = {"date": DAY, "day_type": "workday", "efficiency": None, "allow_normal": "yes", "allow_urgent": "yes",
           "remark": None, "periods_json": "[]"}
    facts = {"profiles": [], "patterns": [], "global": [row], "personal": [{**row, "operator_id": "O1"}]}
    with pytest.raises(ValidationError, match="工作日历里 " + DAY + " 的效率读不出来或不大于 0") as public:
        SnapshotCalendarEngine(facts)._policy_for_date(DAY)
    assert public.value.field == "efficiency"
    with pytest.raises(ValidationError, match="个人日历里 " + DAY + " 的效率"):
        SnapshotCalendarEngine(facts)._policy_for_date(DAY, "O1")


def test_projection_family_shares_period_memo_and_isolates_child_date_overrides(monkeypatch):
    from core.models.calendar_periods import encode_periods
    from core.services.scheduler.calendar import engine as engine_module
    from core.services.scheduler.calendar.engine import CalendarEngine
    from core.services.workbench.resource.calendar_reading import (
        CalendarProjection,
        effective_calendar_day,
        month_stats,
    )

    decoded_calls = []
    real_decode = engine_module.decode_periods

    def counted_decode(raw: str):
        decoded_calls.append(raw)
        return real_decode(raw)

    monkeypatch.setattr(engine_module, "decode_periods", counted_decode)

    lunch_json = encode_periods(LUNCH)
    late_periods = [{"start": "10:00", "end": "18:00", "day_offset": 0}]
    late_json = encode_periods(late_periods)
    night_tail_periods = [{"start": "20:00", "end": "02:00", "day_offset": 0}]
    night_tail_json = encode_periods(night_tail_periods)

    base_rows = {
        DAY: {
            "date": DAY,
            "day_type": "workday",
            "periods_json": lunch_json,
            "efficiency": 1.0,
            "allow_normal": "yes",
            "allow_urgent": "yes",
            "remark": None,
        },
        "2026-10-31": {
            "date": "2026-10-31",
            "day_type": "workday",
            "periods_json": night_tail_json,
            "efficiency": 1.0,
            "allow_normal": "yes",
            "allow_urgent": "yes",
            "remark": None,
        },
        "2026-11-01": {
            "date": "2026-11-01",
            "day_type": "workday",
            "periods_json": "broken-periods-json",
            "efficiency": 1.0,
            "allow_normal": "yes",
            "allow_urgent": "yes",
            "remark": None,
        },
    }
    parent = CalendarProjection(base_rows, engine=CalendarEngine(None))
    assert decoded_calls == []

    parent_day = effective_calendar_day(DAY, base_rows[DAY], projection=parent)
    assert parent_day["efficiency"] == 1.0 and parent_day["allowNormal"] == "yes" and parent_day["day_type"] == "workday"
    assert decoded_calls == [lunch_json]

    oct_days = [
        {"date": DAY, "explicit": True, "is_weekend": False, "effective": parent_day},
        {
            "date": "2026-10-31",
            "explicit": True,
            "is_weekend": True,
            "effective": effective_calendar_day("2026-10-31", base_rows["2026-10-31"], projection=parent),
        },
    ]
    assert month_stats(oct_days, parent)["effective_hours"] is None

    # 子投影首次解析 late_json 后，同投影族后续子投影与父投影均复用该解析产物。
    first_child_row = {
        **base_rows[DAY],
        "efficiency": 0.5,
        "allow_normal": "no",
        "periods_json": late_json,
    }
    child_eff = effective_calendar_day(DAY, first_child_row, projection=parent)
    assert child_eff["efficiency"] == 0.5 and child_eff["allowNormal"] == "no" and child_eff["effective_hours"] == 4.0

    second_child_row = {**first_child_row, "date": "2026-10-06"}
    second_eff = effective_calendar_day("2026-10-06", second_child_row, projection=parent)
    assert second_eff["hours"] == 8.0 and decoded_calls.count(late_json) == 1
    assert decoded_calls.count(lunch_json) == 1

    holiday_child_row = {
        **base_rows[DAY],
        "day_type": "holiday",
        "allow_normal": "no",
        "allow_urgent": "no",
        "periods_json": "[]",
    }
    holiday_eff = effective_calendar_day(DAY, holiday_child_row, projection=parent)
    assert holiday_eff["day_type"] == "holiday" and holiday_eff["is_rest"] is True and holiday_eff["hours"] == 0.0

    # 子投影修改同一天的效率、许可、类型及修复次月 1 日，绝不污染父投影的当日策略和未知容量 None。
    repaired_nov_child = parent.with_rows({**base_rows, "2026-11-01": {**base_rows["2026-11-01"], "periods_json": late_json}})
    assert month_stats(oct_days, repaired_nov_child)["effective_hours"] == 14.0
    assert decoded_calls.count(late_json) == 1

    parent_again = effective_calendar_day(DAY, base_rows[DAY], projection=parent)
    assert parent_again == parent_day
    assert month_stats(oct_days, parent)["effective_hours"] is None
