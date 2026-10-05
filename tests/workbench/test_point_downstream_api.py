"""Actual and field consume only persisted, adopted point witnesses."""

import csv
from io import StringIO

from tests.workbench.point_downstream_support import ACTUAL, FIELD, adopted, app_for, read, report
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
