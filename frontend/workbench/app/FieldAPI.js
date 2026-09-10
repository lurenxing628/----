(function () {
  'use strict';
  function create() {
    const api = window.APSResourceAPI.create('execution'), C = window.FieldContract;
    const queryScope = scope => ({ ...scope, ...(Array.isArray(scope.batch_ids) ? { batch_ids: JSON.stringify(scope.batch_ids) } : {}) });
    function target(group, ref) { if (!C.ref(ref)) throw window.APSResourceContract.failure('报工或任务引用无效。'); return 'execution/' + group + '/' + ref; }
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
  window.FieldAPI = { create };
})();
