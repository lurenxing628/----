(function () {
  'use strict';
  const root = 'entities/batch', xlsx = { types: [window.APSWorkbenchTransport.types.xlsx] };
  // 批次页与分批面板共享 'batches' 会话键，保持待确认状态与已确认的拒绝/完成态在重挂载时一致。
  function create() {
    const api = window.APSResourceAPI.create('batches'), C = window.APSBatchContract;
    const entity = ref => { if (!C.ref(ref)) throw window.APSResourceContract.failure('这个批次已失效，请返回批次列表重新选择。'); return root + '/' + ref; };
    return {
      pendingKey: api.pendingKey, readPending: api.readPending, savePending: api.savePending, clearPending: api.clearPending, lookup: api.lookup,
      list(kind, scope, signal) { if (kind !== 'batch') throw window.APSResourceContract.failure('批次类别不正确。'); return api.preview(root + '/query', scope, signal); },
      detail(kind, ref, signal) { if (kind !== 'batch') throw window.APSResourceContract.failure('批次类别不正确。'); return api.query(entity(ref), {}, signal); },
      operationChoices(batchRef, operationRef, signal) { return api.query(root + '/choices', { batch_ref: batchRef, operation_ref: operationRef }, signal); },
      choices(signal) { return api.query(root + '/choices', {}, signal); },
      materialChoices(scope, signal) { return api.query('entities/material', { ...scope, status: 'active', size: 20 }, signal); },
      facets(scope, field, signal) { return api.preview(root + '/facets', { scope, field }, signal); },
      selection(scope, signal) { return api.preview(root + '/selection', scope, signal); },
      importPreview(file, mode, scope, snapshot, signal) {
        const body = new FormData(); body.set('file', file); body.set('mode', mode); body.set('scope', JSON.stringify(scope)); body.set('snapshot_ref', snapshot);
        return api.preview(root + '/import-preview', body, signal);
      },
      exportPreview(selection, scope, refs, signal) { return api.preview(root + '/export-preview', { selection, scope, ...(selection === 'selected' ? { refs } : {}) }, signal); },
      downloadTemplate(signal) { return api.download(root + '/template', {}, signal, xlsx); },
      downloadExport(exportRef, signal) { return api.download(root + '/export', { export_ref: exportRef }, signal, xlsx); },
      preview(action, ref, input, scope, snapshot, signal) {
        if (action === 'bulk') return api.preview(root + '/bulk-preview', { input, scope, snapshot_ref: snapshot }, signal);
        if (['sync', 'split'].includes(action)) return api.preview(entity(ref) + '/' + action + '-preview', { input, snapshot_ref: snapshot }, signal);
        throw window.APSResourceContract.failure('批次预检操作不正确。');
      },
      async command(kind, action, ref, body) {
        if (kind !== 'batch' || !C.actions.includes(action)) throw window.APSResourceContract.failure('批次操作不正确。');
        let path;
        if (action === 'create') {
          if (ref !== null) throw window.APSResourceContract.failure('新增批次不能绑定已有批次。');
          path = root + '/create';
        } else if (['bulk_confirm', 'import_confirm'].includes(action)) {
          if (ref !== body.input.preview_ref) throw window.APSResourceContract.failure('批量确认与预检结果不一致。');
          path = root + (action === 'bulk_confirm' ? '/bulk-confirm' : '/import-confirm');
        } else path = entity(ref) + '/' + (['sync_confirm', 'split_confirm'].includes(action) ? action.replace('_', '-') : action);
        const result = await api.execute(path, body);
        C.receipt(result, action, ref);
        return result;
      }
    };
  }
  window.APSBatchAPI = { create };
})();
