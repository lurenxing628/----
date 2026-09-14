(function () {
  'use strict';
  const C = window.APSMasterOverviewContract, { Button, ErrorBox } = window.ResourceControls;
  const { Table, Tabs, Pager } = window.MasterOverviewTable;
  const { useState, useEffect, useMemo, useRef } = React;
  async function readList(api, scope, page, token, signal) {
    if (page > 1 && !token) {
      const first = await api.list(scope, 1, undefined, signal);
      token = first.meta.snapshot_ref;
    }
    return api.list(scope, page, token, signal);
  }
  function readContext(context) {
    const empty = { scope: C.scope({}), page: 1, selected: null, section: 'issues', detailPage: 1 };
    if (context == null) return empty;
    if (!C.canonical(context) || typeof context !== 'object' || Array.isArray(context)
        || Object.keys(context).some(key => !['domain', 'entity_ref', 'read_view'].includes(key))) C.fail('跳转到基础资料的条件不支持，页面没有跳转。请刷新后重试。');
    if (context.read_view === undefined) {
      if (!C.ref(context.entity_ref) || !C.domains.some(row => row[0] === context.domain)) C.fail('定位条件缺少资料类别或记录编号，页面没有跳转。请刷新后重试。');
      return { ...empty, initial: { domain: context.domain, entity_ref: context.entity_ref } };
    }
    if (Object.keys(context).length !== 1) C.fail('定位和恢复浏览状态不能同时使用，页面没有跳转。请刷新后重试。');
    const view = context.read_view;
    if (!view || typeof view !== 'object' || Array.isArray(view) || Object.keys(view).some(key => !['scope', 'page', 'selected', 'section', 'detail_page'].includes(key)))
      C.fail('上次操作记录里只能保存浏览状态，页面没有恢复。请刷新后重试。');
    const scope = C.scope(view.scope);
    if (!Number.isSafeInteger(view.page) || view.page < 1 || !Number.isSafeInteger(view.detail_page) || view.detail_page < 1
        || !['issues', 'relations', 'fields'].includes(view.section)) C.fail('上次操作记录里的页码或页签不正确，页面没有恢复。请刷新后重试。');
    const selected = view.selected;
    if (selected !== null && (!selected || typeof selected !== 'object' || Array.isArray(selected)
        || Object.keys(selected).some(key => !['domain', 'entity_ref', 'issue_ref'].includes(key)) || !C.ref(selected.entity_ref)
        || !C.domains.some(row => row[0] === selected.domain) || selected.issue_ref !== undefined && !C.ref(selected.issue_ref))) C.fail('上次操作记录里的资料编号不正确，页面没有恢复。请刷新后重试。');
    return { scope, page: view.page, selected, section: view.section, detailPage: view.detail_page };
  }
  function MasterOverviewWorkspace({ onNavigate, initialContext }) {
    const api = useMemo(() => window.APSMasterOverviewAPI.create(), []);
    const contextKey = C.canonical(initialContext || null);
    const initial = useMemo(() => { try { return readContext(initialContext); } catch (error) { return { ...readContext(null), error }; } }, [contextKey]);
    const contextSeen = useRef(contextKey);
    const [request, setRequest] = useState(() => ({ scope: initial.scope, page: initial.page, initial: initial.initial, restore: initial }));
    const [result, setResult] = useState(null), [loading, setLoading] = useState(true), [error, setError] = useState(null);
    const [selected, setSelected] = useState(null), [section, setSection] = useState('issues'), [detailPage, setDetailPage] = useState(1);
    const [detail, setDetail] = useState(null), [detailLoading, setDetailLoading] = useState(false), [detailError, setDetailError] = useState(null);
    const [search, setSearch] = useState(initial.scope.query), [column, setColumn] = useState(null), [columnText, setColumnText] = useState('');
    const [message, setMessage] = useState(''), [actionError, setActionError] = useState(null), [exporting, setExporting] = useState(false), [stale, setStale] = useState(false);
    const opener = useRef(null), listRef = useRef(null), exportController = useRef(null), alive = useRef(true);
    const detailFocus = useRef(!!(initial.initial || initial.selected));
    const data = result && result.data, scope = data ? data.scope : request.scope;
    const currentScope = useRef(scope); currentScope.current = scope;
    const refresh = () => { detailFocus.current = false; setActionError(null); setMessage(''); setRequest({ scope: currentScope.current, page: 1 }); };
    // Re-read the current page in place: page, selected row, detail section and detail page all survive the refresh.
    const refreshInPlace = () => { setActionError(null); setMessage(''); setRequest({ scope: currentScope.current, page: data ? data.page.number : request.page, keep: true }); };
    useEffect(() => { alive.current = true; return () => { alive.current = false; if (exportController.current) exportController.current.abort(); }; }, []);
    useEffect(() => {
      const changed = () => setRequest({ scope: currentScope.current, page: 1 });
      // Window focus only marks the list as possibly stale; a real data change still resets the list to page 1.
      const focused = () => setStale(true);
      window.addEventListener('focus', focused); window.addEventListener('aps:master-data-changed', changed);
      return () => { window.removeEventListener('focus', focused); window.removeEventListener('aps:master-data-changed', changed); };
    }, []);
    useEffect(() => {
      if (contextSeen.current === contextKey) return;
      contextSeen.current = contextKey;
      detailFocus.current = !!(initial.initial || initial.selected); opener.current = null;
      setRequest({ scope: initial.scope, page: initial.page, initial: initial.initial, restore: initial }); setSearch(initial.scope.query); setColumn(null);
    }, [contextKey, initial]);
    useEffect(() => {
      const controller = new AbortController(); let active = true;
      const kept = request.keep ? selected : null;
      setLoading(true); setError(null); setStale(false); setActionError(null); setMessage('');
      if (!request.keep) { setResult(null); setSelected(null); setDetail(null); }
      if (exportController.current) exportController.current.abort();
      async function read() {
        try {
          if (initial.error) throw initial.error;
          let next = request.locate ? await api.locate(request.scope, request.locate, request.token, controller.signal)
            : await readList(api, request.scope, request.page, request.token, controller.signal);
          if (request.initial) {
            if (!C.ref(request.initial.entity_ref) || !C.domains.some(row => row[0] === request.initial.domain)) C.fail('定位条件缺少资料类别或记录编号，页面没有跳转。请刷新后重试。');
            next = await api.locate(next.data.scope, request.initial, next.meta.snapshot_ref, controller.signal);
          }
          if (!active) return;
          const focus = next.data.selected, restored = request.restore && request.restore.selected;
          const same = (item, target) => (item.entity_ref || item.ref) === target.entity_ref && item.domain === target.domain && (!target.issue_ref || item.issue_ref === target.issue_ref);
          const row = kept ? next.data.rows.find(item => same(item, kept)) : restored ? next.data.rows.find(item => same(item, restored))
            : focus ? next.data.rows.find(item => item.ref === focus.entity_ref && item.domain === focus.domain) : next.data.rows[0];
          if (restored && !row) C.fail('原来选中的资料已不在当前范围，这里没有自动换成其他记录。请刷新后重试。');
          setResult(next); setSelected(row ? selection(row) : null);
          if (!request.keep) { setSection(request.restore ? request.restore.section : 'issues'); setDetailPage(request.restore ? request.restore.detailPage : 1); }
        } catch (failure) { if (active && failure.name !== 'AbortError') setError(failure); }
        finally { if (active) setLoading(false); }
      }
      read(); return () => { active = false; controller.abort(); };
    }, [api, request]);
    useEffect(() => {
      if (!result || !selected) { setDetail(null); setDetailLoading(false); setDetailError(null); return undefined; }
      const controller = new AbortController(); let active = true;
      setDetailLoading(true); setDetail(null); setDetailError(null);
      api.detail(result.data.scope, selected, section, detailPage, result.meta.snapshot_ref, controller.signal).then(value => {
        if (active) setDetail(value);
      }).catch(failure => { if (active && failure.name !== 'AbortError') setDetailError(failure); }).finally(() => { if (active) setDetailLoading(false); });
      return () => { active = false; controller.abort(); };
    }, [api, result, selected, section, detailPage]);
    window.WorkbenchPageContext.useSnapshot({ read_view: { scope, page: data ? data.page.number : 1,
      selected: selected ? { domain: selected.domain, entity_ref: selected.entity_ref, ...(selected.issue_ref ? { issue_ref: selected.issue_ref } : {}) } : null,
      section, detail_page: detailPage } }, !!data && !loading && !error && !initial.error && !detailLoading && !detailError && (!selected || !!detail));
    function selection(row) { return { ...row, entity_ref: row.entity_ref || row.ref }; }
    function filter(patch) { detailFocus.current = false; setRequest({ scope: C.scope({ ...scope, ...patch }), page: 1 }); setColumn(null); }
    function select(row, button) { detailFocus.current = true; opener.current = button; setSelected(selection(row)); setSection('issues'); setDetailPage(1); }
    function clearFilters() { setSearch(''); filter({ domain: 'all', status: 'all', query: '', column_filters: {} }); }
    function closeDetail() { detailFocus.current = false; setSelected(null); const target = opener.current && opener.current.isConnected ? opener.current : listRef.current; opener.current = target; if (target) target.focus(); }
    function locate(target) { if (result) { detailFocus.current = true; setSearch(''); setColumn(null); setRequest({ scope: data.scope, token: result.meta.snapshot_ref, locate: target, page: 1 }); } }
    async function navigate(target) {
      try { C.target(target); if (target.unavailable_reason) C.fail(target.unavailable_reason); if (typeof onNavigate !== 'function') C.fail('dependency not wired: props.onNavigate'); await onNavigate(target.view, target.context); }
      catch (failure) { setActionError(failure); }
    }
    async function exportRows() {
      if (!result || !data.page.total || exporting) return;
      const controller = new AbortController(); exportController.current = controller; setExporting(true); setMessage(''); setActionError(null);
      try {
        const file = await api.export(data.scope, result.meta.snapshot_ref, data.page.total, controller.signal);
        if (alive.current && !controller.signal.aborted) { window.APSMasterOverviewAPI.save(file); setMessage('已发起下载：' + file.filename + '，共 ' + file.count + ' 条。'); }
      } catch (failure) { if (alive.current && failure.name !== 'AbortError') setActionError(failure); }
      finally { if (alive.current) setExporting(false); }
    }
    const overview = data && data.overview, metrics = overview && overview.stats;
    const empty = { scope, rows: [], page: { number: 1, size: scope.size, total: 0, pages: 1 } };
    return <section className="plana master-overview" aria-label="资料总览"><window.MasterOverviewStyles />
      <header className="mo-heading"><div><h2 className="wb-page-title">资料总览</h2><p className="wb-page-context">{result ? '基础资料 · 本机记录 · ' + window.WorkbenchFormat.dateTime(result.meta.as_of) : '基础资料 · 未读取'}</p></div>
        <div className="mo-actions"><Button reasonDisplay="inline" className="btn mo-icon" icon="refresh-cw" aria-label="刷新资料" onClick={refresh} />
          <Button reasonDisplay="inline" transfer="export" disabled={!data || !data.page.total || loading || exporting} onClick={exportRows}>导出筛选结果</Button>
          <Button reasonDisplay="inline" className="btn primary" reason={typeof onNavigate !== 'function' ? window.WorkbenchTerms.outcomes.unavailable : ''} onClick={async () => { try { await onNavigate('process', { source: 'production' }); } catch (failure) { setActionError(failure); } }}>维护基础资料</Button></div></header>
      <div className="wb-metrics mo-metrics" aria-label="总览状态">{[['entities', overview && !overview.complete ? '已读取资料' : '资料条数'], ['issues', '待维护项'], ['affected', '涉及资料'], ['relations', '已关联对数']].map(([key, label]) => <div className="wb-metric" key={key} data-tone={key === 'issues' ? 'warn' : undefined}>
        <span className="wb-metric-label">{label}</span><strong className="wb-metric-value">{metrics ? C.value(metrics[key]) : '未读取'}</strong></div>)}</div>
      <div className="wb-metrics mo-domains" aria-label="资料类别数量">{C.domains.map(([id, label], index) => { const domain = overview && overview.domains[index]; return <button type="button" className="wb-metric mo-domain" key={id} aria-pressed={scope.domain === id} aria-label={'查看资料类别 ' + label}
        onClick={() => filter({ domain: scope.domain === id ? 'all' : id })} disabled={loading}><span className="wb-metric-label">{label}</span><strong className="wb-metric-value">{domain && domain.loaded ? domain.count : '未读取'}</strong><span className="wb-metric-helper">{domain && domain.loaded ? domain.attention + ' 条需维护' + (domain.unknown ? ' · ' + domain.unknown + ' 条未确认' : '') : '来源未读取'}</span></button>; })}</div>
      {overview && <p className="mo-basis">{overview.basis}</p>}
      {overview && overview.gaps.length > 0 && <details className="mo-gaps" open><summary>原始数据缺口 {overview.gaps.length} 项</summary><ul>{overview.gaps.map((gap, index) => <li key={index}>{gap.message}</li>)}</ul></details>}
      <ErrorBox error={error || actionError} />{message && <div className="mo-message" role="status">{message}</div>}
      {stale && !loading && data && <div className="mo-message mo-stale" role="status" data-master-stale><span>切回本页后资料可能已更新，当前页、选中项和详情都还保留着。</span><Button icon="refresh-cw" onClick={refreshInPlace}>刷新本页</Button></div>}
      <Tabs label="清单类型" value={scope.view} onChange={view => filter({ view, status: 'all', column_filters: {} })} values={[["issues", "待维护项", metrics ? metrics.issues : '未读取'], ["entities", "资料清单", metrics ? metrics.entities : '未读取']]} />
      <form className="mo-tools" onSubmit={event => { event.preventDefault(); filter({ query: search }); }}>
        <label>资料类别<select aria-label="筛选资料类别" value={scope.domain} onChange={event => filter({ domain: event.target.value })}><option value="all">全部资料类别</option>{C.domains.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
        <label>状态<select aria-label="筛选检查状态" value={scope.status} onChange={event => filter({ status: event.target.value })}><option value="all">全部状态</option>{Object.entries(C.statuses).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
        <label className="mo-search"><input type="search" aria-label="搜索基础资料" placeholder="编号、名称或待维护项" value={search} maxLength={1000} onChange={event => setSearch(event.target.value)} /></label>
        <Button reasonDisplay="inline" type="submit" icon="search" className="btn mo-icon" aria-label="执行基础资料搜索" />
        <label>排序<select aria-label="基础资料排序" value={scope.sort} onChange={event => filter({ sort: event.target.value, direction: ['label', 'business_code'].includes(event.target.value) ? 'asc' : 'desc' })}>
          <option value="issue_count">待维护项</option><option value="business_code">编号</option><option value="label">名称</option><option value="relation_count">关联项</option></select></label>
        <Button reasonDisplay="inline" icon="chevron-down" className={'btn mo-icon' + (scope.direction === 'asc' ? ' mo-sort-asc' : '')} aria-label={scope.direction === 'asc' ? '切换为降序' : '切换为升序'} onClick={() => filter({ direction: scope.direction === 'asc' ? 'desc' : 'asc' })} />
        <Button reasonDisplay="inline" className="btn mo-icon" icon="x" aria-label="清除基础资料筛选" onClick={clearFilters} /></form>
      {column && <form className="mo-filter-band" onSubmit={event => { event.preventDefault(); const filters = { ...scope.column_filters }; if (columnText) filters[column] = columnText; else delete filters[column]; filter({ column_filters: filters }); }}>
        <label>{C.columns[scope.view].find(row => row[0] === column)[1]}<input aria-label="列包含文字" autoFocus value={columnText} maxLength={1000} onChange={event => setColumnText(event.target.value)} /></label>
        <Button reasonDisplay="inline" type="submit" icon="search">应用列筛选</Button><Button reasonDisplay="inline" icon="x" aria-label="关闭列筛选" onClick={() => setColumn(null)} /></form>}
      {Object.keys(scope.column_filters).length > 0 && <p className="mo-muted">已启用 {Object.keys(scope.column_filters).length} 项列筛选</p>}
      <div className={selected ? 'mo-workspace wb-detail-layout' : 'mo-workspace'}><div className="mo-list" ref={listRef} tabIndex={-1}><Table data={data || empty} selected={selected} onSelect={select} onMaintain={navigate} onClear={clearFilters} onRetry={refresh} navigation={typeof onNavigate === 'function'} loading={loading} error={error}
        onFilter={key => { setColumn(key); setColumnText(scope.column_filters[key] || ''); }} />
        {data && <Pager page={data.page} disabled={loading} onSize={size => filter({ size })} onPage={page => setRequest({ scope: data.scope, page, token: result.meta.snapshot_ref })} />}</div>
        <window.MasterOverviewDetail result={detail} selected={selected} section={section} onSection={value => { setSection(value); setDetailPage(1); }} onPage={setDetailPage} onLocate={locate} onMaintain={navigate}
          onBack={closeDetail} navigation={typeof onNavigate === 'function'} loading={detailLoading} error={detailError} triggerRef={opener} autoFocus={detailFocus.current} /></div>
    </section>;
  }
  window.MasterOverviewWorkspace = MasterOverviewWorkspace;
  MasterOverviewWorkspace.readContext = readContext;
  MasterOverviewWorkspace.readList = readList;
})();
