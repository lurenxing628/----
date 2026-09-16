(function () {
  'use strict';
  const B = window.APSBatchContract, C = window.APSResourceContract, S = window.APSResourceSession;
  const { Button, Modal, ErrorBox } = window.ResourceControls, { Field } = window.BatchControls;
  const defaults = { query: '', page: 1, size: 20, sort: 'business_code', direction: 'asc', column_filters: {} };
  const emptyAdapter = {};
  const scopeKeys = ['query', 'page', 'size', 'sort', 'direction', 'column_filters', 'status', 'ready_status', 'focus', 'batch_ids'];
  const sourceKeys = ['plan_ref', 'batch_ref', 'task_ref', 'operation_ref', 'return_to'];
  // 查看范围读不进来时页面会退回默认范围，提示按“发生了什么 → 哪些没变 → 点哪里”写。
  const refilter = '请点「清除全部筛选」重新查询。', fallbackList = '，已按默认范围显示批次列表。';
  function validReturnTarget(value) {
    return ['run', 'dashboard'].includes(value) || C.object(value)
      && Object.keys(value).every(key => ['view', 'context'].includes(key))
      && C.own(value, 'view') && value.view === 'dashboard' && C.own(value, 'context') && C.object(value.context);
  }
  function sourceContext(value, entityRef) {
    if (value == null) return null;
    if (!C.object(value) || Object.keys(value).some(key => !sourceKeys.includes(key))
        || sourceKeys.slice(0, 4).some(key => C.own(value, key) && !B.ref(value[key]))
        || C.own(value, 'return_to') && !validReturnTarget(value.return_to)
        || value.batch_ref && value.batch_ref !== entityRef) throw C.failure('批次来源或返回入口已失效' + fallbackList);
    return { ...value };
  }
  function readScope(value) {
    if (!C.object(value) || Object.keys(value).some(key => !scopeKeys.includes(key))) throw C.failure('查看范围里有不支持的项。' + refilter);
    const scope = { ...defaults, ...value };
    const sorts = B.columns.map(row => row[0]).filter(key => key !== 'progress');
    if (typeof scope.query !== 'string' || scope.query.length > 200 || !Number.isSafeInteger(scope.page) || scope.page < 1 || scope.page > 1000000
        || !Number.isSafeInteger(scope.size) || scope.size < 1 || scope.size > 100 || !sorts.includes(scope.sort) || !['asc', 'desc'].includes(scope.direction)
        || ![undefined, null, '', ...B.statuses.map(row => row[0])].includes(scope.status)
        || ![undefined, null, '', ...B.ready.map(row => row[0])].includes(scope.ready_status)
        || ![undefined, null, '', 'gaps', 'unready'].includes(scope.focus)) throw C.failure('查看范围或页码不正确。' + refilter);
    if (scope.batch_ids != null && (!Array.isArray(scope.batch_ids) || scope.batch_ids.length > 5000 || scope.batch_ids.some(key => typeof key !== 'string' || !key)))
      throw C.failure('要定位的批次清单不正确。' + refilter);
    if (!C.object(scope.column_filters) || Object.keys(scope.column_filters).some(key => !sorts.includes(key))) throw C.failure('列筛选条件里有不支持的列。' + refilter);
    for (const values of Object.values(scope.column_filters)) {
      if (!Array.isArray(values) || values.length > 5000 || values.some(value => value !== null && typeof value !== 'string'
          && !(typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= Number.MAX_SAFE_INTEGER))) throw C.failure('列筛选的取值不正确。' + refilter);
    }
    return JSON.parse(JSON.stringify(scope));
  }
  function readContext(context) {
    if (context == null) return { scope: { ...defaults }, selected: [], opened: null, sort: null, sourceContext: null };
    if (!C.object(context) || Object.keys(context).some(key => !['entity_ref', 'focus', 'batchIds', 'read_view', ...sourceKeys].includes(key))) throw C.failure('页面跳转带的信息里有不支持的项' + fallbackList);
    if (context.entity_ref !== undefined && !B.ref(context.entity_ref)) throw C.failure('要打开的批次已失效' + fallbackList);
    const view = context.read_view;
    if (view !== undefined && (!C.object(view) || Object.keys(view).some(key => !['scope', 'selected_refs', 'entity_ref', 'sort_state', 'source_context'].includes(key))))
      throw C.failure('上次的查看状态无法恢复' + fallbackList);
    if (view !== undefined && (C.own(context, 'focus') || C.own(context, 'batchIds') || sourceKeys.some(key => C.own(context, key)))) throw C.failure('定位批次和恢复上次查看不能同时用' + fallbackList);
    const scope = readScope(view ? view.scope : { ...defaults, focus: context.focus, batch_ids: context.batchIds });
    const selected = view && view.selected_refs !== undefined ? view.selected_refs : [];
    if (!Array.isArray(selected) || !selected.every(B.ref) || new Set(selected).size !== selected.length) throw C.failure('上次勾选的批次已失效' + fallbackList);
    const opened = view && view.entity_ref !== undefined ? view.entity_ref : context.entity_ref || context.batch_ref || null;
    if (opened !== null && !B.ref(opened)) throw C.failure('上次打开的批次已失效' + fallbackList);
    if (view && context.entity_ref && context.entity_ref !== opened) throw C.failure('批次导航与恢复详情不一致。');
    const sort = view && view.sort_state !== undefined ? view.sort_state : null;
    if (sort !== null && (!C.object(sort) || Object.keys(sort).some(key => !['key', 'direction'].includes(key))
        || sort.key !== scope.sort || sort.direction !== scope.direction)) throw C.failure('批次排序状态与范围不一致。');
    const origin = sourceContext(view ? view.source_context : Object.fromEntries(sourceKeys.filter(key => C.own(context, key)).map(key => [key, context[key]])), opened);
    return { scope, selected: selected.slice(), opened, sort, sourceContext: origin };
  }
  function BatchWorkspace({ adapter = emptyAdapter, onCommitted, disabled = false, initialContext, onNav }) {
    const [initial] = React.useState(() => { try { return readContext(initialContext); } catch (error) { return { ...readContext(null), error }; } });
    const command = S.useCommand(adapter), alive = React.useRef(true), serial = React.useRef(0);
    const [deferred, setDeferred] = React.useState(() => !!initialContext && command.phase !== 'idle');
    const [scope, setScope] = React.useState(initial.scope);
    const [query, setQuery] = React.useState(initial.scope.query), [selected, setSelected] = React.useState(initial.selected);
    const [opened, setOpened] = React.useState(() => deferred ? null : initial.opened);
    const [dialog, setDialog] = React.useState(null), [error, setError] = React.useState(null), [busy, setBusy] = React.useState(false);
    const [revision, setRevision] = React.useState(0), [sort, setSort] = React.useState(initial.sort), [bulk, setBulk] = React.useState({ priority: '', due_date: '', remark: '' });
    const bulkGuard = window.WorkbenchGuards.useDirtyGuard({ dirty: !!dialog && dialog.type === 'bulk' && Object.values(bulk).some(Boolean),
      locked: !!dialog && dialog.type === 'bulk' && busy, message: '批量修改条件尚未确认，离开会放弃本次修改。' });
    React.useEffect(() => { alive.current = true; return () => { alive.current = false; serial.current++; }; }, [adapter]);
    const list = S.useQuery(async signal => {
      if (typeof adapter.list !== 'function') throw C.failure('dependency not wired: window.APSBatchAPI.list');
      return B.list(await adapter.list('batch', scope, signal), scope);
    }, [adapter, scope, revision], !initial.error);
    const data = list.result && list.result.data, snapshot = list.result && list.result.meta.snapshot_ref;
    const blocked = disabled || !!initial.error || command.locked || busy || !!dialog;
    const rememberedScope = Object.fromEntries(scopeKeys.filter(key => scope[key] !== undefined).map(key => [key, scope[key]]));
    window.WorkbenchPageContext.useSnapshot({ read_view: { scope: rememberedScope, selected_refs: selected, entity_ref: opened, sort_state: sort,
      source_context: opened === initial.opened ? initial.sourceContext : null } },
      !!data && !list.loading && !list.error && !initial.error && !deferred && command.phase === 'idle' && !busy && !dialog
      && list.result.meta.source === 'production' && (!opened || data.entities.some(row => row.ref === opened)));
    function filter(patch) { setScope(current => ({ ...current, ...patch, page: 1, snapshot_ref: undefined })); }
    function clearFilters() { setQuery(''); filter({ query: '', status: undefined, ready_status: undefined, column_filters: {}, focus: undefined, batch_ids: undefined }); }
    function close() { if (command.locked || !command.reset()) return; setDialog(null); setError(null); }
    async function closeBulk(detail) {
      if (busy) return;
      if (detail && detail.guardConfirmed === true && detail.guardOwner === bulkGuard || await window.WorkbenchGuards.confirmLeave({ owner: bulkGuard })) close();
    }
    function committed(receipt) {
      const deleted = receipt.data.deleted_refs || [];
      if (deleted.length) { setSelected(current => current.filter(ref => !deleted.includes(ref))); if (deleted.includes(opened)) setOpened(null); }
      setRevision(current => current + 1); filter({}); if (onCommitted) onCommitted(receipt);
    }
    async function preview(action, input, entity, token) {
      if (disabled || command.locked || busy) return;
      setBusy(true); setError(null); const id = ++serial.current;
      try {
        const result = await adapter.preview(action, entity ? entity.ref : null, input, scope, token || snapshot, new AbortController().signal);
        const p = B.preview(result, action, entity ? entity.ref : null, input);
        if (alive.current && id === serial.current) setDialog({ type: 'preview', preview: p });
      } catch (error) { if (alive.current && id === serial.current) setError(error); }
      finally { if (alive.current && id === serial.current) setBusy(false); }
    }
    async function selectFiltered() {
      if (blocked || !snapshot) return;
      setBusy(true); setError(null);
      try { const result = await adapter.selection({ ...scope, snapshot_ref: snapshot });
        if (!result.data || !Array.isArray(result.data.refs) || !result.data.refs.every(B.ref) || result.data.count !== result.data.refs.length || result.meta.snapshot_ref !== snapshot) throw C.failure('全选没有完成，已勾选的批次保持不变。请点「刷新批次列表」后重试。');
        setSelected(current => Array.from(new Set(current.concat(result.data.refs))));
      } catch (error) { setError(error); } finally { setBusy(false); }
    }
    function sortBy(key) {
      const next = !sort || sort.key !== key ? { key, direction: 'asc' } : sort.direction === 'asc' ? { key, direction: 'desc' } : null;
      setSort(next); filter(next ? { sort: next.key, direction: next.direction } : { sort: 'business_code', direction: 'asc' });
    }
    // 没有来源入口时是从侧栏直接进来的，按钮是去下一步而不是返回。
    const returnSource = initial.sourceContext && initial.sourceContext.return_to || null;
    const returnTarget = returnSource || 'run';
    const returnView = typeof returnTarget === 'string' ? returnTarget : returnTarget.view;
    const openEditor = entity => { command.reset(); setDialog({ type: 'base', entity }); };
    const deletion = entity => preview('bulk', { action: 'delete', refs: [entity.ref], patch: {} });
    return <div className="plana batch-workspace wb-fill-viewport" data-batch-workspace><window.BatchControls.Styles />
      <ErrorBox error={initial.error || error} />{busy && <p role="status">正在核对批次资料…</p>}
      {deferred && <div role="status"><p>上次操作还没处理完，暂时没有恢复上次的查看范围。</p><Button disabled={command.phase !== 'idle' || !!dialog || busy}
        onClick={() => { setScope(initial.scope); setQuery(initial.scope.query); setSelected(initial.selected); setOpened(initial.opened); setSort(initial.sort); setDeferred(false); }}>继续上次范围</Button></div>}
      {!dialog && (command.locked || command.phase === 'done') && <div className="batch-band"><window.ResourceForms.Feedback command={command} />
        {command.phase === 'done' && <Button onClick={() => { committed(command.result); command.reset(); }}>刷新列表</Button>}</div>}
      {opened ? <window.BatchDetail adapter={adapter} batchRef={opened} revision={revision} onBack={() => setOpened(null)} onEdit={openEditor} onDelete={deletion} disabled={blocked}
        onOperation={(entity, operation) => { command.reset(); setDialog({ type: 'operation', entity, operation }); }} onSync={(entity, snapshot) => preview('sync', {}, entity, snapshot)} /> : <>
        <div className="batch-list-controls"><form className="toolbar" onSubmit={event => { event.preventDefault(); if (!blocked) filter({ query }); }}><h2 className="wb-page-title">批次列表</h2>
          <label className="search"><window.ResourceControls.Icon name="search" /><input type="search" aria-label="搜索批次号、图号、零件名" placeholder="搜索批次号、图号、零件名…" value={query} disabled={blocked} onChange={event => setQuery(event.target.value)} /></label>
          <Button type="submit" icon="search" disabled={blocked}>搜索</Button><Button icon="filter" disabled={blocked} onClick={() => setDialog({ type: 'filters' })}>筛选</Button>
          <Button icon="refresh-cw" aria-label="刷新批次列表" disabled={blocked} onClick={() => filter({})} /><span className="tb-spacer" />
          <Button transfer="import" disabled={blocked || !snapshot} reason={typeof adapter.importPreview !== 'function' ? window.WorkbenchTerms.outcomes.unavailable : ''} onClick={() => { command.reset(); setDialog({ type: 'files', mode: 'import', scope, snapshot }); }}>批量导入</Button>
          <Button transfer="export" disabled={blocked || !snapshot} reason={typeof adapter.exportPreview !== 'function' ? window.WorkbenchTerms.outcomes.unavailable : ''} onClick={() => setDialog({ type: 'files', mode: 'export', scope, snapshot })}>批量导出</Button>
          <Button icon="plus" className="btn primary" disabled={blocked || !data} onClick={() => openEditor(null)}>新增批次</Button>
        </form>
        <div className="toolbar">{[['status', B.statuses], ['ready_status', B.ready]].map(([key]) => scope[key] && <Button key={key} icon="x" disabled={blocked} onClick={() => filter({ [key]: undefined })}>{B.label(key, scope[key])}</Button>)}
          {Object.keys(scope.column_filters).length > 0 && <span>列筛选 {Object.keys(scope.column_filters).length} 项</span>}
          {(scope.focus || scope.batch_ids) && <span>已定位{scope.focus === 'gaps' ? '工序缺项' : scope.focus === 'unready' ? '未齐套' : '指定批次'}</span>}
          <Button icon="x" disabled={blocked} onClick={clearFilters}>清除全部筛选</Button>
          {onNav && <Button icon={returnSource ? 'arrow-left' : 'arrow-right'} disabled={blocked} onClick={() => typeof returnTarget === 'string' ? onNav(returnTarget) : onNav(returnTarget.view, returnTarget.context)}>{!returnSource ? '下一步 · 去排产' : returnView === 'dashboard' ? '返回值班台' : '返回排产'}</Button>}</div></div>
        {data && data.entities.length > 0 && <ErrorBox error={list.error} />}
        <window.BatchTable rows={data ? data.entities : []} scope={scope} selected={selected} setSelected={setSelected} onOpen={setOpened} onDelete={deletion}
          onSort={sortBy} onFilter={field => setDialog({ type: 'column', field, scope: { ...scope, snapshot_ref: snapshot } })} onClear={clearFilters} onRetry={() => filter({})} error={list.error} loading={list.loading} disabled={blocked || list.loading} />
        {data && <window.WorkbenchControls.Pager page={data.page} sizes={Array.from(new Set([20, 50, 100, data.page.size])).sort((a, b) => a - b)} unit="个批次" label="" sizeLabel="每页条数" showPageJump disabled={blocked || list.loading} onSize={size => filter({ size })} onPage={page => setScope(current => ({ ...current, page, snapshot_ref: snapshot }))} />}
        <div className="toolbar batch-selection"><span>已选 {selected.length} 个批次{selected.some(ref => !data || !data.entities.some(row => row.ref === ref)) ? ' · 含非当前页记录' : ''}</span>
          <Button onClick={selectFiltered} disabled={blocked || !snapshot}>全选当前筛选</Button><Button icon="x" disabled={blocked || !selected.length} onClick={() => setSelected([])}>清除选择</Button>
          <Button icon="square-pen" disabled={blocked || !selected.length} onClick={() => setDialog({ type: 'bulk' })}>批量修改</Button>
          <Button icon="copy" disabled={blocked || !selected.length} onClick={() => preview('bulk', { action: 'copy', refs: selected, patch: {} })}>复制所选</Button>
          <Button icon="trash-2" className="btn danger" disabled={blocked || !selected.length} onClick={() => preview('bulk', { action: 'delete', refs: selected, patch: {} })}>删除所选</Button></div>
      </>}
      {dialog && dialog.type === 'base' && <window.BatchForms.BaseEditor adapter={adapter} entity={dialog.entity} createContext={data && data.create_context} source={list.result && list.result.meta.source}
        command={command} onClose={close} onCommitted={committed} disabled={disabled} />}
      {dialog && dialog.type === 'operation' && <window.BatchOperationEditor adapter={adapter} entity={dialog.entity} operation={dialog.operation} source="production" command={command} onClose={close} onCommitted={committed} disabled={disabled} />}
      {dialog && dialog.type === 'preview' && <window.BatchForms.Preview preview={dialog.preview} command={command} onClose={close} onCommitted={committed} disabled={disabled} />}
      {dialog && dialog.type === 'files' && <window.BatchFiles adapter={adapter} mode={dialog.mode} scope={dialog.scope} selected={selected} snapshot={dialog.snapshot} command={command} onClose={close} onCommitted={committed} disabled={disabled} />}
      {dialog && dialog.type === 'column' && <window.BatchTable.ColumnFilter adapter={adapter} scope={dialog.scope} field={dialog.field} onClose={close} onApply={values => {
        const filters = { ...scope.column_filters }; if (values === undefined) delete filters[dialog.field]; else filters[dialog.field] = values; filter({ column_filters: filters }); close();
      }} />}
      {dialog && dialog.type === 'filters' && <Modal title="筛选批次" icon="filter" onClose={close} footer={<Button onClick={close}>完成</Button>}><div className="modal-b form batch-fields">
        {[['status', '状态', B.statuses], ['ready_status', '齐套显示', B.ready]].map(([key, label, options]) => <Field label={label} key={key}><select value={scope[key] || ''} onChange={event => filter({ [key]: event.target.value || undefined })}>
          <option value="">全部</option>{options.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>)}
      </div></Modal>}
      {dialog && dialog.type === 'bulk' && <Modal title="批量修改批次" icon="square-pen" guardOwner={bulkGuard} locked={busy} onClose={closeBulk} footer={<><Button onClick={closeBulk} disabled={busy}>取消</Button>
        <Button icon="check" disabled={busy} onClick={() => preview('bulk', { action: 'update', refs: selected, patch: Object.fromEntries(Object.entries(bulk).filter(([, value]) => value !== '')) })}>预览变更</Button></>}>
        <div className="modal-b form batch-fields"><Field label="批量优先级"><select value={bulk.priority} onChange={event => setBulk({ ...bulk, priority: event.target.value })}><option value="">不修改</option>{B.priority.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>
          <Field label="批量交期"><input type="date" value={bulk.due_date} onChange={event => setBulk({ ...bulk, due_date: event.target.value })} /></Field><Field label="批量备注"><input value={bulk.remark} onChange={event => setBulk({ ...bulk, remark: event.target.value })} /></Field><ErrorBox error={error} /></div>
      </Modal>}
    </div>;
  }
  window.BatchWorkspace = BatchWorkspace;
  BatchWorkspace.readContext = readContext;
})();
