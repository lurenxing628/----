import React from './shared/runtime/react.js';
import { Button, ErrorBox, useRead, Page } from './ReportControls.jsx';
import ReportAPI from './ReportAPI.js';
import WorkbenchTerms from './WorkbenchTerms.js';
import { Table } from './ReportTable.jsx';

const options = [['overdue', '超期批次'], ['utilization', '资源负荷 / 利用率'], ['downtime', '停机影响'], ['official-review', '正式执行复盘 / Excel']];

function Catalog({ scope, snapshot }) {
  const [kind, setKind] = React.useState('overdue'), [draft, setDraft] = React.useState({}), [filter, setFilter] = React.useState({}),
    [table, setTable] = React.useState({ page: 1, size: 10 }), [notice, setNotice] = React.useState(''), [error, setError] = React.useState(null), [downloading, setDownloading] = React.useState(false);
  const lastColumns = React.useRef([]), lastSort = React.useRef({ field: '', direction: 'asc' });
  const base = kind === 'official-review' ? { ...ReportAPI.scope(scope), snapshot_ref: snapshot, topic: 'delivery' } : { source: 'production', plan_ref: scope.plan_ref, ...filter };
  const input = { ...base, ...table };
  const request = useRead(signal => ReportAPI.catalog(kind, input, signal), kind + JSON.stringify(input));
  const response = request.result;
  if (response) { lastColumns.current = response.data.columns; lastSort.current = response.data.page.sort[0]; }
  const columns = response ? response.data.columns : lastColumns.current;
  function choose(next) { lastColumns.current = []; lastSort.current = { field: '', direction: 'asc' }; setKind(next); setFilter({}); setDraft({}); setTable({ page: 1, size: 10 }); setError(null); setNotice(''); }
  async function download() {
    setDownloading(true); setError(null); setNotice('');
    try { const result = await ReportAPI.download('/api/workbench/v1/reports/' + kind + '/export', { ...input, snapshot_ref: response.meta.snapshot_ref, format: 'xlsx' }); setNotice(WorkbenchTerms.download_started(result.filename) + '（完整范围）。'); }
    catch (failure) { setError(failure); } finally { setDownloading(false); }
  }
  const empty = { title: '当前范围没有结果', hint: kind === 'official-review' ? '当前正式计划里没有符合范围的工序。' : '调整统计日期或搜索条件后重新查询。' };
  return <section aria-label="其他报表列表"><div className="rw-table-heading"><div className="rw-filters rw-filters-start">
    <label>报表<select aria-label="其他报表" value={kind} onChange={event => choose(event.target.value)}>{options.map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
    {['utilization', 'downtime'].includes(kind) && <><label>统计起日<input type="date" aria-label="统计起日" value={draft.window_date_from || ''} onChange={event => setDraft(old => ({ ...old, window_date_from: event.target.value }))} /></label>
      <label>止日<input type="date" aria-label="统计止日" value={draft.window_date_to || ''} onChange={event => setDraft(old => ({ ...old, window_date_to: event.target.value }))} /></label>
      <Button icon="search" aria-label="读取报表范围" onClick={() => { setFilter(draft); setTable(old => ({ ...old, page: 1, snapshot_ref: undefined })); }} /></>}
    {kind !== 'official-review' && <><label>搜索<input type="search" aria-label="搜索报表" value={draft.query || ''} onChange={event => setDraft(old => ({ ...old, query: event.target.value }))} onKeyDown={event => { if (event.key === 'Enter') { setFilter(draft); setTable(old => ({ ...old, page: 1, snapshot_ref: undefined })); } }} /></label>
      <Button icon="search" aria-label="搜索报表结果" onClick={() => { setFilter(draft); setTable(old => ({ ...old, page: 1, snapshot_ref: undefined })); }} />
      <label>排序<select aria-label="报表排序列" value={table.sort || lastSort.current.field} disabled={request.busy || !response} onChange={event => setTable(old => ({ ...old, page: 1, sort: event.target.value, snapshot_ref: response ? response.meta.snapshot_ref : old.snapshot_ref }))}>{columns.map(column => <option key={column.key} value={column.key}>{column.label}</option>)}</select></label>
      <label>顺序<select aria-label="报表排序方向" value={table.direction || lastSort.current.direction || 'asc'} disabled={request.busy || !response} onChange={event => setTable(old => ({ ...old, page: 1, direction: event.target.value, snapshot_ref: response ? response.meta.snapshot_ref : old.snapshot_ref }))}><option value="asc">升序</option><option value="desc">降序</option></select></label></>}
    <Button transfer="export" busy={downloading} disabled={!response || request.busy} reason={response && !response.data.page.total ? '当前范围没有可导出的结果。' : ''} onClick={download}>导出 XLSX</Button></div></div>
    <ErrorBox error={request.error || error} />{notice && <p role="status">{notice}</p>}{request.busy && <p role="status">正在读取报表…</p>}
    {response && <><p>{response.data.data_gaps.join(' ')}{response.data.scope.window_date_from ? ' 统计范围：' + response.data.scope.window_date_from + ' 至 ' + response.data.scope.window_date_to : ''}</p>
      <Table data={kind === 'official-review' ? { ...response.data, topic: 'delivery' } : response.data} empty={empty} /></>}
    <Page page={response ? response.data.page : { number: table.page, size: table.size }} onChange={patch => setTable(old => ({ ...old, ...patch, snapshot_ref: response ? response.meta.snapshot_ref : old.snapshot_ref }))} busy={request.busy || !response} />
  </section>;
}

const ReportCatalog = Catalog;

export { ReportCatalog, Catalog };
export default ReportCatalog;
