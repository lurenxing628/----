"""Selected-plan-only union occupancy, constraints, isolation and scale proof."""

import json
import random
from datetime import datetime, timedelta

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.capacity import plan_calendar_io
from core.services.capacity.plan_calendar_intervals import IntervalIndex, hours, intersection, segments, union
from core.services.workbench import plan_calendar
from core.services.workbench.plan_calendar import project_plan_calendar
from core.services.workbench.plan_occupancy import project_plan_occupancy
from tests.workbench.plan_calendar_support import codes, measured, plan_calendar_case, resource
from tests.workbench.plan_catalog_support import candidate, history, scenario


def test_overlap_is_segmented_and_never_normalized_as_utilization_over_one(calendar_case):
    calendar_case.task()
    _, occupancy, _, _ = calendar_case.project()
    machine = resource(occupancy)
    assert machine["arranged_hours"] == 10 and machine["occupied_hours"] == 8
    assert machine["overlap_hours"] == machine["excess_arranged_hours"] == 2
    assert machine["capacity_shortfall_hours"] == 2
    assert machine["has_overlap"] is True and machine["capacity_insufficient"] is True
    assert machine["utilization"] == 1
    assert [row["concurrent_operations"] for row in machine["segments"]] == [1, 2, 1]


def test_repeated_rows_and_fragments_of_same_operation_do_not_self_conflict(calendar_case):
    with calendar_case.selected() as args:
        original = dict(args["rows"][0])
        args["rows"] = [original, dict(original), dict(original, schedule_id=100, start_time="2026-09-09 10:00:00")]
        _, facts = project_plan_calendar(calendar_case.conn, **args)
        occupancy, _ = project_plan_occupancy(calendar_case.conn, calendar_facts=facts, **args)
        machine = resource(occupancy)
        assert machine["arranged_hours"] == machine["occupied_hours"] == 8
        assert machine["overlap_hours"] == 0 and machine["operation_count"] == 1


def test_half_open_bounds_and_arrangement_not_full_task_span(calendar_case):
    calendar_case.task("2026-09-09 16:00:00", "2026-09-09 18:00:00")
    _, occupancy, _, _ = calendar_case.project("2026-09-09T15:00:00", "2026-09-09T16:00:00")
    assert resource(occupancy)["arranged_hours"] == 1 and resource(occupancy)["has_overlap"] is False
    _, occupancy, _, _ = calendar_case.project("2026-09-09T16:00:00", "2026-09-09T17:00:00")
    assert resource(occupancy)["arranged_hours"] == 1
    assert resource(occupancy)["available_hours"] == 0
    assert resource(occupancy)["outside_available_hours"] == 1


def test_personal_leave_zero_capacity_and_downtime_are_separate(calendar_case):
    calendar_case.calendar(hours=0, operator="PRIVATE-O1", normal="no", urgent="no")
    calendar_case.downtime("2026-09-09 10:00:00", "2026-09-09 12:00:00")
    _, occupancy, _, _ = calendar_case.project()
    assert resource(occupancy)["available_hours"] == 6
    assert resource(occupancy)["outside_available_hours"] == 2
    person = resource(occupancy, "operator")
    assert person["available_hours"] == 0 and person["arranged_hours"] == 8
    assert person["utilization"] is None and person["capacity_insufficient"] is True


def test_external_cycles_never_become_internal_machine_hours(calendar_case):
    calendar_case.execute("UPDATE BatchOperations SET source='external'")
    calendar, occupancy, _, _ = calendar_case.project()
    assert calendar["resources"] == occupancy["resources"] == []
    assert occupancy["basis"] == "selected_plan_only" and occupancy["issues"] == []


@pytest.mark.parametrize("source", [None, "unknown", ""])
def test_unknown_source_is_explicit_not_assumed_internal_or_empty_success(calendar_case, source):
    calendar_case.execute("UPDATE BatchOperations SET source=?", (source,))
    _, occupancy, _, facts = calendar_case.project()
    assert occupancy["state"] == "unavailable" and occupancy["resources"] == []
    assert "assignment_source_unknown" in codes(occupancy["issues"])
    assert facts["unknown_source_operations"] == [calendar_case.op_id]


def test_no_resource_and_unknown_priority_are_not_defaulted(calendar_case):
    calendar_case.execute("UPDATE Schedule SET operator_id=NULL")
    calendar_case.execute("UPDATE Batches SET priority=NULL")
    _, occupancy, _, _ = calendar_case.project()
    assert len(occupancy["resources"]) == 1
    assert codes(occupancy["issues"]) >= {"assignment_resource_missing", "assignment_priority_unknown"}


@pytest.mark.parametrize("mutation,code", [
    ("DELETE FROM OperatorMachine", "assignment_not_authorized"),
    ("UPDATE Machines SET op_type_id='OTHER'", "assignment_work_type_mismatch"),
    ("UPDATE BatchOperations SET op_type_id=NULL", "assignment_work_type_unknown"),
    ("INSERT INTO WorkbenchOperatorProfiles(operator_id,skills_declared) VALUES ('PRIVATE-O1',1)", "assignment_not_qualified"),
    ("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('PRIVATE-O1','OTHER')", "assignment_not_qualified"),
])
def test_task_constraints_do_not_change_machine_capacity(calendar_case, mutation, code):
    calendar_case.execute(mutation)
    calendar, occupancy, _, _ = calendar_case.project()
    assert resource(calendar)["available_hours"] == resource(occupancy)["available_hours"] == 8
    assert code in codes(occupancy["issues"])


def test_one_operator_two_machines_has_person_conflict_without_machine_double_count(calendar_case):
    calendar_case.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('PRIVATE-M2','Machine two','INT')")
    calendar_case.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('PRIVATE-O1','PRIVATE-M2')")
    calendar_case.task(machine="PRIVATE-M2")
    _, occupancy, _, _ = calendar_case.project()
    assert resource(occupancy, "operator")["overlap_hours"] == 2
    assert all(not row["has_overlap"] for row in occupancy["resources"] if row["kind"] == "machine")


def test_version_candidate_and_scenario_are_not_mixed_with_official_occupancy(calendar_case):
    conn, op_id = calendar_case.conn, calendar_case.op_id
    history(conn, 2, op_id=op_id)
    adopted_id = candidate(conn, 1, "adopted", source="schedule")
    candidate_id = candidate(conn, 1, "critical_best", op_id=op_id)
    scenario(conn, "PRIVATE-SCENARIO", 1, op_id=op_id, candidate_id=adopted_id, candidate_key="adopted")
    conn.execute("UPDATE Schedule SET machine_id='PRIVATE-M1',operator_id='PRIVATE-O1' WHERE version=2")
    conn.execute("UPDATE ScheduleCandidateRows SET machine_id='PRIVATE-M1',operator_id='PRIVATE-O1',"
                 "start_time='2026-09-09 10:00:00',end_time='2026-09-09 12:00:00' WHERE candidate_id=?", (candidate_id,))
    conn.execute("UPDATE ScheduleAdjustmentScenarioRow SET machine_id='PRIVATE-M1',operator_id='PRIVATE-O1',"
                 "start_time='2026-09-09 13:00:00',end_time='2026-09-09 14:00:00'")
    conn.commit()
    for kwargs, expected in (({}, 8), ({"version": 2}, 1), ({"role": "critical_best"}, 2), ({"scenario_id": "PRIVATE-SCENARIO"}, 1)):
        _, occupancy, _, _ = calendar_case.project(**kwargs)
        assert resource(occupancy)["arranged_hours"] == expected
        assert resource(occupancy)["overlap_hours"] == 0


def test_caller_must_keep_entry_scope_calendar_and_rows_bound(calendar_case):
    with calendar_case.selected() as args:
        _, facts = project_plan_calendar(calendar_case.conn, **args)
        args["rows"] = [dict(args["rows"][0], end_time="2026-09-09 15:00:00")]
        with pytest.raises(WorkbenchCommandRejected, match="班表和安排"):
            project_plan_occupancy(calendar_case.conn, calendar_facts=facts, **args)
        args["rows"][0]["version"] = 2
        with pytest.raises(WorkbenchCommandRejected, match="不属于所选计划的这一版"):
            project_plan_calendar(calendar_case.conn, **args)
    with pytest.raises(RuntimeError, match="read transaction"):
        project_plan_calendar(calendar_case.conn, **args)


def test_conflicting_duplicates_are_rejected(calendar_case):
    with calendar_case.selected() as args:
        args["rows"] = [args["rows"][0], dict(args["rows"][0], end_time="2026-09-09 15:00:00")]
        with pytest.raises(WorkbenchCommandRejected, match="同一条安排"):
            project_plan_calendar(calendar_case.conn, **args)


def test_oversized_rows_rejected_even_if_duplicates(calendar_case):
    with calendar_case.selected() as args:
        args["rows"] = [args["rows"][0]] * 10001
        with pytest.raises(WorkbenchCommandRejected) as exc:
            project_plan_calendar(calendar_case.conn, **args)
        assert exc.value.code == "query_too_large"


@pytest.mark.parametrize("module,field", [(plan_calendar, "MAX_POLICY_CELLS"), (plan_calendar_io, "MAX_FACT_ROWS")])
def test_capacity_bound_keeps_known_arrangements_and_overlap(calendar_case, monkeypatch, module, field):
    calendar_case.task()
    monkeypatch.setattr(module, field, 1)
    calendar, occupancy, _, _ = calendar_case.project()
    assert calendar["state"] == "unavailable"
    machine = resource(occupancy)
    assert machine["arranged_hours"] == 10 and machine["overlap_hours"] == 2
    assert machine["label"] == "Machine one"
    assert machine["available_hours"] is None and machine["capacity_insufficient"] is None


def test_scale_10000_tasks_100_resource_pairs_is_batched_and_swept(calendar_case):
    conn = calendar_case.conn
    conn.executemany("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'INT')",
                     [("PRIVATE-M" + str(i), "Machine " + str(i)) for i in range(2, 101)])
    conn.executemany("INSERT INTO Operators(operator_id,name) VALUES (?,?)",
                     [("PRIVATE-O" + str(i), "Person " + str(i)) for i in range(2, 101)])
    conn.executemany("INSERT INTO OperatorMachine(machine_id,operator_id) VALUES (?,?)",
                     [("PRIVATE-M" + str(i), "PRIVATE-O" + str(i)) for i in range(2, 101)])
    conn.executemany("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name) VALUES (?,'CAT-B',?,'INT','Turning')",
                     [("SCALE-" + str(i), i) for i in range(2, 10001)])
    conn.executemany("INSERT INTO Schedule(version,op_id,start_time,end_time,machine_id,operator_id) "
                     "VALUES (1,?,'2026-09-09 08:00:00','2026-09-09 16:00:00',?,?)",
                     [(i, "PRIVATE-M" + str((i - 1) % 100 + 1), "PRIVATE-O" + str((i - 1) % 100 + 1)) for i in range(2, 10001)])
    conn.commit()
    with calendar_case.selected() as args:
        assert len(args["rows"]) == 10000
        with measured(conn) as stats:
            calendar, facts = project_plan_calendar(conn, **args)
            occupancy, _ = project_plan_occupancy(conn, calendar_facts=facts, **args)
    assert calendar["state"] == occupancy["state"] == "available"
    assert len(occupancy["resources"]) == 200
    assert len(stats["sql"]) <= 50 and stats["vm_steps"] < 1000000
    assert stats["seconds"] < 12
    assert all(row["arranged_hours"] == 800 and row["occupied_hours"] == 8 and row["utilization"] == 1
               and row["segments"][0]["concurrent_operations"] == 100 for row in occupancy["resources"])
    assert len(json.dumps(calendar)) + len(json.dumps(occupancy)) < 1024 * 1024
    print("plan-projection scale: tasks=10000 resources=200 sql={} vm_steps={} seconds={:.3f} policy_cells={}".format(
        len(stats["sql"]), stats["vm_steps"], stats["seconds"], facts["policy_cells"]))


def test_interval_union_sweep_and_prefix_intersection_match_independent_minute_oracle():
    rng, base = random.Random(38219), datetime(2026, 9, 9)
    for _ in range(100):
        spans = [sorted(rng.sample(range(121), 2)) for _ in range(30)]
        intervals = [(base + timedelta(minutes=start), base + timedelta(minutes=end)) for start, end in spans]
        minute_counts = [sum(start <= minute < end for start, end in spans) for minute in range(120)]
        assert hours(union(intervals)) == pytest.approx(sum(bool(count) for count in minute_counts) / 60)
        assert hours([(start, end) for start, end, count in segments(intervals) if count > 1]) == pytest.approx(
            sum(count > 1 for count in minute_counts) / 60)
        index = IntervalIndex(intervals)
        for start, end in ((0, 120), (20, 60), (60, 90), (119, 120)):
            low, high = base + timedelta(minutes=start), base + timedelta(minutes=end)
            expected = sum(bool(count) for count in minute_counts[start:end]) / 60
            assert index.hours_between(low, high) == pytest.approx(expected)
            assert hours(intersection(union(intervals), [(low, high)])) == pytest.approx(expected)


def test_sparse_year_span_keeps_full_range_without_per_day_sql(calendar_case):
    calendar_case.task("2027-09-09 08:00:00", "2027-09-09 09:00:00")
    with calendar_case.selected(None, None) as args:
        with measured(calendar_case.conn) as stats:
            calendar, facts = project_plan_calendar(calendar_case.conn, **args)
            occupancy, _ = project_plan_occupancy(calendar_case.conn, calendar_facts=facts, **args)
    assert calendar["state"] == "available"
    assert occupancy["time_scope"]["range_end"] == "2027-09-09T09:00:00"
    assert resource(occupancy)["arranged_hours"] == resource(occupancy)["occupied_hours"] == 9
    assert len(resource(occupancy)["segments"]) == 2
    assert len(stats["sql"]) <= 12 and stats["vm_steps"] < 10000
    assert stats["seconds"] < 3
    print("plan-projection sparse: days=366 tasks=2 sql={} seconds={:.3f}".format(len(stats["sql"]), stats["seconds"]))
