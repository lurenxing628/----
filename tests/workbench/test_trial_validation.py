"""Real calendar, qualification, execution ledger and editable business conflicts."""

from datetime import datetime

import pytest

from core.errors import AppError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.scheduler.template_lineage import TemplateLineageWriter
from core.services.workbench.run.compute import compute_candidate_run
from core.services.workbench.run.input import prepare_candidate_run_input
from core.services.workbench.run.preflight import PreflightService
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


@pytest.mark.parametrize("state", ["new_complete"])
def test_fixed_and_unique_execution_projection_protect_changes(trial_case, state):
    case = trial_case
    draft = create(case)
    if state == "lock":
        case.conn.execute("UPDATE Schedule SET lock_status='locked'")
        case.conn.commit()
    elif state == "legacy_finish":
        case.event(case.op_id, "start")
        case.event(case.op_id, "finish")
    else:
        values = case.values(quantity=3 if state == "new_complete" else 1,
                             effective_processing_hours=1, actual_end="2026-09-09T10:00:00" if state == "new_complete" else None)
        case.command("create", case.task(1, case.op_id), values)
    refreshed = service(case.conn).get(draft["draft_ref"])
    assert refreshed["tasks"][0]["edit_context"]["can_change"] is False
    before = snapshot(case.conn)
    with pytest.raises(WorkbenchCommandRejected):
        change(case, refreshed)
    assert snapshot(case.conn) == before


def _mixed_external_cycle(case, *, legacy_start="2026-09-09T11:00:00", legacy_finish=None,
                          legacy_machine_id=None, legacy_operator_id=None):
    case.conn.execute("UPDATE OpTypes SET category='both' WHERE op_type_id='T1'")
    case.conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id) VALUES ('S1','Supplier','T1')")
    case.conn.execute("INSERT INTO ExternalGroups(group_id,part_no,start_seq,end_seq,merge_mode,total_days,supplier_id) "
                      "VALUES ('G','P1',2,3,'merged',1,'S1')")
    members = []
    with TransactionManager(case.conn).transaction():
        for seq in (2, 3):
            cursor = case.conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_id,op_type_name,source,supplier_id,"
                "ext_group_id,setup_hours,unit_hours) VALUES ('P1',?,'T1','Turning','external','S1','G',0,0)", (seq,))
            members.append(TemplateLineageWriter(case.conn).copy_template('B1', cursor.lastrowid))
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
