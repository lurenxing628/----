"""Regression tests for the trial rows' single read boundary: storage invariants reject, point proof is domain."""

import pytest

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_trial_codec import dump, load_object
from tests.workbench.plan_catalog_support import insert_schedule_rows
from tests.workbench.trial_support import create, official, service, trial_case

__all__ = ["trial_case"]


def _rewrite(case, draft_ref, row_ref, edit):
    # 编辑中草稿的 current_json 是真实可写的存储副本（original_json 与已保存方案由触发器锁定）。
    value = load_object(case.conn.execute(
        "SELECT current_json FROM WorkbenchTrialRows WHERE draft_ref=? AND row_ref=?", (draft_ref, row_ref)).fetchone()[0])
    edit(value)
    case.conn.execute("UPDATE WorkbenchTrialRows SET current_json=? WHERE draft_ref=? AND row_ref=?",
                      (dump(value), draft_ref, row_ref))
    case.conn.commit()


def _task(data, row_ref):
    (task,) = [row for row in data["tasks"] if row["row_ref"] == row_ref]
    return task, {item["code"] for item in data["validation"]["issues"]
                  if item.get("task_ref") == task["task_ref"] and item["severity"] == "blocker"}


def test_draft_point_row_is_a_point_event_only_while_its_point_basis_matches(trial_case):
    # 真实零工时点事件读出来是点事件；把它的设备人员改空，依据对不上：照常读出，不再标成点事件，由零工时规则拦下。
    case = trial_case
    point = case.operation(seq=2, setup_hours=0, unit_hours=0)
    intent = official(case)
    insert_schedule_rows(case.conn, 1, [{"op_id": point, "machine_id": "M1", "operator_id": "O1",
                                         "start_time": "2026-09-09T11:00:00", "end_time": "2026-09-09T11:00:00"}])
    case.conn.commit()
    draft = create(case, intent)
    (row_ref,) = [row["row_ref"] for row in draft["tasks"] if row["start"] == row["end"]]
    task, _ = _task(service(case.conn).get(draft["draft_ref"]), row_ref)
    assert (task["event_kind"], task["occupies_resources"]) == ("point", False)
    _rewrite(case, draft["draft_ref"], row_ref, lambda current: current.update(machine_id=None, machine_ref=None))
    task, blockers = _task(service(case.conn).get(draft["draft_ref"]), row_ref)
    assert "event_kind" not in task
    assert "resource_required" in blockers


def test_draft_zero_length_row_without_point_basis_is_blocked_as_a_duration_conflict(trial_case):
    # 正时长的安排被改成起止相同：没有零工时依据，是领域问题而不是存储损坏，照常读出并按工时不符拦下。
    case = trial_case
    draft = create(case)
    row_ref = draft["tasks"][0]["row_ref"]
    _rewrite(case, draft["draft_ref"], row_ref, lambda current: current.update(end=current["start"]))
    task, blockers = _task(service(case.conn).get(draft["draft_ref"]), row_ref)
    assert "event_kind" not in task
    assert "calendar_duration_conflict" in blockers


@pytest.mark.parametrize("field, value", [
    ("end", "2026-09-09T07:00:00"), ("start", None), ("start", 1), ("end", {}),
], ids=["ends_before_start", "start_null", "start_number", "end_object"])
def test_draft_row_times_breaking_the_storage_invariant_are_rejected_as_damaged_storage(trial_case, field, value):
    # 起止倒置或读不出（读不出的时间文本见 test_trial_lifecycle 的损坏结束时间用例）都违反存储不变量：
    # 不管坏成什么类型，都在唯一读边界按草稿存储损坏拒收，冻结与物料推导只用准入后的起止。
    case = trial_case
    draft = create(case)
    _rewrite(case, draft["draft_ref"], draft["tasks"][0]["row_ref"], lambda current: current.update({field: value}))
    with pytest.raises(WorkbenchCommandRejected) as caught:
        service(case.conn).get(draft["draft_ref"])
    assert (caught.value.code, caught.value.status) == ("trial_snapshot_invalid", 409)


_SAVED_ROW_DAMAGE = {
    # 键集不是保存时的那一套（载荷只有保存时的执行状态与保护判定）。
    "key_missing": lambda row, task: task.pop("locked"),
    "key_extra": lambda row, task: task.update(legacy_field=1),
    # 永久行指向的来源行不是本草稿的行。
    "source_row_foreign": lambda row, task: row.update(source_row_ref="f" * 48),
}


@pytest.mark.parametrize("damage", sorted(_SAVED_ROW_DAMAGE))
def test_damaged_saved_scenario_rows_are_rejected_by_reading_and_adopting_alike(trial_case, monkeypatch, damage):
    # 已保存方案的任务载荷是没有表 CHECK 的存储副本：查看和采用经同一处准入与绑定，坏成什么样都按试调存储损坏拒收。
    # 存档列由触发器锁定，这里在仓储读出处换成损坏的存储内容。
    from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
    from tests.workbench.trial_adoption_support import saved_scenario
    from tests.workbench.trial_adoption_support import service as adoption_service

    case = trial_case
    saved = saved_scenario(case)
    real_rows = WorkbenchTrialRepository.iter_scenario_rows

    def damaged_rows(repo_self, ref):
        for stored in real_rows(repo_self, ref):
            row, task = dict(stored), load_object(stored["payload_json"])
            _SAVED_ROW_DAMAGE[damage](row, task)
            yield dict(row, payload_json=dump(task))

    monkeypatch.setattr(WorkbenchTrialRepository, "iter_scenario_rows", damaged_rows)
    with pytest.raises(WorkbenchCommandRejected) as caught:
        service(case.conn).scenario(saved["scenario_ref"])
    assert (caught.value.code, caught.value.status) == ("trial_snapshot_invalid", 409)
    validation = adoption_service(case.conn).preview(saved["scenario_ref"])["validation"]
    assert validation["can_adopt"] is False
    assert [item["code"] for item in validation["issues"]] == ["trial_snapshot_invalid"]


@pytest.mark.parametrize("column", ["snapshot_json", "payload_json"])
def test_unreadable_saved_scenario_archive_blocks_adoption_as_damaged_trial_data(trial_case, monkeypatch, column):
    # 采用只把已保存方案自身的存档读不出来说成试调数据损坏（409 trial_snapshot_invalid，预检显示为不能采用）；
    # 活表读不出来照常 500，见 test_trial_adoption_api 的日历用例。
    from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
    from tests.workbench.trial_adoption_support import saved_scenario
    from tests.workbench.trial_adoption_support import service as adoption_service

    case = trial_case
    saved = saved_scenario(case)
    if column == "snapshot_json":
        real_header = WorkbenchTrialRepository.scenario_header
        monkeypatch.setattr(WorkbenchTrialRepository, "scenario_header",
                            lambda repo_self, ref: dict(real_header(repo_self, ref), snapshot_json="{"))
    else:
        real_rows = WorkbenchTrialRepository.iter_scenario_rows
        monkeypatch.setattr(WorkbenchTrialRepository, "iter_scenario_rows",
                            lambda repo_self, ref: [dict(row, payload_json="{") for row in real_rows(repo_self, ref)])
    validation = adoption_service(case.conn).preview(saved["scenario_ref"])["validation"]
    assert validation["can_adopt"] is False
    assert [item["code"] for item in validation["issues"]] == ["trial_snapshot_invalid"]
