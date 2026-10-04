"""Full saved snapshot, real revalidation, original identity and no scope fallback."""

import pytest

from core.services.workbench.trial.adoption_validation import validate_trial_adoption
from tests.workbench.trial_adoption_support import preview, saved_scenario, service
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import candidate, snapshot


@pytest.mark.parametrize("base", ["official", "candidate"])
def test_saved_arrangement_not_current_candidate_or_official(trial_case, base):
    case = trial_case
    saved = saved_scenario(case, candidate(case) if base == "candidate" else None)
    before = snapshot(case.conn)
    evidence = validate_trial_adoption(case.conn, saved["scenario_ref"])
    row = evidence.payload.schedule_rows[0]
    assert row.machine_id == "M2" and row.operator_id == "O2"
    assert row.start_time.isoformat() == saved["tasks"][0]["start"]
    assert evidence.scenario_ref == saved["scenario_ref"] and evidence.draft_ref == saved["draft_ref"]
    assert not hasattr(evidence, "candidate_ref")
    assert preview(case, saved)
    assert snapshot(case.conn) == before


@pytest.mark.parametrize("sql", [
    "UPDATE Machines SET status='maintenance' WHERE machine_id='M2'",
    "DELETE FROM OperatorMachine WHERE operator_id='O2'",
    "UPDATE BatchOperations SET unit_hours=2",
    "UPDATE Schedule SET lock_status='locked'",
    "INSERT INTO OperatorCalendar(operator_id,date,day_type,shift_start,shift_hours,efficiency,allow_normal,allow_urgent) "
    "VALUES ('O2','2026-09-09','workday','08:00',8,0.5,'yes','yes')",
])
def test_production_drift_blocks_without_mutation(trial_case, sql):
    case = trial_case
    saved = saved_scenario(case)
    case.conn.execute(sql)
    case.conn.commit()
    before = snapshot(case.conn)
    result = service(case.conn).preview(saved["scenario_ref"])
    assert result["validation"]["can_adopt"] is False
    assert result["write_context"]["write_token"] is None
    assert snapshot(case.conn) == before


def test_missing_batch_operations_not_filled_from_current_plan(trial_case):
    case = trial_case
    case.operation(seq=2)
    case.conn.commit()
    saved = saved_scenario(case)
    result = service(case.conn).preview(saved["scenario_ref"])
    assert result["validation"]["can_adopt"] is False
    assert result["validation"]["issues"][0]["code"] == "scenario_scope_incomplete"


def test_disabled_preview_does_not_issue_token(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    result = service(case.conn, False).preview(saved["scenario_ref"])
    assert result["validation"]["can_adopt"] is False and result["write_context"]["write_token"] is None


def test_complete_single_piece_scope_has_read_only_adoption_evidence(trial_case):
    case = trial_case
    case.conn.execute("UPDATE Batches SET quantity=1")
    case.conn.execute("UPDATE BatchOperations SET piece_id='single-piece'")
    case.conn.commit()
    case.plan(1, [case.op_id], end="2026-09-09T09:00:00")
    saved = saved_scenario(case, {"base": {"plan_ref": case.plan_ref(1)}}, changed=False)
    before = snapshot(case.conn)
    result = service(case.conn).preview(saved["scenario_ref"])
    assert result["validation"]["can_adopt"] is True, result
    assert result["validation"]["issues"] == []
    assert snapshot(case.conn) == before


def test_frozen_arrangement_is_kept_like_a_lock_in_trial_and_adoption(trial_case):
    # 不重排时段（来源排产没记录时按交付设置的「锁定近期排程」推算）：试调和正式采用同一口径——时段里的工序不能改，不改动的试调可以采用。
    from core.models.workbench_command import WorkbenchCommandRejected
    from tests.workbench.trial_support import change, create
    from tests.workbench.trial_support import service as draft_service

    case = trial_case
    case.batch("B2")
    other = case.operation(batch="B2", setup_hours=0, unit_hours=1)
    case.plan(1, [case.op_id, other], start="2026-09-09T08:00:00", end="2026-09-09T11:00:00")
    case.conn.execute("UPDATE Schedule SET start_time='2026-09-14T08:00:00',end_time='2026-09-14T11:00:00' WHERE op_id=?", (other,))
    case.conn.commit()
    case.config(freeze_window_enabled="yes", freeze_window_days=3)
    draft = create(case, {"base": {"plan_ref": case.plan_ref(1)}})
    frozen, free = (next(index for index, task in enumerate(draft["tasks"]) if task["batch_id"] == batch) for batch in ("B1", "B2"))
    task = draft["tasks"][frozen]
    assert task["locked"] is True and task["edit_context"]["can_change"] is False
    assert [item["code"] for item in task["edit_context"]["blocked_reasons"]] == ["task_frozen"]
    assert draft["tasks"][free]["edit_context"]["can_change"] is True
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        change(case, draft, task=frozen)
    assert error.value.code == "task_frozen" and "来源排产的不重排时段（2026-09-09 00:00 至 2026-09-12 00:00）要保持原安排" in str(error.value)
    assert "解锁" not in str(error.value) and snapshot(case.conn) == before
    changed = change(case, draft, task=free, start="2026-09-14T13:00:00", key="frozen-trial-change-0002")["data"]
    assert changed["validation"]["issues"] == []
    saved = draft_service(case.conn).save(changed["draft_ref"], {"name": "Frozen kept"},
        changed["write_context"]["write_token"], "frozen-trial-save-0001")["data"]
    assert preview(case, saved)


def test_frozen_arrangement_differs_is_explained_before_adoption(trial_case):
    # 候选把时段里的工序排在别处：试调核对就指出不重排时段，采用预检给同一提示，不再让人“重新预检”。
    from core.services.workbench.run.worker import WorkbenchRunWorker
    from tests.workbench.trial_support import official

    case = trial_case
    official(case, start="2026-09-10T08:00:00", end="2026-09-10T11:00:00")
    run = WorkbenchRunWorker(case.conn).execute(case.accept(settings=case.settings(start_date="2026-09-09"))["run_ref"])
    case.config(freeze_window_enabled="yes", freeze_window_days=3)
    saved = saved_scenario(case, {"base": {"candidate_ref": run["candidates"][0]["candidate_ref"]}}, changed=False)
    assert saved["tasks"][0]["start"].startswith("2026-09-09")
    assert [item["code"] for item in saved["validation"]["issues"]] == ["frozen_arrangement_changed"]
    checked = service(case.conn).preview(saved["scenario_ref"])
    assert checked["validation"]["can_adopt"] is False
    assert [item["code"] for item in checked["validation"]["issues"]] == ["frozen_arrangement_changed"]
    assert "不重排时段" in checked["validation"]["issues"][0]["message"]


def test_trial_follows_the_hold_window_recorded_on_its_source_plan(trial_case):
    """正式计划记下了来源排产的不重排时段：试调按它判断哪些工序不能改，不再按交付设置的天数推算。"""
    import json

    from tests.workbench.trial_support import create

    case = trial_case
    case.batch("B2")
    other = case.operation(batch="B2", setup_hours=0, unit_hours=1)
    case.plan(1, [case.op_id, other], start="2026-09-09T08:00:00", end="2026-09-09T11:00:00")
    case.conn.execute("UPDATE Schedule SET start_time='2026-09-14T08:00:00',end_time='2026-09-14T11:00:00' WHERE op_id=?", (other,))
    policy = {"ready_check": True, "material_strategy": "strict", "start_date": "2026-09-09", "end_date": "2026-09-20",
              "hold_window": {"start": "2026-09-14T00:00", "end": "2026-09-15T00:00"}}
    case.conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=1", (json.dumps({"material_policy": policy}),))
    case.conn.commit()
    case.config(freeze_window_enabled="yes", freeze_window_days=3)
    draft = create(case, {"base": {"plan_ref": case.plan_ref(1)}})
    tasks = {task["batch_id"]: task for task in draft["tasks"]}
    assert tasks["B1"]["edit_context"]["can_change"] is True
    assert tasks["B2"]["edit_context"]["can_change"] is False
    reason = tasks["B2"]["edit_context"]["blocked_reasons"][0]
    assert reason["code"] == "task_frozen" and "不重排时段（2026-09-14 00:00 至 2026-09-15 00:00）" in reason["message"]


def test_trial_counts_the_hold_window_from_its_source_run_start_date(trial_case):
    """来源排产从 09-10 起排、没记时段（按交付设置 1 天）：试调也从 09-10 推算 [09-10, 09-11)，
    不随试调里最早那道工序（09-09）挪到前一天，否则保留的工序和来源排产对不上。"""
    import json

    from tests.workbench.trial_support import create

    case = trial_case
    case.batch("B2")
    other = case.operation(batch="B2", setup_hours=0, unit_hours=1)
    case.plan(1, [case.op_id, other], start="2026-09-09T08:00:00", end="2026-09-09T11:00:00")
    case.conn.execute("UPDATE Schedule SET start_time='2026-09-10T08:00:00',end_time='2026-09-10T11:00:00' WHERE op_id=?", (other,))
    policy = {"ready_check": True, "material_strategy": "strict", "start_date": "2026-09-10", "end_date": "2026-09-20"}
    case.conn.execute("UPDATE ScheduleHistory SET result_summary=? WHERE version=1", (json.dumps({"material_policy": policy}),))
    case.conn.commit()
    case.config(freeze_window_enabled="yes", freeze_window_days=1)
    draft = create(case, {"base": {"plan_ref": case.plan_ref(1)}})
    tasks = {task["batch_id"]: task for task in draft["tasks"]}
    assert tasks["B1"]["edit_context"]["can_change"] is True
    reason = tasks["B2"]["edit_context"]["blocked_reasons"][0]
    assert reason["code"] == "task_frozen" and "不重排时段（2026-09-10 00:00 至 2026-09-11 00:00）" in reason["message"]


def test_window_held_work_in_a_candidate_trial_is_explained_by_its_window(trial_case):
    """候选方案行把因不重排时段保留的工序记作 locked；正式计划里它没锁，试调要说是哪个时段、怎么改，不说"固定工序"。"""
    from core.services.workbench.run.worker import WorkbenchRunWorker
    from tests.workbench.trial_support import create

    case = trial_case
    case.batch("B2")
    other = case.operation(batch="B2", setup_hours=0, unit_hours=1)
    case.plan(1, [case.op_id, other], start="2026-09-09T08:00:00", end="2026-09-09T11:00:00")
    case.conn.execute("UPDATE Schedule SET start_time='2026-09-14T08:00:00',end_time='2026-09-14T11:00:00' WHERE op_id=?", (other,))
    case.conn.commit()
    window = {"start": "2026-09-09T08:00", "end": "2026-09-09T09:00"}
    run = WorkbenchRunWorker(case.conn).execute(case.accept(settings=case.settings("B1", "B2", hold_window=window))["run_ref"])
    draft = create(case, {"base": {"candidate_ref": run["candidates"][0]["candidate_ref"]}})
    task = next(task for task in draft["tasks"] if task["batch_id"] == "B1")
    assert task["locked"] is True and task["edit_context"]["can_change"] is False
    reason = task["edit_context"]["blocked_reasons"][0]
    assert reason["code"] == "task_frozen" and "不重排时段（2026-09-09 08:00 至 2026-09-09 09:00）" in reason["message"]


def test_held_arrangement_that_no_longer_fits_says_why_it_cannot_be_moved(trial_case):
    """时段里的原安排按现在的工时已对不上：试调照常指出，并说明这道为什么改不了、该怎么办，
    不再放到正式采用时才拦下、只让人“重新预检”。"""
    from tests.workbench.trial_support import create

    case = trial_case
    case.batch("B2")
    other = case.operation(batch="B2", setup_hours=0, unit_hours=1)
    case.plan(1, [case.op_id, other], start="2026-09-09T08:00:00", end="2026-09-09T11:00:00")
    case.conn.execute("UPDATE Schedule SET start_time='2026-09-14T08:00:00',end_time='2026-09-14T11:00:00' WHERE op_id=?", (other,))
    case.conn.execute("UPDATE BatchOperations SET setup_hours=setup_hours+1 WHERE id=?", (case.op_id,))
    case.conn.commit()
    case.config(freeze_window_enabled="yes", freeze_window_days=3)
    draft = create(case, {"base": {"plan_ref": case.plan_ref(1)}})
    found = [item for item in draft["validation"]["issues"] if item["code"] == "calendar_duration_conflict"]
    assert len(found) == 1 and "要保持原安排，试调不能改，正式采用会被拦下" in found[0]["message"]
    assert "把不重排时段改短或不设" in found[0]["message"]
