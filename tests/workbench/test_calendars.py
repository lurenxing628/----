"""Private global calendar integration contracts, independent of the future HTTP/UI."""

import json
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest

from core.errors import ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_calendar import CALENDAR_PREVIEW_TTL_SECONDS, MAX_CALENDAR_RANGE_DAYS
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain, canonical_json
from core.services.scheduler.calendar.engine import MAX_CALENDAR_DAYS
from core.services.scheduler.calendar.service import CalendarService
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.calendars import WorkbenchCalendarService
from data.repositories.workbench_calendar_query_repo import WorkbenchCalendarQueryRepository
from tests.workbench.calendar_support import (
    KEY,
    NIGHT,
    WORK,
    annual_database,
    assert_complete_calendar_write,
    assert_other_business_unchanged,
    calendar_database,
    expected_range_dates,
    measure_calendar_call,
    range_input,
    row_for,
    run_confirm,
    run_day,
    seed_d06_resources,
    stored_state,
)
from tests.workbench.identity_metadata_support import business_snapshot, connect_temp, copy_to_temp


@pytest.mark.parametrize("action", (None, [], {}, True, "", "UPDATE", "operator_calendar"))
def test_unknown_action_is_rejected_without_db(action):
    with pytest.raises(ValidationError):
        WorkbenchCalendarService.normalize(action, {})


@pytest.mark.parametrize("payload", (None, [], (), "", True, {1: "bad"}, {"date": NIGHT, "shift_start": "08:00"},
                                     {"date": NIGHT, "write_token": "never persist"}))
def test_strict_object_and_field_whitelist(payload):
    with pytest.raises(ValidationError):
        WorkbenchCalendarService.normalize("upsert", payload)


@pytest.mark.parametrize("day", (None, True, "2023-02-29", "2024-02-30", "2024-13-01", "2026-0-1",
                                 "2026/01/01", "2026-01-01T00:00:00", " 2026-01-01", "0000-01-01"))
def test_only_real_iso_dates_are_accepted(day):
    with pytest.raises(ValidationError):
        WorkbenchCalendarService.normalize("delete", {"date": day})


@pytest.mark.parametrize("field,value", [("eff", value) for value in
                         (0, -1, True, None, "100", float("nan"), float("inf"), 201, 10 ** 400)] +
                         [("hours", value) for value in (-1, 25, True, "8", None, float("nan"))] +
                         [("allowNormal", True), ("allowUrgent", "YES"), ("type", "holiday"), ("note", 0),
                          ("shift_end", "06:30"), ("revision", 2)])
def test_invalid_fields_never_become_defaults(field, value):
    with pytest.raises(ValidationError):
        WorkbenchCalendarService.normalize("upsert", {"date": NIGHT, "fields": {field: value}})


def test_normalization_is_pure_idempotent_and_preserves_omission():
    raw = {"date": NIGHT, "fields": {"eff": 87.5, "note": "  text  ", "allowNormal": "no"}}
    before = deepcopy(raw)
    result = WorkbenchCalendarService.normalize("upsert", raw)
    assert result == {"date": NIGHT, "fields": {"eff": 87.5, "note": "text", "allowNormal": "no"}}
    assert WorkbenchCalendarService.normalize("upsert", result) == result and raw == before
    assert WorkbenchCalendarService.normalize("upsert", {"date": NIGHT}) == {"date": NIGHT, "fields": {}}
    rest = WorkbenchCalendarService.normalize("upsert", {"date": NIGHT, "fields": {"type": "rest"}})
    assert rest["fields"] == {"type": "rest", "hours": 0.0, "allowNormal": "no", "allowUrgent": "no"}
    with pytest.raises(ValidationError):
        WorkbenchCalendarService.normalize("upsert", {"date": NIGHT, "fields": {"type": "rest", "eff": 0}})


@pytest.mark.parametrize("year,month,count", ((2023, 2, 28), (2024, 2, 29), (2026, 12, 31), (2027, 1, 31)))
def test_month_has_all_real_dates_and_readonly_domain_defaults(calendar_env, year, month, count):
    conn, adapter, _ = calendar_env
    before, changes = stored_state(conn), conn.total_changes
    result = adapter.month(year, month)
    assert [day["date"] for day in result["days"]] == [f"{year:04d}-{month:02d}-{day:02d}" for day in range(1, count + 1)]
    assert [day for day in result["cells"] if day] == result["days"] and len(result["cells"]) % 7 == 0
    for day in result["days"]:
        assert not day["explicit"] and day["row"] is None and day["calendar_ref"] is None and day["revision"] is None
        assert day["effective"]["hours"] == pytest.approx(0 if day["is_weekend"] else 22 / 3)
        assert day["effective"]["eff"] == 100
    assert result["stats"]["configured"] == 0
    assert result["as_of"] == "2024-02-29T12:34:56"
    if (year, month) == (2024, 2):
        assert [day["date"] for day in result["days"] if day["is_today"]] == ["2024-02-29"]
    assert stored_state(conn) == before and conn.total_changes == changes and not conn.in_transaction


def test_month_navigation_crosses_year_boundary(calendar_env):
    adapter = calendar_env[1]
    assert adapter.month(2026, 12)["next_month"] == {"year": 2027, "month": 1}
    assert adapter.month(2027, 1)["previous_month"] == {"year": 2026, "month": 12}


@pytest.mark.parametrize("year,month", ((True, 1), (2024, 0), (2024, 13), (0, 1), (10000, 1), (2024, "2")))
def test_month_rejects_invalid_bounds(calendar_env, year, month):
    with pytest.raises(ValidationError):
        calendar_env[1].month(year, month)


def test_holidays_overtime_actual_policies_and_date_key_not_midnight(calendar_env):
    conn, adapter, _ = calendar_env
    domain = CalendarService(conn)
    domain.upsert("2024-02-10", shift_hours=4, efficiency=0.5, allow_normal="no", allow_urgent="yes")
    domain.upsert("2024-02-12", day_type="holiday", shift_hours=0, efficiency=0.75,
                  allow_normal="no", allow_urgent="no", remark="holiday")
    month = adapter.month(2024, 2)
    days = {item["date"]: item for item in month["days"]}
    assert days["2024-02-10"]["effective"]["effective_hours"] == 2
    assert days["2024-02-12"]["effective"]["is_rest"]
    assert month["stats"] == {"configured": 2, "configured_work_days": 1, "work_days": 21,
                              "rest_days": 8, "overrides": 2, "weekend_rest": 7, "effective_hours": pytest.approx(446 / 3)}
    # A weekday named a national holiday is not magically a holiday without configuration.
    assert adapter.snapshot("2026-01-01")["effective"]["hours"] == pytest.approx(22 / 3)
    night, next_day = adapter.snapshot(NIGHT), adapter.snapshot("2026-09-10")
    assert night["effective"]["window_end"] == "2026-09-10T06:30:00"
    assert next_day["effective"]["window_start"] == "2026-09-10T08:30:00"
    assert night["row"] == row_for(conn) and night["revision"] == 1 and len(night["calendar_ref"]) == 48
    assert night["effective"]["efficiency"] == 0.875  # Not the personal exception's 0.625.


@pytest.mark.parametrize("normal,urgent", (("yes", "yes"), ("yes", "no"), ("no", "yes"), ("no", "no")))
def test_priority_switches_are_independent_and_percent_maps_once(calendar_env, normal, urgent):
    conn, adapter, _ = calendar_env
    result = run_day(calendar_env, "upsert", {"date": "2024-02-29", "fields": {
        **WORK, "eff": 125, "allowNormal": normal, "allowUrgent": urgent}})
    saved = adapter.snapshot("2024-02-29")
    row = row_for(conn, "2024-02-29")
    assert row is not None and row["efficiency"] == 1.25
    assert saved["effective"]["allowNormal"] == normal and saved["effective"]["allowUrgent"] == urgent
    assert saved["effective"]["effective_hours"] == (10 if "yes" in (normal, urgent) else 0)
    assert result["data"] == {"date": "2024-02-29", "calendar_ref": saved["calendar_ref"]}


def test_crossnight_omissions_preserved_and_other_tables_untouched(calendar_env):
    conn, adapter, _ = calendar_env
    original, before = row_for(conn), business_snapshot(conn)
    assert original is not None
    run_day(calendar_env, "upsert", {"date": NIGHT, "fields": {"eff": 75, "allowUrgent": "no"}})
    assert row_for(conn) == {**original, "efficiency": 0.75, "allow_urgent": "no"}
    assert adapter.snapshot(NIGHT)["revision"] == 2
    after = business_snapshot(conn)
    assert {key: value for key, value in after.items() if key != "WorkCalendar"} == {
        key: value for key, value in before.items() if key != "WorkCalendar"}


@pytest.mark.parametrize("fields", ({"hours": 6, "shiftEnd": "06:30"}, {"type": "rest", "shiftEnd": "06:30"}))
def test_explicit_end_conflict_never_claims_input_hours_saved(calendar_env, fields):
    conn, adapter, _ = calendar_env
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected, match="算出 8 小时") as error:
        run_day(calendar_env, "upsert", {"date": NIGHT, "fields": fields})
    assert error.value.code == "constraint_conflict" and stored_state(conn) == before
    with pytest.raises(WorkbenchCommandRejected):
        adapter.preview(range_input(start_date=NIGHT, end_date=NIGHT, fields=fields))
    assert stored_state(conn) == before


def test_derived_shift_window_follows_new_hours(calendar_env):
    """按默认开工时刻推出来的班次结束要跟着新工时重推，不能把上一次的推算结果当成真实班表挡住修改。"""
    conn, _, _ = calendar_env
    day = "2024-02-26"
    run_day(calendar_env, "upsert", {"date": day, "fields": WORK}, key=KEY + "-derived-base")
    assert row_for(conn, day)["shift_start"] == "08:00" and row_for(conn, day)["shift_end"] == "16:00"
    run_day(calendar_env, "upsert", {"date": day, "fields": {"hours": 10}}, key=KEY + "-derived-grow")
    saved = row_for(conn, day)
    assert saved["shift_hours"] == 10 and saved["shift_start"] == "08:00" and saved["shift_end"] == "18:00"


def test_rest_day_returns_to_work_without_untouched_field_conflict(calendar_env):
    """休息改回上班时班次结束会重新出现，这属于派生结果，不算未改项被规则改写。"""
    conn, _, _ = calendar_env
    day = "2024-02-27"
    run_day(calendar_env, "upsert", {"date": day, "fields": {"type": "rest"}}, key=KEY + "-rest-base")
    assert row_for(conn, day)["shift_hours"] == 0 and row_for(conn, day)["shift_end"] is None
    run_day(calendar_env, "upsert", {"date": day, "fields": WORK}, key=KEY + "-rest-back")
    saved = row_for(conn, day)
    assert saved["day_type"] == "workday" and saved["shift_hours"] == 8 and saved["shift_end"] == "16:00"


def test_range_preview_matches_single_day_on_derived_window(calendar_env):
    """范围维护和单日保存都按原开工时刻推算新的结束时刻。"""
    conn, adapter, _ = calendar_env
    day = "2024-02-28"
    run_day(calendar_env, "upsert", {"date": day, "fields": WORK}, key=KEY + "-range-base")
    preview = adapter.preview(range_input(start_date=day, end_date=day, fields={"hours": 10}))
    assert [item["after"]["row"]["shift_end"] for item in preview.days] == ["18:00"]
    assert [item["after"]["row"]["shift_hours"] for item in preview.days] == [10]
    night = adapter.preview(range_input(start_date=NIGHT, end_date=NIGHT, fields={"hours": 10}))
    assert night.days[0]["after"]["row"]["shift_start"] == "22:30"
    assert night.days[0]["after"]["row"]["shift_end"] == "08:30"


def test_rest_is_zero_unavailable_and_clear_restores_default_with_new_lifetime(calendar_env):
    conn, adapter, _ = calendar_env
    day = "2024-02-29"
    run_day(calendar_env, "upsert", {"date": day, "fields": {"type": "rest", "note": "holiday"}})
    rest = adapter.snapshot(day)
    assert rest["explicit"] and rest["row"]["shift_hours"] == 0 and rest["row"]["efficiency"] > 0
    assert rest["effective"]["is_rest"] and rest["row"]["allow_normal"] == rest["row"]["allow_urgent"] == "no"
    cleared = run_day(calendar_env, "delete", {"date": day}, key=KEY + "-clear")
    default = adapter.snapshot(day)
    assert not default["explicit"] and default["effective"]["hours"] == pytest.approx(22 / 3) and row_for(conn, day) is None
    assert default["history"][0]["active"] == 0 and default["history"][0]["revision"] == 2
    assert cleared["data"]["calendar_ref"] == rest["calendar_ref"]
    run_day(calendar_env, "upsert", {"date": day, "fields": WORK}, key=KEY + "-new")
    assert adapter.snapshot(day)["calendar_ref"] != rest["calendar_ref"]


@pytest.mark.parametrize("day", (NIGHT, "2024-02-29"))
def test_empty_upsert_never_supplements_or_updates_default_rows(calendar_env, day):
    conn, _, _ = calendar_env
    before = business_snapshot(conn)
    result = run_day(calendar_env, "upsert", {"date": day})
    assert result["result"] == "unchanged" and business_snapshot(conn) == before


def test_clear_absent_date_is_unchanged_and_weekend_clear_returns_weekend_default(calendar_env):
    conn, adapter, _ = calendar_env
    day = "2024-02-10"
    assert run_day(calendar_env, "delete", {"date": day})["result"] == "unchanged"
    run_day(calendar_env, "upsert", {"date": day, "fields": WORK}, key=KEY + "-work")
    run_day(calendar_env, "delete", {"date": day}, key=KEY + "-clear")
    assert adapter.snapshot(day)["effective"]["hours"] == 0 and row_for(conn, day) is None


@pytest.mark.parametrize("scope,dates", (("all", ["2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31", "2027-01-01", "2027-01-02", "2027-01-03"]),
    ("weekday", ["2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31", "2027-01-01"]),
    ("weekend", ["2027-01-02", "2027-01-03"])))
def test_range_preview_is_readonly_exact_and_confirm_writes_only_matches(calendar_env, scope, dates):
    conn, adapter, _ = calendar_env
    before, changes = stored_state(conn), conn.total_changes
    preview = adapter.preview(range_input(scope=scope))
    assert preview.dates == dates and [day["date"] for day in preview.days] == dates
    assert all(day["before"]["row"] is None and day["after"]["row"]["efficiency"] == 1 for day in preview.days)
    assert stored_state(conn) == before and conn.total_changes == changes and not conn.in_transaction
    result = run_confirm(calendar_env, preview)
    assert [item["date"] for item in result["data"]["dates"]] == dates
    assert all(adapter.snapshot(day)["explicit"] for day in dates)
    stored_dates = [row[0] for row in conn.execute("SELECT date FROM WorkCalendar ORDER BY date")]
    assert stored_dates == sorted([NIGHT] + dates)


def test_weekday_filter_is_not_changed_by_explicit_holiday(calendar_env):
    conn, adapter, _ = calendar_env
    CalendarService(conn).upsert("2027-01-01", day_type="holiday", shift_hours=0, efficiency=0.5)
    preview = adapter.preview(range_input(scope="weekday", fields={}))
    assert "2027-01-01" in preview.dates and preview.days[-1]["before"]["explicit"]
    assert run_confirm(calendar_env, preview)["result"] == "unchanged"


@pytest.mark.parametrize("changes", ({"end_date": "2026-12-27"}, {"end_date": "2127-03-01"},
                                    {"scope": "workday"}, {"operation": "replace"},
                                    {"operation": "delete", "fields": WORK}))
def test_bad_or_unbounded_range_rejected(calendar_env, changes):
    with pytest.raises(ValidationError):
        calendar_env[1].preview(range_input(**changes))


def test_empty_filtered_set(calendar_env):
    conn, adapter, _ = calendar_env
    before = business_snapshot(conn)
    empty = adapter.preview(range_input(start_date="2024-02-29", end_date="2024-02-29", scope="weekend"))
    assert empty.dates == [] and run_confirm(calendar_env, empty)["result"] == "unchanged"
    assert business_snapshot(conn) == before


@pytest.mark.parametrize("count", (366, 367, 400, 36500, 36501))
def test_calendar_range_magnitude_normalization_without_database(count):
    assert MAX_CALENDAR_RANGE_DAYS == int(MAX_CALENDAR_DAYS) == 36500
    start = date(2000, 1, 1)
    end = start + timedelta(days=count - 1)
    payload = range_input(start_date=start.isoformat(), end_date=end.isoformat())
    if count > 36500:
        with pytest.raises(ValidationError, match="36500"):
            WorkbenchCalendarService.normalize("preview", payload)
    else:
        normalized = WorkbenchCalendarService.normalize("preview", payload)
        assert normalized == payload
        assert WorkbenchCalendarService.normalize("preview", normalized) == normalized


@pytest.mark.parametrize("scope,count,first,last", (
    ("weekday", 285, "2023-12-18", "2025-01-17"),
    ("weekend", 115, "2023-12-16", "2025-01-18"),
))
def test_continuous_400_days_filter_complete_set_and_persist_both_ends(calendar_env, scope, count, first, last):
    conn, adapter, _ = calendar_env
    payload = range_input(start_date="2023-12-16", end_date="2025-01-18", scope=scope)
    expected = expected_range_dates(payload["start_date"], payload["end_date"], scope)
    before = business_snapshot(conn)
    preview = adapter.preview(payload)
    assert preview.dates == expected and len(preview.dates) == count
    assert (preview.dates[0], preview.dates[-1]) == (first, last)
    assert business_snapshot(conn) == before
    result = run_confirm(calendar_env, preview)
    assert_complete_calendar_write(conn, preview, result)
    assert_other_business_unchanged(conn, before)
    for day in (first, last):
        stored = row_for(conn, day)
        assert stored is not None and stored["shift_hours"] == 8 and stored["efficiency"] == 1


@pytest.mark.parametrize("year,count", ((2025, 365), (2024, 366)))
def test_annual_preview_confirm_measured_complete_and_preserves_resources(annual_env, year, count):
    from core.infrastructure.workbench_resource_schema import RESOURCE_TABLE_NAMES

    conn, adapter, _ = annual_env
    start, end = f"{year}-01-01", f"{year}-12-31"
    CalendarService(conn).upsert_operator_calendar("CO", end, shift_start="23:00", shift_end="05:00",
                                                  efficiency=0.7, remark="annual personal exception")
    before, changes = business_snapshot(conn), conn.total_changes
    assert all(before[table][1] for table in RESOURCE_TABLE_NAMES)
    preview, preview_measure = measure_calendar_call(conn, lambda: adapter.preview(range_input(start_date=start, end_date=end)))
    assert preview.dates == expected_range_dates(start, end) and len(preview.dates) == count
    assert (f"{year}-02-29" in preview.dates) == (count == 366)
    assert conn.total_changes == changes and business_snapshot(conn) == before
    assert preview_measure["sql"] == {"BEGIN": 1, "SELECT": 3, "COMMIT": 1}
    result, confirm_measure = measure_calendar_call(conn, lambda: run_confirm(annual_env, preview))
    assert confirm_measure["sql"]["INSERT"] == count + 1  # Every date plus the one command receipt.
    assert_complete_calendar_write(conn, preview, result)
    assert_other_business_unchanged(conn, before)
    tail = row_for(conn, end)
    assert tail is not None and tail["date"] == end and tail["shift_hours"] == 8 and tail["efficiency"] == 1
    print(json.dumps({"year": year, "days": count, "preview": preview_measure,
                      "confirm": confirm_measure, "readback_last_date": tail["date"]}, sort_keys=True))


@pytest.mark.parametrize("change", ("expired", "future", "dates", "request", "raw", "revision", "aba"))
def test_confirm_rechecks_time_exact_dates_complete_rows_refs_and_versions(calendar_env, change):
    conn, adapter, clock = calendar_env
    preview = adapter.preview(range_input(start_date=NIGHT, end_date=NIGHT, fields={"eff": 75}))
    if change == "expired":
        clock.advance(CALENDAR_PREVIEW_TTL_SECONDS)
    elif change == "future":
        clock.advance(-1)
    elif change == "dates":
        preview = replace(preview, dates=[])
    elif change == "request":
        preview.request["end_date"] = "2026-09-10"
    elif change in ("raw", "revision"):
        conn.execute("UPDATE WorkCalendar SET remark = ? WHERE date = ?", ("changed" if change == "raw" else "night retained", NIGHT))
        conn.commit()
    else:
        CalendarService(conn).delete(NIGHT)
        CalendarService(conn).upsert(NIGHT, shift_start="22:30", shift_end="06:30", efficiency=0.875,
                                     allow_normal="no", allow_urgent="yes", remark="night retained")
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_confirm(calendar_env, preview)
    assert error.value.code == "snapshot_stale" and stored_state(conn) == before and not conn.in_transaction


def test_absent_created_deleted_aba_is_not_an_unchanged_snapshot(calendar_env):
    conn, adapter, _ = calendar_env
    preview = adapter.preview(range_input())
    domain = CalendarService(conn)
    domain.upsert("2027-01-01")
    domain.delete("2027-01-01")
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected, match="已经变了"):
        run_confirm(calendar_env, preview)
    assert stored_state(conn) == before


@pytest.mark.parametrize("failure", ("second_day", "receipt"))
def test_range_and_receipt_failures_roll_back_every_table_and_ref(calendar_env, monkeypatch, failure):
    conn, adapter, _ = calendar_env
    preview, before = adapter.preview(range_input()), stored_state(conn)
    command, calls = WorkbenchCommandService(conn), []
    domain_write = adapter._calendar.upsert_no_tx

    def fail_later(payload):
        calls.append(payload["date"])
        if len(calls) == 2:
            raise ValidationError("fixture second day failed")
        return domain_write(payload)

    original = command.repo.insert

    def receipt_fail(**kwargs):
        original(**kwargs)
        raise OSError("fixture receipt failed after insert")

    if failure == "second_day":
        monkeypatch.setattr(adapter._calendar, "upsert_no_tx", fail_later)
    else:
        monkeypatch.setattr(command.repo, "insert", receipt_fail)
    with pytest.raises(ValidationError if failure == "second_day" else WorkbenchCommandUncertain):
        run_confirm(calendar_env, preview, command=command)
    assert stored_state(conn) == before and command.lookup(KEY) is None and not conn.in_transaction


@pytest.mark.parametrize("action", ("upsert", "delete"))
def test_day_mutations_require_outer_transaction_recheck_full_snapshot_and_rollback(calendar_env, action):
    conn, adapter, _ = calendar_env
    payload = {"date": NIGHT, **({"fields": {"eff": 75}} if action == "upsert" else {})}
    checked, before = adapter.snapshot(NIGHT), stored_state(conn)
    with pytest.raises(RuntimeError, match="外层"):
        adapter.apply(action, adapter.normalize(action, payload), checked)
    with pytest.raises(RuntimeError, match="fixture rollback"):
        with TransactionManager(conn).transaction(begin_immediate=True):
            assert adapter.apply(action, adapter.normalize(action, payload), checked).result == "committed"
            assert conn.in_transaction
            raise RuntimeError("fixture rollback")
    assert stored_state(conn) == before
    CalendarService(conn).upsert(NIGHT, shift_start="22:30", shift_end="06:30", remark="new")
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_day(calendar_env, action, payload, checked=checked)
    assert error.value.code == "stale_write" and stored_state(conn) == before


def test_range_clear_deletes_only_explicit_rows_and_replays_after_expiry(calendar_env):
    conn, adapter, clock = calendar_env
    preview = adapter.preview(range_input(start_date="2026-09-08", end_date="2026-09-10", operation="delete", fields={}))
    first = run_confirm(calendar_env, preview)
    assert [item["result"] for item in first["data"]["dates"]] == ["unchanged", "committed", "unchanged"]
    assert row_for(conn) is None
    clock.advance(CALENDAR_PREVIEW_TTL_SECONDS + 1)
    CalendarService(conn).upsert(NIGHT)
    before = stored_state(conn)

    def expired():
        pytest.fail("receipt must replay before the expired guard")

    second = run_confirm(calendar_env, preview, guard=expired)
    assert second == {**first, "replayed": True} and stored_state(conn) == before
    assert all(set(item) == {"date", "calendar_ref", "result"} for item in second["data"]["dates"])
    assert "write_token" not in canonical_json(first) and "revision" not in canonical_json(first)


def test_same_day_request_key_replays_and_changed_intent_conflicts(calendar_env):
    conn, adapter, _ = calendar_env
    payload = {"date": NIGHT, "fields": {"eff": 75}}
    checked = adapter.snapshot(NIGHT)
    first = run_day(calendar_env, "upsert", payload, checked=checked)
    before = stored_state(conn)
    assert run_day(calendar_env, "upsert", payload, checked=checked) == {**first, "replayed": True}
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_day(calendar_env, "upsert", {"date": NIGHT, "fields": {"eff": 50}})
    assert error.value.code == "request_key_conflict" and stored_state(conn) == before


def test_ref_survives_reconnect_and_reads_do_not_repair_missing_metadata(calendar_env, tmp_path):
    conn, adapter, clock = calendar_env
    before = adapter.snapshot(NIGHT)
    path = tmp_path / "calendar.db"
    copy_to_temp(conn, path)
    with connect_temp(path) as other:
        assert WorkbenchCalendarService(other, clock=clock).snapshot(NIGHT) == before
    conn.execute("DELETE FROM WorkbenchEntityRefs WHERE ref = ?", (before["calendar_ref"],))
    conn.commit()
    changes, stored = conn.total_changes, stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected, match="永久引用不一致"):
        adapter.snapshot(NIGHT)
    assert conn.total_changes == changes and stored_state(conn) == stored


def test_raw_null_fields_preserved_in_snapshot_and_not_silently_rewritten(calendar_env):
    """快照如实显示空列；改效率时，空列只补成引擎本来就按的默认值（08:00 开始、按工时推出结束），
    这一天的时段和工时不变，不算改写（旧库升级加列没回填的行因此能在日历页改好）。"""
    conn, adapter, _ = calendar_env
    conn.execute("UPDATE WorkCalendar SET shift_start = NULL, shift_end = NULL WHERE date = ?", (NIGHT,))
    conn.commit()
    before = adapter.snapshot(NIGHT)
    assert before["row"]["shift_start"] is None
    assert run_day(calendar_env, "upsert", {"date": NIGHT, "fields": {"eff": 50}})["result"] == "committed"
    saved = row_for(conn)
    assert (saved["shift_start"], saved["shift_end"], saved["shift_hours"], saved["efficiency"]) == ("08:00", "16:00", 8, 0.5)
    after = adapter.snapshot(NIGHT)["effective"]
    assert (after["windows"], after["hours"]) == (before["effective"]["windows"], before["effective"]["hours"])


def test_query_failure_propagates_without_fake_default_or_write(calendar_env):
    conn, adapter, _ = calendar_env
    before = stored_state(conn)
    with patch.object(WorkbenchCalendarQueryRepository, "calendar_rows", side_effect=RuntimeError("fixture read failure")):
        with pytest.raises(RuntimeError, match="fixture read failure"):
            adapter.month(2024, 2)
    assert stored_state(conn) == before


def test_subminute_hours_rejected_before_preview_or_domain_write(calendar_env):
    conn, adapter, _ = calendar_env
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected, match="存不稳"):
        adapter.preview(range_input(fields={**WORK, "hours": 1.001}))
    with pytest.raises(WorkbenchCommandRejected, match="存不稳"):
        run_day(calendar_env, "upsert", {"date": "2024-02-29", "fields": {**WORK, "hours": 1.001}})
    assert stored_state(conn) == before


def test_missing_update_revision_trigger_rolls_back(calendar_env):
    conn, _, _ = calendar_env
    conn.execute("DROP TRIGGER wb_ref_calendar_update")
    conn.commit()
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandUncertain) as error:
        run_day(calendar_env, "upsert", {"date": NIGHT, "fields": {"eff": 75}})
    assert "修订号" in str(error.value.__cause__) and stored_state(conn) == before


def test_new_conflicting_shift_after_preview_reports_stale_before_rebuilding(calendar_env):
    conn, adapter, _ = calendar_env
    preview = adapter.preview(range_input(start_date=NIGHT, end_date=NIGHT, fields={"hours": 8}))
    CalendarService(conn).upsert(NIGHT, shift_start="21:30", shift_end="06:30")
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_confirm(calendar_env, preview)
    assert error.value.code == "snapshot_stale" and stored_state(conn) == before


def test_global_rest_does_not_override_personal_exception(calendar_env):
    conn, adapter, _ = calendar_env
    # Clearing global state first is an explicit user intent, not a silent shift overwrite.
    run_day(calendar_env, "delete", {"date": NIGHT})
    run_day(calendar_env, "upsert", {"date": NIGHT, "fields": {"type": "rest"}}, key=KEY + "-rest")
    assert adapter.snapshot(NIGHT)["effective"]["is_rest"]
    policy = CalendarService(conn).policy_for_datetime(datetime(2026, 9, 9, 23, 30), operator_id="CO")
    assert policy.shift_hours == 8.5 and policy.efficiency == 0.625


def test_holiday_default_efficiency_change_invalidates_preview(calendar_env):
    conn, adapter, _ = calendar_env
    conn.execute("INSERT OR REPLACE INTO ScheduleConfig (config_key, config_value) VALUES ('holiday_default_efficiency', '0.5')")
    conn.commit()
    preview = adapter.preview(range_input(fields={"type": "rest"}))
    assert preview.days[0]["after"]["row"]["efficiency"] == 0.5
    conn.execute("UPDATE ScheduleConfig SET config_value = '0.75' WHERE config_key = 'holiday_default_efficiency'")
    conn.commit()
    before = stored_state(conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        run_confirm(calendar_env, preview)
    assert error.value.code == "snapshot_stale" and stored_state(conn) == before


@pytest.mark.parametrize("action", ("upsert", "delete"))
def test_day_receipt_failure_is_atomic_and_delete_replay_ignores_recreation(calendar_env, monkeypatch, action):
    conn, adapter, _ = calendar_env
    payload = {"date": NIGHT, **({"fields": {"eff": 75}} if action == "upsert" else {})}
    before, command = stored_state(conn), WorkbenchCommandService(conn)

    def fail(**_kwargs):
        raise OSError("fixture receipt failure")

    monkeypatch.setattr(command.repo, "insert", fail)
    with pytest.raises(WorkbenchCommandUncertain):
        run_day(calendar_env, action, payload, command=command)
    assert stored_state(conn) == before
    checked = adapter.snapshot(NIGHT)
    first = run_day(calendar_env, action, payload, checked=checked)
    if action == "delete":
        CalendarService(conn).upsert(NIGHT)
    before = stored_state(conn)
    assert run_day(calendar_env, action, payload, checked=checked) == {**first, "replayed": True}
    assert stored_state(conn) == before


def test_actual_recomputed_date_set_must_equal_preview(calendar_env):
    conn, adapter, _ = calendar_env
    preview = adapter.preview(range_input())
    before = stored_state(conn)
    with patch("core.services.workbench.resource.calendars.calendar_range_dates", return_value=preview.dates[:-1]):
        with pytest.raises(WorkbenchCommandRejected, match="命中的日期"):
            run_confirm(calendar_env, preview)
    assert stored_state(conn) == before


def test_populated_d06_tables_and_personal_dates_unchanged_by_global_writes(calendar_env):
    from core.infrastructure.workbench_resource_schema import RESOURCE_TABLE_NAMES

    conn, _, _ = calendar_env
    seed_d06_resources(conn)
    before = business_snapshot(conn)
    assert len(RESOURCE_TABLE_NAMES) == 8
    assert all(before[name][1] for name in RESOURCE_TABLE_NAMES)
    run_day(calendar_env, "upsert", {"date": NIGHT, "fields": {"eff": 75}})
    run_day(calendar_env, "delete", {"date": NIGHT}, key=KEY + "-clear")
    after = business_snapshot(conn)
    assert {key: value for key, value in after.items() if key != "WorkCalendar"} == {
        key: value for key, value in before.items() if key != "WorkCalendar"}


def test_expired_confirm_ref_points_to_the_existing_preview_button():
    """确认时清单编号失效，提示要点的是页面上现有的「预览变更」按钮。"""
    with pytest.raises(ValidationError, match="请重新点「预览变更」"):
        WorkbenchCalendarService.normalize("confirm", {"preview_ref": "stale"})


@pytest.mark.parametrize("fields,changed", (({"note": "只改备注"}, {"remark": "只改备注"}),
                                            ({"eff": 90}, {"efficiency": 0.9})))
def test_legacy_row_without_end_keeps_hours_when_only_note_or_efficiency_changes(calendar_env, fields, changed):
    """旧行只存开始和工时（09:00 起 4 小时、结束为空）：只改备注或效率时补出结束 13:00，工时仍是 4 小时。"""
    conn, adapter, _ = calendar_env
    day = "2026-10-12"
    CalendarService(conn).upsert(day, shift_start="09:00", shift_hours=4, remark="旧")
    conn.execute("UPDATE WorkCalendar SET shift_end = NULL WHERE date = ?", (day,))
    conn.commit()
    before = row_for(conn, day)
    assert run_day(calendar_env, "upsert", {"date": day, "fields": fields})["result"] == "committed"
    assert row_for(conn, day) == {**before, "shift_end": "13:00", **changed}
    assert adapter.snapshot(day)["effective"]["window_end"] == "2026-10-12T13:00:00"


def test_rest_day_with_empty_periods_returns_to_single_shift_but_multi_period_day_still_guarded(calendar_env):
    """休息日存成空时段后，填工时或班次起止就按单班改回工作日；真正按多时段设置的日期仍只能改逐段时段。"""
    conn, _, _ = calendar_env
    rest, periods = "2026-10-14", "2026-10-15"
    run_day(calendar_env, "upsert", {"date": rest, "fields": {"type": "rest", "periods": []}}, key=KEY + "-rest")
    assert row_for(conn, rest)["periods_json"] == "[]"
    run_day(calendar_env, "upsert", {"date": rest, "fields": WORK}, key=KEY + "-hours")
    saved = row_for(conn, rest)
    assert (saved["day_type"], saved["shift_start"], saved["shift_end"], saved["shift_hours"]) == ("workday", "08:00", "16:00", 8)
    assert saved["periods_json"] is None
    CalendarService(conn).upsert(periods, periods=[{"start": "08:00", "end": "12:00", "day_offset": 0},
                                                   {"start": "13:00", "end": "17:00", "day_offset": 0}])
    with pytest.raises(ValidationError, match="已按多时段设置"):
        run_day(calendar_env, "upsert", {"date": periods, "fields": {"hours": 6}}, key=KEY + "-periods")


def test_month_total_counts_night_tail_overlap_once_like_the_engine(calendar_env):
    """跨夜尾巴与次日班次重叠时重叠段归次日：月合计与排产引擎一致，月末尾巴被次月 1 日占用的部分同样扣掉。"""
    conn, adapter, _ = calendar_env
    domain = CalendarService(conn)
    domain.upsert("2026-10-12", periods=[{"start": "22:00", "end": "06:00", "day_offset": 0}])
    domain.upsert("2026-10-13", periods=[{"start": "04:00", "end": "12:00", "day_offset": 0}], efficiency=0.5)
    domain.upsert("2026-10-31", shift_start="22:00", shift_end="06:00")
    domain.upsert("2026-11-01", shift_start="05:00", shift_end="09:00")
    october = adapter.month(2026, 10)
    days = {item["date"]: item["effective"] for item in october["days"]}
    assert days["2026-10-12"]["effective_hours"] == 8 and days["2026-10-13"]["effective_hours"] == 4
    plain = sum(item["effective_hours"] for item in days.values())
    # 10-12 的 04:00–06:00 归 10-13，10-31 的 05:00–06:00 归 11-01。
    assert october["stats"]["effective_hours"] == pytest.approx(plain - 2 - 1)
    engine = domain._engine
    engine.clear_policy_cache()
    assert engine.capacity_hours_between(datetime(2026, 10, 12), datetime(2026, 10, 14)) == pytest.approx(6 + 4)
    conn.execute("UPDATE WorkCalendar SET efficiency = 'bad' WHERE date = '2026-11-01'")
    conn.commit()
    assert adapter.month(2026, 10)["stats"]["effective_hours"] is None


def test_month_view_does_not_depend_on_next_month_integrity(calendar_env):
    """月合计要看次月 1 日是否占用月末夜班尾巴，但只单独读那一行：次月 1 日的永久引用缺失、
    本月以外存了不规范的日期，都不能让本月月视图读不出来。"""
    conn, adapter, _ = calendar_env
    domain = CalendarService(conn)
    domain.upsert("2026-10-31", shift_start="22:00", shift_end="06:00")
    domain.upsert("2026-11-01", shift_start="05:00", shift_end="09:00")
    conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind = 'calendar' AND entity_key = '2026-11-01'")
    conn.execute("INSERT INTO WorkCalendar(date, day_type, shift_hours, efficiency, allow_normal, allow_urgent) "
                 "VALUES ('2026-10-31 00:00:00', 'workday', 8, 1, 'yes', 'yes')")
    conn.commit()
    october = adapter.month(2026, 10)
    plain = sum(item["effective"]["effective_hours"] for item in october["days"])
    assert october["stats"]["effective_hours"] == pytest.approx(plain - 1)
    with pytest.raises(WorkbenchCommandRejected, match="永久引用不一致"):
        adapter.month(2026, 11)


def test_last_date_night_shift_is_rejected_before_any_write(calendar_env):
    """9999-12-31 自己排夜班会跨出系统能处理的日期：保存前就拒绝并说明，库里不留半截数据。"""
    conn = calendar_env[0]
    before = stored_state(conn)
    with pytest.raises(ValidationError, match="班次在当天结束"):
        run_day(calendar_env, "upsert", {"date": "9999-12-31", "fields": {**WORK, "shiftStart": "22:00", "shiftEnd": "06:00"}})
    assert stored_state(conn) == before


@pytest.mark.parametrize("column", ["shift_start", "shift_hours", "efficiency"])
@pytest.mark.parametrize("fields,changed", (({"note": "只改备注"}, {"remark": "只改备注"}),
                                            ({"eff": 90}, {"efficiency": 0.9})))
def test_legacy_blank_column_is_filled_with_the_engine_reading_not_rejected(calendar_env, column, fields, changed):
    """旧库升级加列没回填：班次开始、工时或效率空着，日历页和排产都按默认值解释（08:00 开始、按时段 8 小时、效率 1）。
    只改备注或效率时规则把空值补成同样的值，这一天的时段和工时不变，不算“没改的项被改写”。"""
    conn, adapter, _ = calendar_env
    day = "2026-10-12"
    CalendarService(conn).upsert(day, shift_start="08:00", shift_hours=8, remark="旧")
    conn.execute(f"UPDATE WorkCalendar SET {column} = NULL, shift_end = NULL WHERE date = ?", (day,))
    conn.commit()
    before = adapter.snapshot(day)["effective"]
    assert run_day(calendar_env, "upsert", {"date": day, "fields": fields})["result"] == "committed"
    saved = row_for(conn, day)
    expected = {"shift_start": "08:00", "shift_end": "16:00", "shift_hours": 8, "efficiency": 1.0, "remark": "旧", **changed}
    assert {key: saved[key] for key in expected} == expected
    after = adapter.snapshot(day)["effective"]
    assert (after["windows"], after["hours"]) == (before["windows"], before["hours"])


def test_legacy_blank_column_whose_fill_would_change_the_day_is_still_rejected(calendar_env):
    """补出来的值和引擎原来的解释不一样仍算改写：假期空着效率，引擎按 1 算，保存规则会补成假期默认效率。"""
    conn = calendar_env[0]
    day = "2026-10-13"
    CalendarService(conn).upsert(day, day_type="holiday", shift_hours=0, remark="旧")
    conn.execute("UPDATE WorkCalendar SET efficiency = NULL WHERE date = ?", (day,))
    conn.commit()
    before = row_for(conn, day)
    with pytest.raises(WorkbenchCommandRejected, match="没改的项会被规则改写"):
        run_day(calendar_env, "upsert", {"date": day, "fields": {"note": "只改备注"}})
    assert row_for(conn, day) == before
