(function () {
  'use strict';
  const C = window.APSMasterOverviewContract, T = window.APSWorkbenchTransport, base = '/api/workbench/v1/master-overview';
  const query = (scope, token, extra = {}) => ({ scope: JSON.stringify(scope), ...extra, snapshot_ref: token });
  async function list(scope, page, token, signal) {
    const normalized = C.scope(scope);
    const result = C.list(await T.read(base, query(normalized, token, { page }), { signal, timeout: 20000 }), normalized, token);
    if (result.data.page.number !== page) C.fail('读到的不是当前这一页，页面内容没有变化。请刷新后重试。'); return result;
  }
  async function detail(scope, selected, section, page, token, signal) {
    const normalized = C.scope(scope);
    const result = C.detail(await T.read(base + '/entities/' + selected.domain + '/' + selected.entity_ref, query(normalized, token, { section, detail_page: page }),
      { signal, timeout: 20000 }), normalized, selected, section, token);
    if (result.data.page.number !== page) C.fail('读到的不是当前这一页详情，页面内容没有变化。请刷新后重试。'); return result;
  }
  async function locate(scope, selected, token, signal) {
    if (!C.ref(selected.entity_ref) || !C.domains.some(row => row[0] === selected.domain)) C.fail('定位目标不正确。');
    const result = C.list(await T.read(base + '/locate/' + selected.domain + '/' + selected.entity_ref, query(C.scope(scope), token), { signal, timeout: 20000 }));
    if (!result.data.selected || result.data.selected.entity_ref !== selected.entity_ref || result.data.selected.domain !== selected.domain
      || !result.data.rows.some(row => row.ref === selected.entity_ref && row.domain === selected.domain)) C.fail('清单里没有定位到这条资料，页面内容没有变化。请刷新后重试。');
    return result;
  }
  // 文件名与后缀已由 transport.download 校验；这里只核对快照与行数两个业务头。
  async function exportFile(scope, token, signal) {
    const file = await T.download(base + '/export', query(C.scope(scope), token), { signal, timeout: 20000, types: [T.types.csv] });
    const countText = file.header('X-Workbench-Row-Count'), count = Number(countText);
    if (file.header('X-Workbench-Snapshot-Ref') !== token
      || countText === null || !/^(0|[1-9][0-9]*)$/.test(countText) || !Number.isSafeInteger(count)) C.fail('导出范围或数据版本对不上，没有开始下载。请刷新后重试。');
    return { blob: file.blob, filename: file.filename, count };
  }
  function save(file) {
    T.saveBlob(file.filename, file.blob);
  }
  window.APSMasterOverviewAPI = { list, detail, locate, export: exportFile, save };
})();
