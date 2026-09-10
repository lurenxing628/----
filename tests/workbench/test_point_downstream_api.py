"""Actual and field consume only persisted, adopted point witnesses."""

import csv
import json
from io import StringIO

import pytest

from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION
from core.services.workbench.actual_gantt import ActualGanttService
from core.services.workbench.actual_gantt_scope import ActualGanttScope
from core.services.workbench.field_workspace import FieldWorkspaceService
from tests.workbench.ea_zero_duration_support import adoption_service
from tests.workbench.point_downstream_support import ACTUAL, FIELD, adopted, app_for, read, report
from tests.workbench.trial_support import snapshot
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401


@pytest.mark.parametrize('batches', [[], 'B1', {'batch_id': 'B1'}, [7], None])
def test_field_preserves_explicit_empty_and_bad_batch_scope_rejection(trial_case, batches):
    identity = adopted(trial_case)
    client = app_for(trial_case).test_client()
    before = snapshot(trial_case.conn)
    response = client.get(FIELD + '/tasks', query_string={'source': 'production', 'plan_ref': identity['plan']['plan_ref'],
                                                         'batch_ids': json.dumps(batches)})
    assert response.status_code == 400
    assert response.get_json()['error']['code'] == 'invalid_input'
    assert response.get_json()['error']['message'] == '批次范围须为明确的非空批次号列表。'
    assert snapshot(trial_case.conn) == before


def test_field_all_batch_omission_and_explicit_nonempty_scope_keep_original_identity(trial_case):
    identity = adopted(trial_case)
    client = app_for(trial_case).test_client()
    before = snapshot(trial_case.conn)
    scope = {'source': 'production', 'plan_ref': identity['plan']['plan_ref']}
    all_batches = read(client, FIELD + '/tasks', **scope)
    selected = read(client, FIELD + '/tasks', batch_ids=json.dumps(['B1']), **scope)
    assert 'batch_ids' not in all_batches['data']['scope']
    assert selected['data']['scope']['batch_ids'] == ['B1']
    for result in (all_batches, selected):
        assert result['data']['scope']['plan_ref'] == identity['plan']['plan_ref']
        assert result['data']['tasks'][0]['task_ref'] == identity['task']['task_ref']
        assert result['data']['tasks'][0]['operation_ref'] == identity['task']['operation_ref']
    assert snapshot(trial_case.conn) == before


@pytest.mark.parametrize('setup,unit,quantity,point', [(0, 0, 3, True), (0, 7, 0, True), (2, 7, 0, False)])
def test_real_adoption_services_keep_identity_quantities_and_state(trial_case, setup, unit, quantity, point):
    case = trial_case
    identity = adopted(case, setup=setup, unit=unit, quantity=quantity)
    assert CURRENT_SCHEMA_VERSION == 31
    before = snapshot(case.conn)
    for service in (ActualGanttService(case.conn), FieldWorkspaceService(case.conn)):
        with service.read_snapshot():
            if isinstance(service, ActualGanttService):
                data, _ = service.workspace(ActualGanttScope(identity['plan']['plan_ref']))
                task, execution = data['items'][0]['task'], data['items'][0]['execution']
                assert (data['plan_span']['start'] == data['plan_span']['end']) is point
            else:
                data, _ = service.cohort({'plan_ref': identity['plan']['plan_ref']})
                task = data['tasks'][0]
                execution = task['execution']
            assert task['task_ref'] == identity['task']['task_ref']
            assert task['operation_ref'] == identity['task']['operation_ref']
            assert (task.get('event_kind') == 'point') is point
            if point:
                assert task['duration_seconds'] == 0 and task['occupies_resources'] is False
            assert execution['target_quantity'] == quantity
            assert execution['execution_state'] == 'unreported'
            assert execution['confirmed_finish'] is None
            assert execution['reports'] == [] and execution['records_complete'] is False
    assert snapshot(case.conn) == before


@pytest.mark.parametrize('low,high,count', [
    ('2026-09-09T08:00:00', '2026-09-09T09:00:00', 1),
    ('2026-09-09T07:00:00', '2026-09-09T08:00:00', 0),
    ('2026-09-09T08:00:01', '2026-09-09T09:00:00', 0),
    ('2026-09-09T07:00:00', '2026-09-09T08:00:01', 1)])
def test_real_point_http_half_open_range_and_exports(trial_case, low, high, count):
    identity = adopted(trial_case)
    client = app_for(trial_case).test_client()
    scope = {'plan_ref': identity['plan']['plan_ref'], 'range_start': low, 'range_end': high}
    before = snapshot(trial_case.conn)
    actual = read(client, ACTUAL, **scope)
    field = read(client, FIELD + '/tasks', **scope)
    assert actual['data']['task_count'] == field['data']['page']['total'] == count
    assert actual['data']['plan_span']['start'] == actual['data']['plan_span']['end']
    assert actual['data']['axis_span']['start'] < actual['data']['axis_span']['end']
    response = client.get(ACTUAL + '/export', query_string=dict(scope, snapshot_ref=actual['meta']['snapshot_ref'], format='csv'))
    assert response.status_code == 200, response.get_data(as_text=True)
    rows = list(csv.DictReader(StringIO(response.data.decode('utf-8-sig'))))
    assert len(rows) == count
    if count:
        assert rows[0]['计划事件类型'] == 'point'
        assert rows[0]['计划时长秒'] == '0' and rows[0]['计划占用资源'] == 'False'
        assert rows[0]['任务引用'] == identity['task']['task_ref']
        assert rows[0]['计划开工'] == rows[0]['计划完工']
    assert snapshot(trial_case.conn) == before


def test_real_point_report_http_retains_intervals_unknowns_and_readback(trial_case):
    identity = adopted(trial_case)
    client = app_for(trial_case).test_client()
    known = report(client, identity)
    instant = report(client, identity, quantity=0, start='2026-09-09T09:10:00', end='2026-09-09T09:10:00', hours=None)
    unknown = report(client, identity, quantity=None, start='2026-09-09T09:20:00', end=None, hours=None)
    actual = read(client, ACTUAL, plan_ref=identity['plan']['plan_ref'])
    row, = actual['data']['items']
    assert row['task'] == identity['task']
    assert row['execution']['execution_state'] == 'partial'
    assert row['execution']['remaining_quantity'] is None
    assert row['execution']['unknown_record_count'] == 1
    by_ref = {r['report_ref']: r for r in row['execution']['reports']}
    assert by_ref[known['report_ref']]['effective_processing_hours'] == 1.25
    assert by_ref[known['report_ref']]['actual_start'] < by_ref[known['report_ref']]['actual_end']
    assert by_ref[instant['report_ref']]['completed_quantity'] == 0
    assert by_ref[instant['report_ref']]['effective_processing_hours'] is None
    assert by_ref[unknown['report_ref']]['completed_quantity'] is None
    assert by_ref[unknown['report_ref']]['actual_end'] is None
    field = read(client, FIELD + '/tasks', plan_ref=identity['plan']['plan_ref'])
    assert field['data']['tasks'][0]['event_kind'] == 'point'
    response = client.get(ACTUAL + '/export', query_string={'plan_ref': identity['plan']['plan_ref'], 'format': 'csv', 'snapshot_ref': actual['meta']['snapshot_ref']})
    assert response.status_code == 200
    rows = list(csv.DictReader(StringIO(response.data.decode('utf-8-sig'))))
    assert len(rows) == 3 and all(row['计划事件类型'] == 'point' for row in rows)
    assert next(row for row in rows if row['报工引用'] == unknown['report_ref'])['本次数量'] == ''
    assert next(row for row in rows if row['报工引用'] == known['report_ref'])['有效加工小时'] == '1.25'


def test_point_report_read_does_not_open_public_adoption(trial_case):
    identity = adopted(trial_case)
    service = adoption_service(trial_case.conn)
    assert service.point_rendering_enabled is True
    from core.services.workbench.run_candidate_adoption import WorkbenchRunCandidateAdoptionService

    public = WorkbenchRunCandidateAdoptionService(trial_case.conn, integration_enabled=True)
    assert public.point_rendering_enabled is False
    client = app_for(trial_case).test_client()
    actual = read(client, ACTUAL, plan_ref=identity['plan']['plan_ref'])
    assert actual['data']['items'][0]['execution']['execution_state'] == 'unreported'


def test_real_point_analytics_read_keeps_scheduled_identity(trial_case):
    identity = adopted(trial_case)
    client = app_for(trial_case).test_client()
    response = read(client, '/api/workbench/v1/analytics', plan_ref=identity['plan']['plan_ref'], topic='delivery')
    assert response['data']['page']['total'] == 1
    row, = response['data']['rows']
    assert row['operation_ref'] == identity['task']['operation_ref']
    assert row['planned_start'] == row['planned_end'] == identity['task']['start']


def test_mixed_plan_last_point_is_in_full_cohort_but_not_exclusive_upper_bound(trial_case):
    case = trial_case
    case.operation(seq=2, setup_hours=0, unit_hours=0)
    case.conn.commit()
    identity = adopted(case, setup=1, unit=0)
    client = app_for(case).test_client()
    scope = {'plan_ref': identity['plan']['plan_ref']}
    full = read(client, ACTUAL, **scope)['data']
    assert full['task_count'] == 2
    point = next(item['task'] for item in full['items'] if item['task'].get('event_kind') == 'point')
    assert point['start'] == point['end'] == full['plan_span']['end']
    interval = next(item['task'] for item in full['items'] if item['task'].get('event_kind') != 'point')
    scope.update(range_start=interval['start'], range_end=point['start'])
    assert read(client, ACTUAL, **scope)['data']['task_count'] == 1
    assert read(client, FIELD + '/tasks', **scope)['data']['page']['total'] == 1
    scope.pop('range_start')
    scope.pop('range_end')
    assert read(client, FIELD + '/tasks', **scope)['data']['page']['total'] == 2


@pytest.mark.parametrize('topic', ['delivery', 'quality', 'records', 'machines', 'people'])
def test_real_point_all_analytics_topics_after_report(trial_case, topic):
    identity = adopted(trial_case)
    client = app_for(trial_case).test_client()
    report(client, identity)
    response = read(client, '/api/workbench/v1/analytics', plan_ref=identity['plan']['plan_ref'], topic=topic)
    assert response['data']['page']['total'] == 1
    row, = response['data']['rows']
    if topic in ('delivery', 'quality'):
        assert row['planned_start'] == row['planned_end'] == identity['task']['start']
        assert row['operation_ref'] == identity['task']['operation_ref']


def test_point_is_complete_only_after_real_complete_report(trial_case):
    identity = adopted(trial_case)
    client = app_for(trial_case).test_client()
    known = report(client, identity, quantity=3)
    data = read(client, ACTUAL, plan_ref=identity['plan']['plan_ref'])['data']
    execution = data['items'][0]['execution']
    assert execution['execution_state'] == 'complete'
    assert execution['confirmed_finish'] == '2026-09-09T09:30:00'
    assert execution['reports'][0]['report_ref'] == known['report_ref']
    assert execution['completion_basis'] == 'complete_reports'
    assert execution['reports'][0]['effective_processing_hours'] == 1.25
