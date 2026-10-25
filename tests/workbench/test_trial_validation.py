"""Real calendar, qualification, execution ledger and editable business conflicts."""

from datetime import datetime
from typing import Optional

import pytest

from core.errors import AppError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.personnel.operator_qualification import OperatorQualificationError, OperatorQualificationService
from core.services.scheduler.template_lineage import TemplateLineageWriter
from core.services.workbench.batch.facts import BatchFacts
from core.services.workbench.run.compute import compute_candidate_run
from core.services.workbench.run.input import prepare_candidate_run_input
from core.services.workbench.run.preflight import PreflightService
from core.services.workbench.trial.constraints import _actual_reservations
from tests.workbench.trial_adoption_support import INTENT
from tests.workbench.trial_adoption_support import service as adoption_service
from tests.workbench.trial_support import change, create, service, snapshot
from tests.workbench.trial_support import trial_case as trial_case


def codes(data):
    return {row["code"] for row in data["validation"]["issues"]}


def test_resources_and_start_one_change_and_conflict_remains_editable(trial_case):
    case = trial_case
    draft = create(case)
    conflicted = change(case, draft, operator="O1")["data"]
    assert "machine_authorization_missing" in codes(conflicted)
    assert conflicted["validation"]["can_adopt"] is False
    assert conflicted["tasks"][0]["edit_context"]["can_change"] is True
    fixed = change(case, conflicted, key="trial-change-00000002")["data"]
    assert fixed["validation"]["constraints_status"] == "valid", fixed["validation"]
    rows = case.conn.execute("SELECT before_json,after_json FROM WorkbenchTrialChanges ORDER BY revision").fetchall()
    assert len(rows) == 2


def test_captured_qualifications_match_live_rules_across_work_types_without_sql(trial_case, monkeypatch):
    from data.repositories.operator_machine_repo import OperatorMachineRepository
    from data.repositories.operator_qualification_repo import OperatorQualificationRepository

    case = trial_case
    case.conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T2','Milling')")
    case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M1','T2')")
    other = case.operation(seq=2, op_type_id="T2", op_type_name="Milling", unit_hours=1)
    case.plan(1, [case.op_id, other], start="2026-09-09T08:00:00", end="2026-09-09T11:00:00")
    case.conn.execute("UPDATE Schedule SET start_time='2026-09-09T11:00:00',end_time='2026-09-09T14:00:00' WHERE op_id=?",
                      (other,))
    case.conn.commit()
    draft = None
    qualification = OperatorQualificationService(case.conn)

    def unexpected_sql(*args, **kwargs):
        raise AssertionError("Trial qualification must consume the current capture")

    for state in ("undeclared", "T1", "T1_T2", "unauthorized"):
        if state == "T1":
            case.conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,skills_declared) VALUES ('O1',1)")
            case.conn.execute("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('O1','T1')")
        elif state == "T1_T2":
            case.conn.execute("INSERT INTO OperatorSkill(operator_id,op_type_id) VALUES ('O1','T2')")
        elif state == "unauthorized":
            case.conn.execute("DELETE FROM OperatorMachine WHERE operator_id='O1' AND machine_id='M1'")
        case.conn.commit()
        expected = {}
        for sequence, work_type in ((1, "T1"), (2, "T2")):
            try:
                qualification.require(operator_id="O1", machine_id="M1", op_type_id=work_type)
                expected[sequence] = False
            except OperatorQualificationError:
                expected[sequence] = True
        with monkeypatch.context() as captured:
            captured.setattr(OperatorQualificationRepository, "read_skill_facts", unexpected_sql)
            captured.setattr(OperatorMachineRepository, "exists", unexpected_sql)
            draft = (create(case, {"base": {"plan_ref": case.plan_ref(1)}}) if draft is None
                     else service(case.conn).get(draft["draft_ref"]))
        for task in draft["tasks"]:
            task_codes = {item["code"] for item in draft["validation"]["issues"] if item.get("task_ref") == task["task_ref"]}
            assert ("operator_qualification_invalid" in task_codes) is expected[task["sequence"]], state
            assert ("operator_skill_missing" in task_codes) is (state == "T1" and task["sequence"] == 2)
            assert ("machine_authorization_missing" in task_codes) is (state == "unauthorized")


def test_old_lock_mark_no_longer_blocks_trial_changes(trial_case):
    """正式计划里的锁定标记（旧版「锁定近期排程」顺带打上的）不再起作用：没报工、不在不重排时段里的工序试调照常能改。"""
    case = trial_case
    draft = create(case)
    case.conn.execute("UPDATE Schedule SET lock_status='locked'")
    case.conn.commit()
    refreshed = service(case.conn).get(draft["draft_ref"])
    assert refreshed["tasks"][0]["edit_context"] == {"blocked_reasons": [], "can_change": True}
    task = change(case, refreshed)["data"]["tasks"][0]
    assert task["changed"] is True and task["start"] == "2026-09-09T13:00:00"


@pytest.mark.parametrize("state", ["new_complete"])
def test_fixed_and_unique_execution_projection_protect_changes(trial_case, state):
    case = trial_case
    draft = create(case)
    if state == "legacy_finish":
        case.event(case.op_id, "start")
        case.event(case.op_id, "finish")
    else:
        values = case.values(quantity=3 if state == "new_complete" else 1,
                             effective_processing_hours=1, actual_end="2026-09-09T10:00:00" if state == "new_complete" else None)
        case.command("create", case.task(1, case.op_id), values)
    case.conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,skills_declared) VALUES ('O1',1)")
    case.conn.execute("DELETE FROM OperatorMachine WHERE operator_id='O1' AND machine_id='M1'")
    case.conn.commit()
    refreshed = service(case.conn).get(draft["draft_ref"])
    assert refreshed["tasks"][0]["edit_context"]["can_change"] is False
    assert refreshed["tasks"][0]["execution"]["execution_state"] == "complete"
    assert not codes(refreshed) & {"operator_skill_missing", "machine_authorization_missing", "operator_qualification_invalid"}
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected) as error:
        change(case, refreshed)
    assert error.value.code == "execution_protected"
    assert snapshot(case.conn) == before


def _mixed_external_cycle(case, *, legacy_start="2026-09-09T11:00:00", legacy_finish=None,
                          legacy_machine_id=None, legacy_operator_id=None):
    case.conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='T1'")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','Supplier','T1')")
    case.conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
                      "VALUES ('G','P1',2,3,'merged',1,'S1')")
    members = []
    with TransactionManager(case.conn).transaction():
        writer = TemplateLineageWriter(case.conn)
        template_rows = []
        for seq in (2, 3):
            cursor = case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,"
                "ext_group_id,setup_hours,unit_hours) VALUES ('P1',?,'T1','Turning','external','S1','G',0,0)", (seq,))
            template_rows.append({"id": cursor.lastrowid})
        for prepared in writer.prepare_templates(template_rows, facts=BatchFacts(case.conn).load()):
            members.append(writer.copy_prepared_template('B1', prepared))
    case.batch('B2')
    movable = case.operation('B2', machine_id='M2', operator_id='O2')
    case.plan(1, [case.op_id, *members, movable], end="2026-09-09T11:00:00")
    case.conn.execute("UPDATE Schedule SET machine_id=NULL,operator_id=NULL,start_time='2026-09-09T11:00:00',"
                      "end_time='2026-09-10T11:00:00' WHERE op_id IN (?,?)", members)
    case.conn.execute("UPDATE Schedule SET machine_id='M2',operator_id='O2',start_time='2026-09-09T11:00:00',"
                      "end_time='2026-09-09T11:45:00' WHERE op_id=?", (movable,))
    case.conn.commit()
    case.command('create', case.task(1, case.op_id), case.values(3, actual_end='2026-09-09T11:00:00',
                                                              effective_processing_hours=3))
    case.command('create', case.task(1, members[0]), case.values(3, actual_start='2026-09-09T11:00:00',
        actual_end='2026-09-10T11:30:00', effective_processing_hours=1,
        actual_machine_ref=None, actual_operator_ref=None))
    schedule_id = case.conn.execute('SELECT id FROM Schedule WHERE op_id=?', (members[1],)).fetchone()[0]
    previous = f'{members[1]}:0:0'
    for count, (event_type, event_time) in enumerate([('start', legacy_start)] + ([('finish', legacy_finish)] if legacy_finish else [])):
        event_id = case.conn.execute("INSERT INTO OperationExecutionEvents "
            "(schedule_version,schedule_id,op_id,batch_id,source_table,effective_plan_role,event_type,reported_status,event_time,"
            "actual_machine_id,actual_operator_id,quantity_done,created_by,idempotency_key,request_fingerprint,previous_state_revision) "
            "VALUES (1,?,?,'B1','schedule','adopted',?,?,?,?,?,?,'old-operator',?,'old-fingerprint',?)",
            (schedule_id, members[1], event_type, 'processing' if event_type == 'start' else 'completed', event_time,
             legacy_machine_id, legacy_operator_id, None if event_type == 'start' else 3,
             f'legacy-external-{event_type}', previous)).lastrowid
        previous = f'{members[1]}:{count + 1}:{event_id}'
    case.conn.commit()
    return members, movable


def test_confirmed_merged_return_replaces_legacy_estimate_in_real_trial_adoption(trial_case):
    case = trial_case
    members, _ = _mixed_external_cycle(case)
    settings = case.settings('B2')
    checked, _ = PreflightService(case.conn).evaluate(settings)
    assert checked['blockers'] == []
    prepared = prepare_candidate_run_input(case.conn, settings, case.projections('B2'))
    assert prepared.normalized_batch_ids == ['B2'] and not prepared.execution_fixed_op_ids
    assert compute_candidate_run(case.conn, settings, case.projections('B2')).state == 'complete'
    retained = {table: list(case.conn.execute('SELECT * FROM ' + table)) for table in
                ('OperationExecutionEvents', 'WorkbenchProductionReports', 'WorkbenchProductionReportRevisions')}
    draft = create(case, {'base': {'plan_ref': case.plan_ref(1)}})
    group = [task for task in draft['tasks'] if task['sequence'] in (2, 3)]
    assert {task['execution_anchor']['end'] for task in group} == {'2026-09-10T11:30:00'}
    started = next(task for task in group if task['sequence'] == 3)
    assert started['execution_anchor']['basis'] == 'started_actuals'
    assert '同组已确认回厂时间' in started['execution_anchor']['message']
    assert draft['validation']['constraints_status'] == 'valid', draft['validation']
    index = next(index for index, task in enumerate(draft['tasks']) if task['batch_id'] == 'B2')
    draft = change(case, draft, task=index, start='2026-09-11T08:00:00',
                   machine='M2', operator='O2', key='merged-legacy-trial-change-01')['data']
    saved = service(case.conn).save(draft['draft_ref'], {'name': 'Merged cycle trial'},
        draft['write_context']['write_token'], 'merged-legacy-trial-save-01')['data']
    checked = adoption_service(case.conn).preview(saved['scenario_ref'])
    assert checked['validation']['can_adopt'], checked['validation']
    result = adoption_service(case.conn).adopt(saved['scenario_ref'], checked['write_context']['write_token'],
                                              'merged-legacy-trial-adopt-01', INTENT)
    assert result['result'] == 'committed'
    rows = case.conn.execute('SELECT start_time,end_time FROM Schedule WHERE version=? AND op_id IN (?,?)',
                             (result['data']['official_plan']['version'], *members)).fetchall()
    assert {tuple(datetime.fromisoformat(value) for value in row) for row in rows} == {
        (datetime(2026, 9, 9, 11), datetime(2026, 9, 10, 11, 30))}
    ref = case.conn.execute("SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND source_key=? AND active=1",
                            (str(members[1]),)).fetchone()[0]
    projection = case.ledger.project_operations([ref])[0]
    assert projection.execution_state == 'started' and projection.confirmed_finish is None
    assert projection.known_completed_quantity == 0
    refreshed = prepare_candidate_run_input(case.conn, case.settings('B1', 'B2'), case.projections())
    assert members[1] in refreshed.execution_fixed_op_ids
    assert members[0] in refreshed.execution_completed_op_ids and case.op_id in refreshed.execution_completed_op_ids
    assert refreshed.execution_facts[members[1]].actual_status == 'processing'
    assert refreshed.execution_facts[members[1]].actual_start_time == datetime(2026, 9, 9, 11)
    assert refreshed.execution_facts[members[1]].actual_end_time is None
    for table, old in retained.items():
        assert list(case.conn.execute('SELECT * FROM ' + table)) == old


def test_unselected_external_orphan_resource_blocks_preflight_and_input(trial_case):
    case = trial_case
    case.conn.execute("PRAGMA foreign_keys=OFF")
    _mixed_external_cycle(case, legacy_machine_id='unknown-original')
    case.conn.execute("PRAGMA foreign_keys=ON")
    settings = case.settings('B2')
    checked, _ = PreflightService(case.conn).evaluate(settings)
    assert any(item['code'] == 'external_actual_resource_conflict' for item in checked['blockers'])
    with pytest.raises(AppError):
        prepare_candidate_run_input(case.conn, settings, case.projections('B2'))


def test_merged_external_cycle_preflight_reports_mismatched_started_member(trial_case):
    case = trial_case
    _mixed_external_cycle(case, legacy_start='2026-09-09T11:15:00')
    checked, _ = PreflightService(case.conn).evaluate(case.settings('B1', 'B2'))
    differ = [item for item in checked['blockers'] if item['code'] == 'external_cycle_actuals_differ']
    assert len(differ) == 1
    assert '尚未登记实际完工' in differ[0]['message']


def test_inactive_operation_ref_does_not_fabricate_self_overlap_with_official_schedule(trial_case):
    from tests.workbench.run_candidate_support import corrupt_update

    case = trial_case
    draft = create(case)
    corrupt_update(
        case.conn,
        "WorkbenchPlanSourceRefs",
        "UPDATE WorkbenchPlanSourceRefs SET active=0 WHERE kind='operation' AND source_key=?",
        (str(case.op_id),),
    )
    refreshed = service(case.conn).get(draft["draft_ref"])
    assert not codes(refreshed) & {"machine_overlap", "operator_overlap"}


def _report(start, end, hours, machine: Optional[str] = "MR1", operator: Optional[str] = "OR1"):
    return {"actual_start": start, "actual_end": end, "effective_processing_hours": hours,
            "actual_machine_ref": machine, "actual_operator_ref": operator}


def _reservation_codes(*, unit_hours, reports=(), legacy_facts=(), finish="2026-09-09T10:00:00",
                       window=("2026-09-09T09:00:00", "2026-09-09T12:00:00"), data_gaps=()):
    execution = {"execution_state": "complete", "reports": list(reports), "legacy_facts": list(legacy_facts),
                 "first_actual_start": "2026-09-09T10:00:00", "confirmed_finish": finish, "target_quantity": 3,
                 "data_gaps": list(data_gaps)}
    live = {"facts": {"tables": {
                "BatchOperations": [{"id": 7, "source": "internal", "setup_hours": 0, "unit_hours": unit_hours}],
                "WorkbenchPlanSourceRefs": [{"ref": "op-actual", "source_key": "7", "kind": "operation"}]}},
            "execution": {"op-actual": execution}}
    row = {"operation_ref": "op-trial", "task_ref": "task-trial", "original": {"operation": {"source": "internal"}},
           "current": {"start": window[0], "end": window[1], "machine_ref": "MR1", "operator_ref": "OR1"}}
    return sorted(item["code"] for item in _actual_reservations([row], live))


def test_completed_point_work_zero_duration_reports_hold_no_resources():
    point = "2026-09-09T10:00:00"
    assert _reservation_codes(unit_hours=0, reports=[
        _report(point, point, 0), _report(point, point, 0, machine=None, operator=None)]) == []
    legacy = {"actual_machine_ref": None, "actual_operator_ref": None, "effective_processing_hours": None}
    assert _reservation_codes(unit_hours=0, legacy_facts=[legacy]) == []
    mixed = [_report(point, point, 0, machine=None, operator=None),
             _report(point, "2026-09-09T11:00:00", 1)]
    assert _reservation_codes(unit_hours=0, reports=mixed, finish="2026-09-09T11:00:00") == [
        "execution_resource_overlap", "execution_resource_overlap"]
    # 正工时工序的零时长报工不是合法点报工，占用区间无法证明。
    assert _reservation_codes(unit_hours=1, reports=[_report(point, point, 0)]) == [
        "execution_resource_interval_unknown", "execution_resource_interval_unknown"]


def test_completed_legacy_finish_may_omit_resources_recorded_by_its_start_event():
    started = {"event_type": "start", "actual_machine_ref": "MR1", "actual_operator_ref": "OR1",
               "effective_processing_hours": None}
    finished = {"event_type": "finish", "actual_machine_ref": None, "actual_operator_ref": None,
                "effective_processing_hours": None}
    finish = "2026-09-09T11:00:00"
    assert _reservation_codes(unit_hours=1, legacy_facts=[started, finished], finish=finish,
                              window=("2026-09-09T12:00:00", "2026-09-09T13:00:00")) == []
    # 开工事件记下的设备人员仍按整道工序的实际起止占用。
    assert _reservation_codes(unit_hours=1, legacy_facts=[started, finished], finish=finish) == [
        "execution_resource_overlap", "execution_resource_overlap"]
    # 旧记录的设备身份对不上现在的资料时，占用仍算不清。
    unresolved = {"code": "legacy_resource_identity_unresolved", "fields": ["actual_machine_ref"]}
    assert _reservation_codes(unit_hours=1, legacy_facts=[started, finished], finish=finish, data_gaps=[unresolved],
                              window=("2026-09-09T12:00:00", "2026-09-09T13:00:00")) == ["execution_resource_unknown"]
