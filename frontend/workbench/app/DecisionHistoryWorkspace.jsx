(function () {
  'use strict';
  const A = window.DecisionHistoryAPI, C = window.ResourceControls, L = window.WorkbenchListControls, F = window.WorkbenchFormat;
  const stateLabels = { all: '全部状态', ...window.WorkbenchTerms.run_statuses, committed: '已提交采用', success: '采用成功', unknown: '状态未知', available: '来源可读', current: '当前版本', historical: '历史版本', unavailable: '来源缺失' };
  const clearEventFilters = { date_from: null, date_to: null, state: 'all', page: 1 };
  function ErrorBox({ error }) {
    return error ? <div className="dh-notice dh-error" role="alert">{error.code === 'snapshot_stale' && <strong>历史资料已更新。 </strong>}{error.message || '历史资料读取失败，请重新查询。'}</div> : null;
  }
  function Filters({ query, busy, onApply }) {
    const fields = value => ({ date_from: value.date_from, date_to: value.date_to, state: value.state, order: value.order });
    const [draft, setDraft] = React.useState(() => fields(query)), [error, setError] = React.useState(null);
    React.useEffect(() => { setDraft(fields(query)); setError(null); }, [query]);
    function set(patch) { setDraft(old => ({ ...old, ...patch })); setError(null); }
    function apply(event) {
      event.preventDefault();
      try { onApply(A.scope({ ...query, ...draft, page: 1, condition_page: 1, snapshot_ref: null, date_from: draft.date_from || null, date_to: draft.date_to || null })); setError(null); }
      catch (problem) { setError(problem); }
    }
    return <form className="dh-event-filter" aria-label="历史走势筛选" onSubmit={apply} noValidate><div className="dh-filters">
      <label>来源<select aria-label="历史时间线" value={query.timeline} aria-disabled={busy || undefined} onChange={event => { if (busy) return; onApply(A.scope({ ...query, timeline: event.target.value, selected_entry_ref: null, page: 1, condition_page: 1, snapshot_ref: null })); }}><option value="run">历次排产</option><option value="official">已采用方案</option></select></label>
      <label>起日<input type="date" aria-label="历史发生起日" value={draft.date_from || ''} disabled={busy} onChange={event => set({ date_from: event.target.value })} /></label>
      <label>止日<input type="date" aria-label="历史发生止日" value={draft.date_to || ''} disabled={busy} onChange={event => set({ date_to: event.target.value })} /></label>
      <label>状态<select aria-label="历史条目状态" value={draft.state} disabled={busy} onChange={event => set({ state: event.target.value })}>{A.states.map(state => <option key={state} value={state}>{stateLabels[state]}</option>)}</select></label>
      <div className="dh-actions"><C.Button type="submit" icon="search" busy={busy}>查询</C.Button><C.Button icon="x" aria-label="清除历史日期与状态筛选" disabled={busy} onClick={() => onApply(A.scope({ ...query, ...clearEventFilters, snapshot_ref: null }))} /><details className="dh-more-filter"><summary>{query.order === 'asc' ? '更多 · 从旧到新' : '更多'}</summary><label>顺序<select aria-label="历史时间顺序" value={draft.order} disabled={busy} onChange={event => set({ order: event.target.value })}><option value="desc">从新到旧</option><option value="asc">从旧到新</option></select></label></details></div>
    </div><ErrorBox error={error} /></form>;
  }
  function MetricControls({ query, definitions, metricKey, page, busy, onMetric, onQuery }) {
    const fields = value => ({ range_start: value.range_start, range_end: value.range_end, resource_window_days: value.resource_window_days });
    const [draft, setDraft] = React.useState(() => fields(query)), [error, setError] = React.useState(null);
    React.useEffect(() => { setDraft(fields(query)); setError(null); }, [query]);
    const needsWindow = definitions.some(value => query.metric_keys.includes(value.key) && A.windowMetric(value));
    function apply(event) {
      event.preventDefault();
      try {
        const next = { range_start: null, range_end: null, resource_window_days: draft.resource_window_days };
        if (draft.range_start !== null) { const time = window.WorkbenchDatePickerModel.factoryTime; next.range_start = time(draft.range_start || ''); next.range_end = time(draft.range_end || ''); }
        onQuery({ ...next, condition_page: 1 }); setError(null);
      } catch (problem) { setError(problem); }
    }
    return <div className="dh-metric-tools"><div className="dh-heading"><label className="dh-chart-metric">指标 <select aria-label="历史趋势指标" value={metricKey} aria-disabled={busy || undefined} onChange={event => { if (!busy) onMetric(event.target.value); }}>{query.metric_keys.map(key => { const definition = definitions.find(value => value.key === key); return <option key={key} value={key}>{definition ? definition.label : key}</option>; })}</select></label>{page && <span className="dh-muted">本页 {page.count} 条 · 共 {page.total} 条</span>}
      <details className="dh-metric-filter"><summary>表格指标 · {query.metric_keys.length} 项</summary><div className="dh-metric-options">{definitions.map(definition => <label key={definition.key}><input type="checkbox" checked={query.metric_keys.includes(definition.key)} disabled={busy || query.metric_keys.length === 1 && query.metric_keys[0] === definition.key} onChange={event => onQuery({ metric_keys: event.target.checked ? [...query.metric_keys, definition.key] : query.metric_keys.filter(key => key !== definition.key), condition_page: 1 })} />{definition.label}</label>)}</div></details></div>
      {needsWindow && <form className="dh-resource-filter" aria-label="历史资源时间范围" onSubmit={apply} noValidate><div className="dh-window"><label>统计时段<select aria-label="历史资源统计窗口" value={draft.range_start !== null ? 'absolute' : 'fixed_days'} disabled={busy} onChange={event => setDraft(old => ({ ...old, range_start: event.target.value === 'absolute' ? query.range_start || '' : null, range_end: event.target.value === 'absolute' ? query.range_end || '' : null }))}><option value="fixed_days">各次排产起点后 {draft.resource_window_days} 天</option><option value="absolute">相同日期</option></select></label>
        {draft.range_start === null ? <label>天数<input type="number" aria-label="历史资源窗口天数" min="1" max="366" step="1" value={draft.resource_window_days} disabled={busy} onChange={event => setDraft(old => ({ ...old, resource_window_days: Number(event.target.value) }))} /></label> : <><label>开始<input type="text" data-picker-type="factory-local" aria-label="历史资源共同窗口开始" value={draft.range_start || ''} disabled={busy} onChange={event => setDraft(old => ({ ...old, range_start: event.target.value }))} /></label><label>结束<input type="text" data-picker-type="factory-local" aria-label="历史资源共同窗口结束" value={draft.range_end || ''} disabled={busy} onChange={event => setDraft(old => ({ ...old, range_end: event.target.value }))} /></label></>}
        <C.Button type="submit" busy={busy}>应用时间</C.Button></div><ErrorBox error={error} /></form>}
    </div>;
  }
  function metricHint(metric) {
    return metric.unknown_count ? metric.unknown_count + ' 项待确认' : '';
  }
  function Table({ data, metricKey, selectedEntryRef, onSelect, onReference, busy }) {
    const frame = React.useRef(null), definitions = data.filters.metric_keys.map(key => data.metric_definitions.find(row => row.key === key));
    const marked = data.trend.points.filter(point => point.range_changed).map(point => point.entry_ref);
    function move(event, index) {
      if (busy) return;
      const next = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? Math.min(index + 1, data.entries.length - 1) : event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? Math.max(index - 1, 0) : event.key === 'Home' ? 0 : event.key === 'End' ? data.entries.length - 1 : null;
      if (next !== null) { event.preventDefault(); const entry = data.entries[next]; onSelect(entry, false); frame.current.querySelector('[data-dh-row-choice="' + entry.entry_ref + '"]').focus(); }
    }
    return <div ref={frame} className="dh-history-table wb-table-frame" data-sticky-head data-sticky-actions tabIndex={0} aria-label="历史数值表滚动区域"><table className="wb-table" aria-label="历史走势数值表"><caption className="wb-visually-hidden">与当前页历史趋势图同源的原始数值</caption>
      <thead><tr><th scope="col" className="wb-col-key">发生时间 / 条目</th><th scope="col">来源与状态</th><th scope="col">业务范围</th>{definitions.map(definition => <th key={definition.key} scope="col" className="dh-number" data-metric-key={definition.key} data-active-metric={definition.key === metricKey || undefined}>{definition.label}</th>)}<th scope="col" className="wb-col-actions">对照</th></tr></thead>
      <tbody>{data.entries.map((entry, index) => <tr key={entry.entry_ref} data-history-entry={entry.entry_ref} data-selected={entry.entry_ref === selectedEntryRef || undefined}>
        <td className="wb-col-key"><C.Button className="btn link dh-row-choice" data-dh-row-choice={entry.entry_ref} aria-pressed={entry.entry_ref === selectedEntryRef} disabled={busy} tabIndex={entry.entry_ref === selectedEntryRef || !data.entries.some(row => row.entry_ref === selectedEntryRef) && index === 0 ? 0 : -1} onKeyDown={event => move(event, index)} onClick={() => onSelect(entry, true)}>{entry.occurred_at ? F.dateTime(entry.occurred_at) : '时间未记录'}<small>{entry.label}</small></C.Button></td>
        <td>{A.sourceLabel(entry)}<small>{stateLabels[entry.state] || entry.state}</small></td>
        <td>{F.number(entry.scope.batch_count, { digits: 0 })} 批 / {F.number(entry.scope.operation_count, { digits: 0 })} 道{marked.includes(entry.entry_ref) && <small className="dh-range-change">统计范围有变化</small>}</td>
        {definitions.map(definition => { const metric = entry.metrics[definition.key]; return <td key={definition.key} className="dh-number" data-metric-key={definition.key} data-metric-value={metric.value === null ? '' : metric.value} data-value-state={metric.state} title={metric.reason ? metric.reason.message : undefined}>
          {A.metricText(metric, definition)}{metric.value === null && metric.known_count > 0 && metric.known_subtotal !== null && <small>已知小计 {A.numberText(metric.known_subtotal, metric.unit, definition.precision)}</small>}{metricHint(metric) && <small>{metricHint(metric)}</small>}</td>; })}
        <td className="wb-col-actions">{entry.identity.run_ref ? <><C.Button disabled={busy} aria-label={'将 ' + entry.label + ' 用作对照'} title={entry.source_kind === 'candidate_adoption' ? '对照其来源排产：' + entry.label : undefined} onClick={() => onReference(entry)}>{data.selection.reference && data.selection.reference.identity.run_ref === entry.identity.run_ref ? '当前对照' : '用作对照'}</C.Button>{entry.source_kind === 'candidate_adoption' && <small>对照其来源排产{data.selection.reference && data.selection.reference.identity.run_ref === entry.identity.run_ref ? '：' + data.selection.reference.label : ''}</small>}</> : <span className="dh-muted">{entry.source_kind === 'trial_adoption' ? '试调来源' : '旧正式计划来源'}</span>}</td>
      </tr>)}</tbody></table></div>;
  }
  function Export({ adapter, result, query, busy: reading }) {
    const [format, setFormat] = React.useState(null), [section, setSection] = React.useState('entries'), [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null), [done, setDone] = React.useState(''), active = React.useRef(null);
    React.useEffect(() => () => { if (active.current) active.current.abort(); }, []);
    function cancel() { if (active.current) active.current.abort(); active.current = null; setBusy(false); setFormat(null); }
    async function save() {
      if (active.current || !format) return;
      const controller = new AbortController(); active.current = controller; setBusy(true); setError(null);
      try {
        A.check(typeof adapter.historyExport === 'function', '历史导出接口尚未接入。');
        const file = await adapter.historyExport(query, result.meta.snapshot_ref, format, controller.signal, section);
        if (controller.signal.aborted) return;
        window.APSWorkbenchTransport.saveBlob(file.filename, file.blob); setDone(window.WorkbenchTerms.download_started(file.filename) + ' · ' + file.row_count + ' 条记录'); setFormat(null);
      } catch (problem) { if (!controller.signal.aborted) setError(problem); }
      finally { if (!controller.signal.aborted) { active.current = null; setBusy(false); } }
    }
    return <><C.Button icon="download" disabled={reading || busy} onClick={() => { setFormat('xlsx'); setSection('entries'); setError(null); setDone(''); }}>导出历史</C.Button>{done && <span role="status">{done}</span>}
      {format && <C.Modal title="导出历史走势" icon="download" onClose={cancel} footer={<><C.Button onClick={cancel}>{busy ? '取消导出' : '取消'}</C.Button><C.Button transfer="export" className="btn primary" busy={busy} onClick={save}>下载 {format.toUpperCase()}</C.Button></>}><div className="modal-b dh-export-fields">
        <label>文件格式<select aria-label="历史导出文件格式" value={format} disabled={busy} onChange={event => { setFormat(event.target.value); if (event.target.value === 'csv' && section === 'all') setSection('entries'); }}><option value="xlsx">XLSX</option><option value="csv">CSV</option></select></label>
        <label>导出内容<select aria-label="历史导出内容" value={section} disabled={busy} onChange={event => setSection(event.target.value)}><option value="entries">当前筛选的全部历史条目</option><option value="conditions">选中条目与基准的生产条件</option><option value="configurations">选中条目与基准的算法配置</option>{format === 'xlsx' && <option value="all">全部分区及指标口径、范围和缺项</option>}</select></label>
        <p>条目文件包含当前筛选的全部页面。生产条件与算法配置对应当前选中条目和明确基准。</p><ErrorBox error={error} /></div></C.Modal>}</>;
  }
  const adapters = new WeakMap(); let nextAdapter = 0;
  function Session({ adapter, start, pageContext, navigation, onNavigate, renderTopics }) {
    const [query, setQuery] = React.useState(start.query), [metricKey, setMetricKey] = React.useState(start.metric_key), [revision, refresh] = React.useReducer(value => value + 1, 0), [paused, setPaused] = React.useState(false), [conditionsOpen, setConditionsOpen] = React.useState(false), [missingOpen, setMissingOpen] = React.useState(false);
    const workspace = React.useRef(null), pendingFocus = React.useRef(null), readingHeight = React.useRef(null);
    const api = React.useMemo(() => A.adapter(adapter), [adapter]), serialized = JSON.stringify(query);
    const read = window.APSResourceSession.useQuery(signal => api.history(query, signal), [api, serialized, revision, paused], !paused), result = read.result, data = result && result.data;
    const remembered = { query: { ...query, ...(result ? { snapshot_ref: result.meta.snapshot_ref } : {}) }, selected_entry_ref: query.selected_entry_ref, reference_entry_ref: query.reference_run_ref && 'run:' + query.reference_run_ref, metric_key: metricKey, detail_queries: { ...start.detail_queries, conditions: { page: query.condition_page, size: query.condition_size } } };
    const historyContext = { ...pageContext, source: 'run_history', history_topic: 'decision_history', decision_history_context: remembered };
    window.WorkbenchPageContext.useSnapshot(historyContext);
    React.useLayoutEffect(() => {
      if (!read.loading) readingHeight.current = null;
      const intent = pendingFocus.current;
      if (!data || !intent || !workspace.current) return;
      if (intent.source === 'chart') {
        workspace.current.querySelectorAll('.dh-chart-series[data-metric-unit]').forEach(series => {
          const saved = intent.scrolls.find(value => value.unit === series.getAttribute('data-metric-unit'));
          if (saved) series.querySelector('.dh-chart-scroll').scrollLeft = saved.left;
        });
        const point = workspace.current.querySelector('.dh-chart-entry[data-entry-ref="' + intent.entryRef + '"]');
        if (point) { const scroll = point.closest('.dh-chart-scroll'), item = point.getBoundingClientRect(), viewport = scroll.getBoundingClientRect(); if (item.left < viewport.left) scroll.scrollLeft += item.left - viewport.left; else if (item.right > viewport.right) scroll.scrollLeft += item.right - viewport.right; }
      }
      const pager = intent.source === 'conditions' && workspace.current.querySelector('[data-history-condition-pager]');
      const target = intent.source === 'conditions' ? pager && (intent.label && pager.querySelector('[aria-label="' + intent.label + '"]:not(:disabled)') || pager) : intent.reveal || intent.source === 'detail' ? workspace.current.querySelector('[data-history-detail-title]') : intent.source === 'chart' ? workspace.current.querySelector('.dh-chart-keyboard') : workspace.current.querySelector('[data-dh-row-choice="' + intent.entryRef + '"]');
      if (target) { target.focus({ preventScroll: true }); if (intent.reveal) target.scrollIntoView({ block: 'start' }); pendingFocus.current = null; }
    }, [result, read.loading]);
    function apply(next) { const value = A.scope(next); if (value.timeline !== query.timeline || value.page !== query.page || value.size !== query.size || !value.metric_keys.includes(metricKey)) { setMissingOpen(false); if (pendingFocus.current && pendingFocus.current.source === 'chart') pendingFocus.current = null; } if (value.selected_entry_ref !== query.selected_entry_ref || value.reference_run_ref !== query.reference_run_ref) { setConditionsOpen(false); if (pendingFocus.current && pendingFocus.current.source === 'conditions') pendingFocus.current = null; } setPaused(false); setQuery(value); if (!value.metric_keys.includes(metricKey)) setMetricKey(value.metric_keys[0]); refresh(); }
    function change(patch, paging = false) { if (paging && ('condition_page' in patch || 'condition_size' in patch)) { const trigger = document.activeElement; pendingFocus.current = { source: 'conditions', label: trigger && trigger.getAttribute('aria-label'), reveal: false }; readingHeight.current = workspace.current ? workspace.current.getBoundingClientRect().height : null; } apply({ ...query, ...patch, snapshot_ref: paging && result ? result.meta.snapshot_ref : null }); }
    function reload() { setPaused(false); setQuery(old => ({ ...old, snapshot_ref: null })); refresh(); }
    function select(entry, source, reveal = false) { pendingFocus.current = { source, entryRef: entry.entry_ref, reveal, ...(source === 'chart' ? { scrolls: workspace.current ? Array.from(workspace.current.querySelectorAll('.dh-chart-series[data-metric-unit]'), series => ({ unit: series.getAttribute('data-metric-unit'), left: series.querySelector('.dh-chart-scroll').scrollLeft })) : [] } : {}) }; readingHeight.current = !reveal && workspace.current ? workspace.current.getBoundingClientRect().height : null; change({ selected_entry_ref: entry.entry_ref, condition_page: 1 }); }
    function reference(entry) { pendingFocus.current = { source: 'detail', reveal: true }; change({ reference_run_ref: entry.identity.run_ref, selected_entry_ref: query.selected_entry_ref === 'run:' + entry.identity.run_ref ? null : query.selected_entry_ref, comparison: 'same_conditions', condition_page: 1 }); }
    function endComparison() { setConditionsOpen(false); pendingFocus.current = { source: 'detail', reveal: false }; change({ reference_run_ref: null, comparison: 'observed' }); }
    function open(target) { if (typeof onNavigate === 'function' && target.enabled) onNavigate(target.view, { ...target.context, return_decision_history_context: remembered }); }
    return <div ref={workspace} className="plana run-history-workspace decision-history-workspace" data-decision-history-workspace aria-busy={read.loading} style={read.loading && readingHeight.current !== null ? { minHeight: readingHeight.current } : undefined}><h2 className="wb-page-title">排产记录</h2><header className="dh-heading scheduling-page-tools">{navigation}<div className="dh-actions">
      {result && <Export key={result.meta.snapshot_ref} adapter={api} result={result} query={query} busy={read.loading} />}<C.Button icon="refresh-cw" busy={read.loading} aria-label="刷新历史走势" onClick={reload} />{read.loading && <C.Button onClick={() => setPaused(true)}>取消读取</C.Button>}</div></header>
      {renderTopics && renderTopics(historyContext)}<div id="dh-history-content" role="tabpanel" aria-labelledby="dh-topic-decision_history">
      <Filters query={query} busy={read.loading} onApply={apply} />
      <ErrorBox error={read.error} />{read.error && <C.Button icon="refresh-cw" onClick={reload}>刷新当前条件</C.Button>}{paused && <div className="dh-notice" role="status">读取已取消。<C.Button onClick={reload}>继续读取</C.Button></div>}
      {data && <>
        {result.warnings.map((warning, index) => <div key={index} className="dh-notice" role="status">{warning.message}</div>)}
        <MetricControls query={query} definitions={data.metric_definitions} metricKey={metricKey} page={{ count: data.entries.length, total: data.page.total }} busy={read.loading} onMetric={key => { if (key !== metricKey) { setMissingOpen(false); if (pendingFocus.current && pendingFocus.current.source === 'chart') pendingFocus.current = null; } setMetricKey(key); }} onQuery={change} />
        {data.entries.length ? <window.DecisionHistoryChart.Chart data={data} metricKey={metricKey} selectedEntryRef={query.selected_entry_ref} onSelect={(entry, reveal) => select(entry, 'chart', reveal)} busy={read.loading} missingOpen={missingOpen} onMissingToggle={setMissingOpen} /> : <L.EmptyState kind={data.totals[query.timeline] === 0 ? 'empty' : 'filtered'} title={data.totals[query.timeline] === 0 ? '这条时间线尚无记录' : data.page.total === 0 ? '当前筛选没有历史条目' : '当前页没有历史条目'} hint="历史走势读取已经保存的来源。" action={data.page.total > 0 ? <C.Button onClick={() => change({ page: 1 }, true)}>返回第 1 页</C.Button> : data.totals[query.timeline] > 0 ? <C.Button icon="x" onClick={() => change(clearEventFilters)}>清除日期与状态筛选</C.Button> : null} />}
        <window.DecisionHistoryDetails.Details data={data} onQuery={change} onOpen={open} canNavigate={typeof onNavigate === 'function'} busy={read.loading} conditionsOpen={conditionsOpen} onConditionsToggle={setConditionsOpen}
          onEndComparison={endComparison} />
        {data.entries.length > 0 && <><h3 className="dh-list-title">历史记录</h3><Table data={data} metricKey={metricKey} selectedEntryRef={query.selected_entry_ref} onSelect={(entry, reveal) => select(entry, 'table', reveal)} onReference={reference} busy={read.loading} /></>}
        <div className="dh-page"><L.Pager page={data.page} sizes={[20, 50]} unit="条" label="历史条目" sizeLabel="历史每页条数" busy={read.loading} onPage={number => change({ page: number }, true)} onSize={size => change({ page: 1, size }, true)} /></div>
        <window.DecisionHistoryDetails.Sources data={data} result={result} />
      </>}{read.loading && !data && <L.EmptyState kind="loading" title="正在读取历史走势" hint="正在读取保存的历史记录。" />}</div></div>;
  }
  function Workspace({ initialContext = {}, pageContext = {}, adapter, navigation, onNavigate, renderTopics }) {
    const fallback = React.useMemo(() => A.create(), []), active = adapter || fallback;
    let start; try { start = A.context(initialContext); A.check(active && typeof active.history === 'function', '历史查询接口尚未接入。'); }
    catch (error) { return <div className="plana run-history-workspace decision-history-workspace"><h2 className="wb-page-title">排产记录</h2>{navigation}<ErrorBox error={error} /></div>; }
    if (!adapters.has(active)) adapters.set(active, ++nextAdapter);
    return <Session key={adapters.get(active) + ':' + JSON.stringify(start)} adapter={active} start={start} pageContext={pageContext} navigation={navigation} onNavigate={onNavigate} renderTopics={renderTopics} />;
  }
  window.DecisionHistoryWorkspace = Workspace;
  window.DecisionHistoryViews = { ErrorBox, Filters, MetricControls, Table, Export, Session };
})();
