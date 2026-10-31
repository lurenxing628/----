"""Execution reads keep their real cohort without unrelated plan projections."""

import json
from datetime import datetime, timedelta
from io import BytesIO

import pytest
from openpyxl import load_workbook

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.plan import queries
from tests._support.gantt_current_js import run_current_js
from tests.workbench.execution_ledger_support import all_rows, publish_official_plan
from tests.workbench.field_workspace_support import FieldAPI, _ledger_fixture  # noqa: F401
from tests.workbench.point_downstream_support import ACTUAL, FIELD, app_for, read


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
    field = read(client, FIELD + '/tasks', **scope)
    actual = read(client, ACTUAL, **scope)
    row, = field['data']['tasks']
    item, = actual['data']['items']
    assert row['task_ref'] == item['task']['task_ref'] == refs[0]
    # This legacy plan did not capture adopted quantity evidence. Keep its
    # explicit unknown task quantity while the live ledger has a known target.
    assert row['quantity'] is item['task']['quantity'] is None
    assert row['quantity_basis'] == item['task']['quantity_basis'] == 'unknown'
    assert row['execution']['target_quantity'] == item['execution']['target_quantity'] == 10
    assert row['planned_start'] == item['task']['start'] == scope['range_start']
    assert row['planned_end'] == item['task']['end'] == scope['range_end']
    assert row['execution']['execution_state'] == item['execution']['execution_state'] == 'partial'
    assert row['execution']['reports'][0]['revision_ref'] == item['execution']['reports'][0]['revision_ref']
    detail = read(client, FIELD + '/tasks/' + refs[0], **scope, snapshot_ref=field['meta']['snapshot_ref'])
    assert detail['data']['task'] == row
    assert actual['data']['calendar']['time_scope']['range_start'] == scope['range_start']
    assert actual['data']['calendar']['time_scope']['range_end'] == scope['range_end']
    assert actual['data']['critical_chain']['state'] == 'unavailable'
    assert actual['data']['critical_chain']['reason_code'] == 'process_order_unavailable'
    assert all_rows(case.conn) == before


def test_scoped_actual_chain_retains_outside_predecessors_and_snapshot(ledger_case, monkeypatch):
    case = ledger_case
    plan_ref, refs = _three_tasks(case, record_source=True)
    client = app_for(case).test_client()
    scope = dict(plan_ref=plan_ref, range_start='2026-09-09T12:00:00', range_end='2026-09-09T14:00:00')
    actual = read(client, ACTUAL, **scope)
    chain = actual['data']['critical_chain']
    assert actual['data']['task_count'] == 1 and actual['data']['items_complete'] is True
    assert chain['state'] == 'available' and chain['scope'] == 'full_plan'
    assert chain['plan_task_count'] == 3 and chain['task_refs'] == refs
    assert [node['in_scope'] for node in chain['nodes']] == [False, False, True]
    # The shipped frontend contract judges each chain node's in_scope against the response items it already validated.
    assert run_current_js(r"""
const C = h.runtime.ActualGanttContract, flipped = h.clone(sourceData.payload);
assert.strictEqual(C.workspace(sourceData.payload, sourceData.query), sourceData.payload);
flipped.data.critical_chain.nodes[0].in_scope = true;
assert.throws(() => C.workspace(flipped, sourceData.query), /关键链节点与当前计划或范围不一致/);
const payload = h.clone(sourceData.payload), item = payload.data.items[0], taskRef = item.task.task_ref;
let reportNoReads = 0;
const reports = Array.from({ length: 1000 }, (_, index) => {
  const ref = (index + 1).toString(16).padStart(48, '0'), no = 'RG-' + String(index + 1).padStart(4, '0');
  return {
    report_ref: ref,
    get report_no() { reportNoReads++; return no; },
    actual_start: item.task.start,
    actual_end: item.task.end,
    completed_quantity: 1,
    effective_processing_hours: 0.1,
    actual_machine_ref: item.task.machine_ref,
    actual_operator_ref: item.task.operator_ref,
    recorded_at: item.task.end,
    correction_history: [],
    remark: ''
  };
});
item.execution = {
  ...item.execution,
  execution_state: 'partial',
  known_completed_quantity: 10,
  remaining_quantity: 0,
  confirmed_finish: null,
  data_gaps: [{ report_ref: reports[0].report_ref, message: '待核对数量' }],
  reports,
  remaining_plan: null
};
const origUseMemo = h.runtime.React.useMemo, slots = [];
let cursor = 0;
const same = (a, b) => a && b && a.length === b.length && a.every((v, i) => v === b[i]);
h.runtime.React.useMemo = (fn, deps) => {
  const i = cursor++;
  if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { deps, value: fn() };
  return slots[i].value;
};
try {
  const view = { mode: 'machine', query: '', selected: taskRef, report: null, late: 'all', collapsed: {}, onlySelected: false, details: true, chain: false };
  const baseStates = { 0: sourceData.query, 2: payload, 3: false, 4: null, 5: view };
  cursor = 0;
  const firstTree = h.render(h.runtime.ActualGanttWorkspace, { initialContext: { plan_ref: sourceData.query.plan_ref, task_ref: taskRef }, onNavigate() {} },
    { Content: { ...baseStates, 8: null, 11: null } });
  const selectNode = h.walk(firstTree).find(node => node.type === 'select' && node.props['aria-label'] === '选择报工详情');
  assert(selectNode && selectNode.children[1].length === 1000);
  const readsBeforeHover = reportNoReads;
  cursor = 0;
  const hoverTree = h.render(h.runtime.ActualGanttWorkspace, { initialContext: { plan_ref: sourceData.query.plan_ref, task_ref: taskRef }, onNavigate() {} },
    { Content: { ...baseStates, 8: { item, report: reports[0], title: '报工提示', x: 180, y: 120 }, 11: [taskRef] } });
  assert.strictEqual(reportNoReads - readsBeforeHover, 0, 'Hovering with 1,000 reports and details open must read report_no 0 extra times');
  const selectAfter = h.walk(hoverTree).find(node => node.type === 'select' && node.props['aria-label'] === '选择报工详情');
  assert.strictEqual(selectAfter.children[1].length, 1000);
} finally {
  h.runtime.React.useMemo = origUseMemo;
}
return true;
""", {'payload': actual, 'query': scope})['result'] is True
    token = actual['meta']['snapshot_ref']
    with monkeypatch.context() as patch:
        from core.services.workbench.execution.ledger import ExecutionLedgerService

        patch.setattr(ExecutionLedgerService, 'workspace_projection',
                      lambda *args, **kwargs: pytest.fail('Related chain without resource filter projected ledger'))
        related = read(client, ACTUAL + '/chain', **scope, snapshot_ref=token, target_task_ref=refs[-1])
    assert related['data']['critical_chain']['task_refs'] == refs
    case.conn.execute("UPDATE Schedule SET end_time='2026-09-09T09:30:00' WHERE version=2 AND op_id=?", (case.op_id,))
    case.conn.commit()
    for path, extra in ((ACTUAL + '/chain', dict(target_task_ref=refs[-1])),
                        (ACTUAL + '/export', dict(format='csv'))):
        response = client.get(path, query_string=dict(scope, snapshot_ref=token, **extra))
        assert response.status_code == 409 and response.get_json()['error']['code'] == 'snapshot_stale'


def test_field_scoped_page_write_and_files_keep_same_snapshot(ledger_case, monkeypatch, record_property):
    from core.services.workbench.execution.field_workspace import FieldWorkspaceService

    case = ledger_case
    plan_ref, refs = _three_tasks(case)
    api = FieldAPI(case)
    scope = dict(plan_ref=plan_ref, range_start='2026-09-09T08:00:00', range_end='2026-09-09T14:00:00')
    original, calls = FieldWorkspaceService.cohort, []

    def cohort(reader, values):
        calls.append(values)
        return original(reader, values)

    with monkeypatch.context() as patch:
        patch.setattr(FieldWorkspaceService, 'cohort', cohort)
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
    located = api.read(**scope, size=1, task_ref=refs[1], operation_ref=second['data']['tasks'][0]['operation_ref'])
    assert located['data']['page']['number'] == 2 and located['data']['tasks'][0]['task_ref'] == refs[1]
    mismatch = api.client.get(FIELD + '/tasks', query_string=dict(scope, size=1, task_ref=refs[1],
        operation_ref=first['data']['tasks'][0]['operation_ref']))
    assert mismatch.status_code == 409 and mismatch.get_json()['error']['code'] == 'constraint_conflict'
    response = api.client.get(FIELD + '/files/template', query_string=dict(scope, snapshot_ref=token))
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data)); assert book.worksheets[0].max_row == 4; book.close()
    changed = api.client.get(FIELD + '/tasks', query_string=dict(scope, range_end='2026-09-09T12:00:00', snapshot_ref=token))
    assert changed.status_code == 409 and changed.get_json()['error']['code'] == 'snapshot_stale'
    api.create(case.values(2), first['data']['tasks'][0])
    for path, extra in ((FIELD + '/tasks', dict(page=2, size=1)),
                        (FIELD + '/files/template', {}), (FIELD + '/files/export', {})):
        response = api.client.get(path, query_string=dict(scope, snapshot_ref=token, **extra))
        assert response.status_code == 409 and response.get_json()['error']['code'] == 'snapshot_stale'


def test_field_files_reuse_one_ledger_for_cohort_and_import_preparation(ledger_case, monkeypatch):
    from core.services.workbench.execution.ledger import ExecutionLedgerService
    from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository
    from tests.workbench.field_workspace_support import BASE, success

    case = ledger_case
    plan_ref, _ = _three_tasks(case)
    api = FieldAPI(case)
    api.create(task=api.task(plan_ref=plan_ref))
    reading = api.read()
    calls = {"ledgers": 0, "reports": 0, "current_plans": 0}
    initialize, reports = ExecutionLedgerService.__init__, WorkbenchExecutionRepository.reports

    def ledger(loaded, *args, **kwargs):
        calls["ledgers"] += 1
        initialize(loaded, *args, **kwargs)
        provider = loaded.current_plan_provider

        def current(conn):
            calls["current_plans"] += 1
            return provider(conn)

        loaded.current_plan_provider = current

    def report_rows(repo, refs, limit):
        calls["reports"] += 1
        return reports(repo, refs, limit)

    monkeypatch.setattr(ExecutionLedgerService, "__init__", ledger)
    monkeypatch.setattr(WorkbenchExecutionRepository, "reports", report_rows)
    exported = api.client.get(BASE + "/files/export", query_string={**reading["data"]["scope"],
        "snapshot_ref": reading["meta"]["snapshot_ref"]})
    assert exported.status_code == 200
    assert calls == {"ledgers": 1, "reports": 1, "current_plans": 1}
    calls.update(ledgers=0, reports=0, current_plans=0)
    preview = success(api.upload(exported.data, reading))
    assert preview["data"]["can_confirm"] and preview["data"]["summary"]["unchanged"] == 1
    assert calls == {"ledgers": 1, "reports": 1, "current_plans": 1}
    calls.update(ledgers=0, reports=0, current_plans=0)
    confirmed = success(api.client.post(BASE + "/files/confirm", json=api.confirm_body(preview)))
    assert confirmed["result"] == "unchanged"
    assert calls == {"ledgers": 1, "reports": 1, "current_plans": 1}

    # Choosing an old plan does not make its tasks the current writable tasks.
    case.plan(3, [case.op_id])
    current_task = case.task(3, case.op_id)
    calls.update(ledgers=0, reports=0, current_plans=0)
    old = api.read(plan_ref=plan_ref)["data"]["tasks"][0]
    assert old["execution"]["comparison_task_ref"] == old["task_ref"]
    assert old["execution"]["current_task_ref"] == current_task != old["task_ref"]
    assert old["execution"]["write_context"]["capabilities"]["create"] is False
    assert calls == {"ledgers": 1, "reports": 1, "current_plans": 1}
    calls.update(ledgers=0, reports=0, current_plans=0)
    actual = read(app_for(case).test_client(), ACTUAL, plan_ref=plan_ref)["data"]["items"][0]
    assert actual["execution"]["comparison_task_ref"] == old["task_ref"]
    assert actual["execution"]["current_task_ref"] == current_task
    assert calls == {"ledgers": 1, "reports": 1, "current_plans": 1}


def test_internal_execution_cohort_uses_actual_endpoint_budget(ledger_case):
    case = ledger_case
    plan_ref, _ = _three_tasks(case)
    # A full internal cohort may exceed the plan endpoint's 8 MiB while the
    # paged field response remains small. Only the actual HTTP output is bounded.
    case.conn.execute('UPDATE BatchOperations SET op_type_name=? WHERE id=?', ('工序' * (2 * 1024 * 1024), case.op_id))
    case.conn.commit()
    before = all_rows(case.conn)
    reader = queries.WorkbenchPlanQueryService(case.conn)
    with reader.read_snapshot():
        data = reader.execution_workspace(PlanReadScope(plan_ref))
    assert data['task_count'] == 3 and data['tasks_complete'] is True
    client = app_for(case).test_client()
    field = client.get(FIELD + '/tasks', query_string=dict(plan_ref=plan_ref, size=1, page=2))
    assert field.status_code == 200 and field.get_json()['data']['page']['total'] == 3
    oversized = client.get(FIELD + '/tasks', query_string=dict(plan_ref=plan_ref, size=1, page=1))
    assert oversized.status_code == 413 and oversized.get_json()['error']['code'] == 'query_too_large'
    assert all_rows(case.conn) == before


def test_actual_large_plan_applies_finish_batch_and_overlap_before_ledger(ledger_case, monkeypatch):
    from flask import g

    from core.services.workbench.execution import actual_gantt
    from core.services.workbench.plan.read_context import PlanReadContext

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
    enriched, enrich_rows = [], PlanReadContext._enrich_rows

    def enrich(context, entry, prepared):
        enriched.append(len(prepared))
        return enrich_rows(context, entry, prepared)

    monkeypatch.setattr(PlanReadContext, "_enrich_rows", enrich)
    original = actual_gantt.ExecutionLedgerService.workspace_projection

    def project(ledger, ref, tasks, *, include_history=True, include_resources=True):
        projected.append(len(tasks))
        return original(
            ledger, ref, tasks, include_history=include_history, include_resources=include_resources
        )

    monkeypatch.setattr(actual_gantt.ExecutionLedgerService, 'workspace_projection', project)
    monkeypatch.setattr(queries.WorkbenchPlanQueryService, 'execution_workspace',
                        lambda *args, **kwargs: pytest.fail('Actual reconstructed an execution workspace'))
    app = app_for(case)

    @app.before_request
    def trace():
        g.db.set_trace_callback(statements.append)

    client = app.test_client()
    scopes = [({'plan_finish_date_from': '2026-09-09', 'plan_finish_date_to': '2026-09-09'}, 200),
              ({'batch_ids': json.dumps([batches[0]])}, 100),
              ({'range_start': '2026-09-09T08:00:00', 'range_end': '2026-09-09T08:10:00'}, 10)]
    for scope, expected in scopes:
        statements.clear()
        response = client.get(ACTUAL, query_string=dict(plan_ref=plan_ref, **scope))
        assert response.status_code == 200, response.get_json()
        data = response.get_json()['data']
        assert data['task_count'] == len(data['items']) == projected[-1] == expected
        assert data['availability']['state'] == 'available' and data['items_complete'] is True
        assert data['critical_chain']['state'] == 'available'
        assert data['critical_chain']['plan_task_count'] == len(data['critical_chain']['nodes']) == 20000
        assert data['critical_chain']['visible_node_count'] == expected
        source_reads = [' '.join(sql.upper().replace('"', '').split()) for sql in statements]
        assert sum(' FROM SCHEDULE R WHERE R.VERSION = 2 ' in sql for sql in source_reads) == 1
        if scope.get("plan_finish_date_from"):
            enriched.clear()
            with monkeypatch.context() as patch:
                patch.setattr(actual_gantt, "plan_chain", lambda *args, **kwargs: pytest.fail("Export rebuilt the full chain"))
                exported = client.get(ACTUAL + "/export", query_string=dict(plan_ref=plan_ref, format="csv",
                    snapshot_ref=response.get_json()["meta"]["snapshot_ref"], **scope))
            assert exported.status_code == 200, exported.get_json()
            assert exported.headers["X-Workbench-Operation-Count"] == str(expected)
            assert enriched and max(enriched) == expected and sum(enriched) == expected
    response = client.get(ACTUAL, query_string={'plan_ref': plan_ref})
    assert response.status_code == 413 and projected[-1] == 20000
    error = response.get_json()['error']
    assert error['code'] == 'query_too_large' and '现场甘特数据太多' in error['message']
    assert '日期范围' in error['message'] and '批次' in error['message']


def test_actual_resource_filter_keeps_planned_and_reported_owners(ledger_case):
    case = ledger_case
    plan_ref, refs = _three_tasks(case)
    case.conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M2','Reported machine','T1')")
    case.conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M2')")
    case.conn.commit()
    api = FieldAPI(case)
    task = next(row for row in api.read(plan_ref=plan_ref)['data']['tasks'] if row['task_ref'] == refs[0])
    api.create(case.values(2, actual_machine_ref=case.ref('machine', 'M2')), task)
    client = app_for(case).test_client()
    scope = dict(plan_ref=plan_ref, plan_finish_date_from='2026-09-09',
                 plan_finish_date_to='2026-09-09', batch_ids=json.dumps(['B1']), resource_type='machine')
    for key, expected in (('M1', refs), ('M2', refs[:1])):
        data = read(client, ACTUAL, resource_ref=case.ref('machine', key), **scope)['data']
        assert {item['task']['task_ref'] for item in data['items']} == set(expected)


def test_actual_export_skips_chain_and_keeps_workspace_snapshot_and_deviations(ledger_case, monkeypatch):
    from core.services.workbench.execution import actual_gantt
    from core.services.workbench.execution.actual_gantt_scope import ActualGanttScope

    case = ledger_case
    plan_ref, _ = _three_tasks(case)
    service = actual_gantt.ActualGanttService(case.conn)
    scope = ActualGanttScope.parse({"plan_ref": plan_ref})
    with service.read_snapshot():
        full, full_state = service.workspace(scope)
    with service.read_snapshot():
        exported, export_state = service.workspace(scope, include_chain=False)
    assert "critical_chain" in full and "critical_chain" not in exported
    assert full_state == export_state
    actual_gantt.bind_axis_time(exported, "2026-09-10T12:00:00", "snapshot")
    assert all("deviation" in item for item in exported["items"])
    client = app_for(case).test_client()
    listed = read(client, ACTUAL, plan_ref=plan_ref)

    def unused_chain(*args, **kwargs):
        pytest.fail("CSV export rebuilt the unconsumed critical chain")

    monkeypatch.setattr(actual_gantt, "plan_chain", unused_chain)
    response = client.get(ACTUAL + "/export", query_string={"plan_ref": plan_ref, "format": "csv",
        "snapshot_ref": listed["meta"]["snapshot_ref"]})
    assert response.status_code == 200, response.get_json()
    assert response.headers["X-Workbench-Snapshot-Ref"] == listed["meta"]["snapshot_ref"]
    assert response.headers["X-Workbench-Operation-Count"] == "3"


@pytest.mark.parametrize("raw", ('[{"id":"B1","id":"B2"}]', '[NaN]', '[1e999]', '["B1"'))
def test_execution_batch_arguments_reject_duplicate_keys_and_nonfinite_numbers_as_unreadable_json(raw):
    from core.services.workbench.execution.actual_gantt_scope import ActualGanttScope
    from core.services.workbench.execution.field_workspace_scope import normalize_scope

    with pytest.raises(WorkbenchCommandRejected) as actual:
        ActualGanttScope.parse({'plan_ref': 'a' * 48, 'batch_ids': raw})
    assert (actual.value.code, actual.value.status, str(actual.value)) == ('invalid_input', 400, '批次范围必须是 JSON 数组。')
    with pytest.raises(WorkbenchCommandRejected) as field:
        normalize_scope({'batch_ids': raw})
    assert (field.value.code, field.value.status, str(field.value)) == ('invalid_input', 400, '批次范围无效。')
    # The file-preview form scope arrives already decoded, so its list is checked as is.
    assert normalize_scope({'batch_ids': ['B2', 'B1', 'B2']}) == {'batch_ids': ['B1', 'B2']}


def test_actual_gantt_rejects_stale_snapshot_before_projection(ledger_case, monkeypatch):
    from core.services.workbench.execution.actual_gantt import ActualGanttService
    from core.services.workbench.execution.ledger import ExecutionLedgerService

    case = ledger_case
    plan_ref, _ = _three_tasks(case)
    client = app_for(case).test_client()
    token = read(client, ACTUAL, plan_ref=plan_ref)["meta"]["snapshot_ref"]
    case.conn.execute("UPDATE Schedule SET end_time='2026-09-09T09:30:00' WHERE version=2 AND op_id=?", (case.op_id,))
    case.conn.commit()
    monkeypatch.setattr(ActualGanttService, "_planned",
                        lambda *a, **kw: pytest.fail("should not project planned tasks on stale snapshot"))
    monkeypatch.setattr(ExecutionLedgerService, "workspace_projection",
                        lambda *a, **kw: pytest.fail("should not project ledger on stale snapshot"))
    for path, extra in ((ACTUAL, {}), (ACTUAL + "/export", {"format": "csv"})):
        response = client.get(path, query_string={"plan_ref": plan_ref, "snapshot_ref": token, **extra})
        assert response.status_code == 409 and response.get_json()["error"]["code"] == "snapshot_stale"


def test_critical_chain_skips_long_point_event_chain_without_recursion_error():
    from core.services.scheduler.gantt.critical_chain import compute_critical_chain_from_dependencies

    rows = [{"op_code": "op-0", "operation_ref": "ref-0", "start_time": "2026-10-12 08:00", "end_time": "2026-10-12 09:00"}]
    predecessor_ids = {"op-0": []}
    for index in range(1, 1201):
        code = f"op-{index}"
        rows.append({"op_code": code, "operation_ref": f"ref-{index}", "start_time": "2026-10-12 09:00", "end_time": "2026-10-12 09:00"})
        predecessor_ids[code] = [f"op-{index - 1}"]
    rows.append({"op_code": "op-1201", "operation_ref": "ref-1201", "start_time": "2026-10-12 09:00", "end_time": "2026-10-12 10:00"})
    predecessor_ids["op-1201"] = ["op-1200"]

    result = compute_critical_chain_from_dependencies(rows, predecessor_ids, include_points=False)
    assert result["ids"] == ["op-0", "op-1201"]
    assert result["dropped_count"] == 1200
    assert result["critical_chain_partial"] is True
    assert len(result["edges"]) == 1 and result["edges"][0]["from"] == "op-0" and result["edges"][0]["to"] == "op-1201"
