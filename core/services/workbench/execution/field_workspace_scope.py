"""Field-only scope normalization. Pagination never changes the selected cohort."""

import re
from datetime import datetime

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_load_limits import MAX_WINDOW_BATCHES, too_many_batches
from core.shared.refs import is_ref
from core.shared.strict_parse import parse_bounded_positive_int

STATES = ('unreported', 'started', 'partial', 'complete')
FILTERS = ('plan_ref', 'query', 'state', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref', 'range_start', 'range_end', 'batch_ids')
PARAMETERS = FILTERS + ('page', 'size', 'snapshot_ref', 'source', 'task_ref', 'operation_ref')


def invalid(message):
    raise WorkbenchCommandRejected('invalid_input', message, 400)


def _references(result):
    for key in ('plan_ref', 'resource_ref'):
        if key in result and not is_ref(result[key]):
            invalid('计划或资源的编号不对，请刷新后重新选择。')
    if result.get('resource_type') not in (None, 'machine', 'operator'):
        invalid('现场资源类型只能为设备或人员。')
    if 'resource_ref' in result and 'resource_type' not in result:
        invalid('选了具体设备或人员，就要同时选资源类型。')


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
    if (start is None) != (end is None):
        invalid('计划日期或时间范围起止须同时提供。')
    pattern = r'\d{4}-\d\d-\d\d' + (r'T\d\d:\d\d:\d\d' if times else '')
    fmt = '%Y-%m-%dT%H:%M:%S' if times else '%Y-%m-%d'
    for value in (item for item in (start, end) if item is not None):
        try:
            if type(value) is not str or not re.fullmatch(pattern, value):
                raise ValueError()
            datetime.strptime(value, fmt)
        except ValueError as exc:
            raise WorkbenchCommandRejected('invalid_input', '计划日期或时间范围无效。', 400) from exc
    if start is not None and (start > end or times and start == end):
        invalid('计划范围起止顺序无效。')


def _batches(result):
    if 'batch_ids' not in result:
        return
    ids = result['batch_ids']
    if type(ids) is list and len(ids) > MAX_WINDOW_BATCHES:
        invalid(too_many_batches(MAX_WINDOW_BATCHES))
    if type(ids) is not list or not ids or any(type(item) is not str or not item or len(item) > 200 for item in ids):
        invalid('批次范围须为明确的非空批次号列表。')
    result['batch_ids'] = sorted(set(ids))


def normalize_scope(value):
    """The JSON-decoded read body or file-preview scope: only ``PARAMETERS``; ``FILTERS`` are returned normalized."""
    if type(value) is not dict or set(value) - set(PARAMETERS):
        invalid('查询条件无效，请清除筛选后重试。')
    if value.get('source', 'production') != 'production':
        invalid('现场记录仅接受真实生产来源。')
    if any(value.get(key) is not None and type(value[key]) is not str for key in ('task_ref', 'operation_ref')):
        invalid('要核对的任务或工序编号不对，请刷新后重新选择。')
    if value.get('operation_ref') and not value.get('task_ref'):
        invalid('按工序核对时要同时指定具体任务，只给工序不够。')
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
        parsed = parse_bounded_positive_int(value.get(key, default), max_value=upper, allow_str=False)
        if parsed is None:
            invalid('页码或每页数量无效。')
        result.append(parsed)
    return tuple(result)

