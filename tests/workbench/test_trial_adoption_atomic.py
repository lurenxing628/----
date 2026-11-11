"""Real SQLite rollback and concurrent same-key receipt replay for trial adoption."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from tests.workbench.trial_adoption_support import INTENT, KEY, full_plan, preview, saved_scenario, service
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import connect, snapshot


def test_receipt_insert_failure_rolls_back_trial_adoption(trial_case, monkeypatch):
    from core.services.scheduler.config import config_snapshot
    from core.services.scheduler.execution import execution_ledger_adapter

    case = trial_case
    value, _ = full_plan(case)
    case.conn.execute(
        'CREATE TRIGGER cq_failure BEFORE INSERT ON "WorkbenchCommandReceipts"'
        " WHEN NEW.action='trial.scenario.adopt'"
        " BEGIN SELECT RAISE(ABORT,'injected CQ failure'); END"
    )
    case.conn.commit()
    saved = saved_scenario(case, value, changed=False)
    token = preview(case, saved)
    before = snapshot(case.conn)
    reads = []
    for module, name in ((execution_ledger_adapter, "current_execution_plan"), (config_snapshot, "build_schedule_config_snapshot")):
        original = getattr(module, name)
        def read_once(*args, _original=original, _name=name, **kwargs):
            reads.append(_name)
            return _original(*args, **kwargs)
        monkeypatch.setattr(module, name, read_once)
    with pytest.raises(WorkbenchCommandUncertain):
        service(case.conn).adopt(saved["scenario_ref"], token, KEY, INTENT)
    assert sorted(reads) == ["build_schedule_config_snapshot", "current_execution_plan"]
    assert not case.conn.in_transaction and snapshot(case.conn) == before
    svc = service(case.conn)
    assert svc.commands.lookup(KEY, action=svc._action, context_ref=saved["scenario_ref"]) is None


def test_two_connections_concurrently_replay_one_trial_adoption(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    token = preview(case, saved)
    barrier = Barrier(2)

    def adopt():
        conn = connect(case.path)
        try:
            with case.app.app_context():
                barrier.wait(timeout=5)
                return service(conn).adopt(saved["scenario_ref"], token, KEY, INTENT)
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(adopt) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(item["replayed"] for item in results) == [False, True]
    assert len({item["receipt_ref"] for item in results}) == 1
    assert case.conn.execute("SELECT COUNT(*) FROM ScheduleHistory").fetchone()[0] == 2
    assert case.conn.execute("SELECT COUNT(*) FROM OperationLogs WHERE action='adopt_trial_scenario'").fetchone()[0] == 1


def test_all_frozen_scenario_with_live_violation_blocks_as_constraint_unproven(trial_case):
    case = trial_case
    case.config(freeze_window_enabled="yes", freeze_window_days=3)
    saved = saved_scenario(case, changed=False, suffix="frozen-01")
    clean_preview = service(case.conn).preview(saved["scenario_ref"])
    assert clean_preview["validation"]["can_adopt"] is False
    assert [row["code"] for row in clean_preview["write_context"]["blocked_reasons"]] == [
        "scenario_nothing_to_adopt"
    ]

    case.conn.execute("UPDATE Operators SET status='inactive' WHERE operator_id='O1'")
    case.conn.commit()
    frozen_invalid = saved_scenario(
        case, {"base": {"plan_ref": case.plan_ref(1)}}, changed=False, suffix="frozen-02"
    )
    violated_preview = service(case.conn).preview(frozen_invalid["scenario_ref"])
    assert violated_preview["validation"]["can_adopt"] is False
    blocked_codes = {row["code"] for row in violated_preview["write_context"]["blocked_reasons"]}
    assert blocked_codes == {"operator_missing", "operator_qualification_invalid"}
    assert all("不重排时段" in row["message"] for row in violated_preview["validation"]["issues"])

    with pytest.raises(WorkbenchCommandRejected) as rejected:
        service(case.conn).adopt(
            frozen_invalid["scenario_ref"], "unused-token", "trial-adopt-frozen-violation-01", INTENT
        )
    assert rejected.value.code == "scenario_constraint_unproven"
