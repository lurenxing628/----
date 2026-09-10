"""FB: real admission/adoption -> Field -> actual Gantt, with read-only proofs."""

import csv
import io

from tests.workbench.point_downstream_support import ACTUAL, FIELD, app_for, read, report
from tests.workbench.test_piece_chain_end_to_end import workspace
from tests.workbench.test_piece_chain_support import adopt_candidate
from tests.workbench.test_piece_presentation import PIECES, real_case
from tests.workbench.trial_support import snapshot
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401

FIELDS = ('piece_id', 'quantity', 'batch_quantity', 'quantity_basis', 'quantity_reason')


def setup(case):
    _, (_, refs) = real_case(case)
    adopted = adopt_candidate(case, refs[0])
    plan = adopted['data']['official_plan']
    return app_for(case).test_client(), plan, adopted


def verify_chain(client, case, plan):
    before = snapshot(case.conn)
    formal = workspace(case.conn, plan['plan_ref'])
    field = read(client, FIELD + '/tasks', plan_ref=plan['plan_ref'])
    actual = read(client, ACTUAL, plan_ref=plan['plan_ref'])
    original = {t['task_ref']: t for t in formal['tasks']}
    actual_items = {i['task']['task_ref']: i for i in actual['data']['items']}
    assert set(original) == set(actual_items) == {t['task_ref'] for t in field['data']['tasks']}
    for task in field['data']['tasks']:
        source, item = original[task['task_ref']], actual_items[task['task_ref']]
        for key in FIELDS + ('operation_ref', 'task_ref', 'plan_ref'):
            assert task[key] == source[key] == item['task'][key], key
        detail = read(client, FIELD + '/tasks/' + task['task_ref'],
                      plan_ref=plan['plan_ref'], snapshot_ref=field['meta']['snapshot_ref'])
        assert detail['data']['task'] == task
        assert task['execution']['execution_state'] == item['execution']['execution_state']
        # Field adds labels/write contexts, but never rewrites report identities or facts.
        assert len(task['execution']['reports']) == len(item['execution']['reports'])
        for left, right in zip(task['execution']['reports'], item['execution']['reports']):
            for key, value in right.items():
                if key != 'write_context':
                    assert left[key] == value, key
    assert snapshot(case.conn) == before
    return formal, field, actual


def test_piece_downstream_exact_identity_quantity_and_search(trial_case):
    case = trial_case
    client, plan, _ = setup(case)
    formal, field, actual = verify_chain(client, case, plan)
    pieces = [t for t in field['data']['tasks'] if t['piece_id'] is not None]
    assert len(pieces) == 6
    assert {t['piece_id'] for t in pieces} == set(PIECES)
    assert all(t['quantity'] == t['execution']['target_quantity'] == 1 and t['batch_quantity'] == 3 for t in pieces)
    common = [t for t in field['data']['tasks'] if t['batch_id'] == 'B1' and t['piece_id'] is None]
    assert len(common) == 2 and all(t['quantity'] == t['execution']['target_quantity'] == 3 for t in common)
    for piece in PIECES:
        filtered = read(client, FIELD + '/tasks', plan_ref=plan['plan_ref'], query=piece)['data']['tasks']
        assert len(filtered) == 2 and {t['piece_id'] for t in filtered} == {piece}
        response = client.get(ACTUAL + '/export', query_string=dict(plan_ref=plan['plan_ref'],
            snapshot_ref=actual['meta']['snapshot_ref'], format='csv', local_query=piece))
        assert response.status_code == 200, response.get_data(as_text=True)
        rows = list(csv.DictReader(io.StringIO(response.data.decode('utf-8-sig'))))
        assert len(rows) == 2
        assert all(r['单件编号'] == piece and r['计划应做数量'] == '1' and r['计划批次数量'] == '3' for r in rows)
        assert {r['任务引用'] for r in rows} == {t['task_ref'] for t in filtered}


def test_piece_downstream_old_plan_unknown_and_current_master_drift(trial_case):
    case = trial_case
    client, plan, _ = setup(case)
    before = verify_chain(client, case, plan)[0]
    case.conn.execute("UPDATE Batches SET quantity=99 WHERE batch_id='B1'")
    case.conn.commit()
    assert verify_chain(client, case, plan)[0]['tasks'] == before['tasks']
    old = {'plan_ref': case.plan_ref(4)}
    formal, field, actual = verify_chain(client, case, old)
    task = field['data']['tasks'][0]
    assert task['quantity'] is None and task['batch_quantity'] is None
    assert task['quantity_basis'] == 'unknown' and task['quantity_reason'] == 'plan_target_not_recorded'
    assert task['execution']['target_quantity'] == 99
    assert not task['execution']['write_context']['capabilities']['create']


def test_piece_downstream_missing_receipt_stays_unknown(trial_case):
    client, plan, adopted = setup(trial_case)
    trial_case.conn.execute('DELETE FROM WorkbenchCommandReceipts WHERE receipt_ref=?', (adopted['receipt_ref'],))
    trial_case.conn.commit()
    _, field, actual = verify_chain(client, trial_case, plan)
    for task in field['data']['tasks']:
        assert task['quantity'] is None and task['batch_quantity'] is None
        assert task['quantity_reason'] == 'plan_target_unavailable'


def test_piece_downstream_report_does_not_complete_sibling_or_change_refs(trial_case):
    case = trial_case
    client, plan, _ = setup(case)
    formal = workspace(case.conn, plan['plan_ref'])
    task = next(t for t in formal['tasks'] if t['piece_id'] == PIECES[0] and t['sequence'] == 20)
    before = snapshot(case.conn)
    report(client, {'task': task}, quantity=0, hours=0)
    _, field, _ = verify_chain(client, case, plan)
    rows = {t['task_ref']: t for t in field['data']['tasks']}
    assert rows[task['task_ref']]['execution']['execution_state'] != 'complete'
    assert all(t['execution']['execution_state'] == 'unreported' for t in rows.values()
               if t['piece_id'] is not None and t['task_ref'] != task['task_ref'])
    stored = rows[task['task_ref']]['execution']['reports'][0]
    assert stored['completed_quantity'] == 0
    assert stored['recorded_against_plan_ref'] == task['plan_ref']
    assert stored['recorded_against_task_ref'] == task['task_ref']
    assert stored['operation_ref'] == task['operation_ref']
    after = snapshot(case.conn)
    for table in ('Batches', 'BatchOperations', 'Schedule', 'WorkbenchTaskRefs', 'WorkbenchPlanSourceRefs', 'OperationExecutionEvents'):
        assert after[table] == before[table], table
    for table in ('WorkbenchProductionReports', 'WorkbenchProductionReportRevisions'):
        assert set(before[table]) <= set(after[table]), table


def test_piece_downstream_frontend_model():
    import os
    import subprocess
    from pathlib import Path

    from tests.workbench.test_live_browser import runtime_tools

    node, _, modules = runtime_tools()
    result = subprocess.run([node, str(Path(__file__).with_name('piece_downstream_contract.cjs'))],
        env=dict(os.environ, NODE_PATH=modules), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
