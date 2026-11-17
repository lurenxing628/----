"""Real SQLite rollback and concurrent same-key receipt replay for trial adoption."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench.facts.candidate_facts import TABLE_KEYS
from core.shared.strict_json import canonical_json
from data.repositories.workbench_run_candidate_repo import WorkbenchRunCandidateRepository
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository
from tests.workbench.execution_ledger_support import publish_official_plan
from tests.workbench.trial_adoption_support import (
    BAD_RESOURCE_NAMES,
    INTENT,
    KEY,
    external_operation,
    full_plan,
    preview,
    saved_scenario,
    service,
)
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import candidate, connect, official, snapshot


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


def _external_plan(case):
    external = external_operation(case)
    publish_official_plan(case.conn, 1, [
        {"op_id": case.op_id, "machine_id": "M1", "operator_id": "O1",
         "start_time": "2026-09-09T08:00:00", "end_time": "2026-09-09T11:00:00"},
        {"op_id": external, "machine_id": None, "operator_id": None,
         "start_time": "2026-09-09T11:00:00", "end_time": "2026-09-11T11:00:00"}])
    case.conn.commit()
    return {"base": {"plan_ref": case.plan_ref(1)}}


def _external_candidate(case):
    external_operation(case)
    case.conn.commit()
    return candidate(case)


def _rename(archive, table, key, value):
    columns = archive["columns"][table]
    (row,) = [row for row in archive["tables"][table] if row[columns.index(TABLE_KEYS[table])] == key]
    row[columns.index("name")] = value


def _saved_machine_label(resources, value):
    (row,) = [row for row in resources["machines"] if row["business_code"] == "M2"]
    row["label"] = value


def _recorded_supplier_label(admission, value):
    (row,) = [row for row in admission["source"]["suppliers"].values() if row["supplier_id"] == "S1"]
    row["label"] = value


def _recorded_type_label(admission, value):
    for row in admission["source"]["operation_types"].values():
        row["label"] = value


def _saved_type_name(resources, value):
    (row,) = [row for row in resources["op_types"] if row["op_type_id"] == "T1"]
    row["name"] = value


def _trial_document(column, damage):
    """A trial repository row whose stored ``column`` document holds the damaged name."""
    def rewrite(row, value):
        document = json.loads(row[column])
        damage(document, value)
        return dict(row, **{column: canonical_json(document)})
    return rewrite


def _run_archive(damage):
    """A run's capture row whose generation archive holds the damaged name, with that archive's stored size."""
    def rewrite(row, value):
        archive = json.loads(row["conditions_archive_json"])
        damage(archive, value)
        text = canonical_json(archive)
        return dict(row, conditions_archive_json=text, conditions_archive_bytes=len(text.encode("utf-8")))
    return rewrite


# Each archive an adopted task's resource or operation type name is read from, damaged where its repository reads
# it: the source draft's archive (a kept arrangement's machine), the scenario's saved resources (a new slot's
# machine), the supplier an official source recorded, a candidate source's generation archive (its supplier), the
# type the source recorded for a kept arrangement, and the scenario's saved type a new slot holds.
_NAME_SOURCES = {
    "draft_archive": (official, False, WorkbenchTrialRepository, "draft_header", _trial_document(
        "admission_json", lambda admission, value: _rename(admission["facts"], "Machines", "M1", value))),
    "saved_scenario": (official, True, WorkbenchTrialRepository, "scenario_header",
                       _trial_document("resources_json", _saved_machine_label)),
    "official_supplier": (_external_plan, False, WorkbenchTrialRepository, "draft_header",
                          _trial_document("admission_json", _recorded_supplier_label)),
    "candidate_supplier": (_external_candidate, False, WorkbenchRunCandidateRepository, "job_capture",
                           _run_archive(lambda archive, value: _rename(archive, "Suppliers", "S1", value))),
    "draft_type": (official, False, WorkbenchTrialRepository, "draft_header",
                   _trial_document("admission_json", _recorded_type_label)),
    "saved_type": (official, True, WorkbenchTrialRepository, "scenario_header",
                   _trial_document("resources_json", _saved_type_name)),
}


@pytest.mark.parametrize("name", sorted(BAD_RESOURCE_NAMES))
@pytest.mark.parametrize("source", sorted(_NAME_SOURCES))
def test_adoption_rejects_a_stored_resource_name_readers_do_not_show(trial_case, monkeypatch, source, name):
    # 采用写进正式计划的资源名与读取同一准入；不合法就按所在存档损坏拒绝，正式计划不变：试调存档是可操作的
    # trial_snapshot_invalid（预览阻断、采用 409），候选生成期归档是 candidate_artifact_invalid 500。
    case = trial_case
    base, changed, repository, method, rewrite = _NAME_SOURCES[source]
    saved = saved_scenario(case, base(case), changed=changed)
    token = preview(case, saved)
    read = getattr(repository, method)
    monkeypatch.setattr(repository, method, lambda repo, ref: rewrite(read(repo, ref), BAD_RESOURCE_NAMES[name]))
    before = snapshot(case.conn)
    if source == "candidate_supplier":
        for adoption in (lambda: service(case.conn).preview(saved["scenario_ref"]),
                         lambda: service(case.conn).adopt(saved["scenario_ref"], token, KEY, INTENT)):
            with pytest.raises(WorkbenchCommandRejected) as rejected:
                adoption()
            assert (rejected.value.code, rejected.value.status) == ("candidate_artifact_invalid", 500)
    else:
        checked = service(case.conn).preview(saved["scenario_ref"])
        assert checked["validation"]["can_adopt"] is False
        assert [row["code"] for row in checked["validation"]["issues"]] == ["trial_snapshot_invalid"]
        with pytest.raises(WorkbenchCommandRejected) as rejected:
            service(case.conn).adopt(saved["scenario_ref"], token, KEY, INTENT)
        assert (rejected.value.code, rejected.value.status) == ("trial_snapshot_invalid", 409)
    assert snapshot(case.conn) == before


def test_adoption_records_a_new_slot_type_name_as_the_scenario_saved_it(trial_case):
    # 工种名与资源名同一准入：合法名称首尾的空白原样写进正式计划，不裁剪。
    case = trial_case
    case.conn.execute("UPDATE OpTypes SET name=' Turning ' WHERE op_type_id='T1'")
    case.conn.commit()
    saved = saved_scenario(case, official(case))
    service(case.conn).adopt(saved["scenario_ref"], preview(case, saved), KEY, INTENT)
    assert [row[0] for row in case.conn.execute(
        "SELECT op_type_label FROM Schedule WHERE version=(SELECT MAX(version) FROM Schedule)")] == [" Turning "]
