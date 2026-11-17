import React from './shared/runtime/react.js';
import C from './MasterOverviewContract.js';
import { Button, ErrorBox, MetricValue } from './ResourceControls.jsx';
import { Table, Tabs, Pager } from './MasterOverviewTable.jsx';
import APSMasterOverviewAPI from './MasterOverviewAPI.js';
import WorkbenchPageContext from './WorkbenchPageContext.jsx';
import WorkbenchTerms from './WorkbenchTerms.js';
import WorkbenchFormat from './WorkbenchFormat.js';
import MasterOverviewDetail from './MasterOverviewDetail.jsx';
import { ref48, failure, nonempty } from './shared/contract/kit.js';
import { useQuery } from './shared/session/query.js';

// 键集、定位与恢复浏览的互斥已由 WorkbenchNavigation.admit 按受控导航声明准入，这里核对取值。
function readContext(context) {
  const empty = { scope: C.scope({}), page: 1, selected: null, section: 'issues', detailPage: 1 };
  // 侧栏直接进入时 main.jsx 传空对象，按“无定位”处理。
  if (!Object.keys(context).length) return empty;
  if (context.read_view === undefined) {
    if (!ref48(context.entity_ref) || !C.domains.some(row => row[0] === context.domain)) throw failure('定位条件缺少资料类别或记录编号，页面没有跳转。请刷新后重试。');
    return { ...empty, initial: { domain: context.domain, entity_ref: context.entity_ref } };
  }
  const view = context.read_view;
  if (!view || typeof view !== 'object' || Array.isArray(view) || Object.keys(view).some(key => !['scope', 'page', 'selected', 'section', 'detail_page'].includes(key)))
    throw failure('上次操作记录里只能保存浏览状态，页面没有恢复。请刷新后重试。');
  const scope = C.scope(view.scope);
  if (!Number.isSafeInteger(view.page) || view.page < 1 || !Number.isSafeInteger(view.detail_page) || view.detail_page < 1
      || !['issues', 'relations', 'fields'].includes(view.section)) throw failure('上次操作记录里的页码或页签不正确，页面没有恢复。请刷新后重试。');
  const selected = view.selected;
  if (selected !== null && (!selected || typeof selected !== 'object' || Array.isArray(selected)
      || Object.keys(selected).some(key => !['domain', 'entity_ref', 'issue_ref'].includes(key)) || !ref48(selected.entity_ref)
      || !C.domains.some(row => row[0] === selected.domain) || selected.issue_ref !== undefined && !nonempty(selected.issue_ref))) throw failure('上次操作记录里的资料编号不正确，页面没有恢复。请刷新后重试。');
  return { scope, page: view.page, selected, section: view.section, detailPage: view.detail_page };
}
const closedDetail = { view: null, selected: null, section: 'issues', page: 1, captured: null };
const same = (item, target) => (item.entity_ref || item.ref) === target.entity_ref && item.domain === target.domain && (!target.issue_ref || item.issue_ref === target.issue_ref);
function selection(row) { return { ...row, entity_ref: row.entity_ref || row.ref }; }
// 读回一页清单后，详情选择跟到这一页：原地刷新沿用原来的选中项、页签和页码，选中项不在新清单里就收起；
// 恢复浏览用保存的选中项、页签和页码；其余选中定位到的资料或首行。随清单读回的首页待维护项（captured）直接展示，不再单独读取。
function follow(view, request, current) {
  const data = view.list.data, restore = request.restore, focus = data.selected;
  const row = request.inPlace ? current.selected && data.rows.find(item => same(item, current.selected))
    : restore && restore.selected ? data.rows.find(item => same(item, restore.selected))
    : focus ? data.rows.find(item => item.ref === focus.entity_ref && item.domain === focus.domain) : data.rows[0];
  const section = request.inPlace ? current.section : restore ? restore.section : 'issues';
  const page = request.inPlace ? current.page : restore ? restore.detailPage : 1;
  return { view, selected: row ? selection(row) : null, section, page,
    captured: row && row.domain === view.captured.data.entity.domain && (row.entity_ref || row.ref) === view.captured.data.entity.ref
      && section === 'issues' && page === 1 ? view.captured : null };
}
function Statistics({ overview, pending, error, scope, domainsId, onDomain }) {
  const metrics = overview && overview.stats, loading = !overview && pending, failure = !overview && error;
  return <><div className="wb-metrics mo-metrics" aria-label="总览状态" aria-busy={pending}>{[['entities', overview && !overview.complete ? '已读取资料' : '资料条数'], ['issues', '待维护项'], ['affected', '涉及资料'], ['relations', '已关联对数']].map(([key, label]) => <div className="wb-metric" key={key} data-tone={key === 'issues' ? 'warn' : undefined}>
    <span className="wb-metric-label">{label}</span><strong className="wb-metric-value"><MetricValue pending={loading} error={failure}>{metrics ? C.value(metrics[key]) : '未读取'}</MetricValue></strong></div>)}</div>
    <div className="wb-metrics mo-domains" aria-label="资料类别数量" aria-busy={pending}>{C.domains.map(([id, label], index) => { const domain = overview && overview.domains[index], countId = domainsId + '-' + id; return <button type="button" className="wb-metric mo-domain" key={id} aria-pressed={scope.domain === id} aria-label={'查看资料类别 ' + label} aria-describedby={countId + '-count ' + countId + '-helper'}
      onClick={() => onDomain(scope.domain === id ? 'all' : id)}><span className="wb-metric-label">{label}</span><strong className="wb-metric-value" id={countId + '-count'}><MetricValue pending={loading} error={failure}>{domain && domain.loaded ? domain.count : '未读取'}</MetricValue></strong>
      <span className="wb-metric-helper" id={countId + '-helper'}><MetricValue pending={loading && !failure} kind="helper">{failure ? '请刷新重试' : domain && domain.loaded ? domain.attention + ' 条需维护' + (domain.unknown ? ' · ' + domain.unknown + ' 条未确认' : '') : '来源未读取'}</MetricValue></span></button>; })}</div></>;
}
function ListTabs({ scope, metrics, pending, error, onChange }) {
  const count = key => <MetricValue pending={!metrics && pending} error={!metrics && error} kind="count">{metrics ? metrics[key] : '未读取'}</MetricValue>;
  return <Tabs label="清单类型" value={scope.view} onChange={onChange} values={[['issues', '待维护项', count('issues')], ['entities', '资料清单', count('entities')]]} />;
}
function MasterOverviewWorkspace({ onNavigate, initialContext }) {
  const api = APSMasterOverviewAPI;
  const contextKey = C.canonical(initialContext);
  const initial = React.useMemo(() => { try { return readContext(initialContext); } catch (error) { return { ...readContext({}), error }; } }, [contextKey]);
  const contextSeen = React.useRef(contextKey);
  const [request, setRequest] = React.useState(() => ({ scope: initial.scope, page: initial.page, initial: initial.initial, restore: initial }));
  const [search, setSearch] = React.useState(initial.scope.query), [column, setColumn] = React.useState(null), [columnText, setColumnText] = React.useState('');
  const [message, setMessage] = React.useState(''), [actionError, setActionError] = React.useState(null), [exporting, setExporting] = React.useState(false), [stale, setStale] = React.useState(false);
  const opener = React.useRef(null), listRef = React.useRef(null), listHeight = React.useRef(0), exportController = React.useRef(null), alive = React.useRef(true);
  const domainsId = React.useId();
  const detailFocus = React.useRef(!!(initial.initial || initial.selected));
  // 一次读取得到一页清单和随它读回的首页待维护项。统计是整份快照的统计、与筛选无关，接续读取期间一直显示上一次结果（keep 不变）；
  // 清单只在原地刷新时继续显示上一次结果，其余读取先清空。导出只读当前结果。
  const read = useQuery(signal => readPage(request, signal), [request], { keep: 'master-overview' });
  const view = request.inPlace ? read.shown : read.result, data = view && view.list.data, scope = data ? data.scope : request.scope;
  const pending = read.loading, readError = read.error, latest = read.shown, overview = latest && latest.list.data.overview, metrics = overview && overview.stats;
  // 详情选择记在它所属的那一页上；新读回的当前结果先按 follow 定下选择再渲染，这一页不在屏幕上时详情收起。
  const [chosen, setChosen] = React.useState(closedDetail);
  const followed = read.result !== null && chosen.view !== read.result ? follow(read.result, request, chosen) : null;
  if (followed) setChosen(followed);
  const detailState = followed || (chosen.view === view ? chosen : closedDetail), { selected, section, page: detailPage, captured } = detailState;
  const detailRead = useQuery(signal => api.detail(view.list.data.scope, selected, section, detailPage, view.list.meta.snapshot_ref, signal),
    [view, detailState], { enabled: Boolean(selected) && !captured });
  const currentDetail = selected ? captured || detailRead.result : null;
  const detailPending = Boolean(selected) && !captured && detailRead.loading, currentDetailError = detailRead.error;
  const currentScope = React.useRef(scope); currentScope.current = scope;
  React.useLayoutEffect(() => {
    if (!pending && listRef.current) listHeight.current = Math.ceil(listRef.current.parentElement.getBoundingClientRect().height);
  }, [pending, data, selected, currentDetail, detailPending]);
  async function readPage(next, signal) {
    if (initial.error) throw initial.error;
    let list = next.locate ? await api.locate(next.scope, next.locate, next.token, signal) : await api.list(next.scope, next.page, next.token, signal);
    if (next.initial) list = await api.locate(list.data.scope, next.initial, list.meta.snapshot_ref, signal);
    const restored = next.restore && next.restore.selected;
    if (restored && !list.data.rows.some(item => same(item, restored))) throw failure('原来选中的资料已不在当前范围，这里没有自动换成其他记录。请刷新后重试。');
    const first = list.data.selected || list.data.rows[0];
    return { list, captured: first ? C.detail({ ...list, data: list.data.selected_detail }, list.data.scope, selection(first), 'issues', list.meta.snapshot_ref) : null };
  }
  // 每次新读取先撤下上一次的提示和“可能已更新”标记，并停掉进行中的导出。
  function reread(next) { setStale(false); setActionError(null); setMessage(''); if (exportController.current) exportController.current.abort(); setRequest(next); }
  const refresh = () => { detailFocus.current = false; reread({ scope: currentScope.current, page: 1 }); };
  // Re-read the current page in place: page, selected row, detail section and detail page all survive the refresh.
  const refreshInPlace = () => reread({ scope: currentScope.current, page: data.page.number, inPlace: true });
  React.useEffect(() => { alive.current = true; return () => { alive.current = false; if (exportController.current) exportController.current.abort(); }; }, []);
  React.useEffect(() => {
    const changed = () => reread({ scope: currentScope.current, page: 1 });
    // Window focus only marks the list as possibly stale; a real data change still resets the list to page 1.
    const focused = () => setStale(true);
    window.addEventListener('focus', focused); window.addEventListener('aps:master-data-changed', changed);
    return () => { window.removeEventListener('focus', focused); window.removeEventListener('aps:master-data-changed', changed); };
  }, []);
  React.useEffect(() => {
    if (contextSeen.current === contextKey) return;
    contextSeen.current = contextKey;
    detailFocus.current = !!(initial.initial || initial.selected); opener.current = null;
    reread({ scope: initial.scope, page: initial.page, initial: initial.initial, restore: initial }); setSearch(initial.scope.query); setColumn(null);
  }, [contextKey, initial]);
  WorkbenchPageContext.useSnapshot({ read_view: { scope, page: data ? data.page.number : 1,
    selected: selected ? { domain: selected.domain, entity_ref: selected.entity_ref, ...(selected.issue_ref ? { issue_ref: selected.issue_ref } : {}) } : null,
    section, detail_page: detailPage } }, !!data && !pending && !detailPending && !currentDetailError && (!selected || !!currentDetail));
  function filter(patch) { detailFocus.current = false; reread({ scope: C.scope({ ...scope, ...patch }), page: 1 }); setColumn(null); }
  function select(row, button) { detailFocus.current = true; opener.current = button; setChosen({ view, selected: selection(row), section: 'issues', page: 1, captured: null }); }
  function clearFilters() { setSearch(''); filter({ domain: 'all', status: 'all', query: '', column_filters: {} }); }
  function closeDetail() { detailFocus.current = false; setChosen({ view, selected: null, section, page: detailPage, captured: null }); const target = opener.current && opener.current.isConnected ? opener.current : listRef.current; opener.current = target; if (target) target.focus(); }
  function locate(target) { detailFocus.current = true; setSearch(''); setColumn(null); reread({ scope: data.scope, token: view.list.meta.snapshot_ref, locate: target, page: 1 }); }
  async function navigate(target) {
    try { C.target(target); if (target.unavailable_reason) throw failure(target.unavailable_reason); await onNavigate(target.view, target.context); }
    catch (failure) { setActionError(failure); }
  }
  async function exportRows() {
    const current = read.result;
    if (!current || exporting) return;
    const controller = new AbortController(); exportController.current = controller; setExporting(true); setMessage(''); setActionError(null);
    try {
      const file = await api.export(current.list.data.scope, current.list.meta.snapshot_ref, controller.signal);
      if (alive.current && !controller.signal.aborted) { APSMasterOverviewAPI.save(file); setMessage(WorkbenchTerms.download_started(file.filename) + '（共 ' + file.count + ' 条）。'); }
    } catch (failure) { if (alive.current && failure.name !== 'AbortError') setActionError(failure); }
    finally { if (alive.current) setExporting(false); }
  }
  const empty = { scope, rows: [], page: { number: 1, size: scope.size, total: 0, pages: 1 } };
  return <section className="plana master-overview" aria-label="资料总览">
    <header className="mo-heading"><div><h2 className="wb-page-title">资料总览</h2><p className="wb-page-context">{latest ? '基础资料 · ' + WorkbenchTerms.data_as_of(WorkbenchFormat.dateTime(latest.list.meta.as_of)) : '基础资料'}
      <span role="status">{pending ? latest ? ' · 正在更新统计' : ' · 正在读取资料' : readError ? ' · 读取失败' : ''}</span></p></div>
      <div className="mo-actions"><Button reasonDisplay="inline" className="btn mo-icon" icon="refresh-cw" aria-label="刷新资料" onClick={refresh} />
        <Button reasonDisplay="inline" transfer="export" disabled={!read.result || exporting} onClick={exportRows}>导出筛选结果</Button>
        <Button reasonDisplay="inline" className="btn primary" onClick={async () => { try { await onNavigate('process', { source: 'production' }); } catch (failure) { setActionError(failure); } }}>维护基础资料</Button></div></header>
    <Statistics overview={overview} pending={pending} error={readError} scope={scope} domainsId={domainsId} onDomain={domain => filter({ domain })} />
    {overview && overview.gaps.length > 0 && <details className="mo-gaps" open><summary>原始数据缺口 {overview.gaps.length} 项</summary><ul>{overview.gaps.map((gap, index) => <li key={index}>{gap.message}</li>)}</ul></details>}
    <ErrorBox error={readError || actionError} />{message && <div className="mo-message" role="status">{message}</div>}
    {stale && !pending && data && <div className="mo-message mo-stale" role="status" data-master-stale><span>切回本页后资料可能已更新，当前页、选中项和详情都还保留着。</span><Button icon="refresh-cw" onClick={refreshInPlace}>刷新本页</Button></div>}
    <section className="mo-controls" aria-label="资料清单筛选"><ListTabs scope={scope} metrics={metrics} pending={pending} error={readError} onChange={view => filter({ view, status: 'all', column_filters: {} })} />
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
    {Object.keys(scope.column_filters).length > 0 && <p className="mo-muted">已启用 {Object.keys(scope.column_filters).length} 项列筛选</p>}</section>
    <div className={selected ? 'mo-workspace wb-detail-layout' : 'mo-workspace'}><div className="mo-list" ref={listRef} tabIndex={-1} style={pending && listHeight.current ? { minHeight: listHeight.current } : undefined}><Table data={data || empty} selected={selected} onSelect={select} onMaintain={navigate} onClear={clearFilters} onRetry={refresh} navigation loading={pending} error={readError}
      onFilter={key => { setColumn(key); setColumnText(scope.column_filters[key] === undefined ? '' : scope.column_filters[key]); }} />
      <Pager page={(data || empty).page} disabled={pending || !data} onSize={size => filter({ size })} onPage={page => reread({ scope: data.scope, page, token: view.list.meta.snapshot_ref })} /></div>
      <MasterOverviewDetail result={currentDetail} selected={selected} section={section} page={detailPage}
        onSection={value => { if (value !== section || detailPage !== 1) setChosen({ view, selected, section: value, page: 1, captured: null }); }}
        onPage={page => { if (page !== detailPage) setChosen({ view, selected, section, page, captured: null }); }} onLocate={locate} onMaintain={navigate}
        onBack={closeDetail} navigation loading={detailPending} error={currentDetailError} triggerRef={opener} autoFocus={detailFocus.current} /></div>
  </section>;
}
MasterOverviewWorkspace.readContext = readContext;
MasterOverviewWorkspace.Statistics = Statistics;
MasterOverviewWorkspace.ListTabs = ListTabs;

export { MasterOverviewWorkspace, readContext, Statistics, ListTabs };
export default MasterOverviewWorkspace;
