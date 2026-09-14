(function () {
  'use strict';
  const C = window.APSMasterOverviewContract, base = '/api/workbench/v1/master-overview';
  function url(path, scope, token, extra = {}) {
    const query = new URLSearchParams({ scope: JSON.stringify(C.scope(scope)), ...extra });
    if (token) query.set('snapshot_ref', token);
    return base + path + '?' + query.toString();
  }
  function create() {
    return {
      list: async (scope, page, token, signal) => {
        const result = C.list(await window.APSWorkbenchTransport.read(url('', scope, token, { page }), signal), scope, token);
        if (result.data.page.number !== page) C.fail('读到的不是当前这一页，页面内容没有变化。请刷新后重试。'); return result;
      },
      detail: async (scope, selected, section, page, token, signal) => {
        const result = C.detail(await window.APSWorkbenchTransport.read(url('/entities/' + selected.domain + '/' + selected.entity_ref, scope, token, { section, detail_page: page }), signal), scope, selected, section, token);
        if (result.data.page.number !== page) C.fail('读到的不是当前这一页详情，页面内容没有变化。请刷新后重试。'); return result;
      },
      locate: async (scope, selected, token, signal) => {
        if (!C.ref(selected.entity_ref) || !C.domains.some(row => row[0] === selected.domain)) C.fail('定位目标不正确。');
        const result = C.list(await window.APSWorkbenchTransport.read(url('/locate/' + selected.domain + '/' + selected.entity_ref, scope, token), signal));
        if (!result.data.selected || result.data.selected.entity_ref !== selected.entity_ref || result.data.selected.domain !== selected.domain
          || !result.data.rows.some(row => row.ref === selected.entity_ref && row.domain === selected.domain)) C.fail('清单里没有定位到这条资料，页面内容没有变化。请刷新后重试。');
        return result;
      },
      export: (scope, token, count, signal) => download(scope, token, count, signal)
    };
  }
  async function download(scope, token, count, signal) {
    const controller = new AbortController(), abort = () => controller.abort();
    let timedOut = false;
    if (signal) { signal.addEventListener('abort', abort, { once: true }); if (signal.aborted) controller.abort(); }
    const timer = setTimeout(() => { timedOut = true; abort(); }, 20000);
    try {
      const response = await fetch(url('/export', scope, token), { signal: controller.signal, credentials: 'same-origin', headers: { Accept: 'text/csv' } });
      const type = (response.headers.get('content-type') || '').toLowerCase();
      if (!response.ok) {
        const payload = type.includes('application/json') ? await response.json() : null;
        C.fail(payload && payload.error && payload.error.message || '基础资料导出失败，没有开始下载。请刷新后重试。');
      }
      if (!type.startsWith('text/csv') || response.headers.get('X-Workbench-Snapshot-Ref') !== token
        || response.headers.get('X-Workbench-Row-Count') !== String(count)) C.fail('导出范围或数据版本对不上，没有开始下载。请刷新后重试。');
      const filename = scope.view === 'issues' ? '基础资料待维护项.csv' : '基础资料清单.csv';
      return { blob: await response.blob(), filename, count };
    } catch (error) {
      if (timedOut) C.fail('基础资料导出超时，请重试。');
      throw error;
    } finally {
      clearTimeout(timer);
      if (signal) signal.removeEventListener('abort', abort);
    }
  }
  function save(file) {
    const objectUrl = URL.createObjectURL(file.blob), anchor = document.createElement('a');
    anchor.href = objectUrl; anchor.download = file.filename;
    try { document.body.appendChild(anchor); anchor.click(); }
    finally { anchor.remove(); setTimeout(() => URL.revokeObjectURL(objectUrl), 1000); }
  }
  window.APSMasterOverviewAPI = { create, save };
})();
