"""Actual and field consume only persisted, adopted point witnesses."""

import csv
from datetime import datetime, timedelta
from io import StringIO

import pytest

from core.models.workbench_run_baseline import RunCandidateBaselineScope
from core.services.workbench.run.candidate_analysis import read_candidate_analysis
from core.services.workbench.run.candidate_baseline import WorkbenchRunCandidateBaselineQueryService
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.plan_transport_support import run_probe
from tests.workbench.point_downstream_support import ACTUAL, FIELD, adopted, app_for, read, report
from tests.workbench.run_candidate_support import compute, corrupt_update
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401


def test_real_point_report_http_retains_intervals_unknowns_and_readback(trial_case, monkeypatch):
    from core.services.workbench.facts import candidate_archive

    identity = adopted(trial_case)
    client = app_for(trial_case).test_client()
    catalog = read(client, '/api/workbench/v1/plans', collection='history')['data']['plans']
    assert next(row for row in catalog if row['plan_ref'] == identity['plan']['plan_ref'])['capabilities']['view']
    scope_reads, require_scope = [], candidate_archive.require_candidate_scope

    def scope_once(run, candidate, *args, **kwargs):
        scope_reads.append(candidate['candidate_ref'])
        return require_scope(run, candidate, *args, **kwargs)

    with monkeypatch.context() as point_read:
        point_read.setattr(candidate_archive, 'require_candidate_scope', scope_once)
        plan = read(client, '/api/workbench/v1/plans/' + identity['plan']['plan_ref'] + '/workspace')
    assert scope_reads == [identity['candidate_ref']]
    task, = plan['data']['tasks']
    assert task['event_kind'] == 'point' and task['start'] == task['end']
    assert task['task_ref'] == identity['task']['task_ref']
    known = report(client, identity)
    instant = report(client, identity, quantity=0, start='2026-09-09T09:10:00', end='2026-09-09T09:10:00', hours=None)
    unknown = report(client, identity, quantity=None, start='2026-09-09T09:20:00', end=None, hours=None)
    actual = read(client, ACTUAL, plan_ref=identity['plan']['plan_ref'])
    row, = actual['data']['items']
    assert row['task'] == identity['task']
    assert row['execution']['execution_state'] == 'partial'
    assert row['execution']['remaining_quantity'] is None
    assert row['execution']['unknown_record_count'] == 1
    assert row['deviation']['finish_deviation_minutes'] is None and row['deviation']['finish_late'] is False
    assert row['deviation']['unclosed'] is True
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
    assert next(row for row in rows if row['报工编号'] == unknown['report_ref'])['本次数量'] == ''
    assert next(row for row in rows if row['报工编号'] == known['report_ref'])['有效加工工时（小时）'] == '1.25'


def test_real_point_one_microsecond_http_preserves_capacity_and_full_dto(trial_case, tmp_path):
    identity = adopted(trial_case)
    task = identity['task']
    scope = {'range_start': task['start'],
             'range_end': (datetime.fromisoformat(task['start']) + timedelta(microseconds=1)).isoformat()}
    plan_ref = identity['plan']['plan_ref']
    response = read(app_for(trial_case).test_client(),
                    '/api/workbench/v1/plans/' + plan_ref + '/workspace', **scope)
    data = response['data']
    point, = data['tasks']
    assert point['task_ref'] == task['task_ref'] and point['event_kind'] == 'point'
    assert point['start'] == point['end'] == scope['range_start']
    assert {key: data['time_scope'][key] for key in scope} == scope
    calendar = data['projections']['calendar']
    capacity = 1e-6 / 3600.0
    hours_fields = ('available_hours', 'effective_hours', 'normal_available_hours', 'normal_effective_hours',
                    'urgent_available_hours', 'urgent_effective_hours')
    assert {row['kind'] for row in calendar['resources']} == {'machine', 'operator'}
    for row in [calendar['global']] + calendar['resources']:
        assert all(row[field] == capacity for field in hours_fields)
    capacities = {row['resource_ref']: row['available_hours'] for row in calendar['resources']}
    occupancy = data['projections']['occupancy']['resources']
    assert {row['kind'] for row in occupancy} == {'machine', 'operator'}
    for row in occupancy:
        assert row['available_hours'] == capacities[row['resource_ref']] == capacity
        assert row['utilization'] == 0
        assert all(row[field] == 0 for field in ('arranged_hours', 'occupied_hours', 'overlap_hours',
                   'excess_arranged_hours', 'available_occupied_hours', 'outside_available_hours',
                   'capacity_shortfall_hours', 'available_overlap_hours'))
    fixture = {'name': 'real adopted point one-microsecond scope', 'kind': 'workspace',
               'plan_ref': plan_ref, 'scope': scope, 'payload': response}
    assert run_probe(tmp_path, [fixture])['checks'] == 1


def test_point_source_capacity_rejection_retains_original_413(trial_case):
    case = trial_case
    identity = adopted(case)
    corrupt_update(case.conn, 'WorkbenchRunJobs',
        'UPDATE WorkbenchRunJobs SET facts_json=? WHERE run_ref='
        '(SELECT run_ref FROM WorkbenchRunCandidates WHERE candidate_ref=?)',
        ('{}' + ' ' * (64 * 1024 * 1024), identity['candidate_ref']))
    changes = case.conn.total_changes
    client = app_for(case).test_client()
    for path, query in (
        ('/api/workbench/v1/plans/' + identity['plan']['plan_ref'] + '/workspace', {}),
        ('/api/workbench/v1/plans', {'collection': 'history'}),
    ):
        response = client.get(path, query_string=query)
        assert response.status_code == 413
        assert response.get_json()['error']['code'] == 'candidate_capacity_exceeded'
    assert case.conn.total_changes == changes


@pytest.mark.parametrize('current_unit_hours', [0, 0.5])
def test_candidate_comparison_keeps_original_adopted_point_after_hours_change(trial_case, current_unit_hours):
    case = trial_case
    adopted(case)
    case.conn.execute('UPDATE BatchOperations SET unit_hours=? WHERE id=?', (current_unit_hours, case.op_id))
    case.conn.commit()
    accepted = case.accept(key='point-baseline-rerun-0001', settings=case.settings(start_date='2026-09-10'))
    result = WorkbenchRunWorker(case.conn).execute(accepted['run_ref'])
    assert result['state'] == 'complete', result
    ref = result['candidates'][0]['candidate_ref']
    data, _ = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(RunCandidateBaselineScope(ref))
    row, = data['comparisons']
    previous, = row['baseline_segments']
    assert previous['event_kind'] == 'point' and previous['interval_comparable']
    assert previous['elapsed_hours'] == 0 and previous['occupies_resources'] is False
    assert row['status'] == 'matched' and row['comparison_available']
    assert row['delta']['start_hours'] == 24 and row['delta']['elapsed_hours'] == current_unit_hours * 3
    analysis, _ = read_candidate_analysis(case.conn, ref)
    assert analysis['operations']['unknown_operation_refs'] == []
    assert analysis['operations']['changed_operation_refs'] == [row['operation_ref']]
    assert analysis['metrics']['changed_operation_count']['value'] == 1
    assert analysis['before_metrics']['overdue_count']['unknown_count'] == 0
    assert analysis['before_metrics']['total_tardiness_hours']['value'] == 0
    assert analysis['batches'][0]['before']['risk'] == 'on_time'
    assert 'schedule_time_invalid' not in analysis['batches'][0]['before']['issues']


def test_equal_legacy_interval_is_not_a_point_when_current_hours_become_zero(trial_case):
    case = trial_case
    case.plan(1, [case.op_id], start='2026-09-09T08:00:00', end='2026-09-09T08:00:00')
    case.conn.execute('UPDATE BatchOperations SET unit_hours=0 WHERE id=?', (case.op_id,))
    case.conn.commit()
    _, refs = compute(case, case.settings(start_date='2026-09-10'))
    data, _ = WorkbenchRunCandidateBaselineQueryService(case.conn).baseline(RunCandidateBaselineScope(refs[0]))
    row, = data['comparisons']
    previous, = row['baseline_segments']
    assert not previous['interval_comparable'] and 'event_kind' not in previous
    assert row['status'] == 'not_comparable' and not row['comparison_available']
    assert any(gap['field'] == 'point_evidence' and gap['code'] == 'source_missing' for gap in previous['data_gaps'])
    analysis, _ = read_candidate_analysis(case.conn, refs[0])
    assert analysis['before_metrics']['overdue_count']['unknown_count'] == 1
    assert 'schedule_time_invalid' in analysis['batches'][0]['before']['issues']


def test_held_adopted_point_carries_its_witness_into_runtime_seeds(trial_case):
    """不重排时段保留已采用的零工时安排：见证在冻结前缀校验时取得并随 seed 带出，不再事后补挂。"""
    from core.algorithm_contracts.schedule_point_evidence import PointSeedResult, SchedulePointEvidence
    from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_result_item
    from tests.workbench.run_compute_support import compute_run

    case = trial_case
    point = datetime.fromisoformat(adopted(case)['task']['start'])
    successor = case.operation(seq=2)
    window = {'start': point.isoformat(timespec='minutes'),
              'end': (point + timedelta(hours=1)).isoformat(timespec='minutes')}
    result = compute_run(case.conn, case.settings(hold_window=window), case.projections())
    assert result.schedule_input.frozen_op_ids == {case.op_id}
    seed, = [row for row in result.schedule_input.seed_results if row['op_id'] == case.op_id]
    assert seed['seed_source'] == 'freeze_window' and seed['start_time'] == seed['end_time'] == point
    assert type(seed['_point_evidence']) is SchedulePointEvidence
    assert type(coerce_seed_result_item(seed, idx=0)) is PointSeedResult
    for payload in result.candidate_payloads.values():
        rows = {row.op_id: row for row in payload.schedule_rows}
        assert rows[case.op_id].start_time == rows[case.op_id].end_time == point
        assert rows[successor].start_time >= point
