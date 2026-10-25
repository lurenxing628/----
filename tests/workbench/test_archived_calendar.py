"""Saved identity, calendar versions and known/unknown day coverage contracts."""

from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

import pytest

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity.plan_calendar_engine import SnapshotCalendarEngine
from core.services.workbench.facts.archived_calendar import ArchivedCalendar
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.plan.occupancy import _resource_occupancy
from tests.workbench.run_candidate_support import candidate_case as _candidate_case  # noqa: F401

MACHINE, OPERATOR = "a" * 48, "b" * 48
RESOURCES = [{"kind": "machine", "ref": MACHINE, "saved_id": "M1"},
             {"kind": "operator", "ref": OPERATOR, "saved_id": "O1"}]


def archive(version=35):
    return {"tables": {"SchemaVersion": [{"id": 1, "version": version}],
        "WorkbenchEntityRefs": [{"kind": kind, "ref": ref, "entity_key": key, "active": 1}
                                for kind, ref, key in (("machine", MACHINE, "M1"), ("operator", OPERATOR, "O1"))],
        "Machines": [{"machine_id": "M1", "name": "保存的设备", "status": "active"}],
        "Operators": [{"operator_id": "O1", "name": "保存的人员", "status": "active"}],
        "WorkCalendar": [], "OperatorCalendar": [], "MachineDowntimes": [],
        "WorkbenchOperatorProfiles": [], "WorkbenchShiftProfiles": [], "WorkbenchShiftPatternDays": [],
        "WorkbenchShiftDayPeriods": [], "WorkbenchCalendarDefaults": []}}


def day(key, start="08:00", end: object = "16:00", *, hours: object = 8, efficiency: object = 1,
        normal="yes", urgent="yes", operator=None):
    row = {"date": key, "day_type": "workday", "shift_start": start, "shift_end": end,
           "shift_hours": hours, "efficiency": efficiency, "allow_normal": normal, "allow_urgent": urgent,
           "remark": None, "periods_json": None}
    if operator is not None:
        row["operator_id"] = operator
    return row


def project(saved, start="2026-10-12T00:00:00", end="2026-10-13T00:00:00", resources=RESOURCES, **kwargs):
    return dict(ArchivedCalendar(saved, source_ref="saved-calendar-ref", **kwargs).iter_resources(resources, start, end))


def test_saved_schema_defaults_keep_old_hours_and_modern_periods():
    legacy, modern = archive(33), archive(35)
    del legacy["tables"]["WorkbenchCalendarDefaults"]
    del legacy["tables"]["WorkbenchShiftDayPeriods"]
    old = project(legacy)[MACHINE]
    new = project(modern)[MACHINE]
    assert old["available_hours"] == 8
    assert [(row["start"], row["end"]) for row in old["windows"]] == [
        ("2026-10-12T08:00:00", "2026-10-12T16:00:00")]
    assert new["available_hours"] == pytest.approx(22 / 3, abs=1e-6)
    assert len(new["windows"]) == 2
    assert old["source"]["schema_version"] == 33 and new["source"]["schema_version"] == 35
    resources = project(modern)
    assert resources[OPERATOR]["windows"] == resources[MACHINE]["windows"]
    assert resources[OPERATOR]["basis"] == "personal_or_operator_shift_calendar"
    assert all(row["provenance"] == "domain_default" for row in resources[OPERATOR]["windows"])
    assert resources[MACHINE]["days"][0]["downtime_scope_hours"] == 0.0
    assert resources[MACHINE]["days"][0]["downtime_available_hours"] == 0.0
    modern["tables"]["WorkbenchCalendarDefaults"] = [{"singleton": 1, "periods_json":
        '[{"start":"09:00","end":"12:00","day_offset":0},{"start":"14:00","end":"18:00","day_offset":0}]'}]
    assert project(modern)[MACHINE]["available_hours"] == 7


def test_saved_v33_calendar_rows_without_periods_column_keep_their_single_shift():
    legacy = archive(33)
    del legacy["tables"]["WorkbenchCalendarDefaults"]
    del legacy["tables"]["WorkbenchShiftDayPeriods"]
    # v33 的日历表还没有 periods_json 列，真实归档行里根本没有这个键。
    legacy["tables"]["WorkCalendar"] = [
        {key: value for key, value in day("2026-10-12", "06:00", "10:00", hours=4).items() if key != "periods_json"}]
    legacy["tables"]["OperatorCalendar"] = [
        {key: value for key, value in day("2026-10-12", "09:00", "12:00", hours=3, operator="O1").items()
         if key != "periods_json"}]
    resources = project(legacy)
    assert resources[MACHINE]["available_hours"] == 4
    assert [(row["start"], row["end"]) for row in resources[MACHINE]["windows"]] == [
        ("2026-10-12T06:00:00", "2026-10-12T10:00:00")]
    assert resources[OPERATOR]["available_hours"] == 3
    assert [(row["start"], row["end"], row["provenance"]) for row in resources[OPERATOR]["windows"]] == [
        ("2026-10-12T09:00:00", "2026-10-12T12:00:00", "personal_calendar")]


def test_night_tail_priority_overlay_and_downtime_use_exact_half_open_window():
    saved = archive()
    saved["tables"]["WorkCalendar"] = [day("2026-10-12", "22:00", "06:00", efficiency=0.5),
                                        day("2026-10-13", "05:00", "05:30", hours=0.5, normal="no")]
    saved["tables"]["MachineDowntimes"] = [
        {"machine_id": "M1", "start_time": "2026-10-13T04:30:00", "end_time": "2026-10-13T05:15:00", "status": "active"},
        {"machine_id": "M1", "start_time": "2026-10-13T00:00:00", "end_time": "2026-10-14T00:00:00", "status": "cancelled"},
        {"machine_id": "M1", "start_time": "2026-10-14T00:00:00", "end_time": "2026-10-15T00:00:00", "status": "active"}]
    result = project(saved, "2026-10-13T04:00:00", "2026-10-13T06:00:00")[MACHINE]
    assert result["available_hours"] == 1.25
    assert result["effective_hours"] == 0.75
    assert result["normal_available_hours"] == 1 and result["urgent_available_hours"] == 1.25
    assert [(row["start"], row["end"]) for row in result["windows"]] == [
        ("2026-10-13T04:00:00", "2026-10-13T04:30:00"),
        ("2026-10-13T05:15:00", "2026-10-13T05:30:00"),
        ("2026-10-13T05:30:00", "2026-10-13T06:00:00")]
    saved["tables"]["MachineDowntimes"] = [
        {"machine_id": "M1", "start_time": "2026-10-14T01:00:00", "end_time": "2026-10-14T00:00:00", "status": "active"}]
    invalid = project(saved, "2026-10-13T04:00:00", "2026-10-13T06:00:00")[MACHINE]
    assert invalid["state"] == "unavailable" and invalid["issues"][0]["code"] == "downtime_invalid"


def test_machine_downtime_history_is_parsed_once_and_bad_states_keep_their_window(monkeypatch):
    from core.services.workbench.facts import archived_calendar

    saved = archive()
    old_start, old_end = "2020-01-01T08:00:00", "2020-01-01T09:00:00"
    saved["tables"]["MachineDowntimes"] = [
        {"machine_id": "M1", "start_time": old_start, "end_time": old_end, "status": "active"}
        for _ in range(100)] + [
        {"machine_id": "M1", "start_time": "bad-cancelled", "end_time": None, "status": "cancelled"},
        {"machine_id": "M1", "start_time": "2026-10-15T08:00:00", "end_time": "2026-10-15T09:00:00", "status": "unknown"}]
    parsed, original = [], archived_calendar.instant

    def instant(value):
        if value in (old_start, old_end):
            parsed.append(value)
        return original(value)

    monkeypatch.setattr(archived_calendar, "instant", instant)
    result = project(saved, "2026-10-12T00:00:00", "2026-10-16T00:00:00", resources=RESOURCES[:1])[MACHINE]
    assert len(parsed) == 200
    assert [row["state"] for row in result["days"]] == ["available", "available", "available", "unavailable"]
    assert result["days"][-1]["issues"][0]["code"] == "downtime_invalid"


def test_microsecond_calendar_and_occupancy_preserve_device_and_person_hours():
    saved = archive()
    saved["tables"]["WorkCalendar"] = [day("2026-10-12", efficiency=0.5)]
    start, pause, resume, end = ["2026-10-12T08:00:00." + str(value).zfill(6) for value in range(4)]
    saved["tables"]["MachineDowntimes"] = [
        {"machine_id": "M1", "start_time": pause, "end_time": resume, "status": "active"}]
    calendars = project(saved, start, end)
    unit = 1e-6 / 3600.0
    low, first, last, high = (datetime.fromisoformat(value) for value in (start, pause, resume, end))
    operations = {"one": [(low, high)], "two": [(first, last)]}
    refs = {"machine": {"M1": SimpleNamespace(ref=MACHINE)}, "operator": {"O1": SimpleNamespace(ref=OPERATOR)}}
    for kind, key, ref, duration in (("machine", "M1", MACHINE, 2), ("operator", "O1", OPERATOR, 3)):
        calendar = calendars[ref]
        for mode in ("", "normal_", "urgent_"):
            for measure, factor in (("available_hours", 1), ("effective_hours", 0.5)):
                field = mode + measure
                assert calendar[field] == calendar["days"][0][field]
                assert calendar[field] == pytest.approx(duration * unit * factor, rel=1e-12, abs=0)
        resource = _resource_occupancy(kind, key, operations, {**calendar, "label": kind}, refs, kind)
        assert resource["available_hours"] == calendar["available_hours"]
        expected = {"arranged_hours": 4 * unit, "occupied_hours": 3 * unit, "overlap_hours": unit,
                    "excess_arranged_hours": unit, "available_occupied_hours": duration * unit,
                    "outside_available_hours": (3 - duration) * unit,
                    "capacity_shortfall_hours": unit if kind == "operator" else 0,
                    "available_overlap_hours": unit if kind == "operator" else 0}
        for field, value in expected.items():
            assert resource[field] == pytest.approx(value, rel=1e-12, abs=0)
        assert resource["utilization"] == 1
        for field in ("downtime_scope_hours", "downtime_available_hours"):
            assert calendar["days"][0][field] == pytest.approx(unit if kind == "machine" else 0, rel=1e-12, abs=0)


def test_saved_personal_override_and_rotating_rest_keep_operator_capacity():
    saved = archive()
    tables = saved["tables"]
    tables["WorkbenchCalendarDefaults"] = [{"singleton": 1, "periods_json":
        '[{"start":"08:00","end":"16:00","day_offset":0}]'}]
    tables["WorkbenchOperatorProfiles"] = [{"operator_id": "O1", "shift_profile_id": "NIGHT"}]
    tables["WorkbenchShiftProfiles"] = [{"profile_id": "NIGHT", "anchor_date": "2026-10-12", "cycle_days": 2, "status": "active"}]
    tables["WorkbenchShiftPatternDays"] = [
        {"profile_id": "NIGHT", "day_offset": 0, "is_rest": 0, "shift_start": "22:00", "shift_end": "06:00"},
        {"profile_id": "NIGHT", "day_offset": 1, "is_rest": 1, "shift_start": "22:00", "shift_end": "06:00"}]
    tail = project(saved, "2026-10-13T00:00:00", "2026-10-13T06:00:00")[OPERATOR]
    assert tail["available_hours"] == 6 and tail["windows"][0]["provenance"] == "domain_default_operator_shift"
    rest = project(saved, "2026-10-13T08:00:00", "2026-10-13T16:00:00")[OPERATOR]
    assert rest["state"] == "available" and rest["windows"] == [] and rest["available_hours"] == 0
    tables["OperatorCalendar"] = [day("2026-10-13", "09:00", "12:00", hours=3, efficiency=0.25, normal="no", operator="O1")]
    tables["WorkbenchShiftProfiles"][0]["status"] = "inactive"
    personal = project(saved, "2026-10-13T09:00:00", "2026-10-13T12:00:00")[OPERATOR]
    assert personal["state"] == "available" and personal["available_hours"] == 3
    assert personal["effective_hours"] == 0.75 and personal["normal_available_hours"] == 0
    assert personal["windows"][0]["provenance"] == "personal_calendar"
    tables["WorkbenchOperatorProfiles"] = []
    tables["OperatorCalendar"] = [day("2026-10-12", "22:00", "06:00", operator="O1")]
    personal_tail = project(saved, "2026-10-13T00:00:00", "2026-10-13T06:00:00")[OPERATOR]
    assert personal_tail["available_hours"] == 6
    assert personal_tail["windows"][0]["provenance"] == "personal_calendar"
    tables["OperatorCalendar"][0]["operator_id"] = None
    distinct = project(saved, "2026-10-13T00:00:00", "2026-10-13T06:00:00")
    assert distinct[MACHINE]["available_hours"] == 6 and distinct[OPERATOR]["available_hours"] == 0


def test_broken_policy_days_keep_other_days_known_and_defaults_are_lazy():
    saved = archive()
    saved["tables"]["WorkCalendar"] = [day("2026-10-13", end=None, hours=None)]
    result = project(saved, "2026-10-12T00:00:00", "2026-10-16T00:00:00")[MACHINE]
    assert result["state"] == "partial" and result["available_hours"] is None and result["windows"] is None
    assert [row["state"] for row in result["days"]] == ["available", "unavailable", "unavailable", "available"]
    assert (result["known_days"], result["unknown_days"]) == (2, 2)
    assert result["known_windows"]
    saved["tables"]["WorkbenchCalendarDefaults"] = [{"singleton": 1, "periods_json": "null"}]
    saved["tables"]["WorkCalendar"] = [day("2026-10-14", end=None, hours=0), day("2026-10-15")]
    explicit = project(saved, "2026-10-15T08:00:00", "2026-10-15T16:00:00")[MACHINE]
    assert explicit["state"] == "available" and explicit["available_hours"] == 8
    implicit = project(saved, "2026-10-16T08:00:00", "2026-10-16T16:00:00")[MACHINE]
    assert implicit["state"] == "unavailable" and implicit["available_hours"] is None

    engine = SnapshotCalendarEngine({
        "global": [day("2026-10-14", end=None, hours=0), day("2026-10-15")],
        "personal": [],
        "profiles": [],
        "patterns": [],
        "defaults": [{"singleton": 1, "periods_json": "null"}],
    })
    assert engine.working_hours_between(
        datetime(2026, 10, 15, 8, 0),
        datetime(2026, 10, 15, 16, 0),
    ) == 8.0
    with pytest.raises(ValidationError):
        engine.working_hours_between(
            datetime(2026, 10, 16, 8, 0),
            datetime(2026, 10, 16, 16, 0),
        )


@pytest.mark.parametrize("table,rows", [
    ("WorkbenchOperatorProfiles", [{"shift_profile_id": "P1"}]),  # 缺列
    ("WorkbenchShiftPatternDays", [{"profile_id": ["P1"], "day_offset": 0}]),  # 取值类型不对
])
def test_structurally_damaged_saved_calendar_table_makes_every_day_calendar_invalid(table, rows):
    saved = archive()
    saved["tables"][table] = rows
    factory = ArchivedCalendar(saved)
    assert factory.engine is None
    projected = dict(factory.iter_resources(RESOURCES, "2026-10-12T00:00:00", "2026-10-13T00:00:00"))
    for ref in (MACHINE, OPERATOR):
        assert projected[ref]["state"] == "unavailable" and projected[ref]["available_hours"] is None
        assert [item["code"] for item in projected[ref]["issues"]] == ["calendar_invalid"]


def test_deleted_or_replaced_identity_stays_unknown_while_true_zero_stays_zero():
    saved = archive()
    original = deepcopy(saved)
    saved["tables"]["WorkbenchEntityRefs"][0]["ref"] = "c" * 48
    replaced = project(saved)[MACHINE]
    assert replaced["state"] == "unavailable" and replaced["available_hours"] is None
    assert replaced["issues"][0]["missing_fact"] == "WorkbenchEntityRefs.machine"
    unavailable = project(original, resources=[{"kind": "machine", "ref": "d" * 48, "saved_id": None}])["d" * 48]
    assert unavailable["available_hours"] is None
    zero = project(original, "2026-10-17T00:00:00", "2026-10-18T00:00:00")[MACHINE]
    assert zero["state"] == "available" and zero["windows"] == [] and zero["available_hours"] == 0
    original["tables"]["Machines"][0]["status"] = "inactive"
    inactive = project(original)
    assert inactive[MACHINE]["available_hours"] == 0 and inactive[MACHINE]["windows"] == []
    assert inactive[OPERATOR]["available_hours"] == pytest.approx(22 / 3, abs=1e-6)
    original["tables"]["Machines"][0]["status"] = "maintain"
    maintain = project(original)
    assert maintain[MACHINE]["available_hours"] == 0 and maintain[MACHINE]["windows"] == []
    assert maintain[OPERATOR]["available_hours"] == inactive[OPERATOR]["available_hours"]
    del original["tables"]["OperatorCalendar"]
    missing = project(original)[OPERATOR]
    assert missing["state"] == "unavailable" and missing["available_hours"] is None
    assert missing["issues"][0]["missing_fact"] == "OperatorCalendar"
    missing_profile = archive()
    del missing_profile["tables"]["WorkbenchOperatorProfiles"]
    missing = project(missing_profile)[OPERATOR]
    assert missing["state"] == "unavailable" and missing["issues"][0]["missing_fact"] == "WorkbenchOperatorProfiles"


def test_declared_bounded_coverage_is_not_extended_with_implicit_defaults():
    saved = archive()
    result = project(saved, "2026-10-12T00:00:00", "2026-10-15T00:00:00",
                     coverage={"start": "2026-10-12T00:00:00", "end": "2026-10-14T00:00:00"})[MACHINE]
    assert [row["state"] for row in result["days"]] == ["available", "available", "unavailable"]
    assert result["days"][-1]["end"] == "2026-10-15T00:00:00"
    assert result["days"][-1]["issues"][0]["missing_fact"] == "calendar_coverage"
    with pytest.raises(WorkbenchCommandRejected) as exc:
        project(saved, "2020-01-01T00:00:00", "2031-01-01T00:00:00")
    assert exc.value.status == 422


def test_real_run_table_archive_and_trial_dictionary_archive_never_read_live_calendars(candidate_case):
    case = candidate_case
    saved = ProductionFactsCapture(case.conn).archive()
    resources = [{"kind": kind, "ref": case.ref(kind, key), "saved_id": key}
                 for kind, key in (("machine", "M1"), ("operator", "O1"))]
    case.conn.execute("UPDATE Machines SET status='inactive' WHERE machine_id='M1'")
    case.conn.execute("UPDATE WorkbenchCalendarDefaults SET periods_json=?",
                      ('[{"start":"09:00","end":"12:00","day_offset":0}]',))
    case.conn.commit()
    case.conn.execute("BEGIN")
    current_snapshot = ProductionFactsCapture(case.conn).archive()
    statements = []
    case.conn.set_trace_callback(statements.append)
    try:
        factory = ArchivedCalendar(saved)
        run = dict(factory.iter_resources(resources, "2026-10-12T08:00:00", "2026-10-12T16:00:00"))
        trial = dict(ArchivedCalendar({"tables": factory._tables}).iter_resources(
            resources, "2026-10-12T08:00:00", "2026-10-12T16:00:00"))
        current = dict(ArchivedCalendar(current_snapshot, metadata_basis="current_transaction_snapshot").iter_resources(
            resources, "2026-10-12T08:00:00", "2026-10-12T16:00:00"))
    finally:
        case.conn.set_trace_callback(None)
        case.conn.rollback()
    assert statements == []
    assert run == trial
    assert all(row["available_hours"] == 8 for row in run.values())
    assert all(row["source"]["metadata_basis"] == "saved_archive" for row in run.values())
    assert current[resources[0]["ref"]]["available_hours"] == 0
    assert current[resources[1]["ref"]]["available_hours"] == 3
    assert all(row["source"]["metadata_basis"] == "current_transaction_snapshot" for row in current.values())


def test_streaming_releases_person_groups_and_derived_facts_keeps_shared_shift(monkeypatch):
    saved = archive()
    tables = saved["tables"]
    second_ref = "c" * 48
    tables["WorkbenchEntityRefs"].append({"kind": "operator", "ref": second_ref, "entity_key": "O2", "active": 1})
    tables["Operators"].append({"operator_id": "O2", "name": "乙", "status": "active"})
    tables["WorkbenchOperatorProfiles"] = [{"operator_id": who, "shift_profile_id": "S"} for who in ("O1", "O2")]
    tables["WorkbenchShiftProfiles"] = [{"profile_id": "S", "anchor_date": "2026-10-12", "cycle_days": 1, "status": "active"}]
    tables["WorkbenchShiftPatternDays"] = [{"profile_id": "S", "day_offset": 0, "is_rest": 0,
                                           "shift_start": "09:00", "shift_end": "17:00"}]
    factory = ArchivedCalendar(saved)
    engine = factory.engine
    assert engine is not None
    global_key = "2026-10-12"
    global_policy = engine._policy_for_date(global_key)
    reads, pattern = [], engine.operator_shift_calendar.repo.pattern_day
    monkeypatch.setattr(engine.operator_shift_calendar.repo, "pattern_day", lambda *args: (reads.append(args), pattern(*args))[1])
    stream = factory.iter_resources([RESOURCES[1], {"kind": "operator", "ref": second_ref, "saved_id": "O2"}],
                                    "2026-10-12T08:00:00", "2026-10-14T17:00:00")
    _, first = next(stream)
    assert first["state"] == "available" and "O1" in engine._policy_operator_keys
    engine.working_hours_between(datetime.fromisoformat("2026-10-12T08:00:00"),
                                 datetime.fromisoformat("2026-10-13T17:00:00"), operator_id="O1")
    _, second = next(stream)
    assert second["available_hours"] == first["available_hours"]
    assert "O1" not in engine._policy_operator_keys and "O1" not in engine._segment_cache
    assert "O1" not in engine.operator_shift_calendar._profiles
    assert all(key[0] != "O1" for key in engine._policy_cache)
    assert all(key[0] != "O1" for key in engine._working_hours_prefix)
    assert "O2" not in engine._policy_operator_keys and len(factory._shift_days) == 3
    assert engine._public_calendar_rows and len(reads) == 1
    assert engine.operator_shift_calendar._patterns
    assert list(stream) == []
    assert not engine._policy_operator_keys
    assert not engine._policy_cache
    assert engine._public_policy_cache[global_key] is global_policy
    engine.clear_policy_cache()
    assert engine._policy_for_date("2026-10-12", "O1").shift_hours == pytest.approx(22 / 3)
