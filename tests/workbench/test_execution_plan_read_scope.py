"""Execution reads keep their real cohort without unrelated plan projections."""

from datetime import datetime, timedelta
from io import BytesIO

import pytest
from openpyxl import load_workbook

from core.models.hours import exact_hours_text, stored_exact_hours, sum_hours
from core.models.process_route_text import serialize_route_rows
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_route import check_route_text
from core.services.workbench.plan import queries
from tests._support.gantt_current_js import run_current_js
from tests.workbench.execution_ledger_support import all_rows, publish_official_plan
from tests.workbench.field_workspace_support import FieldAPI, _ledger_fixture  # noqa: F401
from tests.workbench.plan_catalog_support import update_schedule_rows
from tests.workbench.point_downstream_support import ACTUAL, FIELD, app_for, read_body


def _three_tasks(case, *, record_source=False):
    second, third = case.op('OP2', seq=2), case.op('OP3', seq=3)
    rows = [
        {
            'op_id': op_id,
            'machine_id': 'M1',
            'operator_id': 'O1',
            'start_time': '2026-09-09T' + start,
            'end_time': '2026-09-09T' + end,
        }
        for op_id, start, end in (
            (case.op_id, '08:00:00', '10:00:00'),
            (second, '10:00:00', '12:00:00'),
            (third, '12:00:00', '14:00:00'),
        )
    ]
    publish_official_plan(case.conn, 2, rows, record_source=record_source)
    case.conn.commit()
    case.path = case.conn.execute('PRAGMA database_list').fetchone()[2]
    return case.plan_ref(2), [case.task(2, op_id) for op_id in (case.op_id, second, third)]


def _unrelated_too_large(*args, **kwargs):
    raise WorkbenchCommandRejected('query_too_large', 'Oversized unrelated baseline comparison.', 413)


def test_unrelated_plan_projection_cannot_block_execution_cohort(ledger_case, monkeypatch):
    case = ledger_case
    plan_ref, refs = _three_tasks(case)
    api = FieldAPI(case)
    task = api.task(plan_ref=plan_ref)
    api.create(case.values(2), task)
    client = app_for(case).test_client()
    before = all_rows(case.conn)
    monkeypatch.setattr(queries, 'workspace_projections', _unrelated_too_large)
    full = client.get('/api/workbench/v1/plans/' + plan_ref + '/workspace')
    assert full.status_code == 413 and full.get_json()['error']['code'] == 'query_too_large'
    scope = dict(plan_ref=plan_ref, range_start='2026-09-09T08:00:00', range_end='2026-09-09T10:00:00')
    field = read_body(client, FIELD + '/tasks', **scope)
    actual = read_body(client, ACTUAL, **scope)
    row, = field['data']['tasks']
    item, = actual['data']['items']
    assert row['task_ref'] == item['task']['task_ref'] == refs[0]
    assert row['quantity'] == item['task']['quantity'] == 10
    assert row['quantity_basis'] == item['task']['quantity_basis'] == 'run_admission'
    assert row['execution']['target_quantity'] == item['execution']['target_quantity'] == 10
    assert row['planned_start'] == item['task']['start'] == scope['range_start']
    assert row['planned_end'] == item['task']['end'] == scope['range_end']
    assert row['execution']['execution_state'] == item['execution']['execution_state'] == 'partial'
    assert row['execution']['reports'][0]['revision_ref'] == item['execution']['reports'][0]['revision_ref']
    assert row['execution']['reports'][0]['revision_count'] == item['execution']['reports'][0]['revision_count'] == 1
    assert item['execution']['reports'][0]['correction_history'] == []
    detail = read_body(client, FIELD + '/tasks/' + refs[0], **scope, snapshot_ref=field['meta']['snapshot_ref'])
    assert detail['data']['task'] == row
    assert actual['data']['calendar']['time_scope']['range_start'] == scope['range_start']
    assert actual['data']['calendar']['time_scope']['range_end'] == scope['range_end']
    assert actual['data']['gantt_graph']['state'] == 'available'
    assert len(actual['data']['gantt_graph']['nodes']) == 3
    assert all_rows(case.conn) == before


def test_scoped_actual_graph_keeps_full_plan_chain_and_hover_skips_report_reads(ledger_case):
    case = ledger_case
    case.conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M2','Parallel lathe')")
    case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M2','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Parallel operator')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O2','M2')")
    case.conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B_SIDE','P1',10)")
    side_op = case.op('OP_SIDE', seq=1, batch='B_SIDE')
    second, third = case.op('OP2', seq=2), case.op('OP3', seq=3)
    publish_official_plan(
        case.conn,
        2,
        [
            {'op_id': case.op_id, 'machine_id': 'M1', 'operator_id': 'O1', 'start_time': '2026-09-09T08:00:00', 'end_time': '2026-09-09T10:00:00'},
            {'op_id': second, 'machine_id': 'M1', 'operator_id': 'O1', 'start_time': '2026-09-09T10:00:00', 'end_time': '2026-09-09T12:00:00'},
            {'op_id': third, 'machine_id': 'M1', 'operator_id': 'O1', 'start_time': '2026-09-09T12:00:00', 'end_time': '2026-09-09T14:00:00'},
            {'op_id': side_op, 'machine_id': 'M2', 'operator_id': 'O2', 'start_time': '2026-09-09T08:00:00', 'end_time': '2026-09-09T09:00:00'},
        ],
        record_source=True,
    )
    case.conn.commit()
    case.path = case.conn.execute('PRAGMA database_list').fetchone()[2]
    plan_ref = case.plan_ref(2)
    refs = [case.task(2, op_id) for op_id in (case.op_id, second, third)]
    client = app_for(case).test_client()
    scope = dict(plan_ref=plan_ref, range_start='2026-09-09T12:00:00', range_end='2026-09-09T14:00:00')
    actual = read_body(client, ACTUAL, **scope)
    batch_query = dict(plan_ref=plan_ref, batch_ids=['B2', 'B1'])
    batched = read_body(client, ACTUAL, plan_ref=plan_ref, batch_ids=batch_query['batch_ids'])
    assert batched['data']['scope']['batch_ids'] == ['B1', 'B2']
    # Filtering by B1/B2 trims unselected non-critical B_SIDE from gantt_graph.nodes while keeping critical B1.
    assert {node['batch_id'] for node in batched['data']['gantt_graph']['nodes']} == {'B1'}
    assert len(batched['data']['gantt_graph']['nodes']) == 3
    # Filtering by non-critical B_SIDE keeps both B_SIDE and critical-chain B1.
    side_batched = read_body(client, ACTUAL, plan_ref=plan_ref, batch_ids=['B_SIDE'])
    assert {node['batch_id'] for node in side_batched['data']['gantt_graph']['nodes']} == {'B1', 'B_SIDE'}
    assert len(side_batched['data']['gantt_graph']['nodes']) == 4
    graph = actual['data']['gantt_graph']
    assert actual['data']['task_count'] == 1 and actual['data']['items_complete'] is True
    assert graph['state'] == 'available' and graph['scope'] == 'full_plan'
    assert len(graph['nodes']) == 4 and graph['critical_task_refs'] == refs
    assert 'critical_chain' not in actual['data']
    # The shipped frontend contract accepts the scoped response whose graph keeps the full-plan chain.
    assert run_current_js(r"""
const C = h.module('ActualGanttContract.js'), ActualGanttWorkspace = h.module('ActualGanttWorkspace.jsx').default, H = h.module('shared/hours.js'), SessionQuery = h.module('shared/session/query.js');
h.equal(C.workspace(sourceData.payload, sourceData.query), sourceData.payload);
h.equal(C.workspace(sourceData.batched, C.scope(sourceData.batchQuery)), sourceData.batched);
for (const wrong of [
  { plan_ref: sourceData.query.plan_ref },
  { ...sourceData.query, range_start: '2026-09-09T08:00:00' },
  { ...sourceData.query, plan_finish_date_from: '2026-09-09', plan_finish_date_to: '2026-09-09' },
  { ...sourceData.query, resource_type: 'machine', resource_ref: sourceData.machineRef },
  sourceData.batchQuery,
]) assert.throws(() => C.workspace(sourceData.payload, wrong), /范围不完整/);
for (const wrong of [
  { plan_ref: sourceData.query.plan_ref, batch_ids: ['B1'] },
  { plan_ref: sourceData.query.plan_ref, batch_ids: ['B2', 'B3'] },
]) assert.throws(() => C.workspace(sourceData.batched, wrong), /范围不完整/);
const payload = h.clone(sourceData.payload), item = payload.data.items[0], taskRef = item.task.task_ref;
let reportNoReads = 0;
const tenth = H.parseHours('0.1');
const reports = Array.from({ length: 1000 }, (_, index) => {
  const ref = (index + 1).toString(16).padStart(48, '0'), no = 'RG-' + String(index + 1).padStart(4, '0');
  return { report_ref: ref, get report_no() { reportNoReads++; return no; }, actual_start: item.task.start, actual_end: item.task.end,
    completed_quantity: 1, effective_processing_hours: 0.1, effective_processing_hours_exact: tenth, actual_machine_ref: item.task.machine_ref,
    actual_operator_ref: item.task.operator_ref, recorded_at: item.task.end, correction_history: [], revision_count: 3, remark: '' };
});
item.execution = { ...item.execution, execution_state: 'partial', known_completed_quantity: 10, remaining_quantity: 0,
  confirmed_finish: null, data_gaps: [{ report_ref: reports[0].report_ref, message: '待核对数量' }], reports, remaining_plan: null };
// The page reads this very payload object (post-contract shape), so its report_no getters count every read the page makes;
// the shipped contract copies reports while parsing, so the read is answered at the query hook instead of the network.
const origUseQuery = SessionQuery.useQuery;
SessionQuery.useQuery = () => ({ result: payload, shown: payload, loading: false, error: null, status: 'ready', reload() {} });
try {
  const { plan_ref, ...range } = sourceData.query;
  const page = h.mount(ActualGanttWorkspace, { initialContext: { plan_ref, task_ref: taskRef, scope: range }, onNavigate() {} });
  const reportSelect = tree => h.walk(tree).find(node => node.type === 'select' && node.props['aria-label'] === '选择报工详情');
  h.walk(page.tree).find(node => node.type === 'button' && node.props['aria-controls'] === 'actual-gantt-detail').props.onClick({ currentTarget: {}, preventDefault() {}, stopPropagation() {} });
  const firstTree = page.update();
  const selectNode = reportSelect(firstTree);
  assert(selectNode && selectNode.children[1].length === 1000);
  const readsBeforeHover = reportNoReads;
  // Hover the selected task's first report mark (keyboard focus reports the mark itself).
  h.walk(firstTree).find(node => node.props && node.props['data-task-ref'] === taskRef && node.props['data-report-ref'] === reports[0].report_ref && node.props.onFocus)
    .props.onFocus({ type: 'focus', currentTarget: { getBoundingClientRect: () => ({ right: 180, top: 120 }) } });
  const hoverTree = page.update();
  assert(h.walk(hoverTree).some(node => node.props && node.props.role === 'tooltip'), 'The hovered report shows its tooltip');
  assert.strictEqual(reportNoReads - readsBeforeHover, 0, 'Hovering with 1,000 reports and details open must read report_no 0 extra times');
  const selectAfter = reportSelect(hoverTree);
  assert.strictEqual(selectAfter.children[1].length, 1000);
  selectAfter.props.onChange({ target: { value: reports[0].report_ref } });
  const reportTree = page.update();
  const historyNode = h.walk(reportTree).find(node => node.type === 'p' && Array.isArray(node.children) && node.children.join('').includes('历史版本 3 条'));
  assert(historyNode, 'Selected report detail must display revision_count even when correction_history is empty');
  page.unmount();
} finally {
  SessionQuery.useQuery = origUseQuery;
}
return true;
""", {'payload': actual, 'query': scope, 'batched': batched, 'batchQuery': batch_query, 'machineRef': case.ref('machine', 'M1')})['result'] is True


def _hours_text(amount):
    return None if amount is None else exact_hours_text(amount)


def _hour_totals(values):
    totals = sum_hours(values)
    return {'known': _hours_text(totals.known), 'unknown': totals.unknown}


def test_actual_group_hours_match_backend_exact_totals(ledger_case):
    """Actual Gantt groups sum the browser's local visible set exactly as the backend's sum_hours does."""
    case = ledger_case
    plan_ref, refs = _three_tasks(case)
    case.conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M2','Second lathe')")
    case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M2','T1')")
    case.conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O2','Second operator')")
    case.conn.executemany("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)",
                          [('O1', 'M2'), ('O2', 'M1'), ('O2', 'M2')])
    case.conn.commit()
    api = FieldAPI(case)
    # 0.1 + 0.2, a legal zero, an unknown, a sum past 2**53 (no end time, so no span bound) and an exponent text.
    reports = [(refs[0], 0.1, 'M1', 'O1', {}), (refs[0], 0.2, 'M1', 'O2', {}), (refs[0], 0, 'M2', 'O1', {}),
               (refs[0], None, 'M2', 'O2', {}), (refs[1], 9007199254740991, 'M1', 'O1', {'actual_end': None}),
               (refs[1], 2, 'M1', 'O2', {'actual_end': None}), (refs[2], 1e-07, 'M2', 'O1', {}), (refs[2], 1.75, 'M2', 'O2', {})]
    for task_ref, hours, machine, operator, patch in reports:
        task = next(row for row in api.read(plan_ref=plan_ref)['data']['tasks'] if row['task_ref'] == task_ref)
        api.create(case.values(1, effective_processing_hours=hours, actual_machine_ref=case.ref('machine', machine),
                               actual_operator_ref=case.ref('operator', operator), **patch), task)
    scope = {'plan_ref': plan_ref}
    payload = read_body(app_for(case).test_client(), ACTUAL, **scope)
    items = payload['data']['items']
    # Expected amounts come from the stored exact text, never from the public number.
    stored = {ref: None if text is None else stored_exact_hours(text) for ref, text in case.conn.execute(
        "SELECT report_ref, effective_processing_hours FROM WorkbenchProductionReports WHERE voided = 0")}
    assert len(stored) == len(reports) == sum(len(item['execution']['reports']) for item in items)
    for item in items:
        for report in item['execution']['reports']:
            assert report['effective_processing_hours_exact'] == _hours_text(stored[report['report_ref']])
    expected = {}
    for mode in ('machine', 'operator', 'batch'):
        for view, shown in (('all', items), ('selected', [item for item in items if item['task']['task_ref'] == refs[0]])):
            groups = {}
            for item in shown:
                planned = item['task']['batch_id'] if mode == 'batch' else item['task'][mode + '_ref']
                groups.setdefault(planned, [])
                for report in item['execution']['reports']:
                    key = item['task']['batch_id'] if mode == 'batch' else report['actual_' + mode + '_ref']
                    groups.setdefault(key, []).append(stored[report['report_ref']])
            expected[mode + ':' + view] = {key: _hour_totals(values) for key, values in groups.items()}
    m1, m2 = case.ref('machine', 'M1'), case.ref('machine', 'M2')
    assert expected['machine:selected'][m1]['known'] == '0.3' and expected['machine:selected'][m2]['known'] == '0'
    assert expected['machine:all'][m1] == {'known': '9007199254740993.3', 'unknown': 0}
    assert expected['machine:all'][m2] == {'known': '1.7500001', 'unknown': 1}
    primitives = [[], [0], [0, None], [None], [0.1, 0.2], [9007199254740991, 2], [1e-07, 1.75, 3]]
    result = run_current_js(r"""
const C = h.module('ActualGanttContract.js'), M = h.module('ActualGanttModel.js'), H = h.module('shared/hours.js');
const text = amount => amount === null ? null : H.exactHoursText(amount);
const totals = hours => ({ known: text(hours.known), unknown: hours.unknown });
const admitted = C.workspace(sourceData.payload, sourceData.query), prepared = M.prepare(admitted.data, admitted.meta.as_of);
const view = { query: '', late: 'all', onlySelected: false, selected: null }, groups = {};
for (const mode of ['machine', 'operator', 'batch']) {
  const grouped = M.groupPrepared(prepared, mode);
  for (const [name, value] of [['all', view], ['selected', { ...view, onlySelected: true, selected: sourceData.selected }]])
    groups[mode + ':' + name] = Object.fromEntries(M.selectPrepared(grouped, value).groups.map(group => [group.id, totals(group.hours)]));
}
const primitives = sourceData.primitives.map(texts => totals(H.sumHours(texts.map(value => value === null ? null : H.parseHours(value)))));
return { groups, primitives };
""", {'payload': payload, 'query': scope, 'selected': refs[0],
      'primitives': [[_hours_text(value) for value in values] for values in primitives]})['result']
    assert result['groups'] == expected
    assert result['primitives'] == [_hour_totals(values) for values in primitives]
    assert result['primitives'][:4] == [{'known': None, 'unknown': 0}, {'known': '0', 'unknown': 0},
                                        {'known': '0', 'unknown': 1}, {'known': None, 'unknown': 1}]


def test_field_scoped_page_write_and_files_keep_same_snapshot(ledger_case, monkeypatch, record_property):
    from core.services.workbench.execution.field_workspace import FieldWorkspaceService
    from core.services.workbench.execution.ledger import ExecutionLedgerService
    from data.repositories.workbench_field_query_repo import WorkbenchFieldQueryRepository

    case = ledger_case
    plan_ref, refs = _three_tasks(case)
    api = FieldAPI(case)
    scope = dict(plan_ref=plan_ref, range_start='2026-09-09T08:00:00', range_end='2026-09-09T14:00:00')
    original, calls = FieldWorkspaceService.page, []

    def page_spy(reader, ws_scope, values, number, size, **kwargs):
        calls.append((values, number, size))
        return original(reader, ws_scope, values, number, size, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(FieldWorkspaceService, 'page', page_spy)
        direct = api.read(**scope, size=1, page=2)
    assert len(calls) == 1 and direct['data']['page']['number'] == 2
    assert direct['data']['tasks'][0]['task_ref'] == refs[1]
    record_property('direct_page', 2)
    record_property('cohort_query_calls', len(calls))
    record_property('data_fields', sorted(direct['data']))
    token = direct['meta']['snapshot_ref']
    second = api.read(**scope, size=1, page=2, snapshot_ref=token)
    assert second['data'] == direct['data'] and second['meta'].keys() == direct['meta'].keys()
    assert second['meta']['request_ref'] != direct['meta']['request_ref']
    assert all(second['meta'][key] == value for key, value in direct['meta'].items() if key != 'request_ref')
    first = api.read(**scope, size=1, snapshot_ref=token)
    assert second['meta']['snapshot_ref'] == token and second['meta']['as_of'] == first['meta']['as_of']
    assert second['data']['tasks'][0]['task_ref'] == refs[1]
    omitted = api.read(range_start=scope['range_start'], range_end=scope['range_end'], size=1, snapshot_ref=token)
    assert omitted['meta']['snapshot_ref'] == token and omitted['data']['scope'] == first['data']['scope']
    located = api.read(**scope, size=1, task_ref=refs[1], operation_ref=second['data']['tasks'][0]['operation_ref'])
    assert located['data']['page']['number'] == 2 and located['data']['tasks'][0]['task_ref'] == refs[1]
    mismatch = api.client.post(FIELD + '/tasks', json=dict(scope, size=1, task_ref=refs[1],
        operation_ref=first['data']['tasks'][0]['operation_ref']))
    assert mismatch.status_code == 409 and mismatch.get_json()['error']['code'] == 'constraint_conflict'
    response = api.client.post(FIELD + '/files/template', json=dict(scope, snapshot_ref=token))
    assert response.status_code == 200
    template_bytes = response.data
    book = load_workbook(BytesIO(template_bytes)); assert book.worksheets[0].max_row == 4; book.close()
    changed = api.client.post(FIELD + '/tasks', json=dict(scope, range_end='2026-09-09T12:00:00', snapshot_ref=token))
    assert changed.status_code == 409 and changed.get_json()['error']['code'] == 'snapshot_stale'
    api.create(case.values(2), first['data']['tasks'][0])
    with monkeypatch.context() as patch:
        patch.setattr(WorkbenchFieldQueryRepository, 'field_task_rows',
                      lambda *a, **kw: pytest.fail('should not query field task rows on stale snapshot'))
        patch.setattr(WorkbenchFieldQueryRepository, 'field_summary',
                      lambda *a, **kw: pytest.fail('should not query field summary on stale snapshot'))
        patch.setattr(ExecutionLedgerService, 'load_many',
                      lambda *a, **kw: pytest.fail('should not load ledger on stale snapshot'))
        patch.setattr(ExecutionLedgerService, 'project_operation',
                      lambda *a, **kw: pytest.fail('should not project operation on stale snapshot'))
        for path, extra in ((FIELD + '/tasks', dict(page=2, size=1)),
                            (FIELD + '/tasks/' + refs[0], {}),
                            (FIELD + '/files/template', {}), (FIELD + '/files/export', {})):
            response = api.client.post(path, json=dict(scope, snapshot_ref=token, **extra))
            assert response.status_code == 409 and response.get_json()['error']['code'] == 'snapshot_stale'
        stale_preview = api.upload(template_bytes, direct)
        assert stale_preview.status_code == 409 and stale_preview.get_json()['error']['code'] == 'snapshot_stale'


def test_field_files_reuse_one_ledger_for_cohort_and_import_preparation(ledger_case, monkeypatch):
    from core.services.workbench.execution.ledger import ExecutionLedgerService
    from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository
    from tests.workbench.field_workspace_support import BASE, success

    case = ledger_case
    plan_ref, _ = _three_tasks(case)
    api = FieldAPI(case)
    api.create(task=api.task(plan_ref=plan_ref))
    reading = api.read()
    calls = {"ledgers": 0, "active_reports": 0, "reports": 0, "current_plans": 0}
    initialize = ExecutionLedgerService.__init__
    active_reports = WorkbenchExecutionRepository.active_reports
    reports = WorkbenchExecutionRepository.reports

    def ledger(loaded, *args, **kwargs):
        calls["ledgers"] += 1
        initialize(loaded, *args, **kwargs)
        provider = loaded.current_plan_provider

        def current(conn):
            calls["current_plans"] += 1
            return provider(conn)

        loaded.current_plan_provider = current

    def active_report_rows(repo, refs, limit):
        calls["active_reports"] += 1
        return active_reports(repo, refs, limit)

    def report_rows(repo, refs, limit):
        calls["reports"] += 1
        return reports(repo, refs, limit)

    monkeypatch.setattr(ExecutionLedgerService, "__init__", ledger)
    monkeypatch.setattr(WorkbenchExecutionRepository, "active_reports", active_report_rows)
    monkeypatch.setattr(WorkbenchExecutionRepository, "reports", report_rows)
    exported = api.client.post(BASE + "/files/export", json={**reading["data"]["scope"],
        "snapshot_ref": reading["meta"]["snapshot_ref"]})
    assert exported.status_code == 200
    assert calls == {"ledgers": 1, "active_reports": 1, "reports": 0, "current_plans": 1}
    calls.update(ledgers=0, active_reports=0, reports=0, current_plans=0)
    preview = success(api.upload(exported.data, reading))
    assert preview["data"]["can_confirm"] and preview["data"]["summary"]["unchanged"] == 1
    assert calls == {"ledgers": 1, "active_reports": 1, "reports": 1, "current_plans": 1}
    calls.update(ledgers=0, active_reports=0, reports=0, current_plans=0)
    confirmed = success(api.client.post(BASE + "/files/confirm", json=api.confirm_body(preview)))
    assert confirmed["result"] == "unchanged"
    assert calls == {"ledgers": 1, "active_reports": 1, "reports": 1, "current_plans": 1}

    # Choosing an old plan does not make its tasks the current writable tasks.
    case.plan(3, [case.op_id])
    current_task = case.task(3, case.op_id)
    calls.update(ledgers=0, active_reports=0, reports=0, current_plans=0)
    old = api.read(plan_ref=plan_ref)["data"]["tasks"][0]
    assert old["execution"]["comparison_task_ref"] == old["task_ref"]
    assert old["execution"]["current_task_ref"] == current_task != old["task_ref"]
    assert old["execution"]["write_context"]["capabilities"]["create"] is False
    assert calls == {"ledgers": 1, "active_reports": 0, "reports": 1, "current_plans": 1}
    calls.update(ledgers=0, active_reports=0, reports=0, current_plans=0)
    actual = read_body(app_for(case).test_client(), ACTUAL, plan_ref=plan_ref)["data"]["items"][0]
    assert actual["execution"]["comparison_task_ref"] == old["task_ref"]
    assert actual["execution"]["current_task_ref"] == current_task
    assert calls == {"ledgers": 1, "active_reports": 1, "reports": 0, "current_plans": 1}


def test_field_task_pages_bound_only_the_returned_page(ledger_case, monkeypatch):
    from web.routes.workbench import execution as execution_routes

    case = ledger_case
    # One task alone exceeds the field response budget; the other pages stay small.
    # Only the actual HTTP page is bounded, never the whole scoped plan.
    # A name a real route save admits (the route text cap is 256 KiB); the budget shrinks instead.
    name = '工序' * 4096
    check_route_text(serialize_route_rows([(1, name)]))
    monkeypatch.setattr(execution_routes, 'MAX_WINDOW_RESPONSE_BYTES', 16 * 1024)
    case.conn.execute('UPDATE BatchOperations SET op_type_name=? WHERE id=?', (name, case.op_id))
    plan_ref, _ = _three_tasks(case)
    before = all_rows(case.conn)
    client = app_for(case).test_client()
    field = client.post(FIELD + '/tasks', json=dict(plan_ref=plan_ref, size=1, page=2))
    assert field.status_code == 200 and field.get_json()['data']['page']['total'] == 3
    oversized = client.post(FIELD + '/tasks', json=dict(plan_ref=plan_ref, size=1, page=1))
    assert oversized.status_code == 413 and oversized.get_json()['error']['code'] == 'query_too_large'
    assert all_rows(case.conn) == before


def test_actual_large_plan_applies_finish_batch_and_overlap_before_ledger(ledger_case, monkeypatch):
    from flask import g

    from core.services.workbench.execution import actual_gantt
    from core.services.workbench.plan.read_context import PlanReadContext
    from web.routes.workbench import actual_gantt as actual_gantt_routes

    case = ledger_case
    batches = ['SCALE-' + str(index).zfill(3) for index in range(200)]
    case.conn.executemany("INSERT INTO Batches(batch_id,part_no,quantity) VALUES (?,'P1',10)",
                          [(batch,) for batch in batches])
    case.conn.executemany("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source) "
                          "VALUES (?,?,?,'T1','Turning','internal')",
                          [('SCALE-' + str(index), batch, sequence)
                           for index, (batch, sequence) in enumerate((batch, sequence)
                               for batch in batches for sequence in range(1, 101))])
    rows = list(case.conn.execute("SELECT id,batch_id,seq FROM BatchOperations WHERE batch_id LIKE 'SCALE-%' ORDER BY id"))
    assert len(rows) == 20000
    start = datetime(2026, 9, 9, 8)
    schedule = []
    for index, row in enumerate(rows):
        low = start + timedelta(days=index // 200, minutes=index % 200)
        schedule.append({"op_id": row['id'], "machine_id": "M1", "operator_id": "O1",
                         "start_time": low.isoformat(), "end_time": (low + timedelta(minutes=1)).isoformat()})
    publish_official_plan(case.conn, 2, schedule, record_source=True)
    case.conn.commit()
    case.path = case.conn.execute('PRAGMA database_list').fetchone()[2]
    plan_ref, projected, statements = case.plan_ref(2), [], []
    prepared_counts, projected_tasks = [], PlanReadContext.projected_tasks

    def track_projected_tasks(context, ref, rows, *, resources):
        prepared_counts.append(len(rows))
        return projected_tasks(context, ref, rows, resources=resources)

    monkeypatch.setattr(PlanReadContext, "projected_tasks", track_projected_tasks)
    original = actual_gantt.ExecutionLedgerService.workspace_projection

    def project(ledger, ledger_scope, ref, tasks, *, include_history=True):
        projected.append(len(tasks))
        return original(ledger, ledger_scope, ref, tasks, include_history=include_history)

    monkeypatch.setattr(actual_gantt.ExecutionLedgerService, 'workspace_projection', project)
    app = app_for(case)

    @app.before_request
    def trace():
        g.db.set_trace_callback(statements.append)

    client = app.test_client()
    scopes = [({'plan_finish_date_from': '2026-09-09', 'plan_finish_date_to': '2026-09-09'}, 200),
              ({'batch_ids': [batches[0]]}, 100),
              ({'range_start': '2026-09-09T08:00:00', 'range_end': '2026-09-09T08:10:00'}, 10)]
    for scope, expected in scopes:
        statements.clear()
        response = client.post(ACTUAL, json=dict(plan_ref=plan_ref, **scope))
        assert response.status_code == 200, response.get_json()
        data = response.get_json()['data']
        assert data['task_count'] == len(data['items']) == projected[-1] == expected
        assert data['availability']['state'] == 'available' and data['items_complete'] is True
        assert data['gantt_graph']['state'] == 'available' and len(data['gantt_graph']['nodes']) == 20000
        assert 'critical_chain' not in data
        source_reads = [' '.join(sql.upper().replace('"', '').split()) for sql in statements]
        assert sum(
            (' FROM SCHEDULE R ' in sql and ' WHERE R.VERSION = 2 ' in sql)
            or (' FROM SCHEDULE S ' in sql and ' WHERE S.VERSION = 2 ' in sql)
            for sql in source_reads
        ) == 1
        if scope.get("plan_finish_date_from"):
            from core.services.workbench.plan.read_context import PlanReadContext

            prepared_counts.clear()
            with monkeypatch.context() as patch:
                patch.setattr(PlanReadContext, "gantt_graph",
                              lambda *args, **kwargs: pytest.fail("Export rebuilt the full process graph"))
                exported = client.post(ACTUAL + "/export", json=dict(plan_ref=plan_ref, format="csv",
                    snapshot_ref=response.get_json()["meta"]["snapshot_ref"], **scope))
            assert exported.status_code == 200, exported.get_json()
            assert exported.headers["X-Workbench-Operation-Count"] == str(expected)
            assert prepared_counts and max(prepared_counts) == expected and sum(prepared_counts) == expected
    whole = client.post(ACTUAL, json={'plan_ref': plan_ref})
    assert whole.status_code == 200 and projected[-1] == 20000
    data = whole.get_json()['data']
    assert data['task_count'] == len(data['items']) == 20000 and data['items_complete'] is True
    with monkeypatch.context() as patch:
        patch.setattr(actual_gantt_routes, 'MAX_ACTUAL_RESPONSE_BYTES', 1024 * 1024)
        response = client.post(ACTUAL, json=dict(plan_ref=plan_ref, **scopes[-1][0]))
    assert response.status_code == 413
    error = response.get_json()['error']
    assert error['code'] == 'query_too_large' and '现场甘特数据太多' in error['message']
    assert '日期范围' in error['message'] and '批次' in error['message']


def test_actual_resource_filter_keeps_planned_and_reported_owners(ledger_case):
    case = ledger_case
    plan_ref, refs = _three_tasks(case)
    case.conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M2','Reported machine')")
    case.conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M2','T1')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M2')")
    case.conn.commit()
    api = FieldAPI(case)
    task = next(row for row in api.read(plan_ref=plan_ref)['data']['tasks'] if row['task_ref'] == refs[0])
    api.create(case.values(2, actual_machine_ref=case.ref('machine', 'M2')), task)
    client = app_for(case).test_client()
    scope = dict(plan_ref=plan_ref, plan_finish_date_from='2026-09-09',
                 plan_finish_date_to='2026-09-09', batch_ids=['B1'], resource_type='machine')
    for key, expected in (('M1', refs), ('M2', refs[:1])):
        data = read_body(client, ACTUAL, resource_ref=case.ref('machine', key), **scope)['data']
        assert {item['task']['task_ref'] for item in data['items']} == set(expected)


def test_actual_export_skips_graph_and_keeps_workspace_snapshot_and_deviations(ledger_case, monkeypatch):
    from core.services.workbench.execution import actual_gantt
    from core.services.workbench.execution.actual_gantt_scope import ActualGanttScope

    case = ledger_case
    plan_ref, _ = _three_tasks(case)
    service = actual_gantt.ActualGanttService(case.conn)
    scope = ActualGanttScope.parse({"plan_ref": plan_ref})
    with service.read_snapshot() as gantt_scope:
        full, full_state = service.workspace(gantt_scope, scope, full_workspace=True)
    with service.read_snapshot() as gantt_scope:
        exported, export_state = service.workspace(gantt_scope, scope, full_workspace=False)
    assert full["gantt_graph"] is not None
    assert exported["gantt_graph"] is None and exported["calendar"] is None
    assert full_state == export_state
    actual_gantt.bind_axis_time(exported, "2026-09-10T12:00:00")
    assert all("deviation" in item for item in exported["items"])
    client = app_for(case).test_client()
    listed = read_body(client, ACTUAL, plan_ref=plan_ref)

    from core.services.workbench.plan.read_context import PlanReadContext

    def unused_graph(*args, **kwargs):
        pytest.fail("CSV export rebuilt the full process graph")

    monkeypatch.setattr(PlanReadContext, "gantt_graph", unused_graph)
    response = client.post(ACTUAL + "/export", json={"plan_ref": plan_ref, "format": "csv",
        "snapshot_ref": listed["meta"]["snapshot_ref"]})
    assert response.status_code == 200, response.get_json()
    assert response.headers["X-Workbench-Snapshot-Ref"] == listed["meta"]["snapshot_ref"]
    assert response.headers["X-Workbench-Operation-Count"] == "3"


_ACTUAL_REJECTED = '现场甘特的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。'
_FIELD_REJECTED = '现场记录的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。'


@pytest.mark.parametrize("raw", ('[{"id":"B1","id":"B2"}]', '[NaN]', '[1e999]', '["B1"'))
def test_execution_read_bodies_reject_duplicate_keys_and_nonfinite_numbers_as_unreadable_json(ledger_case, raw):
    from core.services.workbench.execution.field_workspace_scope import normalize_scope

    plan_ref, _ = _three_tasks(ledger_case)
    client = app_for(ledger_case).test_client()
    body = '{"plan_ref": "' + plan_ref + '", "batch_ids": ' + raw + '}'
    for path, message in ((ACTUAL, _ACTUAL_REJECTED), (FIELD + '/tasks', _FIELD_REJECTED)):
        response = client.post(path, data=body, content_type='application/json')
        assert response.status_code == 400 and response.get_json()['error']['message'] == message
    # The file-preview form scope is decoded by the same strict JSON reader, and its list is checked as is.
    assert normalize_scope({'batch_ids': ['B2', 'B1', 'B2']}) == {'batch_ids': ['B1', 'B2']}


def test_execution_reads_take_the_scope_only_from_a_post_body(ledger_case):
    plan_ref, refs = _three_tasks(ledger_case)
    client = app_for(ledger_case).test_client()
    for path in (ACTUAL, ACTUAL + '/export', FIELD + '/tasks', FIELD + '/tasks/' + refs[0],
                 FIELD + '/files/template', FIELD + '/files/export'):
        assert client.get(path, query_string={'plan_ref': plan_ref}).status_code == 405
    for path, message in ((ACTUAL, _ACTUAL_REJECTED), (FIELD + '/tasks', _FIELD_REJECTED)):
        response = client.post(path + '?plan_ref=' + plan_ref, json={})
        assert response.status_code == 400 and response.get_json()['error']['message'] == message


def test_execution_reads_carry_batch_lists_longer_than_a_request_line(ledger_case, monkeypatch):
    import json
    from urllib.parse import urlencode

    from core.services.workbench.execution import actual_gantt_scope, field_workspace_scope

    case = ledger_case
    plan_ref, refs = _three_tasks(case)
    before = all_rows(case.conn)
    client = app_for(case).test_client()
    batches = ['B1'] + ['NO-SUCH-BATCH-' + str(index).zfill(6) for index in range(4999)]
    # As a GET argument this list would not fit the 65536-byte request line (the server answers 414).
    assert len(urlencode({'batch_ids': json.dumps(batches)})) > 65536
    cohort = dict(plan_ref=plan_ref, batch_ids=batches)
    actual = read_body(client, ACTUAL, **cohort)
    assert actual['data']['scope']['batch_ids'] == sorted(batches)
    assert {item['task']['task_ref'] for item in actual['data']['items']} == set(refs)
    token = actual['meta']['snapshot_ref']
    assert read_body(client, ACTUAL, snapshot_ref=token, **cohort)['meta']['snapshot_ref'] == token
    exported = client.post(ACTUAL + '/export', json=dict(cohort, format='csv', snapshot_ref=token))
    assert exported.status_code == 200 and exported.headers['X-Workbench-Operation-Count'] == '3'
    field = read_body(client, FIELD + '/tasks', **cohort)
    assert field['data']['scope']['batch_ids'] == sorted(batches)
    assert [row['task_ref'] for row in field['data']['tasks']] == refs
    pinned = dict(field['data']['scope'], snapshot_ref=field['meta']['snapshot_ref'])
    assert read_body(client, FIELD + '/tasks/' + refs[0], **pinned)['data']['task']['task_ref'] == refs[0]
    for mode in ('template', 'export'):
        assert client.post(FIELD + '/files/' + mode, json=pinned).status_code == 200
    # The whole list is admitted against the one backend bound: one batch past it is refused, not truncated,
    # and the refusal names the bound so the user knows how far to narrow the range.
    monkeypatch.setattr(actual_gantt_scope, 'MAX_WINDOW_BATCHES', len(batches) - 1)
    monkeypatch.setattr(field_workspace_scope, 'MAX_WINDOW_BATCHES', len(batches) - 1)
    for path in (ACTUAL, FIELD + '/tasks'):
        error = client.post(path, json=cohort)
        assert error.status_code == 400
        assert error.get_json()['error']['code'] == 'invalid_input'
        assert error.get_json()['error']['message'] == '一次最多选 4999 个批次，请缩小范围后重试。'
    assert all_rows(case.conn) == before


def test_actual_gantt_rejects_stale_snapshot_before_projection(ledger_case, monkeypatch):
    from core.services.workbench.execution.actual_gantt import ActualGanttService
    from core.services.workbench.execution.ledger import ExecutionLedgerService

    case = ledger_case
    plan_ref, _ = _three_tasks(case)
    client = app_for(case).test_client()
    token = read_body(client, ACTUAL, plan_ref=plan_ref)["meta"]["snapshot_ref"]
    update_schedule_rows(case.conn, 2, where="op_id = ?", params=(case.op_id,), end_time="2026-09-09T09:30:00", sync_history=False)
    case.conn.commit()
    monkeypatch.setattr(ActualGanttService, "_planned",
                        lambda *a, **kw: pytest.fail("should not project planned tasks on stale snapshot"))
    monkeypatch.setattr(ExecutionLedgerService, "workspace_projection",
                        lambda *a, **kw: pytest.fail("should not project ledger on stale snapshot"))
    for path, extra in ((ACTUAL, {}), (ACTUAL + "/export", {"format": "csv"})):
        response = client.post(path, json={"plan_ref": plan_ref, "snapshot_ref": token, **extra})
        assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"
