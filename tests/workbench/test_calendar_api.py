"""Actual HTTP contracts on fixture databases; no prototype data or stub CalendarAdmin."""

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.services.scheduler.calendar_service import CalendarService
from core.services.workbench.calendars import WorkbenchCalendarService
from core.services.workbench.commands import WorkbenchCommandService
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from tests.workbench.calendar_api_support import (
    BASE,
    NIGHT,
    WORK,
    assert_error,
    assert_no_private_facts,
    calendar_api_fixture,
)


@pytest.mark.parametrize("year,month,count", [(2024, 2, 29), (2023, 2, 28), (2026, 12, 31), (2027, 1, 31)])
def test_month_switching_is_real_complete_and_read_only(calendar_api, year, month, count):
    before = calendar_api.state()
    response = calendar_api.month(year, month)
    data = response["data"]
    assert response["meta"]["source"] == "production" and response["meta"]["time_basis"] == "factory_local"
    assert data["as_of"] == "2026-09-09T12:34:56"
    assert [item["date"] for item in data["days"]] == [f"{year:04d}-{month:02d}-{n:02d}" for n in range(1, count + 1)]
    assert [item for item in data["cells"] if item is not None] == data["days"]
    assert len(data["cells"]) % 7 == 0 and data["stats"]["configured"] == 0
    for day in data["days"]:
        assert day["entity"] is None and day["calendar_ref"] is None and day["stored"] is None
        assert day["fields"]["hours"] == (0 if date.fromisoformat(day["date"]).weekday() >= 5 else 8)
        assert day["fields"]["eff"] == 100
    assert calendar_api.state() == before
    assert_no_private_facts(response)


def test_month_navigation_boundary_and_snapshot_binding(calendar_api):
    assert calendar_api.month(2026, 12)["data"]["next_month"] == {"year": 2027, "month": 1}
    assert calendar_api.month(2027, 1)["data"]["previous_month"] == {"year": 2026, "month": 12}
    before = calendar_api.month()
    token = before["meta"]["snapshot_ref"]
    assert calendar_api.month(snapshot_ref=token)["meta"]["snapshot_ref"] == token
    calendar_api.advance(60)
    assert calendar_api.month(snapshot_ref=token)["meta"]["as_of"] == before["meta"]["as_of"]
    assert calendar_api.save({"note": "Edited"}).status_code == 200
    assert_error(calendar_api.client.get(BASE + "/month", query_string={"year": 2026, "month": 9, "snapshot_ref": token}), "snapshot_stale")


def test_actual_night_policy_readonly_fields_and_public_identity(calendar_api):
    day = calendar_api.day()
    assert day["is_today"] and re.fullmatch("[a-f0-9]{48}", day["calendar_ref"])
    assert day["entity"]["ref"] == day["calendar_ref"] and day["entity"]["business_code"] == NIGHT
    assert day["stored"]["shift_start"] == "22:30" and day["stored"]["shift_end"] == "06:30"
    assert day["fields"]["eff"] == 87.5 and day["effective"]["efficiency"] == 0.875
    assert day["effective"]["window_end"] == "2026-09-10T06:30:00"
    assert day["effective"]["allowNormal"] == "no" and day["effective"]["allowUrgent"] == "yes"
    assert calendar_api.day("2026-09-10")["effective"]["window_start"] == "2026-09-10T08:00:00"
    assert_no_private_facts(day)


def test_day_save_preserves_hidden_windows_and_personal_profile_priority(calendar_api):
    before, old_ref = calendar_api.row(), calendar_api.day()["calendar_ref"]
    with calendar_api.db() as conn:
        preserved = [tuple(row) for row in conn.execute("SELECT * FROM OperatorCalendar")]
    response = calendar_api.save({"eff": 125, "note": "Changed"})
    assert response.status_code == 200 and response.get_json()["result"] == "committed"
    assert calendar_api.row() == {**before, "efficiency": 1.25, "remark": "Changed"}
    assert calendar_api.day()["calendar_ref"] == old_ref
    with calendar_api.db() as conn:
        service = CalendarService(conn)
        personal = service.policy_for_datetime(datetime(2026, 9, 10, 1), operator_id="CAL-O")
        assert personal.date_str == NIGHT and personal.efficiency == 0.625 and personal.shift_hours == 8.5
        assert personal.work_window()[0] == datetime(2026, 9, 9, 23, 15)
        profile = service.policy_for_datetime(datetime(2026, 9, 10, 22), operator_id="CAL-O")
        assert profile.work_window() == (datetime(2026, 9, 10, 21, 15), datetime(2026, 9, 11, 5, 15))
        assert [tuple(row) for row in conn.execute("SELECT * FROM OperatorCalendar")] == preserved


@pytest.mark.parametrize("fields", [{"hours": 6}, {"type": "rest"}])
def test_incompatible_hidden_end_rejects_save_and_preview(calendar_api, fields):
    before = calendar_api.state()
    assert_error(calendar_api.save(fields), "constraint_conflict")
    response = calendar_api.client.post(BASE + "/range/preview", json={"input": {
        "start_date": NIGHT, "end_date": NIGHT, "fields": fields}})
    assert_error(response, "constraint_conflict")
    assert calendar_api.state() == before


def test_rest_delete_recreate_uses_new_identity_and_aba_stale_guards(calendar_api):
    day = "2026-09-10"
    original = calendar_api.day_body(day, {"note": "Old absent view"})
    assert calendar_api.save({"type": "rest", "eff": 80}, day).status_code == 200
    stored = calendar_api.day(day)
    assert stored["effective"]["is_rest"] and stored["fields"]["hours"] == 0
    delete = calendar_api.day_body(day, action="delete")
    assert calendar_api.client.post(BASE + "/delete", json=delete).status_code == 200
    assert calendar_api.row(day) is None and calendar_api.day(day)["effective"]["hours"] == 8
    assert_error(calendar_api.client.post(BASE + "/upsert", json=original), "stale_write")
    assert calendar_api.save(WORK, day).status_code == 200
    assert calendar_api.day(day)["calendar_ref"] != stored["calendar_ref"]
    assert_error(calendar_api.client.post(BASE + "/delete", json={**delete, "request_key": "stale-recreated-day-01"}), "stale_write")
    replay = calendar_api.client.post(BASE + "/delete", json=delete).get_json()
    assert replay["replayed"] and replay["data"]["calendar_ref"] == stored["calendar_ref"]
    assert calendar_api.row(day) is not None


@pytest.mark.parametrize("normal,urgent", [("yes", "yes"), ("yes", "no"), ("no", "yes"), ("no", "no")])
def test_priority_and_efficiency_units_match_real_engine(calendar_api, normal, urgent):
    day = "2026-09-10"
    response = calendar_api.save({**WORK, "hours": 7.5, "eff": 125, "allowNormal": normal, "allowUrgent": urgent}, day)
    assert response.status_code == 200
    saved = calendar_api.day(day)
    assert saved["fields"]["hours"] == 7.5 and saved["stored"]["efficiency"] == 1.25
    assert saved["fields"]["type"] == "work"
    assert saved["effective"]["effective_hours"] == (9.375 if "yes" in (normal, urgent) else 0)


def test_stale_day_token_wrong_date_action_and_receipt_first_after_expiry(calendar_api):
    body = calendar_api.day_body(fields={"note": "First"})
    wrong = {**body, "input": {"date": "2026-09-10", "fields": {"note": "Wrong"}}}
    assert_error(calendar_api.client.post(BASE + "/upsert", json=wrong), "stale_write")
    first = calendar_api.client.post(BASE + "/upsert", json=body).get_json()
    assert first["result"] == "committed"
    assert_error(calendar_api.client.post(BASE + "/upsert", json={**body, "request_key": "stale-day-request-001"}), "stale_write")
    assert_error(calendar_api.client.post(BASE + "/upsert", json={**body, "input": {"date": NIGHT, "fields": {"note": "Second"}}}), "request_key_conflict")
    calendar_api.advance(901)
    with patch("web.routes.workbench.calendars.validate_write_context", side_effect=AssertionError("guard must not run")):
        assert calendar_api.client.post(BASE + "/upsert", json=body).get_json() == {**first, "replayed": True}


@pytest.mark.parametrize("action,fields", [("upsert", {}), ("delete", None)])
def test_noop_absent_day_has_receipt_but_no_placeholder_row(calendar_api, action, fields):
    day = "2026-09-10"
    body = calendar_api.day_body(day, fields, action=action)
    result = calendar_api.client.post(BASE + "/" + action, json=body).get_json()
    assert result["result"] == "unchanged" and result["data"]["calendar_ref"] is None
    assert calendar_api.row(day) is None
    assert calendar_api.client.get("/api/workbench/v1/commands/" + body["request_key"]).get_json()["receipt_ref"] == result["receipt_ref"]


@pytest.mark.parametrize("scope,expected", [("all", 7), ("weekday", 5), ("weekend", 2)])
def test_preview_is_readonly_complete_then_atomic_confirm(calendar_api, scope, expected):
    before = calendar_api.state()
    preview = calendar_api.preview(scope=scope)
    assert preview["counts"] == {"selected": expected, "changed": expected, "unchanged": 0, "configured_before": 0, "configured_after": expected}
    assert len(preview["days"]) == len(preview["dates"]) == expected
    assert all(item["before"]["calendar_ref"] is None for item in preview["days"])
    assert_no_private_facts(preview)
    assert calendar_api.state() == before
    response, body = calendar_api.confirm(preview)
    result = response.get_json()
    assert response.status_code == 200 and result["result"] == "committed"
    assert [item["date"] for item in result["data"]["dates"]] == preview["dates"]
    assert all(re.fullmatch("[a-f0-9]{48}", item["calendar_ref"]) for item in result["data"]["dates"])
    calendar_api.advance(901)
    with patch("web.routes.workbench.calendars.resolve_preview", side_effect=AssertionError("receipt must be first")):
        assert calendar_api.client.post(BASE + "/range/confirm", json=body).get_json() == {**result, "replayed": True}


@pytest.mark.parametrize("operation", ["upsert", "delete"])
def test_range_revalidates_all_facts_before_writing(calendar_api, operation):
    initial = calendar_api.preview()
    assert calendar_api.confirm(initial)[0].status_code == 200
    preview = calendar_api.preview(operation=operation, fields={"note": "Range edit"} if operation == "upsert" else {})
    with calendar_api.db() as conn:
        conn.execute("UPDATE WorkCalendar SET remark='Outside edit' WHERE date='2027-01-03'")
    before = calendar_api.state()
    assert_error(calendar_api.confirm(preview)[0], "snapshot_stale")
    assert calendar_api.state() == before


@pytest.mark.parametrize("operation", ["upsert", "delete"])
def test_range_midwrite_and_receipt_failures_roll_back_every_row(calendar_api, operation):
    from data.repositories.calendar_repo import CalendarRepository

    assert calendar_api.confirm(calendar_api.preview())[0].status_code == 200
    preview = calendar_api.preview(operation=operation, fields={"note": "Changed"} if operation == "upsert" else {})
    before = calendar_api.state()
    method = CalendarRepository.upsert if operation == "upsert" else CalendarRepository.delete
    calls = []

    def fail_second(self, value):
        calls.append(value)
        if len(calls) == 2:
            raise RuntimeError("fixture calendar write failure")
        return method(self, value)

    with patch.object(CalendarRepository, operation, fail_second):
        response, body = calendar_api.confirm(preview)
    assert_error(response, "storage_failure", 500, "unknown")
    assert len(calls) == 2 and calendar_api.state() == before
    with patch.object(WorkbenchCommandRepository, "insert", side_effect=RuntimeError("fixture receipt failure")):
        assert_error(calendar_api.client.post(BASE + "/range/confirm", json=body), "storage_failure", 500, "unknown")
    assert calendar_api.state() == before
    assert calendar_api.client.post(BASE + "/range/confirm", json=body).status_code == 200


def test_expired_missing_mismatched_or_forged_previews_never_write(calendar_api):
    first, second = calendar_api.preview(), calendar_api.preview(scope="weekday")
    body = calendar_api.confirm_body(first)
    before = calendar_api.state()
    assert_error(calendar_api.client.post(BASE + "/range/confirm", json={**body, "write_token": second["write_context"]["write_token"]}), "stale_write")
    assert_error(calendar_api.client.post(BASE + "/range/confirm", json={**body, "input": {"preview_ref": "0" * 32}}), "snapshot_stale")
    forged = {**body, "input": {**body["input"], "days": first["days"]}}
    assert_error(calendar_api.client.post(BASE + "/range/confirm", json=forged), "invalid_input", 422)
    calendar_api.advance(901)
    assert_error(calendar_api.client.post(BASE + "/range/confirm", json=body), "stale_write")
    assert calendar_api.state() == before


def test_preview_domain_expiry_is_checked_even_if_token_clock_is_valid(calendar_api, monkeypatch):
    import web.public_token_registry as registry

    preview = calendar_api.preview()
    stamp = calendar_api.now.timestamp()
    monkeypatch.setattr(registry, "time", SimpleNamespace(time=lambda: stamp))
    calendar_api.advance(901)
    before = calendar_api.state()
    assert_error(calendar_api.confirm(preview)[0], "snapshot_stale")
    assert calendar_api.state() == before


def test_annual_range_has_no_62_day_limit_and_complete_rows(calendar_api):
    start, end = date(2027, 1, 1), date(2028, 2, 4)
    preview = calendar_api.preview(start_date=start.isoformat(), end_date=end.isoformat(), scope="weekday")
    expected = [(start + timedelta(days=i)).isoformat() for i in range(400) if (start + timedelta(days=i)).weekday() < 5]
    assert preview["dates"] == expected
    response, _ = calendar_api.confirm(preview)
    assert response.status_code == 200
    assert [item["date"] for item in response.get_json()["data"]["dates"]] == expected
    with calendar_api.db() as conn:
        assert [row[0] for row in conn.execute("SELECT date FROM WorkCalendar WHERE date>=? AND date<=? ORDER BY date", (start.isoformat(), end.isoformat()))] == expected


def test_36500_limit_is_checked_before_chosen_weekdays(calendar_api):
    start = date(2027, 1, 1)
    before = calendar_api.state()
    for scope in ("all", "weekday", "weekend"):
        response = calendar_api.client.post(BASE + "/range/preview", json={"input": {
            "start_date": start.isoformat(), "end_date": (start + timedelta(days=36500)).isoformat(), "scope": scope}})
        assert_error(response, "invalid_input", 422)
    assert calendar_api.state() == before
    # Exercise the full admitted range over HTTP; delete on absent dates has no write.
    preview = calendar_api.preview(start_date=start.isoformat(), end_date=(start + timedelta(days=36499)).isoformat(),
                                   operation="delete", fields={})
    assert len(preview["dates"]) == len(preview["days"]) == 36500
    assert preview["counts"]["changed"] == 0 and calendar_api.state() == before


@pytest.mark.parametrize("query", [{}, {"year": 2026, "month": 0}, {"year": 2026, "month": 13},
    {"year": 2026, "month": "09"}, {"year": 2026, "month": 9, "operator_id": "CAL-O"},
    {"year": 2026, "month": 9, "owner_ref": "0" * 48}, [("year", "2026"), ("year", "2027"), ("month", "9")]])
def test_month_rejects_unknown_owner_and_bad_query(calendar_api, query):
    response = calendar_api.client.get(BASE + "/month", query_string=query)
    assert response.status_code in (400, 422) and response.get_json()["error"]["code"] == "invalid_input"


@pytest.mark.parametrize("input", [{"date": "2026-09-09T00:00:00Z"}, {"date": "2026-02-30"},
    {"date": NIGHT, "owner_ref": "0" * 48}, {"date": NIGHT, "fields": {"shift_start": "12:00"}},
    {"date": NIGHT, "fields": {"hours": True}}, {"date": NIGHT, "fields": {"eff": 0}},
    {"date": NIGHT, "fields": {"hours": 25}}, {"date": NIGHT, "fields": {"eff": "100"}}])
def test_invalid_writes_are_rejected_without_mutation(calendar_api, input):
    body = calendar_api.day_body()
    before = calendar_api.state()
    assert_error(calendar_api.client.post(BASE + "/upsert", json={**body, "input": input}), "invalid_input", 422)
    assert calendar_api.state() == before


def test_missing_identity_and_read_failure_do_not_repair_or_maintain(calendar_api, monkeypatch):
    from core.services.system.system_maintenance_service import SystemMaintenanceService

    calls = []
    monkeypatch.setattr(SystemMaintenanceService, "run_if_due", lambda *args, **kwargs: calls.append("maintenance"))
    before = calendar_api.state()
    calendar_api.month()
    calendar_api.preview()
    assert calls == [] and calendar_api.state() == before
    with patch.object(WorkbenchCalendarService, "preview", side_effect=RuntimeError("private fixture error")):
        response = calendar_api.client.post(BASE + "/range/preview", json={"input": {"start_date": NIGHT, "end_date": NIGHT}})
        assert_error(response, "storage_failure", 500)
        assert "private fixture error" not in response.get_data(as_text=True)
    with calendar_api.db() as conn:
        conn.execute("DELETE FROM WorkbenchEntityRefs WHERE kind='calendar'")
    corrupt = calendar_api.state()
    assert_error(calendar_api.client.get(BASE + "/month", query_string={"year": 2026, "month": 9}), "constraint_conflict")
    assert calendar_api.state() == corrupt and calls == []


def test_configured_holiday_and_weekend_overtime_use_real_policy_counts(calendar_api):
    with calendar_api.db() as conn:
        service = CalendarService(conn)
        service.upsert("2024-02-10", shift_hours=4, efficiency=0.5, allow_normal="no", allow_urgent="yes")
        service.upsert("2024-02-12", day_type="holiday", shift_hours=0, efficiency=0.75, allow_normal="no", allow_urgent="no")
    data = calendar_api.month(2024, 2)["data"]
    assert data["stats"] == {"configured": 2, "configured_work_days": 1, "work_days": 21,
                              "rest_days": 8, "overrides": 2, "weekend_rest": 7, "effective_hours": 162}
    holiday = next(item for item in data["days"] if item["date"] == "2024-02-12")
    assert holiday["explicit"] and holiday["stored"]["day_type"] == "holiday" and holiday["fields"]["type"] == "rest"


def test_global_rest_does_not_reopen_shift_and_clear_does_not_remove_personal_exception(calendar_api):
    assert calendar_api.save({"type": "rest", "eff": 100}, "2026-09-10").status_code == 200
    body = calendar_api.day_body(action="delete")
    assert calendar_api.client.post(BASE + "/delete", json=body).status_code == 200
    with calendar_api.db() as conn:
        service = CalendarService(conn)
        rest = service.policy_for_datetime(datetime(2026, 9, 10, 22), operator_id="CAL-O")
        assert rest.shift_hours == 0 and not rest.is_priority_allowed("urgent")
        personal = service.policy_for_datetime(datetime(2026, 9, 10, 1), operator_id="CAL-O")
        assert personal.shift_hours == 8.5 and personal.efficiency == 0.625 and personal.date_str == NIGHT
    assert calendar_api.day()["entity"] is None


def test_modified_public_preview_cannot_change_retained_intent(calendar_api):
    preview = calendar_api.preview()
    expected = preview["dates"][:]
    preview["request"]["fields"]["eff"] = 25
    preview["dates"].clear()
    preview["days"][0]["after"]["fields"]["hours"] = 1
    preview["days"][0]["before"]["stored"] = {"shift_hours": 1}
    response, _ = calendar_api.confirm(preview)
    assert response.status_code == 200
    assert [item["date"] for item in response.get_json()["data"]["dates"]] == expected
    assert calendar_api.row(expected[0])["shift_hours"] == 8 and calendar_api.row(expected[0])["efficiency"] == 1


def test_empty_filtered_preview_and_clear_restore_domain_defaults(calendar_api):
    empty = calendar_api.preview(start_date="2026-12-28", end_date="2026-12-28", scope="weekend")
    assert empty["dates"] == [] and calendar_api.confirm(empty)[0].get_json()["result"] == "unchanged"
    assert calendar_api.confirm(calendar_api.preview())[0].status_code == 200
    deleted = calendar_api.preview(operation="delete", fields={})
    assert deleted["counts"]["configured_before"] == 7 and deleted["counts"]["configured_after"] == 0
    assert deleted["days"][-1]["after"]["effective"]["is_rest"]
    response, _ = calendar_api.confirm(deleted)
    assert response.status_code == 200 and len(response.get_json()["data"]["dates"]) == 7
    assert all(calendar_api.row(day) is None for day in deleted["dates"])


def test_filtered_range_keeps_unselected_changes_and_rejects_selected_aba(calendar_api):
    preview = calendar_api.preview(scope="weekday")
    assert calendar_api.save(WORK, "2027-01-02").status_code == 200
    assert calendar_api.confirm(preview)[0].status_code == 200
    assert calendar_api.row("2027-01-02") is not None
    preview = calendar_api.preview(start_date="2027-03-01", end_date="2027-03-02")
    assert calendar_api.save(WORK, "2027-03-02").status_code == 200
    assert calendar_api.client.post(BASE + "/delete", json=calendar_api.day_body("2027-03-02", action="delete")).status_code == 200
    before = calendar_api.state()
    assert_error(calendar_api.confirm(preview)[0], "snapshot_stale")
    assert calendar_api.state() == before


def test_restart_loses_pending_context_not_entity_identity_or_committed_receipt(calendar_api):
    body = calendar_api.day_body(fields={"note": "Saved before restart"})
    saved = calendar_api.client.post(BASE + "/upsert", json=body).get_json()
    pending = calendar_api.preview()
    identity = calendar_api.day()["entity"]["ref"]
    calendar_api.client.application.extensions.pop("aps_public_opaque_tokens")
    calendar_api.client.application.extensions.pop("workbench_calendar_previews_v1")
    assert_error(calendar_api.confirm(pending)[0], "snapshot_stale")
    assert calendar_api.day()["entity"]["ref"] == identity
    replay = calendar_api.client.post(BASE + "/upsert", json=body).get_json()
    assert replay == {**saved, "replayed": True}


def test_receipt_failure_rolls_back_single_day_and_unknown_after_commit_is_queryable(calendar_api):
    body = calendar_api.day_body(fields={"note": "Committed data"})
    before = calendar_api.state()
    with patch.object(WorkbenchCommandRepository, "insert", side_effect=RuntimeError("fixture receipt failure")):
        assert_error(calendar_api.client.post(BASE + "/upsert", json=body), "storage_failure", 500, "unknown")
    assert calendar_api.state() == before
    original = WorkbenchCommandService.execute

    def lose_response(self, **kwargs):
        original(self, **kwargs)
        raise RuntimeError("fixture transport loss after commit")

    with patch.object(WorkbenchCommandService, "execute", lose_response):
        error = assert_error(calendar_api.client.post(BASE + "/upsert", json=body), "storage_failure", 500, "unknown")
    result = calendar_api.client.get(error["error"]["result_target"]).get_json()
    assert result["result"] == "committed" and result["replayed"] and result["data"]["date"] == NIGHT
    assert calendar_api.row()["remark"] == "Committed data"


@pytest.mark.parametrize("operation", ["day", "range"])
def test_concurrent_duplicate_http_intents_have_one_receipt(calendar_api, operation):
    body = calendar_api.day_body(fields={"note": "Concurrent"}) if operation == "day" else calendar_api.confirm_body(calendar_api.preview())
    path = BASE + ("/upsert" if operation == "day" else "/range/confirm")
    start = Barrier(2)

    def send(_):
        with calendar_api.client.application.test_client() as client:
            start.wait(timeout=10)
            response = client.post(path, json=body)
            return response.status_code, response.get_json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, range(2)))
    assert [item[0] for item in results] == [200, 200], results
    assert results[0][1]["receipt_ref"] == results[1][1]["receipt_ref"]
    assert sorted(item[1]["replayed"] for item in results) == [False, True]
    with calendar_api.db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchCommandReceipts WHERE request_key=?", (body["request_key"],)).fetchone()[0] == 1


def test_live_preview_capacity_does_not_evict_older_intent(calendar_api, monkeypatch):
    from web.routes.workbench import calendars_preview

    monkeypatch.setattr(calendars_preview, "_MAX_PREVIEWS", 1)
    first = calendar_api.preview()
    before = calendar_api.state()
    response = calendar_api.client.post(BASE + "/range/preview", json={"input": {"start_date": NIGHT, "end_date": NIGHT, "fields": {}}})
    assert_error(response, "preview_capacity", 503)
    assert calendar_api.state() == before and calendar_api.confirm(first)[0].status_code == 200


@pytest.mark.parametrize("body", [None, [], {}, {"input": {}, "before": {}}, {"input": {}, "owner_ref": "0" * 48}])
def test_preview_rejects_extra_context_and_nonobject_envelope(calendar_api, body):
    before = calendar_api.state()
    response = calendar_api.client.post(BASE + "/range/preview", json=body)
    assert_error(response, "invalid_input", 400)
    assert calendar_api.state() == before


def test_real_get_connection_date_converter_keeps_iso_snapshot_and_identity(calendar_api):
    from core.infrastructure.database import get_connection
    from data.repositories.workbench_calendar_query_repo import WorkbenchCalendarQueryRepository

    conn = get_connection(calendar_api.client.application.config["DATABASE_PATH"])
    try:
        raw = conn.execute("SELECT date FROM WorkCalendar WHERE date=?", (NIGHT,)).fetchone()[0]
        assert type(raw) is date
        state = WorkbenchCalendarQueryRepository(conn).range_states(NIGHT, NIGHT)[NIGHT]
        assert state["row"]["date"] == state["identity"]["entity_key"] == NIGHT
        assert state["identity"]["ref"] == calendar_api.day()["calendar_ref"]
    finally:
        conn.close()


@pytest.mark.parametrize("value", [datetime(2026, 9, 9), datetime(2026, 9, 9, tzinfo=timezone.utc),
                                  "2026-09-09T00:00:00Z", "2026/09/09", "2026-02-30", None])
def test_repository_rejects_timestamp_instead_of_silently_extracting_date(schema_conn, value):
    from core.models.workbench_command import WorkbenchCommandRejected
    from data.repositories.workbench_calendar_query_repo import WorkbenchCalendarQueryRepository

    repo = WorkbenchCalendarQueryRepository(schema_conn)
    with patch.object(repo, "fetchall", return_value=[{"date": value}]):
        with pytest.raises(WorkbenchCommandRejected, match="日期无效"):
            repo.range_states(NIGHT, NIGHT)


@pytest.mark.parametrize("operation", ["day", "range"])
def test_short_token_validation_only_runs_under_command_write_transaction(calendar_api, operation):
    from flask import g

    from core.infrastructure.transaction import in_transaction_context
    from web.routes.workbench import calendars

    body = calendar_api.day_body(fields={"note": "Guarded"}) if operation == "day" else calendar_api.confirm_body(calendar_api.preview())
    original, seen = calendars.validate_write_context, []

    def guarded(*args):
        assert g.db.in_transaction and in_transaction_context(g.db)
        seen.append(args[2])
        return original(*args)

    path = BASE + ("/upsert" if operation == "day" else "/range/confirm")
    with patch.object(calendars, "validate_write_context", guarded):
        assert calendar_api.client.post(path, json=body).status_code == 200
    assert seen == ["calendar.upsert" if operation == "day" else "calendar.confirm"]
