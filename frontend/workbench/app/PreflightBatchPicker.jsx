import React from './shared/runtime/react.js';
import { Button, ErrorBox } from './PreflightControls.jsx';
import WorkbenchFormat from './WorkbenchFormat.js';
import { WorkbenchReference } from './WorkbenchReferences.jsx';
import ResourceControls, { EmptyState, Pager } from './ResourceControls.jsx';
import APSBatchContract from './BatchContract.js';
import { useQuery } from './shared/session/query.js';
import PreflightAPI from './PreflightAPI.js';

const baseScope = () => ({ query: '', page: 1, size: 20, sort: 'business_code', direction: 'asc', column_filters: { status: ['pending', 'scheduled', 'processing', 'completed'] } });
function DueDate({ value }) {
  try { return <span>交期：{WorkbenchFormat.date(value)}</span>; }
  catch (error) {
    if (!(error instanceof TypeError)) throw error;
    return <span>交期原值待核对<WorkbenchReference entries={{ '原交期': value, '格式说明': error.message }} /></span>;
  }
}
function PreflightBatchPicker({ selected, onChange, disabled }) {
  const [scope, setScope] = React.useState(baseScope), [query, setQuery] = React.useState('');
  // error 只放选择动作（勾选、快捷全选）的错误；批次列表的读取错误是 read.error。换范围就是一次新读取，同时撤下上一次动作的错误。
  const [error, setError] = React.useState(null), [selecting, setSelecting] = React.useState(false);
  const serial = React.useRef(0), selectionController = React.useRef(null);
  const read = useQuery(signal => PreflightAPI.list(scope, signal), [scope]);
  React.useEffect(() => () => { serial.current++; if (selectionController.current) selectionController.current.abort(); }, []);
  const result = read.result, loading = read.loading;
  const data = result && result.data, snapshot = result && result.meta.snapshot_ref, chosen = new Set(selected);
  const busy = disabled || loading || selecting;
  function rescope(next) { setError(null); setScope(next); }
  function filter(patch) { rescope(old => ({ ...old, ...patch, page: 1, snapshot_ref: undefined })); }
  function toggle(ref) {
    if (busy) return;
    onChange(chosen.has(ref) ? selected.filter(item => item !== ref) : selected.concat(ref));
  }
  async function select(mode) {
    if (busy || mode === 'filtered' && !snapshot) return;
    const id = ++serial.current, controller = new AbortController(); selectionController.current = controller;
    setSelecting(true); setError(null);
    try {
      let requestScope = { ...scope, snapshot_ref: snapshot };
      if (mode !== 'filtered') {
        const next = { ...baseScope(), ...(mode === 'ready' ? { ready_status: 'yes' } : {}) };
        const listed = await PreflightAPI.list(next, controller.signal);
        requestScope = { ...next, snapshot_ref: listed.meta.snapshot_ref };
      }
      const result = await PreflightAPI.selection(requestScope, controller.signal), refs = APSBatchContract.selection(result, requestScope.snapshot_ref);
      if (id === serial.current) onChange(refs);
    } catch (problem) { if (id === serial.current) setError(problem); }
    finally { if (id === serial.current) setSelecting(false); }
  }
  const visible = data ? data.entities : [], visibleSet = new Set(visible.map(row => row.ref)), hidden = selected.filter(ref => !visibleSet.has(ref)).length;
  return <section className="pf-picker" aria-label="选择排产批次">
    <form className="pf-tools" onSubmit={event => { event.preventDefault(); if (!busy) filter({ query }); }}>
      <ResourceControls.Search aria-label="搜索排产批次" placeholder="批次号、图号、零件名" value={query} disabled={busy} onChange={event => setQuery(event.target.value)} />
      <Button icon="search" type="submit" disabled={busy}>搜索</Button>
      <label className="wb-inline-filter"><span>齐套</span><select aria-label="批次齐套筛选" disabled={busy} value={scope.ready_status || ''} onChange={event => filter({ ready_status: event.target.value || undefined })}>
        <option value="">全部</option>{APSBatchContract.ready.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select></label><Button icon="refresh-cw" aria-label="刷新批次范围" disabled={busy} onClick={() => filter({})}>刷新范围</Button>
    </form>
    <div className="pf-tools"><Button disabled={busy} onClick={() => select('all')}>全部待排</Button><Button disabled={busy} onClick={() => select('ready')}>仅齐套</Button>
      <Button disabled={busy || !snapshot} onClick={() => select('filtered')}>全选当前筛选</Button><Button icon="x" disabled={disabled || selecting || !selected.length} onClick={() => onChange([])}>清除选择</Button>
      <span aria-live="polite">已选 {selected.length} 批{hidden > 0 ? ' · 含非当前页 ' + hidden + ' 批' : ''}</span></div>
    <ErrorBox error={read.error} /><ErrorBox error={error} />{(read.error || error) && <Button icon="refresh-cw" disabled={disabled || loading || selecting} onClick={() => filter({})}>刷新批次</Button>}
    {loading || selecting ? <EmptyState kind="loading" title={selecting ? '正在核对全部选择范围' : '正在读取批次'} /> : data && !visible.length ? <EmptyState kind="filtered" title="当前筛选没有待排批次" hint="调整关键词或齐套筛选后再试。" action={<Button onClick={() => { setQuery(''); rescope(baseScope()); }}>清除筛选</Button>} /> : null}
    {!loading && data && <div className="pf-picker-list">{visible.map(row => <label className="pf-picker-row" key={row.ref}>
      <input type="checkbox" aria-label={'选择 ' + row.business_code} checked={chosen.has(row.ref)} disabled={busy} onChange={() => toggle(row.ref)} />
      <strong>{row.business_code}</strong><span>{row.relationships.part_no} · {row.label}</span><span>{row.relationships.operation_count} 道工序</span>
      <DueDate value={row.fields.due_date} /><span>优先级：{APSBatchContract.label('priority', row.fields.priority)}</span>
      <span>{APSBatchContract.label('status', row.status)} · {APSBatchContract.readyLabel(row.display_ready_status)}</span>
    </label>)}</div>}
    {data && <Pager page={data.page} size={scope.size} sizes={[20, 50, 100]} unit="批" label="批次" busy={busy}
      onSize={size => filter({ size })} onPage={page => rescope(old => ({ ...old, page, snapshot_ref: snapshot }))} />}
  </section>;
}
export { PreflightBatchPicker };
export default PreflightBatchPicker;
