"""Field-only scope normalization. Pagination never changes the selected cohort."""

import json
import re
from datetime import datetime

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.zero_duration_evidence import overlaps

STATES = ('unreported', 'started', 'partial', 'paused', 'exception', 'complete')
FILTERS = ('plan_ref', 'query', 'state', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref', 'range_start', 'range_end', 'batch_ids')
PARAMETERS = FILTERS + ('page', 'size', 'snapshot_ref', 'source', 'task_ref', 'operation_ref')


def invalid(message):
    raise WorkbenchCommandRejected('invalid_input', message, 400)


def _references(result):
    for key in ('plan_ref', 'resource_ref'):
        if key in result and (type(result[key]) is not str or not re.fullmatch('[0-9a-f]{48}', result[key])):
            invalid('计划或资源永久引用无效。')
    if result.get('resource_type') not in (None, 'machine', 'operator'):
        invalid('现场资源类型只能为设备或人员。')
    if 'resource_ref' in result and 'resource_type' not in result:
        invalid('资源引用必须同时提供资源类型。')


def _search(result):
    if result.get('state', 'all') not in ('all',) + STATES:
        invalid('报工状态筛选无效。')
    if result.get('state') == 'all':
        del result['state']
    if 'query' in result:
        if type(result['query']) is not str or len(result['query']) > 200 or '\x00' in result['query']:
            invalid('搜索内容无效。')
        result['query'] = result['query'].strip()


def _dates(result, keys, *, times=False):
    start, end = [result.get(key) for key in keys]
    if bool(start) != bool(end):
        invalid('计划日期或时间范围起止须同时提供。')
    pattern = r'\d{4}-\d\d-\d\d' + (r'T\d\d:\d\d:\d\d' if times else '')
    fmt = '%Y-%m-%dT%H:%M:%S' if times else '%Y-%m-%d'
    for value in filter(None, (start, end)):
        try:
            if type(value) is not str or not re.fullmatch(pattern, value):
                raise ValueError()
            datetime.strptime(value, fmt)
        except ValueError as exc:
            raise WorkbenchCommandRejected('invalid_input', '计划日期或时间范围无效。', 400) from exc
    if start and (start > end or times and start == end):
        invalid('计划范围起止顺序无效。')


def _batches(result):
    if 'batch_ids' not in result:
        return
    try:
        ids = json.loads(result['batch_ids']) if type(result['batch_ids']) is str else result['batch_ids']
    except (ValueError, TypeError) as exc:
        raise WorkbenchCommandRejected('invalid_input', '批次范围无效。', 400) from exc
    if type(ids) is not list or not 1 <= len(ids) <= 5000 or any(type(item) is not str or not item or len(item) > 200 for item in ids):
        invalid('批次范围须为明确的非空批次号列表。')
    result['batch_ids'] = sorted(set(ids))


def normalize_scope(value):
    if type(value) is not dict or set(value) - set(PARAMETERS):
        invalid('现场范围包含未知参数，未忽略筛选。')
    if value.get('source', 'production') != 'production':
        invalid('现场记录仅接受真实生产来源。')
    if value.get('operation_ref') and not value.get('task_ref'):
        invalid('执行工序辅助核验须绑定明确任务，不能替代任务引用。')
    result = {key: item for key, item in value.items() if item is not None and item != '' and key in FILTERS}
    _references(result)
    _search(result)
    _dates(result, ('plan_finish_date_from', 'plan_finish_date_to'))
    _dates(result, ('range_start', 'range_end'), times=True)
    _batches(result)
    return result


def page_input(value):
    result = []
    for key, default, upper in [('page', 1, 100000), ('size', 20, 100)]:
        raw = value.get(key, default)
        if type(raw) not in (str, int) or not re.fullmatch('[1-9][0-9]*', str(raw)) or int(raw) > upper:
            invalid('页码或每页数量无效。')
        result.append(int(raw))
    return tuple(result)


def matches(task, scope):
    if scope.get('batch_ids') and task['batch_id'] not in scope['batch_ids']:
        return False
    if scope.get('range_start') and not overlaps(task['planned_start'], task['planned_end'], scope['range_start'], scope['range_end']):
        return False
    if scope.get('state') and task['execution']['execution_state'] != scope['state']:
        return False
    if scope.get('query'):
        searchable = [task['batch_id'], task['operation_label'], task['part_name'], task.get('piece_id'),
                      task.get('planned_machine_label'), task.get('planned_operator_label')]
        for report in task['execution']['reports']:
            searchable.extend(report.get(key) for key in ('report_no', 'actual_machine_label', 'actual_operator_label'))
        if scope['query'].casefold() not in ' '.join(value for value in searchable if isinstance(value, str)).casefold():
            return False
    if scope.get('plan_finish_date_from') and not scope['plan_finish_date_from'] <= task['planned_end'][:10] <= scope['plan_finish_date_to']:
        return False
    return _matches_resource(task, scope)


def _matches_resource(task, scope):
    if not scope.get('resource_ref'):
        return True
    kind, ref = scope['resource_type'], scope['resource_ref']
    return task['planned_' + kind + '_ref'] == ref or any(row['actual_' + kind + '_ref'] == ref for row in task['execution']['reports'])
