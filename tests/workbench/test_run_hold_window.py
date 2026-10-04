"""不重排时段：排产检查里可见、精确到分，替代工作台看不到的「锁定近期排程」。"""

import json

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_preflight import normalize_preflight_input
from core.services.workbench.run.history_projection import scope_summary
from core.services.workbench.run.preflight import PreflightService
from core.services.workbench.run.worker import WorkbenchRunWorker
from core.services.workbench.trial.materials import plan_material_policy
from tests.workbench.run_candidate_adoption_support import INTENT, preview, service
from tests.workbench.run_candidate_adoption_support import candidate_case as _case  # noqa: F401
from tests.workbench.run_candidate_support import compute

# 三道工序在 M1/O1 上依次排在 2026-09-09：08:00-08:45、08:45-09:30、09:30-10:15。
WINDOW = {"start": "2026-09-09T09:00", "end": "2026-09-09T09:10"}


def plan_three(case):
    second, third = case.operation(seq=2), case.operation(seq=3)
    case.conn.commit()
    _run, refs = compute(case)
    service(case.conn).adopt(refs[0], preview(case, refs[0]), "hold-window-adopt-0001", INTENT)
    return {1: case.op_id, 2: second, 3: third}


def held(checked):
    return {row["sequence"]: (row["held"] or {}).get("basis") for row in checked["tasks"]}


@pytest.mark.parametrize("window", [
    {"start": "2026-09-09T09:00"}, {"start": "2026-09-09T09:00", "end": "2026-09-09T09:00"},
    {"start": "2026-09-09T09:00:00", "end": "2026-09-09T10:00:00"}, {"start": "2026-09-08T23:00", "end": "2026-09-09T10:00"},
    {"start": "2026-09-25T23:00", "end": "2026-09-26T00:01"}, {"start": "2026-09-09T25:00", "end": "2026-09-09T26:00"},
    {"start": 1, "end": 2}, "2026-09-09T09:00", []])
def test_window_must_be_minute_precise_ordered_and_inside_the_run_dates(candidate_case, window):
    with pytest.raises(WorkbenchCommandRejected) as error:
        normalize_preflight_input(candidate_case.settings(hold_window=window))
    assert error.value.code == "invalid_input" and "不重排时段" in str(error.value)


@pytest.mark.parametrize("window", [None, WINDOW, {"start": "2026-09-09T00:00", "end": "2026-09-26T00:00"}])
def test_null_and_in_range_windows_are_accepted(candidate_case, window):
    assert normalize_preflight_input(candidate_case.settings(hold_window=window))["hold_window"] == window


def test_window_keeps_overlapping_work_and_its_earlier_operations_only(candidate_case):
    """时段只碰到第 2 道：第 2 道按时段保留，同批第 1 道一起保留（否则会后道先做），第 3 道照常重排。"""
    case = candidate_case
    ops = plan_three(case)
    settings = case.settings(hold_window=WINDOW)
    checked, _ = PreflightService(case.conn).evaluate(settings)
    assert held(checked) == {1: "hold_window", 2: "hold_window", 3: None}
    assert checked["counts"]["held_tasks"] == checked["counts"]["hold_window_tasks"] == 2
    assert checked["effective_config"]["hold_window"] == WINDOW
    assert checked["effective_config"]["hold_window_source"] == "explicit"
    accepted = case.accept(key="hold-window-run-00000002", settings=settings)
    ref = WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])["candidates"][0]["candidate_ref"]
    tasks = {row["op_id"]: row for row in (json.loads(item[0]) for item in case.conn.execute(
        "SELECT payload_json FROM WorkbenchRunCandidateTasks WHERE candidate_ref=?", (ref,)))}
    assert [tasks[ops[seq]]["locked"] for seq in (1, 2, 3)] == [True, True, False]


def test_explicit_null_overrides_the_delivered_setting_and_no_key_follows_it(candidate_case):
    """交付设置开着「锁定近期排程」3 天：不带这个键按它推算并标"按交付设置"；本次填"不设"就全部重排。"""
    case = candidate_case
    plan_three(case)
    case.config(freeze_window_enabled="yes", freeze_window_days=3)
    default, _ = PreflightService(case.conn).evaluate(case.settings())
    assert default["effective_config"]["hold_window"] == {"start": "2026-09-09T00:00", "end": "2026-09-12T00:00"}
    assert default["effective_config"]["hold_window_source"] == "default"
    assert set(held(default).values()) == {"hold_window"}
    cleared, _ = PreflightService(case.conn).evaluate(case.settings(hold_window=None))
    assert cleared["effective_config"]["hold_window"] is None
    assert cleared["effective_config"]["hold_window_source"] == "explicit"
    assert set(held(cleared).values()) == {None} and cleared["counts"]["held_tasks"] == 0


def test_window_is_recorded_for_history_candidate_and_the_adopted_official_plan(candidate_case):
    """排产记录、方案详情回显本次时段；采用后正式计划记下它，从正式计划发起的试调按同一时段判断。"""
    case = candidate_case
    plan_three(case)
    settings = case.settings(hold_window=WINDOW)
    accepted = case.accept(key="hold-window-run-00000003", settings=settings)
    refs = [row["candidate_ref"] for row in WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])["candidates"]]
    assert scope_summary(json.dumps(normalize_preflight_input(settings)))["hold_window"] == WINDOW
    result = service(case.conn).adopt(refs[0], preview(case, refs[0]), "hold-window-adopt-0002", INTENT)
    version = result["data"]["official_plan"]["version"]
    assert plan_material_policy(case.conn, version)["hold_window"] == WINDOW


def test_old_records_without_the_key_and_broken_values_are_shown_as_gaps():
    old = scope_summary(json.dumps({"start_date": "2026-09-09", "end_date": "2026-09-10", "ready_check": True,
                                    "missing_resource_policy": "auto_assign", "completed_policy": "preserve_actuals",
                                    "batch_refs": ["a" * 48]}))
    assert "hold_window" not in old and old["data_gaps"] == []
    broken = scope_summary(json.dumps({"start_date": "2026-09-09", "end_date": "2026-09-10", "ready_check": True,
                                       "missing_resource_policy": "auto_assign", "completed_policy": "preserve_actuals",
                                       "batch_refs": ["a" * 48], "hold_window": {"start": "x", "end": "y"}}))
    assert broken["hold_window"] is None and [gap["field"] for gap in broken["data_gaps"]] == ["hold_window"]


def test_window_holds_only_that_run_and_is_not_turned_into_a_permanent_lock(candidate_case):
    """时段保留的工序采用后按未锁定落库：下次排产填"不设"就全部照常重排，不会因为上次保留过就一直放不开。"""
    case = candidate_case
    ops = plan_three(case)
    settings = case.settings(hold_window=WINDOW)
    accepted = case.accept(key="hold-window-run-00000004", settings=settings)
    refs = [row["candidate_ref"] for row in WorkbenchRunWorker(case.conn).execute(accepted["run_ref"])["candidates"]]
    result = service(case.conn).adopt(refs[0], preview(case, refs[0]), "hold-window-adopt-0004", INTENT)
    version = result["data"]["official_plan"]["version"]
    locks = dict(case.conn.execute("SELECT op_id,lock_status FROM Schedule WHERE version=?", (version,)).fetchall())
    assert [locks[ops[seq]] for seq in (1, 2, 3)] == ["unlocked"] * 3
    checked, _ = PreflightService(case.conn).evaluate(case.settings(hold_window=None))
    assert set(held(checked).values()) == {None}


def test_huge_delivered_days_hold_until_the_end_instead_of_failing(candidate_case):
    """交付设置的锁定天数大到越过 9999 年：按一直保留到最后推算，排产检查照常给出结果，不因日期溢出报错。"""
    case = candidate_case
    plan_three(case)
    case.config(freeze_window_enabled="yes", freeze_window_days=10 ** 7)
    checked, _ = PreflightService(case.conn).evaluate(case.settings())
    assert checked["effective_config"]["hold_window"] == {"start": "2026-09-09T00:00", "end": "9999-12-31T23:59"}
    assert set(held(checked).values()) == {"hold_window"}
