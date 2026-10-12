"""Actual and field consume only persisted, adopted point witnesses."""

import csv
from io import StringIO

import pytest

from core.models.workbench_run_baseline import RunCandidateBaselineScope
from core.services.workbench.run.candidate_analysis import read_candidate_analysis
from core.services.workbench.run.candidate_baseline import WorkbenchRunCandidateBaselineQueryService
from core.services.workbench.run.worker import WorkbenchRunWorker
from tests.workbench.point_downstream_support import ACTUAL, FIELD, adopted, app_for, read, report
from tests.workbench.run_candidate_support import compute
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401


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
    assert next(row for row in rows if row['报工编号'] == unknown['report_ref'])['本次数量'] == ''
    assert next(row for row in rows if row['报工编号'] == known['report_ref'])['有效加工工时（小时）'] == '1.25'


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
