"""FB: real admission/adoption -> Field -> actual Gantt, with read-only proofs."""

import csv
import io

from tests.workbench.piece_chain_support import adopt_candidate
from tests.workbench.piece_presentation_support import PIECES, real_case
from tests.workbench.point_downstream_support import ACTUAL, FIELD, app_for, read
from tests.workbench.test_piece_chain_end_to_end import workspace
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
        assert {r['任务编号'] for r in rows} == {t['task_ref'] for t in filtered}


def test_piece_downstream_frontend_model():
    import subprocess
    from pathlib import Path

    from tests.workbench.node_runtime_support import node_runtime

    result = subprocess.run([node_runtime(), str(Path(__file__).with_name('piece_downstream_contract.cjs'))],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
