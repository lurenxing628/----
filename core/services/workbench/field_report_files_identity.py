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
            raise WorkbenchCommandRejected('invalid_input', '无法唯一确定批次工序，请使用下载模板中的任务编号。', 422)
        return candidates[0]
    candidates = by_ref.get(value['task_ref'], [])
    if len(candidates) != 1:
        raise WorkbenchCommandRejected('invalid_input', '任务编号在当前范围里没有唯一对应的一条，请重新下载模板；不能用自己编的、过期的或范围外的编号。', 422)
    task = candidates[0]
    expected = identity_values(task)
    if (value['batch_id'] != task['batch_id'] or value['operation_label'] != task['operation_label']
            or value['operation_scope'] != expected['operation_scope']
            or (value['piece_id'] or None) != expected['piece_id']):
        raise WorkbenchCommandRejected('invalid_input', '任务编号和批次、工序、工序范围或单件编号对不上；请保留模板里预填的编号，不要改。', 422)
    return task
