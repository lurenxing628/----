"""Explicit current-task identity for field files; legacy labels stay fail-closed."""

from core.models.workbench_command import WorkbenchCommandRejected


def identity_values(task):
    return {'task_ref': task['task_ref'],
            'operation_scope': '共同工序' if task['piece_id'] is None else '单件',
            'piece_id': task['piece_id']}


def task_indexes(tasks):
    by_scope, by_ref = {}, {}
    for task in tasks:
        by_scope.setdefault((task['batch_id'], task['operation_label']), []).append(task)
        by_ref.setdefault(task['task_ref'], []).append(task)
    return by_scope, by_ref


def matched_task(row, by_scope, by_ref):
    value = row['values']
    if row['format_version'] == 1:
        candidates = by_scope.get((value['batch_id'], value['operation_label']), [])
        if len(candidates) != 1:
            raise WorkbenchCommandRejected('invalid_input', '批次与工序未唯一匹配当前范围；分件重名不能猜关联。', 422)
        return candidates[0]
    candidates = by_ref.get(value['task_ref'], [])
    if len(candidates) != 1:
        raise WorkbenchCommandRejected('invalid_input', '任务编号未唯一匹配当前读取范围，请重新下载模板；不能使用伪造、过期或范围外编号。', 422)
    task = candidates[0]
    expected = identity_values(task)
    if (value['batch_id'] != task['batch_id'] or value['operation_label'] != task['operation_label']
            or value['operation_scope'] != expected['operation_scope']
            or (value['piece_id'] or None) != expected['piece_id']):
        raise WorkbenchCommandRejected('invalid_input', '任务编号与批次、工序、工序范围或单件编号不一致；请保留模板预填身份。', 422)
    return task
