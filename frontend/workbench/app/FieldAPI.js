(function () {
  'use strict';
  function initial(value = {}) {
    const scope = { ...(value.scope || {}) };
    delete scope.snapshot_ref;
    return { ...scope, ...(value.plan_ref ? { plan_ref: value.plan_ref } : {}),
      task_ref: value.task_ref || value.entity_ref, operation_ref: value.operation_ref,
      page: value.table ? value.table.page : undefined, size: value.table ? value.table.size : 20 };
  }
  function checked(result, input) {
    const value = window.FieldContract.query(result, 'list'), data = value.data;
    const invalid = input.snapshot_ref && value.meta.snapshot_ref !== input.snapshot_ref
      || input.plan_ref && (!data.scope || data.scope.plan_ref !== input.plan_ref)
      || input.page !== undefined && !input.task_ref && data.page.number !== input.page;
    if (invalid) throw window.APSResourceContract.failure('读到的现场数据与原计划、页码或数据版本不一致，没有替换原来的任务。');
    return value;
  }
  async function readView(api, input, signal) {
    if (input.snapshot_ref) return checked(await api.list(input, signal), input);
    if (input.operation_ref && !input.task_ref) throw window.APSResourceContract.failure('核对原工序时缺少明确任务，没有改选其他任务。');
    if (input.page !== undefined && (!Number.isInteger(input.page) || input.page < 1 || input.page > 100000))
      throw window.APSResourceContract.failure('现场原页码无效，未切换到其他页。');
    const firstQuery = { ...input, page: 1 };
    delete firstQuery.snapshot_ref; delete firstQuery.task_ref; delete firstQuery.operation_ref;
    const first = checked(await api.list(firstQuery, signal), firstQuery);
    if (!input.task_ref && (input.page === undefined || input.page === 1)) return first;
    const bound = { ...first.data.scope, page: input.page || 1, size: input.size,
      task_ref: input.task_ref, operation_ref: input.operation_ref, snapshot_ref: first.meta.snapshot_ref };
    const result = checked(await api.list(bound, signal), bound);
    const original = input.task_ref && result.data.tasks.find(task => task.task_ref === input.task_ref);
    if (input.page !== undefined && result.data.page.number !== input.page || input.task_ref && !original
      || original && input.operation_ref && original.operation_ref !== input.operation_ref
      || JSON.stringify(result.data.scope) !== JSON.stringify(first.data.scope))
      throw window.APSResourceContract.failure('原现场任务、页码或筛选范围已不匹配，没有切换到其他任务。');
    return result;
  }
  function create() {
    const api = window.APSResourceAPI.create('execution'), C = window.FieldContract;
    const queryScope = scope => ({ ...scope, ...(Array.isArray(scope.batch_ids) ? { batch_ids: JSON.stringify(scope.batch_ids) } : {}) });
    function target(group, ref) { if (!C.ref(ref)) throw window.APSResourceContract.failure('报工或任务编号无效。'); return 'execution/' + group + '/' + ref; }
    return {
      readPending: api.readPending, savePending: api.savePending, clearPending: api.clearPending, lookup: api.lookup,
      list(scope, signal) { return api.query('execution/tasks', queryScope(scope), signal); },
      detail(ref, scope, signal) { return api.query(target('tasks', ref), queryScope(scope), signal); },
      choices(kind, scope, signal) { return api.choices(kind, scope, signal); },
      previewFile(file, scope, snapshot, signal) {
        const body = new FormData(); body.set('file', file); body.set('scope', JSON.stringify(scope)); body.set('snapshot_ref', snapshot);
        return api.preview('execution/files/preview', body, signal);
      },
      download(mode, scope, snapshot, signal) { return api.download('execution/files/' + mode, { ...queryScope(scope), snapshot_ref: snapshot }, signal); },
      downloadErrors(previewRef, signal) { return api.download('execution/files/errors', { preview_ref: previewRef }, signal); },
      async command(kind, action, ref, body, signal) {
        if (kind !== 'execution' || !['create', 'supplement', 'correct', 'import_confirm'].includes(action)) throw window.APSResourceContract.failure('现场操作不正确。');
        const path = action === 'create' ? target('tasks', ref) + '/reports' : action === 'import_confirm' ? 'execution/files/confirm' : target('reports', ref) + '/' + action;
        if (action === 'import_confirm' && ref !== body.input.preview_ref) throw window.APSResourceContract.failure('确认与原预检不匹配。');
        return api.execute(path, body, signal);
      }
    };
  }
  window.FieldAPI = { create, initial, readView };
})();
