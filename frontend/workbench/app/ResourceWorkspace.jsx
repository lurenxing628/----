(function () {
  'use strict';
  const C = window.APSResourceContract, S = window.APSResourceSession;
  const { Button, Icon, ErrorBox, Issues, Modal } = window.ResourceControls;
  const Forms = window.ResourceForms, Tables = window.ResourceTables;
  const emptyAdapter = {};
  const readScopeKeys = ['query', 'status', 'page', 'size', 'sort', 'direction', 'category', 'column_filters'];
  function readColumns(config) {
    const fields = config.kind === 'op_type' ? config.category === 'internal' ? ['available_machines', 'available_operators', 'remark']
      : ['default_merge_mode', 'remark'] : { material: ['spec', 'stock_qty'], machine: ['op_type_ref', 'group_ref'],
        operator: ['skill_refs', 'shift_profile_ref'], supplier: ['op_type_refs', 'default_days'] }[config.kind];
    return ['business_code', 'label', ...fields, ...(config.kind === 'op_type' ? [] : ['status'])];
  }
  function resourceReadView(view, node) {
    if (!C.object(view) || Object.keys(view).some(key => !['scope', 'selected_refs', 'sort_active', 'detail'].includes(key))) throw C.failure('资源恢复记录只能包含只读查看状态。');
    const config = C.nodes[node], scope = view.scope;
    if (!C.object(scope) || Object.keys(scope).some(key => !readScopeKeys.includes(key)) || typeof scope.query !== 'string'
        || !Number.isSafeInteger(scope.page) || scope.page < 1 || !Number.isSafeInteger(scope.size) || scope.size < 1 || scope.size > 100
        || typeof scope.sort !== 'string' || !readColumns(config).includes(scope.sort)
        || !['asc', 'desc'].includes(scope.direction) || typeof view.sort_active !== 'boolean') throw C.failure('资源恢复范围、排序或分页不正确。');
    if (config.category ? scope.category !== config.category || C.own(scope, 'status') : C.own(scope, 'category')
        || !['', ...(C.statuses[config.kind] || []).map(row => row[0])].includes(scope.status)) throw C.failure('资源恢复范围与当前节点不一致。');
    const selected = view.selected_refs;
    if (!Array.isArray(selected) || selected.some(value => typeof value !== 'string' || !/^[0-9a-f]{48}$/.test(value)) || new Set(selected).size !== selected.length)
      throw C.failure('资源已选引用集合不正确。');
    if (scope.column_filters !== undefined) {
      if (!C.object(scope.column_filters) || Object.keys(scope.column_filters).some(key => !readColumns(config).includes(key)))
        throw C.failure('资源恢复列筛选字段不正确。');
      Object.values(scope.column_filters).forEach(value => window.ResourceTableFilterModel.rule(value));
    }
    if (view.detail !== null) {
      if (!C.object(view.detail) || Object.keys(view.detail).some(key => !['kind', 'entity_ref', 'category'].includes(key))) throw C.failure('资源只读详情恢复字段不正确。');
      const checked = navigation({ source: 'production', ...view.detail });
      if (checked.error || !checked.context || ['part', 'calendar'].includes(checked.context.kind)) throw C.failure('资源只读详情恢复目标不正确。');
    }
    return JSON.parse(JSON.stringify(view));
  }
  function navigation(context) {
    if (context === undefined || context === null) return { context: null };
    try {
      if (!C.object(context) || context.source !== 'production') throw C.failure('导航来源不正确，只能定位生产资料。');
      const keys = Object.keys(context), kind = context.kind, ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
      if (keys.length === 1 && keys[0] === 'source') return { context: null };
      if (!['material', 'op_type', 'machine', 'operator', 'supplier', 'part', 'calendar'].includes(kind)) throw C.failure('未知的基础资料导航类型。');
      const allowed = ['source', 'kind'].concat(kind === 'calendar' ? ['month', 'date'] : ['entity_ref', 'read_view'], kind === 'op_type' ? ['category'] : [],
        kind === 'part' ? ['stage', 'template_operation_ref', 'template_external_group_ref'] : []);
      if (keys.some(key => !allowed.includes(key))) throw C.failure('导航含有不支持的定位字段，未忽略或按编号查找。');
      if (C.own(context, 'read_view') && ['entity_ref', 'stage', 'template_operation_ref', 'template_external_group_ref'].some(key => C.own(context, key)))
        throw C.failure('基础资料单次定位与只读恢复范围不能混用。');
      if (kind === 'calendar') {
        if (typeof context.month !== 'string' || !/^\d{4}-(0[1-9]|1[0-2])$/.test(context.month) || Number(context.month.slice(0, 4)) < 1
            || C.own(context, 'date') && (!window.APSCalendarContract.isDate(context.date) || context.date.slice(0, 7) !== context.month))
          throw C.failure('导航月份或日期不正确，日期必须属于指定月份。');
      } else if ((!C.own(context, 'read_view') || C.own(context, 'entity_ref')) && !ref(context.entity_ref)) throw C.failure('导航缺少有效的原记录引用，不能按同号或同名替代。');
      if (kind === 'op_type' && !['internal', 'external'].includes(context.category)) throw C.failure('工种导航缺少明确的自制或外协类别，不能猜测节点。');
      if (kind === 'part' && (C.own(context, 'stage') && !['route', 'source', 'hours'].includes(context.stage)
          || ['template_operation_ref', 'template_external_group_ref'].some(key => C.own(context, key) && !ref(context[key]))))
        throw C.failure('工艺阶段或模板记录引用不正确。');
      const node = kind === 'part' ? 'process' : kind === 'op_type' ? context.category === 'internal' ? 'op_int' : 'op_ext' : kind;
      const restored = C.own(context, 'read_view') ? kind === 'part' ? window.APSProcessReadView.read(context.read_view) : resourceReadView(context.read_view, node) : undefined;
      return { context: { ...context, ...(restored ? { read_view: restored } : {}) }, node };
    } catch (error) { return { context: null, error }; }
  }
  function navigationDialog(context) {
    return { kind: context.kind, action: 'view', ref: context.entity_ref, category: context.category, navigation: true };
  }
  const scopeFor = node => ({ query: '', ...(C.nodes[node] && C.nodes[node].kind !== 'op_type' ? { status: '' } : {}), page: 1, size: 20, sort: 'business_code', direction: 'asc',
    ...(C.nodes[node] && C.nodes[node].category ? { category: C.nodes[node].category } : {}) });
  async function readList(adapter, kind, scope, signal) {
    if (typeof adapter.list !== 'function') throw C.failure('资源列表接口尚未接入。');
    const result = C.query(await adapter.list(kind, scope, signal), 'list');
    if (result.data.page.number !== scope.page || result.data.page.size !== scope.size)
      throw C.failure('返回页码与请求范围不一致，请重新读取。');
    const page = Math.min(scope.page, Math.max(1, Math.ceil(result.data.page.total / scope.size)));
    if (page === scope.page) return result;
    // A smaller total can invalidate the last page; keep the returned snapshot and all filters.
    const clamped = C.query(await adapter.list(kind, { ...scope, page, snapshot_ref: result.meta.snapshot_ref }, signal), 'list');
    if (clamped.data.page.number !== page || clamped.data.page.size !== scope.size || clamped.data.page.total !== result.data.page.total
        || clamped.meta.snapshot_ref !== result.meta.snapshot_ref || clamped.meta.source !== result.meta.source)
      throw C.failure('收缩页码后的列表与原读取范围不一致，请重新读取。');
    return clamped;
  }
  const Rail = window.ResourceRail;
  function Toolbar({ config, scope, onFilter, loading, disabled, onRefresh, onCreate, createReason, onExternal, adapter, selected, ready, onClearSelection }) {
    const [search, setSearch] = React.useState(scope.query);
    React.useEffect(() => setSearch(scope.query), [scope.query, config.kind]);
    return <form className="toolbar" onSubmit={event => { event.preventDefault(); onFilter({ query: search }); }}>
      <label className="search"><span className="ic"><Icon name="search" /></span><input type="search" aria-label="搜索编号或名称" placeholder={'搜索' + config.label + '编号、名称…'} value={search} disabled={disabled} onChange={event => setSearch(event.target.value)} /></label>
      <Button type="submit" icon="search" disabled={disabled} aria-busy={loading}>搜索</Button>
      {C.statuses[config.kind] && <label className="field"><select aria-label="状态筛选" value={scope.status} disabled={disabled} style={{ height: 32 }} onChange={event => onFilter({ status: event.target.value })}>
        <option value="">全部状态</option>{C.statuses[config.kind].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
      <Button icon="refresh-cw" aria-label="刷新列表" onClick={onRefresh} disabled={disabled} busy={loading} />
      {selected.length > 0 && <Button icon="x" aria-label="清除所有选择" onClick={onClearSelection} disabled={disabled}>清除选择</Button>}
      <span className="tb-spacer" /><div className="wb-actions">
      {[['openImport', 'file-input', '导入'], ['openExport', 'file-output', '导出'], ['openBulk', 'minus', '批量删除']].map(([name, icon, label]) => <Button key={name} icon={icon} transfer={name === 'openImport' ? 'import' : name === 'openExport' ? 'export' : undefined}
        disabled={disabled || loading} reasonDisplay="tooltip" reason={typeof adapter[name] !== 'function' || typeof adapter.supports === 'function' && !adapter.supports(name, config.kind) ? label + '向导尚未接入。' : !ready ? '请先读取当前范围。' : name === 'openBulk' && !selected.length ? '请先勾选记录。' : ''}
        onClick={() => onExternal(name)}>{label}</Button>)}
      <Button icon="plus" className="btn primary wb-action wb-primary" reason={createReason} disabled={disabled} onClick={onCreate}>新增{config.label}</Button></div>
    </form>;
  }
  function Calendar({ adapter, disabled, onExternal }) {
    const [month, setMonth] = React.useState(() => {
      const date = new Date(); return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0');
    });
    return <div className="cal-wrap"><div className="cal-panel"><div className="cal-top" style={{ flexWrap: 'wrap' }}>
      <label className="field"><span>月份</span><input type="month" value={month} disabled={disabled} onChange={event => setMonth(event.target.value)} /></label>
      <Button icon="calendar-days" disabled={disabled || !month} reason={typeof adapter.openCalendar !== 'function' ? '工作日历向导尚未接入，不能修改日历。' : ''}
        onClick={() => onExternal('openCalendar', { month })}>维护工作日历</Button></div><p className="muted" role="status">{typeof adapter.openCalendar === 'function' ? '工作日历由已接入的日历向导读取和维护。' : '工作日历明细尚未接入。'}</p></div>
      <aside className="cal-panel cal-side"><h3>默认规则</h3><p>尚未读取。未推定每天工时、效率或周末安排。</p></aside></div>;
  }
  function ResourceWorkspace({ adapter = emptyAdapter, onNavigate, initialNode = 'material', initialContext, renderPart, renderCalendar, externalRevision = 0, onNavigationReady, rememberEnabled = true }) {
    adapter = adapter && typeof adapter === 'object' ? adapter : emptyAdapter;
    const [target] = React.useState(() => navigation(initialContext));
    const command = S.useCommand(adapter);
    const [deferred, setDeferred] = React.useState(() => !!target.context && command.phase !== 'idle');
    const [navigationError, setNavigationError] = React.useState(target.error || null);
    const startNode = target.node || initialNode;
    const readView = target.context && !['part', 'calendar'].includes(target.context.kind) && target.context.read_view;
    const [node, setNode] = React.useState(startNode), [scope, setScope] = React.useState(() => readView ? readView.scope : scopeFor(startNode));
    const [sortActive, setSortActive] = React.useState(!!readView && readView.sort_active);
    const [selected, setSelected] = React.useState(() => readView ? readView.selected_refs : []), [revision, setRevision] = React.useState(0);
    const [dialog, setDialog] = React.useState(() => !deferred && target.context && !['part', 'calendar'].includes(target.context.kind)
      ? readView ? readView.detail ? navigationDialog(readView.detail) : null : navigationDialog(target.context) : null), [external, setExternal] = React.useState({ busy: false, error: null });
    const [refreshState, setRefreshState] = React.useState({});
    const [editContext, setEditContext] = React.useState(null), [contextError, setContextError] = React.useState(null);
    const [contextReview, setContextReview] = React.useState(null), [contextBusy, setContextBusy] = React.useState(false);
    const counts = S.useCounts(adapter, revision + ':' + externalRevision);
    const config = C.nodes[node], basic = !!config && !['part', 'calendar'].includes(config.kind);
    const blocked = command.locked || external.busy;
    React.useEffect(() => {
      if (basic && onNavigationReady) onNavigationReady(!dialog && command.phase === 'idle' && !external.busy);
    }, [basic, dialog, command.phase, external.busy, onNavigationReady]);
    const list = S.useQuery(signal => readList(adapter, config.kind, scope, signal), [adapter, node, scope, revision, externalRevision], basic);
    const detail = S.useQuery(async signal => {
      if (typeof adapter.detail !== 'function') throw C.failure('资源详情接口尚未接入。');
      const result = C.query(await adapter.detail(dialog.kind, dialog.ref, signal), 'entity');
      if (result.data.ref !== dialog.ref) throw C.failure('详情对象与所选记录不一致。');
      if (dialog.navigation && (result.meta.source !== 'production' || C.own(result.data, 'kind') && result.data.kind !== dialog.kind
          || dialog.kind === 'op_type' && result.data.fields.category !== dialog.category))
        throw C.failure('原记录的来源、类型或工种类别与导航不一致，未打开替代对象。');
      return result;
    }, [adapter, dialog && dialog.ref, dialog && dialog.kind], !!(dialog && dialog.ref));
    const data = list.result && list.result.data;
    const savedDetail = dialog && dialog.action === 'view' ? { kind: dialog.kind, entity_ref: dialog.ref, ...(dialog.kind === 'op_type' ? { category: dialog.category } : {}) } : null;
    const savedScope = Object.fromEntries(readScopeKeys.filter(key => scope[key] !== undefined).map(key => [key, scope[key]]));
    window.WorkbenchPageContext.useSnapshot({ source: 'production', kind: config && config.kind, ...(config && config.category ? { category: config.category } : {}),
      read_view: { scope: savedScope, selected_refs: selected, sort_active: sortActive, detail: savedDetail } },
      rememberEnabled && basic && !!data && !list.loading && !list.error && !navigationError && !deferred && command.phase === 'idle' && !external.busy
      && list.result.meta.source === 'production' && (!dialog || dialog.action === 'view' && !!detail.result && !detail.loading && !detail.error));
    React.useEffect(() => {
      if (data && data.page.number < scope.page) setScope(current => current === scope
        ? { ...current, page: data.page.number, snapshot_ref: list.result.meta.snapshot_ref } : current);
    }, [list.result, scope]);
    const refreshGeneration = React.useRef(0), mounted = React.useRef(true);
    React.useEffect(() => { mounted.current = true; return () => { mounted.current = false; refreshGeneration.current++; }; }, []);
    function refresh() { setScope(current => ({ ...current, snapshot_ref: undefined })); setRevision(value => value + 1); }
    function navigate(next) {
      if (blocked || dialog) return;
      setNode(next); setScope(scopeFor(next)); setSortActive(false); setSelected([]); setContextError(null); setExternal({ busy: false, error: null });
    }
    function filter(patch) { if (!blocked) setScope(current => ({ ...current, ...patch, page: 1, snapshot_ref: undefined })); }
    function columnFilter(key, rule) {
      if (blocked) return;
      setScope(current => {
        const column_filters = { ...(current.column_filters || {}) };
        if (rule === null || rule.mode === 'exclude' && !rule.values.length) delete column_filters[key];
        else column_filters[key] = { mode: rule.mode, values: rule.values.slice() };
        return { ...current, column_filters, page: 1, snapshot_ref: undefined };
      });
    }
    function sortColumn(sort, direction) {
      if (blocked) return;
      setSortActive(direction !== null);
      filter(direction === null ? { sort: 'business_code', direction: 'asc' } : { sort, direction });
    }
    function changePage(page) {
      if (blocked || !list.result) return;
      setScope(current => ({ ...current, page, snapshot_ref: list.result.meta.snapshot_ref }));
    }
    function open(action, ref = null, related = null) {
      if (blocked) return;
      if (!command.reset()) return;
      setRefreshState({}); setContextError(null); setEditContext(null); setContextReview(null);
      setDialog({ kind: related ? related.kind : config.kind, action, ref, category: related ? related.category : config.category,
        history: related && dialog ? (dialog.history || []).concat({ ...dialog, action: 'view', history: undefined }) : [],
        createContext: related ? null : data && data.create_context, source: related ? null : list.result && list.result.meta.source });
    }
    function back() {
      if (blocked || !dialog || !dialog.history || !dialog.history.length || !command.reset()) return;
      const history = dialog.history.slice();
      setDialog({ ...history.pop(), history }); setContextError(null); setEditContext(null); setContextReview(null);
    }
    function edit(action, stockOnly = false) {
      setDialog(current => ({ ...current, action, stockOnly, category: detail.result.data.fields.category }));
    }
    function close() { if (!command.locked && !contextBusy && command.reset()) { setDialog(null); setEditContext(null); setContextReview(null); refreshGeneration.current++; } }
    function continueNavigation() {
      if (command.phase !== 'idle' || dialog || external.busy) { setNavigationError(C.failure('请先核实原请求并关闭原结果，再继续导航。')); return; }
      setNavigationError(null); setDeferred(false); setNode(target.node); setScope(readView ? readView.scope : scopeFor(target.node));
      if (readView) { setSelected(readView.selected_refs); setSortActive(readView.sort_active); setDialog(readView.detail ? navigationDialog(readView.detail) : null); }
      else if (!['part', 'calendar'].includes(target.context.kind)) setDialog(navigationDialog(target.context));
    }
    async function reloadContext() {
      if (command.locked || contextBusy) return;
      setContextError(null); setContextReview(null); setContextBusy(true);
      try {
        let result;
        if (dialog.ref) result = C.query(await adapter.detail(dialog.kind, dialog.ref, new AbortController().signal), 'entity');
        else result = C.query(await adapter.list(dialog.kind, { ...scope, page: 1, snapshot_ref: undefined }, new AbortController().signal), 'list');
        if (dialog.ref && result.data.ref !== dialog.ref) throw C.failure('读取的资料与所选记录不一致，请重新读取并核对。');
        setContextReview(result);
      } catch (error) { setContextError(error); }
      finally { setContextBusy(false); }
    }
    function acceptContext() {
      setEditContext({ context: dialog.ref ? contextReview.data.write_context : contextReview.data.create_context,
        source: contextReview.meta.source, entity: dialog.ref ? contextReview.data : null });
      if (dialog.ref && dialog.kind === 'op_type') setDialog(current => ({ ...current, category: contextReview.data.fields.category }));
      setContextReview(null); setContextError(null);
    }
    async function readAfterCommand() {
      if (command.phase !== 'done') return;
      const generation = ++refreshGeneration.current, intent = command.intent;
      if (intent.action === 'delete') setSelected(current => current.filter(ref => ref !== intent.ref));
      setRefreshState({ loading: true }); refresh();
      try {
        if (typeof adapter.list !== 'function') throw C.failure('列表刷新接口尚未接入。');
        const intentNode = Object.keys(C.nodes).find(key => C.nodes[key].kind === intent.kind && (!C.nodes[key].category || C.nodes[key].category === intent.category));
        const sameView = config && config.kind === intent.kind && (intent.kind !== 'op_type' || config.category === intent.category);
        const readScope = { ...(sameView ? scope : scopeFor(intentNode)), snapshot_ref: undefined };
        if (intent.kind === 'op_type') { delete readScope.status; readScope.category = intent.category; }
        const refreshedList = await readList(adapter, intent.kind, readScope, new AbortController().signal);
        let fresh = null;
        if (intent.action !== 'delete') {
          const ref = C.resultRef(command.result, intent.ref);
          if (typeof ref !== 'string' || !ref) throw C.failure('保存回执未提供对象引用，无法重读详情。');
          if (intent.ref && ref !== intent.ref) throw C.failure('保存回执对象与原请求不一致，需核实。');
          if (typeof adapter.detail !== 'function') throw C.failure('详情刷新接口尚未接入。');
          fresh = C.query(await adapter.detail(intent.kind, ref, new AbortController().signal), 'entity');
          if (fresh.data.ref !== ref) throw C.failure('保存结果详情与回执对象不一致。');
        }
        if (mounted.current && generation === refreshGeneration.current) setRefreshState({ done: true, detail: fresh, list: refreshedList });
      } catch (error) { if (mounted.current && generation === refreshGeneration.current) setRefreshState({ error }); }
    }
    React.useEffect(() => { if (command.phase === 'done') readAfterCommand(); }, [command.phase, command.result && command.result.receipt_ref]);
    async function openExternal(name, extra = {}) {
      if (blocked || typeof adapter[name] !== 'function') return;
      setExternal({ busy: true, error: null });
      let callbackCalled = false;
      const onCommitted = result => {
        callbackCalled = true;
        if (C.receipt(result) !== 'terminal') { setExternal({ busy: false, error: C.failure('向导未返回完成回执，结果仍待核实。') }); return; }
        if (result.data && Number.isInteger(result.data.deleted_count) && Array.isArray(result.data.rows)) {
          const removed = new Set(result.data.rows.map(row => row.entity_ref));
          setSelected(current => current.filter(ref => !removed.has(ref)));
        }
        refresh(); setExternal({ busy: false, error: null, result });
      };
      try {
        const result = await adapter[name](config.kind, { refs: selected.slice(), scope: { ...scope, source: list.result && list.result.meta.source, snapshot_ref: list.result && list.result.meta.snapshot_ref }, ...extra, onCommitted }, new AbortController().signal);
        if (callbackCalled) return;
        if (result && ['opened', 'cancelled'].includes(result.state)) { setExternal({ busy: false, error: null }); return; }
        if (C.receipt(result) === 'terminal') { onCommitted(result); return; }
        throw C.failure('向导未返回明确结果，未视为成功。');
      } catch (error) { setExternal({ busy: false, error }); }
    }
    const editorEntity = detail.result && detail.result.data;
    const editorReady = dialog && (dialog.action === 'create' || editorEntity);
    return <div className="plana resource-workspace" data-resource-workspace="true">
      <Rail node={node} counts={counts} onNode={navigate} onNavigate={onNavigate} disabled={blocked || !!dialog} />
      <section className="content">
        <ErrorBox error={navigationError} />
        {deferred && <div role="status"><p>原请求优先处理，精确导航暂缓；待核实写入未被覆盖。</p><Button icon="arrow-right" onClick={continueNavigation}>继续原导航</Button></div>}
        {!config ? <ErrorBox error={C.failure('未知的基础资料节点，请选择产能链中的资源。')} /> : <>
          {!(node === 'calendar' && renderCalendar) && <><div className="crumb"><span>产能链</span><span className="sep">/</span><span>{({ input: '输入', internal: '自制链', external: '外协链', global: '全局' })[config.chain]}</span><span className="sep">/</span><span className="cur">{config.label}</span></div>
          <div className="chead wb-page-heading"><h2>{config.label}{node === 'material' ? ' · 物料主数据' : ''}</h2></div></>}
          <ErrorBox error={external.error} />{external.busy && <p role="status">正在打开维护向导…</p>}
          {external.result && <Forms.Feedback command={{ phase: 'done', result: external.result }} />}
          {node === 'process' ? typeof renderPart === 'function' ? renderPart({ adapter, onNavigate, onRefresh: refresh, rememberEnabled: rememberEnabled && !navigationError && !deferred, initialContext: !deferred && target.context && target.context.kind === 'part' ? target.context : undefined }) : <p role="status" className="muted">工艺工作区尚未接入。</p> : node === 'calendar' ? typeof renderCalendar === 'function' ? renderCalendar({ onCommitted: refresh, rememberEnabled: rememberEnabled && !navigationError && !deferred, initialContext: !deferred && target.context && target.context.kind === 'calendar' ? target.context : undefined }) : <Calendar adapter={adapter} disabled={blocked} onExternal={openExternal} /> : <>
            <window.ResourceMetrics node={node} data={data} />
            {selected.length > 0 && <p className="muted" aria-live="polite">已选择 <b data-resource-selection-count>{selected.length}</b> 条{data && selected.some(ref => !data.entities.some(row => row.ref === ref)) && <> · <span>含非当前页记录</span></>}</p>}
            <Toolbar config={config} scope={scope} onFilter={filter} loading={list.loading} disabled={blocked} onRefresh={refresh} onCreate={() => open('create')}
              createReason={C.blocked(data && data.create_context, config.kind, 'create', list.result && list.result.meta.source)} onExternal={openExternal} adapter={adapter} selected={selected} ready={!!data} onClearSelection={() => setSelected([])} />
            {data && data.entities.length > 0 && <ErrorBox error={list.error} />}
            {data && <Issues issues={list.result.warnings} />}
            <Tables key={node} kind={config.kind} category={config.category} entities={data ? data.entities : []} source={list.result && list.result.meta.source} selected={selected} onSelect={setSelected}
              disabled={blocked || list.loading} headerDisabled={blocked} loading={list.loading} error={list.error} adapter={adapter} scope={scope} matchingCount={data && data.page.total}
              onRetry={refresh} onClear={() => filter({ query: '', column_filters: {}, ...(config.kind === 'op_type' ? {} : { status: '' }) })}
              onOpen={ref => open('view', ref)} onDelete={ref => open('delete', ref)} sort={scope.sort} direction={scope.direction} sortActive={sortActive} onSort={sortColumn} onColumnFilter={columnFilter} />
            {data && <Tables.Pager page={data.page} disabled={blocked || list.loading} onPage={changePage} onSize={size => filter({ size })} />}
          </>}
        </>}
      </section>
      {dialog && (dialog.action === 'view' || !editorReady) && <Forms.Detail key={dialog.kind + ':' + dialog.ref} adapter={adapter} kind={dialog.kind} result={detail.result} busy={detail.loading} error={detail.error} onRetry={detail.reload} onClose={close}
        onRelated={(kind, ref, category) => open('view', ref, { kind, category })} onBack={dialog.history && dialog.history.length ? back : null}
        onEdit={() => edit('update')} onAdjustStock={() => edit('update', true)} onDelete={() => edit('delete')} />}
      {editorReady && dialog.action !== 'view' && <><Forms key={dialog.kind + ':' + (dialog.ref || 'create') + ':' + dialog.action} adapter={adapter} kind={dialog.kind} action={dialog.action} entity={editorEntity} category={dialog.category} stockOnly={!!dialog.stockOnly}
        acceptedEntity={editContext && editContext.entity}
        writeContext={editContext ? editContext.context : editorEntity ? editorEntity.write_context : dialog.createContext} source={editContext ? editContext.source : editorEntity ? detail.result.meta.source : dialog.source}
        command={command} onClose={close} onReloadContext={reloadContext} refreshState={refreshState} onRefresh={readAfterCommand}
        contextError={contextError} contextBusy={contextBusy} contextReview={contextReview} onAcceptContext={acceptContext} /></>}
      {!dialog && (command.locked || command.phase === 'done') && <Modal title="原请求结果" icon="history" onClose={close} locked={command.locked} footer={<Button onClick={close} reason={command.locked ? '原请求尚未核实。' : ''}>关闭</Button>}>
        <div className="modal-b"><Forms.Feedback command={command} /><ErrorBox error={refreshState.error} /></div></Modal>}
    </div>;
  }
  window.ResourceWorkspace = ResourceWorkspace;
  ResourceWorkspace.navigation = navigation;
  ResourceWorkspace.readView = resourceReadView;
})();
