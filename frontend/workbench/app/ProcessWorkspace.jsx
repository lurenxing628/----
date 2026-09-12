(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSProcessContract, A = window.APSProcessActions, S = window.APSResourceSession;
  const { Button, Icon, ErrorBox, Issues } = window.ResourceControls;
  const FileButtons = window.ProcessFileButtons;
  const emptyAdapter = {};
  const readScopeKeys = window.APSProcessReadView.scopeKeys;
  async function readList(adapter, scope, signal) {
    if (!adapter || typeof adapter.list !== 'function') throw C.failure('工艺列表接口尚未接入。');
    let request = scope;
    if (scope.page > 1 && !scope.snapshot_ref) {
      const firstScope = { ...scope, page: 1 }, first = P.list(await adapter.list('part', firstScope, signal), firstScope);
      if (first.meta.source !== 'production') throw C.failure('未取得原范围的生产快照，不能恢复后续页。');
      request = { ...scope, snapshot_ref: first.meta.snapshot_ref };
    }
    return P.list(await adapter.list('part', request, signal), request);
  }
  function Pipeline({ entity }) {
    const w = entity.workflow;
    return <div className="pipe" aria-label="工艺三阶段">
      {['route', 'source', 'hours'].map((key, index) => <React.Fragment key={key}>{index > 0 && <span className="pp-arr" />}<span className={'pp ' + (w[key].state === 'confirmed' ? 'done' : w[key].state === 'locked' ? 'lock' : 'warn')}>
        {({ route: '路线', source: '归属', hours: '工时' })[key]} · {w[key].state === 'confirmed' ? '已确认' : w[key].state === 'locked' ? key === 'source' ? '待路线' : '待归属' : w[key].state === 'present' ? '已有记录' : w[key].state === 'missing' ? '待录入' : '未确认'}</span></React.Fragment>)}
    </div>;
  }
  function ProcessTable({ entities, selected, setSelected, onOpen, onDelete, disabled, loading, error, scope, adapter, onSort, onFilter, matchingCount, deleteReason }) {
    const allRef = React.useRef(null), visible = entities.map(row => row.ref);
    const table = React.useRef(null), [widths, setWidths] = React.useState(null);
    const selectedSet = new Set(selected), all = !!visible.length && visible.every(ref => selectedSet.has(ref));
    const ordering = P.ordering(scope), width = column => widths ? widths[column.key] : column.width;
    React.useEffect(() => { if (allRef.current) allRef.current.indeterminate = !all && visible.some(ref => selectedSet.has(ref)); }, [entities, selected, all]);
    function resize(key, value) {
      if (disabled || !Number.isFinite(value)) return;
      const current = {};
      table.current.querySelectorAll('thead th[data-column]').forEach(cell => { current[cell.dataset.column] = cell.getBoundingClientRect().width; });
      setWidths({ ...current, [key]: Math.max(56, value) });
    }
    const sizing = widths ? { width: Object.values(widths).reduce((total, value) => total + value, 0), minWidth: 0 } :
      { minWidth: 234 + P.columns.reduce((total, column) => total + column.width, 0) };
    return <div className="wb-table-frame"><div className="card-scroll wb-table-shell"><table ref={table} className="tbl wb-table" aria-label="零件工艺列表" aria-busy={loading} style={{ ...sizing, tableLayout: 'fixed' }}><caption className="wb-visually-hidden">{"零件工艺列表"}</caption>
      <thead><tr><th scope="col" data-column="__selection" style={{ width: widths ? widths.__selection : 44 }}><input ref={allRef} type="checkbox" aria-label="全选当前页" checked={all} disabled={disabled || loading || !visible.length}
        onChange={event => setSelected(event.target.checked ? Array.from(new Set(selected.concat(visible))) : selected.filter(ref => !visible.includes(ref)))} /></th>
        {P.columns.map(column => { const sorted = ordering.find(row => row.field === column.key); return <th scope="col" key={column.key} data-column={column.key} style={{ width: width(column) }} aria-sort={sorted ? sorted.direction === 'asc' ? 'ascending' : 'descending' : 'none'}>
          <window.ResourceTableHeader column={column} kind="part" scope={scope} adapter={adapter} sort={sorted && sorted.field} direction={sorted && sorted.direction} sortActive={!!sorted}
            onSort={onSort} onFilter={rule => onFilter(column.key, rule)} filter={scope.column_filters && scope.column_filters[column.key]} matchingCount={matchingCount}
            width={width(column)} onResize={value => resize(column.key, value)} disabled={disabled} scopeTransform={A.facetScope} pageSize={50} />
        </th>; })}<th scope="col" data-column="__actions" style={{ width: widths ? widths.__actions : 190 }}>下一步 / 操作</th></tr></thead>
      <tbody>{entities.map(row => <tr key={row.ref} data-process-ref={row.ref}>
        <td><input type="checkbox" aria-label={'选择 ' + row.business_code} checked={selectedSet.has(row.ref)} disabled={disabled || loading} onChange={event => setSelected(event.target.checked ? selected.concat(row.ref) : selected.filter(ref => ref !== row.ref))} /></td>
        <td><Button className="lnk" disabled={disabled || loading} aria-label={'查看 ' + row.business_code} onClick={() => onOpen(row.ref)} style={{ whiteSpace: 'normal', overflowWrap: 'anywhere', textAlign: 'left' }}>{row.business_code}</Button></td>
        <td>{row.label}{row.issues.length > 0 && <Issues issues={row.issues} />}</td><td className="r">{row.relationships.operation_count}</td><td><Pipeline entity={row} /></td>
        <td><div className="wb-actions" style={{ flexWrap: 'wrap' }}><Button className="linkbtn" icon="arrow-right" disabled={disabled || loading} aria-label={'浏览步骤 ' + row.business_code} onClick={() => onOpen(row.ref)}>{row.workflow.route.state !== 'confirmed' ? '确认路线' : ({ source: '确认归属', hours: '填写工时', ready: '已就绪 · 汇总' })[row.workflow.stage]}</Button>
          <Button className="mini" icon="minus" disabled={disabled || loading} reasonDisplay="tooltip" reason={deleteReason} aria-label={'删除 ' + row.business_code} onClick={() => onDelete([row.ref])} /></div></td>
      </tr>)}{!entities.length && <tr><td colSpan={6} style={{ padding: 28, textAlign: 'center' }} className="muted">{loading ? '正在读取工艺…' : error ? '工艺读取失败。' : '当前条件下没有零件。'}</td></tr>}</tbody>
    </table></div></div>;
  }
  function ProcessWorkspace({ adapter = emptyAdapter, onCommitted, disabled = false, initialContext, onNavigationReady, rememberEnabled = true }) {
    const command = S.useCommand(adapter);
    const [target] = React.useState(() => {
      if (initialContext == null) return { context: null };
      const parsed = window.ResourceWorkspace.navigation(initialContext);
      return parsed.context && parsed.context.kind !== 'part' ? { error: C.failure('工艺导航必须指向原零件记录。') } : parsed;
    });
    const [deferred, setDeferred] = React.useState(() => !!target.context && command.phase !== 'idle');
    const [navigationError, setNavigationError] = React.useState(target.error || null);
    const restored = target.context && target.context.read_view;
    const restoredRef = restored ? restored.entity_ref : target.context && target.context.entity_ref;
    const navigationDialog = () => restoredRef ? ({ ref: restoredRef, adapter, navigation: target.context }) : null;
    const [recoveryError, setRecoveryError] = React.useState(null);
    const [scope, setScope] = React.useState(() => restored ? restored.scope : { query: '', page: 1, size: 20, sort: [], column_filters: {} });
    const [search, setSearch] = React.useState(() => restored ? restored.scope.query : '');
    const [selected, setSelected] = React.useState(() => restored ? restored.selected_refs : []), [dialog, setDialog] = React.useState(() => !deferred && target.context ? navigationDialog() : null);
    const previousAdapter = React.useRef(adapter);
    window.WorkbenchGuards.useDirtyGuard({ dirty: false, locked: !dialog && command.locked, message: '工艺原请求尚未核实，请保留当前页面。' });
    React.useEffect(() => {
      if (previousAdapter.current === adapter) return;
      previousAdapter.current = adapter; setSelected([]); setDialog(null); setScope(current => ({ ...current, page: 1, snapshot_ref: undefined }));
    }, [adapter]);
    React.useEffect(() => { if (onNavigationReady) onNavigationReady(!dialog && command.phase === 'idle' && !recoveryError); }, [dialog, command.phase, recoveryError, onNavigationReady]);
    React.useEffect(() => {
      try {
        const intent = typeof adapter.readPending === 'function' && adapter.readPending();
        const restored = A.restored(intent);
        if (restored) setDialog({ ...restored, adapter });
        setRecoveryError(null);
      } catch (error) { setRecoveryError(error); }
    }, [adapter]);
    React.useEffect(() => {
      const restored = A.restored(command.intent);
      if (restored && ['sending', 'pending', 'checking', 'done'].includes(command.phase))
        setDialog(current => current && current.adapter === adapter && (current.ref && restored.fileKind
          || current.mode === restored.mode && current.ref === restored.ref && current.fileKind === restored.fileKind) ? current : { ...restored, adapter });
    }, [adapter, command.intent, command.phase]);
    const list = S.useQuery(signal => readList(adapter, scope, signal), [adapter, scope]);
    const data = list.result && list.result.data, counts = data && data.metrics.counts;
    const savedScope = Object.fromEntries(readScopeKeys.filter(key => scope[key] !== undefined).map(key => [key, scope[key]]));
    window.WorkbenchPageContext.useSnapshot({ source: 'production', kind: 'part', read_view: { scope: savedScope, selected_refs: selected,
      entity_ref: dialog && !dialog.mode && !dialog.fileKind ? dialog.ref : null } },
      rememberEnabled && !!data && !list.loading && !list.error && !navigationError && !deferred && !recoveryError && command.phase === 'idle'
      && list.result.meta.source === 'production' && (!dialog || !dialog.mode && !dialog.fileKind && data.entities.some(row => row.ref === dialog.ref)));
    const filter = patch => { if (!disabled) setScope(current => ({ ...current, ...patch, page: 1, snapshot_ref: undefined })); };
    function sortBy(key, direction) {
      const ordering = P.ordering(scope), next = ordering.filter(item => item.field !== key);
      if (direction) { const index = ordering.findIndex(item => item.field === key); next.splice(index < 0 ? next.length : index, 0, { field: key, direction }); }
      filter({ sort: next, direction: undefined });
    }
    function columnFilter(key, rule) {
      const filters = A.filters(scope.column_filters);
      if (rule === null) delete filters[key]; else filters[key] = rule;
      filter({ column_filters: filters });
    }
    function committed(receipt) {
      if (C.receipt(receipt) !== 'terminal') return;
      setScope(current => ({ ...current, page: 1, snapshot_ref: undefined }));
      if (Number.isSafeInteger(receipt.data.deleted_count) && Array.isArray(receipt.data.rows)) {
        const removed = new Set(receipt.data.rows.map(row => row.entity_ref)); setSelected(current => current.filter(ref => !removed.has(ref)));
      }
      if (onCommitted) onCommitted(receipt);
    }
    function action(mode, refs = selected, fileKind) {
      if (!data || blocked || list.loading) return;
      setDialog({ mode, fileKind, refs: refs.slice(), scope: A.scope(scope), snapshot_ref: list.result.meta.snapshot_ref, page_size: data.page.size,
        source: list.result.meta.source, create_context: data.create_context, adapter });
    }
    const deleteReason = P.reason(data && data.capabilities, 'delete', typeof adapter.bulkPreview === 'function' && typeof adapter.command === 'function');
    const blocked = disabled || !!dialog || command.locked || !!recoveryError;
    function continueNavigation() {
      if (blocked || command.phase !== 'idle') { setNavigationError(C.failure('请先处理原请求并关闭原工艺详情，再继续导航。')); return; }
      setDeferred(false); setNavigationError(null); setDialog(navigationDialog());
    }
    return <div className="process-workspace" data-process-workspace>
      <ErrorBox error={navigationError} />{deferred && <div role="status"><p>原工艺请求优先处理，精确导航暂缓。</p><Button icon="arrow-right" onClick={continueNavigation}>继续原导航</Button></div>}
      <div className="statline wb-metrics" style={{ '--wb-columns': 4 }}>
        {[['total', '零件总数', 'primary'], ['source', '待分拣', 'warn'], ['hours', '待填工时', 'warn'], ['ready', '已就绪', 'ok']].map(([key, label, tone]) =>
          <div key={key} className="stat wb-metric" data-tone={tone}><span className="sl wb-metric-label">{label}</span><span className="sv wb-metric-value">{counts ? counts[key] : '待读取'}</span></div>)}
      </div>
      <div className="subtabs" role="tablist" aria-label="工艺阶段">{P.stages.map(([stage, label, key]) => <Button key={key} className={'subtab' + ((scope.stage || '') === stage ? ' on' : '')}
        role="tab" aria-selected={(scope.stage || '') === stage} disabled={blocked} onClick={() => filter({ stage: stage || undefined })}>{label} <span className="cnt">{counts ? counts[key] : '…'}</span></Button>)}</div>
      <form className="toolbar" onSubmit={event => { event.preventDefault(); if (!blocked) filter({ query: search }); }}>
        <label className="search"><span className="ic"><Icon name="search" /></span><input type="search" aria-label="搜索图号、名称、路线" placeholder="搜索图号、名称、路线…" value={search} disabled={blocked} onChange={event => setSearch(event.target.value)} /></label>
        <Button type="submit" icon="search" disabled={blocked}>搜索</Button><Button icon="refresh-cw" aria-label="刷新工艺列表" disabled={blocked} busy={list.loading} onClick={() => filter({})} />
        <span className="tb-spacer" /><div className="wb-actions" style={{ flexWrap: 'wrap' }}>
          <FileButtons capabilities={data && data.capabilities} disabled={blocked || list.loading}
            onAction={typeof adapter.filePreview === 'function' && typeof adapter.fileDownload === 'function' ? (kind, mode) => action(mode, selected, kind) : undefined} />
          <Button icon="plus" className="btn primary" disabled={blocked || list.loading} reason={P.reason(data && data.capabilities, 'create', typeof adapter.command === 'function') || A.createReason(data && data.create_context, list.result && list.result.meta.source)} onClick={() => action('create')}>新增零件</Button>
        </div>
      </form>
      <div className="toolbar"><span className="muted" aria-live="polite">已选 <b data-process-selection-count>{selected.length}</b> 项{selected.some(ref => !data || !data.entities.some(row => row.ref === ref)) ? ' · 含非当前页记录' : ''}</span>
        <Button icon="x" aria-label="清除所有选择" disabled={blocked || !selected.length} onClick={() => setSelected([])}>清除选择</Button>
        <Button icon="minus" className="btn danger" disabled={blocked || list.loading || !selected.length} reasonDisplay="tooltip" reason={deleteReason} onClick={() => action('bulk')}>批量删除</Button>
      </div>
      <ErrorBox error={list.error} />{list.error && <Button icon="refresh-cw" disabled={blocked} onClick={() => filter({})}>重试读取工艺</Button>}
      <ErrorBox error={recoveryError} />{!dialog && command.locked && <window.ResourceForms.Feedback command={command} />}
      {list.result && <Issues issues={list.result.warnings} />}
      <ProcessTable entities={data ? data.entities : []} selected={selected} setSelected={setSelected} onOpen={ref => setDialog({ ref, adapter })} onDelete={refs => action('bulk', refs)} deleteReason={deleteReason}
        disabled={blocked} loading={list.loading} error={list.error} scope={scope} adapter={adapter} onSort={sortBy} onFilter={columnFilter} matchingCount={data && data.page.total} />
      {data && <window.ResourceTables.Pager page={data.page} disabled={blocked || list.loading} onSize={size => filter({ size })}
        onPage={page => setScope(current => ({ ...current, page, snapshot_ref: list.result.meta.snapshot_ref }))} />}
      {dialog && dialog.adapter === adapter && (dialog.fileKind ? <window.ProcessFileActions adapter={adapter} kind={dialog.fileKind} mode={dialog.mode} request={dialog} disabled={disabled} onCommitted={committed} onClose={() => setDialog(null)} /> :
        dialog.mode ? <window.ProcessCollectionActions adapter={adapter} request={dialog} disabled={disabled} onCommitted={committed} onClose={() => setDialog(null)} onOpen={ref => setDialog({ ref, adapter })} /> :
        <window.ProcessDetail key={dialog.ref} adapter={adapter} partRef={dialog.ref} disabled={disabled} onCommitted={committed} onClose={() => setDialog(null)}
          navigationReadOnly={!!dialog.navigation} initialStage={dialog.navigation && dialog.navigation.stage}
          templateOperationRef={dialog.navigation && dialog.navigation.template_operation_ref} templateExternalGroupRef={dialog.navigation && dialog.navigation.template_external_group_ref} />)}
    </div>;
  }
  window.ProcessWorkspace = ProcessWorkspace;
  ProcessWorkspace.readView = window.APSProcessReadView.read;
  ProcessWorkspace.readList = readList;
})();
