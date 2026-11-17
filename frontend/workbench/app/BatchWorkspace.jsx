import React from './shared/runtime/react.js';
import B from './BatchContract.js';
import S from './shared/session/command-session.js';
import APSBatchAPI from './BatchAPI.js';
import { useQuery } from './shared/session/query.js';
import { Button, Modal, ErrorBox, Icon, Pager } from './ResourceControls.jsx';
import { Field } from './BatchControls.jsx';
import WorkbenchGuards from './WorkbenchGuards.js';
import WorkbenchPageContext from './WorkbenchPageContext.jsx';
import { Feedback } from './ResourceForms.jsx';
import BatchDetail from './BatchDetail.jsx';
import BatchTable from './BatchTable.jsx';
import BatchForms from './BatchForms.jsx';
import BatchOperationEditor from './BatchOperationEditor.jsx';
import BatchMaterialEditor from './BatchMaterialEditor.jsx';
import BatchFiles from './BatchFiles.jsx';
import { failure, object, ref48 } from './shared/contract/kit.js';

const defaults = { query: '', page: 1, size: 20, sort: 'business_code', direction: 'asc', column_filters: {} };
const emptyBulk = { priority: '', due_date: '', remark: '' };
const scopeKeys = ['query', 'page', 'size', 'sort', 'direction', 'column_filters', 'status', 'ready_status', 'focus', 'batch_ids'];
// 查看范围读不进来时页面会退回默认范围，提示按“发生了什么 → 哪些没变 → 点哪里”写。
const refilter = '请点「清除全部筛选」重新查询。', fallbackList = '，已按默认范围显示批次列表。';
function readScope(value) {
  if (!object(value) || Object.keys(value).some(key => !scopeKeys.includes(key))) throw failure('查看范围里有不支持的项。' + refilter);
  const scope = { ...defaults, ...value };
  const sorts = B.columns.map(row => row[0]).filter(key => key !== 'progress');
  if (typeof scope.query !== 'string' || scope.query.length > 200 || !Number.isSafeInteger(scope.page) || scope.page < 1 || scope.page > 1000000
      || !Number.isSafeInteger(scope.size) || scope.size < 1 || scope.size > 100 || !sorts.includes(scope.sort) || !['asc', 'desc'].includes(scope.direction)
      || ![undefined, null, '', ...B.statuses.map(row => row[0])].includes(scope.status)
      || ![undefined, null, '', ...B.ready.map(row => row[0])].includes(scope.ready_status)
      || ![undefined, null, '', 'gaps', 'unready'].includes(scope.focus)) throw failure('查看范围或页码不正确。' + refilter);
  if (scope.batch_ids != null && (!Array.isArray(scope.batch_ids) || scope.batch_ids.some(key => typeof key !== 'string' || !key)))
    throw failure('要定位的批次清单不正确。' + refilter);
  if (!object(scope.column_filters) || Object.keys(scope.column_filters).some(key => !sorts.includes(key))) throw failure('列筛选条件里有不支持的列。' + refilter);
  for (const values of Object.values(scope.column_filters)) {
    if (!Array.isArray(values) || values.length > 5000 || values.some(value => value !== null && typeof value !== 'string'
        && !(typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= Number.MAX_SAFE_INTEGER))) throw failure('列筛选的取值不正确。' + refilter);
  }
  const result = {};
  for (const [key, item] of Object.entries(scope)) {
    if (item !== undefined) result[key] = item;
  }
  return result;
}
// 键集、定位与恢复查看的互斥、return_to 信封已由 WorkbenchNavigation.admit 按受控导航声明准入；这里核对取值。
// 返回入口和其他页面一样放在顶层 return_to：排产检查只带 view（回去时恢复排产页自己的状态），值班台带上离开时的 context。
function readContext(context) {
  // 侧栏直接进入时 main.jsx 传空对象，按默认范围显示。
  if (!Object.keys(context).length) return { scope: { ...defaults }, selected: [], opened: null, sort: null, returnTarget: null };
  if (context.entity_ref !== undefined && !ref48(context.entity_ref)) throw failure('要打开的批次已失效' + fallbackList);
  const view = context.read_view;
  if (view !== undefined && (!object(view) || Object.keys(view).some(key => !['scope', 'selected_refs', 'entity_ref', 'sort_state'].includes(key))))
    throw failure('上次的查看状态无法恢复' + fallbackList);
  const scope = readScope(view ? view.scope : { ...defaults, focus: context.focus, batch_ids: context.batchIds });
  const selected = view && view.selected_refs !== undefined ? view.selected_refs : [];
  if (!Array.isArray(selected) || !selected.every(ref48) || new Set(selected).size !== selected.length) throw failure('上次勾选的批次已失效' + fallbackList);
  const located = context.entity_ref !== undefined ? context.entity_ref : context.batch_ref !== undefined ? context.batch_ref : null;
  const opened = view && view.entity_ref !== undefined ? view.entity_ref : located;
  if (opened !== null && !ref48(opened)) throw failure('上次打开的批次已失效' + fallbackList);
  if (context.batch_ref !== undefined && context.batch_ref !== opened) throw failure('批次来源已失效' + fallbackList);
  const sort = view && view.sort_state !== undefined ? view.sort_state : null;
  if (sort !== null && (!object(sort) || Object.keys(sort).some(key => !['key', 'direction'].includes(key))
      || sort.key !== scope.sort || sort.direction !== scope.direction)) throw failure('批次排序状态与范围不一致。');
  return { scope, selected, opened, sort, returnTarget: context.return_to === undefined ? null : context.return_to };
}
function BatchWorkspace({ initialContext, onNav }) {
  const [initial] = React.useState(() => { try { return readContext(initialContext); } catch (error) { return { ...readContext({}), error }; } });
  const command = S.useCommand(APSBatchAPI), alive = React.useRef(true), serial = React.useRef(0);
  const [deferred, setDeferred] = React.useState(() => Object.keys(initialContext).length > 0 && command.phase !== 'idle');
  const [scope, setScope] = React.useState(initial.scope);
  const [query, setQuery] = React.useState(initial.scope.query), [selected, setSelected] = React.useState(initial.selected);
  const [opened, setOpened] = React.useState(() => deferred ? null : initial.opened);
  const [dialog, setDialog] = React.useState(null), [error, setError] = React.useState(null), [busy, setBusy] = React.useState(false);
  const [revision, setRevision] = React.useState(0), [sort, setSort] = React.useState(initial.sort), [bulk, setBulk] = React.useState(emptyBulk);
  const bulkGuard = WorkbenchGuards.useDirtyGuard({ dirty: !!dialog && dialog.type === 'bulk' && Object.values(bulk).some(Boolean),
    locked: !!dialog && dialog.type === 'bulk' && busy, message: '批量修改条件尚未确认，离开会放弃本次修改。' });
  React.useEffect(() => { alive.current = true; return () => { alive.current = false; serial.current++; }; }, []);
  const list = useQuery(async signal => {
    return B.list(await APSBatchAPI.list('batch', scope, signal), scope);
  }, [scope, revision], { enabled: !initial.error });
  const data = list.result && list.result.data, snapshot = list.result && list.result.meta.snapshot_ref;
  const entityRefs = React.useMemo(() => data ? new Set(data.entities.map(row => row.ref)) : null, [data]);
  const blocked = !!initial.error || command.locked || busy || !!dialog;
  const rememberedScope = Object.fromEntries(scopeKeys.filter(key => scope[key] !== undefined).map(key => [key, scope[key]]));
  WorkbenchPageContext.useSnapshot({ read_view: { scope: rememberedScope, selected_refs: selected, entity_ref: opened, sort_state: sort },
    ...(initial.returnTarget ? { return_to: initial.returnTarget } : {}) },
    !!data && !deferred && command.phase === 'idle' && !busy && !dialog
    && list.result.meta.source === 'production' && (!opened || entityRefs.has(opened)));
  function filter(patch) { setScope(current => ({ ...current, ...patch, page: 1, snapshot_ref: undefined })); }
  function clearFilters() { setQuery(''); filter({ query: '', status: undefined, ready_status: undefined, column_filters: {}, focus: undefined, batch_ids: undefined }); }
  function close() { if (command.locked || !command.reset()) return; setDialog(null); setBulk(emptyBulk); setError(null); }
  async function closeBulk() { if (!busy && await WorkbenchGuards.confirmLeave({ owner: bulkGuard })) close(); }
  function committed(receipt) {
    // 只有删除类回执（批量删除、文件导入）带 deleted_refs。
    const deleted = receipt.data.deleted_refs === undefined ? [] : receipt.data.deleted_refs;
    if (deleted.length) {
      const deletedSet = new Set(deleted);
      setSelected(current => current.filter(ref => !deletedSet.has(ref)));
      if (deletedSet.has(opened)) setOpened(null);
    }
    setRevision(current => current + 1); filter({});
  }
  async function preview(action, input, entity, token) {
    if (command.locked || busy || !command.reset()) return;
    setBusy(true); setError(null); const id = ++serial.current;
    try {
      const result = await APSBatchAPI.preview(action, entity ? entity.ref : null, input, scope, token || snapshot, new AbortController().signal);
      const p = B.preview(result, action, entity ? entity.ref : null, input);
      if (alive.current && id === serial.current) setDialog({ type: 'preview', preview: p });
    } catch (error) { if (alive.current && id === serial.current) setError(error); }
    finally { if (alive.current && id === serial.current) setBusy(false); }
  }
  async function selectFiltered() {
    if (blocked || !snapshot) return;
    setBusy(true); setError(null);
    try { const refs = B.selection(await APSBatchAPI.selection({ ...scope, snapshot_ref: snapshot }), snapshot);
      setSelected(current => Array.from(new Set(current.concat(refs))));
    } catch (error) { setError(error); } finally { setBusy(false); }
  }
  function sortBy(key) {
    const next = !sort || sort.key !== key ? { key, direction: 'asc' } : sort.direction === 'asc' ? { key, direction: 'desc' } : null;
    setSort(next); filter(next ? { sort: next.key, direction: next.direction } : { sort: 'business_code', direction: 'asc' });
  }
  // 没有返回入口时是从侧栏直接进来的，按钮是去下一步而不是返回。
  const returnTarget = initial.returnTarget;
  // 打开任何对话框都先清掉上一条命令的终态，免得新对话框重放旧回执或被旧终态锁住。
  const openDialog = next => { if (command.reset()) setDialog(next); };
  const openEditor = entity => openDialog({ type: 'base', entity });
  const deletion = entity => preview('bulk', { action: 'delete', refs: [entity.ref], patch: {} });
  const columnFilterCount = Object.keys(scope.column_filters).length;
  return <div className="plana batch-workspace wb-fill-viewport" data-batch-workspace>
    <ErrorBox error={initial.error || error} />{busy && <p role="status">正在核对批次资料…</p>}
    {deferred && <div role="status"><p>上次操作还没处理完，暂时没有恢复上次的查看范围。</p><Button disabled={command.phase !== 'idle' || !!dialog || busy}
      onClick={() => { setScope(initial.scope); setQuery(initial.scope.query); setSelected(initial.selected); setOpened(initial.opened); setSort(initial.sort); setDeferred(false); }}>继续上次范围</Button></div>}
    {!dialog && (command.locked || command.phase === 'done' || command.phase === 'rejected' && command.intent) && <div className="batch-band"><Feedback command={command} />
      {command.phase === 'done' && <Button onClick={() => { committed(command.result); command.reset(); }}>刷新列表</Button>}</div>}
    {opened ? <BatchDetail batchRef={opened} revision={revision} onBack={() => setOpened(null)} onEdit={openEditor} onDelete={deletion} disabled={blocked}
      onMaterials={entity => openDialog({ type: 'materials', entity })}
      onOperation={(entity, operation) => openDialog({ type: 'operation', entity, operation })} onSync={(entity, snapshot) => preview('sync', {}, entity, snapshot)} /> : <>
      <div className="batch-list-controls"><form className="toolbar" onSubmit={event => { event.preventDefault(); if (!blocked) filter({ query }); }}><h2 className="wb-page-title">批次列表</h2>
        <label className="search"><Icon name="search" /><input type="search" aria-label="搜索批次号、图号、零件名" placeholder="搜索批次号、图号、零件名…" value={query} disabled={blocked} onChange={event => setQuery(event.target.value)} /></label>
        <Button type="submit" icon="search" disabled={blocked}>搜索</Button><Button icon="filter" disabled={blocked} onClick={() => openDialog({ type: 'filters' })}>筛选</Button>
        <Button icon="refresh-cw" aria-label="刷新批次列表" disabled={blocked} onClick={() => filter({})} /><span className="tb-spacer" />
        <Button transfer="import" disabled={blocked || !snapshot} onClick={() => openDialog({ type: 'files', mode: 'import', scope, snapshot })}>批量导入</Button>
        <Button transfer="export" disabled={blocked || !snapshot} onClick={() => openDialog({ type: 'files', mode: 'export', scope, snapshot })}>批量导出</Button>
        <Button icon="plus" className="btn primary" disabled={blocked || !data} onClick={() => openEditor(null)}>新增批次</Button>
      </form>
      <div className="toolbar">{[['status', B.statuses], ['ready_status', B.ready]].map(([key]) => scope[key] && <Button key={key} icon="x" disabled={blocked} onClick={() => filter({ [key]: undefined })}>{B.label(key, scope[key])}</Button>)}
        {columnFilterCount > 0 && <span>列筛选 {columnFilterCount} 项</span>}
        {(scope.focus || scope.batch_ids) && <span>已定位{scope.focus === 'gaps' ? '工序缺项' : scope.focus === 'unready' ? '未齐套' : '指定批次'}</span>}
        <Button icon="x" disabled={blocked} onClick={clearFilters}>清除全部筛选</Button>
        {onNav && <Button icon={returnTarget ? 'arrow-left' : 'arrow-right'} disabled={blocked} onClick={() => returnTarget
          ? onNav(returnTarget.view, returnTarget.context)
          : onNav('run', selected.length > 0 ? { scope: { source: 'production', batch_refs: selected } } : {})}>{!returnTarget ? '下一步 · 去排产' : returnTarget.view === 'dashboard' ? '返回值班台' : '返回排产'}</Button>}</div></div>
      <BatchTable rows={data ? data.entities : []} scope={scope} selected={selected} setSelected={setSelected} onOpen={setOpened} onDelete={deletion}
        onSort={sortBy} onFilter={field => openDialog({ type: 'column', field, scope: { ...scope, snapshot_ref: snapshot } })} onClear={clearFilters} onRetry={() => filter({})} error={list.error} loading={list.loading} disabled={blocked || list.loading} />
      <Pager page={data ? data.page : { number: scope.page, size: scope.size }} sizes={Array.from(new Set([20, 50, 100, data ? data.page.size : scope.size])).sort((a, b) => a - b)} unit="个批次" label="" sizeLabel="每页条数" showPageJump disabled={blocked || !data} busy={list.loading} onSize={size => filter({ size })} onPage={page => setScope(current => ({ ...current, page, snapshot_ref: snapshot }))} />
      <div className="toolbar batch-selection"><span>已选 {selected.length} 个批次{selected.some(ref => !entityRefs || !entityRefs.has(ref)) ? ' · 含非当前页记录' : ''}</span>
        <Button onClick={selectFiltered} disabled={blocked || !snapshot}>全选当前筛选</Button><Button icon="x" disabled={blocked || !selected.length} onClick={() => setSelected([])}>清除选择</Button>
        <Button icon="square-pen" disabled={blocked || !selected.length} onClick={() => openDialog({ type: 'bulk' })}>批量修改</Button>
        <Button icon="copy" disabled={blocked || !selected.length} onClick={() => preview('bulk', { action: 'copy', refs: selected, patch: {} })}>复制所选</Button>
        <Button icon="trash-2" className="btn danger" disabled={blocked || !selected.length} onClick={() => preview('bulk', { action: 'delete', refs: selected, patch: {} })}>删除所选</Button></div>
    </>}
    {dialog && dialog.type === 'base' && <BatchForms.BaseEditor entity={dialog.entity} createContext={data && data.create_context} source={list.result && list.result.meta.source}
      command={command} onClose={close} onCommitted={committed} />}
    {dialog && dialog.type === 'operation' && <BatchOperationEditor entity={dialog.entity} operation={dialog.operation} source="production" command={command} onClose={close} onCommitted={committed} />}
    {dialog && dialog.type === 'materials' && <BatchMaterialEditor entity={dialog.entity} command={command} onClose={close} onCommitted={committed} />}
    {dialog && dialog.type === 'preview' && <BatchForms.Preview preview={dialog.preview} command={command} onClose={close} onCommitted={committed} />}
    {dialog && dialog.type === 'files' && <BatchFiles mode={dialog.mode} scope={dialog.scope} selected={selected} snapshot={dialog.snapshot} command={command} onClose={close} onCommitted={committed} />}
    {dialog && dialog.type === 'column' && <BatchTable.ColumnFilter scope={dialog.scope} field={dialog.field} onClose={close} onApply={values => {
      const filters = { ...scope.column_filters }; if (values === undefined) delete filters[dialog.field]; else filters[dialog.field] = values; filter({ column_filters: filters }); close();
    }} />}
    {dialog && dialog.type === 'filters' && <Modal title="筛选批次" icon="filter" onClose={close} footer={<Button onClick={close}>完成</Button>}><div className="modal-b form batch-fields">
      {[['status', '状态', B.statuses], ['ready_status', '齐套显示', B.ready]].map(([key, label, options]) => <Field label={label} key={key}><select value={scope[key] == null ? '' : scope[key]} onChange={event => filter({ [key]: event.target.value === '' ? undefined : event.target.value })}>
        <option value="">全部</option>{options.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>)}
    </div></Modal>}
    {dialog && dialog.type === 'bulk' && <Modal title="批量修改批次" icon="square-pen" guardOwner={bulkGuard} locked={busy} onClose={close} footer={<><Button onClick={closeBulk} disabled={busy}>取消</Button>
      <Button icon="check" disabled={busy} onClick={() => preview('bulk', { action: 'update', refs: selected, patch: Object.fromEntries(Object.entries(bulk).filter(([, value]) => value !== '')) })}>预览变更</Button></>}>
      <div className="modal-b form batch-fields"><Field label="批量优先级"><select value={bulk.priority} onChange={event => setBulk({ ...bulk, priority: event.target.value })}><option value="">不修改</option>{B.priority.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>
        <Field label="批量交期"><input type="date" value={bulk.due_date} onChange={event => setBulk({ ...bulk, due_date: event.target.value })} /></Field><Field label="批量备注"><input value={bulk.remark} onChange={event => setBulk({ ...bulk, remark: event.target.value })} /></Field><ErrorBox error={error} /></div>
    </Modal>}
  </div>;
}

export { BatchWorkspace };
export default BatchWorkspace;
