(function () {
  'use strict';
  const options = [['overdue', '超期批次'], ['utilization', '资源负荷 / 利用率'], ['downtime', '停机影响'], ['official-review', '正式执行复盘 / Excel']];
  function Catalog({ api, scope, snapshot }) {
    const { Button, ErrorBox, useRead, Page } = window.ReportControls;
    const [kind, setKind] = React.useState('overdue'), [draft, setDraft] = React.useState({}), [filter, setFilter] = React.useState({}),
      [table, setTable] = React.useState({ page: 1, size: 10 }), [notice, setNotice] = React.useState(''), [error, setError] = React.useState(null), [downloading, setDownloading] = React.useState(false);
    const base = kind === 'official-review' ? { ...window.ReportAPI.scope(scope), snapshot_ref: snapshot, topic: 'delivery' } : { source: 'production', plan_ref: scope.plan_ref, ...filter };
    const input = { ...base, ...table };
    const request = useRead(signal => api.catalog(kind, input, signal), kind + JSON.stringify(input));
    const response = request.result;
    function choose(next) { setKind(next); setFilter({}); setDraft({}); setTable({ page: 1, size: 10 }); setError(null); setNotice(''); }
    async function download() {
      setDownloading(true); setError(null);
      try { await api.download('/api/workbench/v1/reports/' + kind + '/export', { ...input, snapshot_ref: response.meta.snapshot_ref, format: 'xlsx' }); setNotice('完整范围 XLSX 已交给浏览器下载。'); }
      catch (failure) { setError(failure); } finally { setDownloading(false); }
    }
    return <section aria-label="其他报表列表"><div className="rw-table-heading"><div className="rw-filters" style={{ marginLeft: 0 }}>
      <label>报表<select aria-label="其他报表" value={kind} onChange={event => choose(event.target.value)}>{options.map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
      {['utilization', 'downtime'].includes(kind) && <><label>统计起日<input type="date" aria-label="统计起日" value={draft.window_date_from || ''} onChange={event => setDraft(old => ({ ...old, window_date_from: event.target.value }))} /></label>
        <label>止日<input type="date" aria-label="统计止日" value={draft.window_date_to || ''} onChange={event => setDraft(old => ({ ...old, window_date_to: event.target.value }))} /></label>
        <Button icon="search" aria-label="读取报表范围" onClick={() => { setFilter(draft); setTable({ page: 1, size: 10 }); }} /></>}
      {kind !== 'official-review' && <><label>搜索<input type="search" aria-label="搜索报表" value={draft.query || ''} onChange={event => setDraft(old => ({ ...old, query: event.target.value }))} onKeyDown={event => { if (event.key === 'Enter') { setFilter(draft); setTable({ page: 1, size: 10 }); } }} /></label>
        <Button icon="search" aria-label="搜索报表结果" onClick={() => { setFilter(draft); setTable({ page: 1, size: 10 }); }} />
        {response && <><label>排序<select aria-label="报表排序列" value={table.sort || response.data.page.sort[0].field} onChange={event => setTable(old => ({ ...old, page: 1, sort: event.target.value, snapshot_ref: response.meta.snapshot_ref }))}>{response.data.columns.map(column => <option key={column.key} value={column.key}>{column.label}</option>)}</select></label>
          <label>顺序<select aria-label="报表排序方向" value={table.direction || 'asc'} onChange={event => setTable(old => ({ ...old, page: 1, direction: event.target.value, snapshot_ref: response.meta.snapshot_ref }))}><option value="asc">升序</option><option value="desc">降序</option></select></label></>}</>}
      <Button transfer="export" busy={downloading} disabled={!response || request.busy} reason={response && !response.data.page.total ? '当前范围没有可导出的结果。' : ''} onClick={download}>导出 XLSX</Button></div></div>
      <ErrorBox error={request.error || error} />{notice && <p role="status">{notice}</p>}{request.busy && <p role="status">正在读取报表…</p>}
      {response && <><p>{response.data.data_gaps.join(' ')}{response.data.scope.window_date_from ? ' 统计范围：' + response.data.scope.window_date_from + ' 至 ' + response.data.scope.window_date_to : ''}</p>
        <window.ReportTable.Table data={kind === 'official-review' ? { ...response.data, topic: 'delivery' } : response.data} />
        <Page page={response.data.page} onChange={patch => setTable(old => ({ ...old, ...patch, snapshot_ref: response.meta.snapshot_ref }))} busy={request.busy} /></>}
    </section>;
  }
  window.ReportCatalog = Catalog;
})();
