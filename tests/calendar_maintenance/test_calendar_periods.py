"""生产日历保留午休与跨午夜分段。"""

from datetime import date, datetime

import pytest

from core.services.capacity.plan_calendar_engine import SnapshotCalendarEngine
from core.services.capacity.plan_calendar_windows import policy_projection
from core.services.scheduler.calendar.service import CalendarService

DAY = "2026-10-05"
LUNCH = [{"start": "08:00", "end": "12:00", "day_offset": 0},
         {"start": "13:00", "end": "17:00", "day_offset": 0}]


def dt(clock, day=DAY):
    return datetime.fromisoformat(day + "T" + clock)


def test_lunch_is_neither_processing_nor_capacity_and_native_slot_stops_at_noon(schema_conn):
    service = CalendarService(schema_conn)
    service.upsert(DAY, periods=LUNCH, efficiency=.8)
    assert service.add_working_hours(dt("11:00"), 2) == dt("14:00")
    assert service.adjust_to_working_time(dt("12:15")) == dt("13:00")
    assert service.working_hours_between(dt("08:00"), dt("17:00")) == 8
    assert service.certified_slot_window(dt("11:00")) == (dt("08:00"), dt("12:00"))
    assert service.certified_slot_window(dt("12:30")) is None
    engine = SnapshotCalendarEngine({"global": [service.get(DAY).to_dict()], "personal": [], "profiles": [], "patterns": []})
    projected = policy_projection(engine, date.fromisoformat(DAY), date.fromisoformat(DAY), dt("00:00"), dt("23:59"))
    assert projected["available_hours"] == 8 and projected["effective_hours"] == 6.4
    assert len(projected["windows"]) == 2


def test_split_night_uses_explicit_next_day_without_filling_the_break(schema_conn):
    service = CalendarService(schema_conn)
    periods = [{"start": "22:00", "end": "01:00", "day_offset": 0},
               {"start": "02:00", "end": "06:00", "day_offset": 1}]
    service.upsert(DAY, periods=periods)
    start, end = dt("23:00"), dt("04:00", "2026-10-06")
    assert service.add_working_hours(start, 4) == end
    assert service.working_hours_between(start, end) == 4
    assert service.adjust_to_working_time(dt("01:30", "2026-10-06")) == dt("02:00", "2026-10-06")


def test_calendar_range_builds_once_per_day_and_only_reads_new_receipt_refs(schema_conn, monkeypatch):
    from core.infrastructure.transaction import TransactionManager
    from core.models.calendar import WorkCalendar
    from core.services.workbench.resource.calendars import WorkbenchCalendarService

    CalendarService(schema_conn).upsert("2026-10-12", shift_hours=8)
    domain = WorkbenchCalendarService(schema_conn)
    built, persisted, ref_reads = [], [], []
    build = domain._calendar._admin._build_work_calendar
    save = domain._calendar._admin.repo.upsert_many
    refs = domain._query.created_refs

    def counted_build(**kwargs):
        model = build(**kwargs)
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

    from core.infrastructure.transaction import TransactionManager
    from core.models.workbench_command import WorkbenchCommandRejected
    from core.services.workbench.resource.calendars import WorkbenchCalendarService

    now = [datetime(2026, 10, 12, 9)]
    domain = WorkbenchCalendarService(schema_conn, clock=lambda: now[0])
    request = {"start_date": DAY, "end_date": DAY, "fields": {"hours": 8}, "scope": "all", "operation": "upsert"}
    preview = domain.preview(request)
    CalendarService(schema_conn).upsert(DAY, shift_hours=7)
    with TransactionManager(schema_conn).transaction(begin_immediate=True):
        with pytest.raises(WorkbenchCommandRejected, match="范围里的日历已经变了"):
            domain.confirm({"preview_ref": preview.preview_ref}, preview)
    preview = domain.preview({**request, "fields": {"note": "核对"}})
    now[0] += timedelta(minutes=15)
    with TransactionManager(schema_conn).transaction(begin_immediate=True):
        with pytest.raises(WorkbenchCommandRejected, match="已过期"):
            domain.confirm({"preview_ref": preview.preview_ref}, preview)
    for fields in ({"hours": 1.234}, {"hours": 1e-10}, {"hours": 1e-10, "periods": []},
                   {"hours": 6, "shiftEnd": "17:00"}, {"hours": 6, "periods": LUNCH}):
        with pytest.raises(WorkbenchCommandRejected) as error:
            domain.preview({**request, "fields": fields})
        assert error.value.code == "constraint_conflict"
    assert CalendarService(schema_conn).get(DAY).shift_hours == 7


def test_zero_and_full_day_hours_keep_their_windows_through_confirmation(schema_conn):
    from core.infrastructure.transaction import TransactionManager
    from core.services.workbench.resource.calendars import WorkbenchCalendarService

    domain = WorkbenchCalendarService(schema_conn)
    for hours in (24, 0):
        preview = domain.preview({"start_date": DAY, "end_date": DAY, "scope": "all",
                                  "operation": "upsert", "fields": {"hours": hours}})
        assert preview.days[0]["after"]["effective"]["hours"] == hours
        with TransactionManager(schema_conn).transaction(begin_immediate=True):
            result = domain.confirm({"preview_ref": preview.preview_ref}, preview)
        assert result.result == "committed"
        service = CalendarService(schema_conn)
        row = service.get(DAY)
        assert row.shift_hours == hours and row.shift_end == (row.shift_start if hours else None)
        assert service._engine._policy_for_date(DAY).shift_hours == hours


@pytest.mark.parametrize("personal", [False, True], ids=["global", "personal"])
def test_explicit_periods_replace_legacy_nonminute_hours(schema_conn, personal):
    from core.infrastructure.transaction import TransactionManager
    from core.services.workbench.resource.calendars import WorkbenchCalendarService
    from core.services.workbench.resource.operator_calendars import WorkbenchOperatorCalendarService

    if personal:
        schema_conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
        schema_conn.execute("INSERT INTO OperatorCalendar(operator_id,date,shift_start,shift_hours) VALUES ('O1',?,'08:00',1.234)", (DAY,))
        schema_conn.commit()
        domain = WorkbenchOperatorCalendarService(schema_conn, "O1")
        before = domain.snapshot(DAY)
        assert domain.proposed_row({"periods": LUNCH}, before).shift_hours == 8
        with TransactionManager(schema_conn).transaction(begin_immediate=True):
            normalized = domain.normalize("upsert", {"date": DAY, "fields": {"type": "work", "periods": LUNCH}})
            result = domain._apply_checked("upsert", normalized, domain.snapshot(DAY))
    else:
        schema_conn.execute("INSERT INTO WorkCalendar(date,shift_start,shift_hours) VALUES (?,'08:00',1.234)", (DAY,))
        schema_conn.commit()
        domain = WorkbenchCalendarService(schema_conn)
        preview = domain.preview({"start_date": DAY, "end_date": DAY, "scope": "all",
                                  "operation": "upsert", "fields": {"periods": LUNCH}})
        assert preview.days[0]["after"]["row"]["shift_hours"] == 8
        with TransactionManager(schema_conn).transaction(begin_immediate=True):
            result = domain.confirm({"preview_ref": preview.preview_ref}, preview)
    assert result.result == "committed"
    service = CalendarService(schema_conn)
    row = service.get_operator_calendar("O1", DAY) if personal else service.get(DAY)
    assert row.shift_hours == 8 and (row.shift_start, row.shift_end) == ("08:00", "17:00")
    assert service._engine._policy_for_date(DAY, "O1" if personal else None).shift_hours == 8
