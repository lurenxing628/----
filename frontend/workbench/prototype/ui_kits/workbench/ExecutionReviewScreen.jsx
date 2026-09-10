function ERSection({ id, title, detail, actions, className = '', children }) {
  return <section className={'er-section ' + className} aria-labelledby={id}>
    <header className="er-section-heading"><div><h3 id={id}>{title}</h3>{detail && <p>{detail}</p>}</div>{actions && <div className="er-actions">{actions}</div>}</header>
    {children}
  </section>;
}

function ERReportButton({ children = '工序明细', onClick, disabled = false }) {
  const { ControlButton } = window.APSWorkbenchUI, { Icon } = window.APSAnalysisUI;
  return <ControlButton size="sm" disabled={disabled} onClick={onClick}>{children}<Icon name="arrow-up-right" /></ControlButton>;
}

function ERMetrics({ analysis }) {
  const { MetricStrip, Metric } = window.APSWorkbenchUI;
  const { formatNumber: n, formatPercent: pct } = window.APSExecutionAnalysis, s = analysis.summary;
  return <MetricStrip columns={4} className="er-metrics" aria-label="当前筛选执行指标">
    <Metric data-er-metric="fulfillment" label="到期工序完成率" value={pct(s.fulfilledRate)}
      helper={'已确认 ' + n(s.confirmedDue) + ' / 计划已到期 ' + n(s.due) + ' 道'} />
    <Metric data-er-metric="ontime" label="到期工序按时完成率" value={pct(s.ontimeRate)}
      helper={'按时 ' + n(s.dueOnTime) + ' / 计划已到期 ' + n(s.due) + ' 道'} />
    <Metric data-er-metric="unclosed" label="已超时未确认完成" value={n(s.lateOpen)} unit="道" tone={s.lateOpen ? 'warning' : undefined}
      helper={'距计划完成时间已超过 ' + n(analysis.toleranceMinutes) + ' 分钟'} />
    <Metric data-er-metric="hours" label="已报有效工时" value={n(s.knownHours)} unit={s.knownHours == null ? '' : 'h'}
      helper={n(s.records) + ' 条报工 · ' + n(s.unknownHourRecords) + ' 条工时未知'} />
  </MetricStrip>;
}

function ERInsights({ analysis, go }) {
  const { Icon } = window.APSAnalysisUI;
  return <ERSection id="er-insights-title" title="事实重点" detail="仅陈述记录差距与数据缺口" className="er-insights">
    {analysis.insights.length ? <ul className="er-insight-list">{analysis.insights.map(item => {
      const patch = {};
      ['focus', 'batch', 'resourceType', 'resource'].forEach(key => { if (item[key] !== undefined) patch[key] = item[key]; });
      return <li key={item.id} data-tone={item.tone}><button type="button" className="er-insight" data-er-insight={item.id}
        onClick={() => go(item.topic, patch)}><span><strong>{item.title}</strong><span className="er-insight-detail">{item.detail}</span></span><Icon name="arrow-up-right" /></button></li>;
    })}</ul> : <p className="er-empty">当前范围没有模型列出的事实重点。</p>}
  </ERSection>;
}

function ERResources({ analysis, go, state, onChange }) {
  const { ControlButton } = window.APSWorkbenchUI, { DistributionChart, Icon } = window.APSAnalysisUI;
  const { formatNumber: n } = window.APSExecutionAnalysis;
  const kind = state.resourceKind, page = state.resourcePage;
  const rows = window.APSReportWorkbench.sortRows(analysis.resources[kind], 'hours', 'desc');
  const size = 6, pages = Math.max(1, Math.ceil(rows.length / size)), current = Math.min(page, pages);
  const visible = rows.slice((current - 1) * size, current * size), resourceType = kind === 'machines' ? 'machine' : 'person';
  const inspect = row => go(kind, { resourceType, resource: row.resourceKey });
  const chartItems = visible.filter(row => row.hours !== null).map(row => ({ id: row.id, label: row.resource, count: row.hours, tone: 'notice' }));
  const choose = value => onChange({ resourceKind: value, resourcePage: 1 });
  const options = [['machines', '设备'], ['people', '人员']];
  return <ERSection id="er-resources-title" title="资源工时集中" detail="已报有效工时（h）· 未接入日历产能，不代表利用率或人员效率"
    actions={<ERReportButton onClick={() => go(kind)}>资源明细</ERReportButton>} className="er-resources">
    <div className="er-resource-toolbar"><div className="er-resource-tabs" role="tablist" aria-label="资源工时维度">{options.map(([id, label], index) =>
      <button key={id} type="button" role="tab" id={'er-resource-' + id} aria-selected={kind === id} aria-controls="er-resource-panel" tabIndex={kind === id ? 0 : -1}
        onClick={() => choose(id)} onKeyDown={event => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? 1 : 1 - index;
          choose(options[next][0]); document.getElementById('er-resource-' + options[next][0]).focus();
        }}>{label}</button>)}</div><span>按已知工时降序 · 未知保留</span></div>
    <div id="er-resource-panel" role="tabpanel" aria-labelledby={'er-resource-' + kind}>
      {chartItems.length > 0 && <DistributionChart items={chartItems} label={(kind === 'machines' ? '设备' : '人员') + '已报有效工时（h）'} onSelect={item => inspect(visible.find(row => row.id === item.id))} />}
      {visible.length ? <ul className="er-resource-notes">{visible.map(row => <li key={row.id} data-er-resource={row.id} data-hours={row.hours === null ? 'unknown' : row.hours}>
        <button type="button" className="er-resource-link" onClick={() => inspect(row)}><span>{row.resource}</span><Icon name="arrow-up-right" /></button>
        <span>{row.hours === null ? '工时未知' : n(row.hours) + ' h'} · {n(row.operations)} 道工序 · {n(row.records)} 条报工{row.unknownHours > 0 ? ' · ' + n(row.unknownHours) + ' 条工时未知' : ''}</span>
      </li>)}</ul> : <p className="er-empty">当前范围没有实际资源报工记录。</p>}
      <div className="er-pagination" aria-label="资源工时分页"><span aria-live="polite">共 {n(rows.length)} 项 · 本页 {n(visible.length)} 项 · 第 {current} / {pages} 页</span>
        <ControlButton className="er-icon-button" size="sm" aria-label="资源上一页" title="资源上一页" disabled={current <= 1} onClick={() => onChange({ resourcePage: current - 1 })}><Icon name="chevron-left" /></ControlButton>
        <ControlButton className="er-icon-button" size="sm" aria-label="资源下一页" title="资源下一页" disabled={current >= pages} onClick={() => onChange({ resourcePage: current + 1 })}><Icon name="chevron-right" /></ControlButton>
      </div>
    </div>
  </ERSection>;
}

function EROverview({ analysis, go, state, onChange }) {
  const { TrendChart, DistributionChart } = window.APSAnalysisUI, { formatNumber: n } = window.APSExecutionAnalysis, s = analysis.summary;
  return <React.Fragment>
    <div className="er-overview-grid">
      <ERSection id="er-trend-title" title="计划与实际累计完工" detail={'按工序计数 · 数据截至 ' + analysis.asOfLabel}
        actions={<ERReportButton onClick={() => go('delivery')}>工序明细</ERReportButton>} className="er-trend">
        <TrendChart points={analysis.trend} label="计划与实际累计完工工序" />
        <p className="er-method">实际曲线由当前记录按发生时间回算，不是历史当时快照；数据截至时间之后的实际值未知。</p>
      </ERSection>
      <ERInsights analysis={analysis} go={go} />
    </div>
    <div className="er-distribution-grid">
      <ERSection id="er-finish-title" title="已完工偏差分布" detail={'样本 ' + n(s.finishSample) + ' 道 · 仅已完工且有计划结束时间'} className="er-finish"
        actions={<ERReportButton onClick={() => go('delivery', { focus: 'finishLate' })}>晚完工明细</ERReportButton>}>
        <dl className="er-stat-line"><div><dt>中位数</dt><dd data-er-stat="median">{n(s.medianFinish)}{s.medianFinish == null ? '' : ' 分钟'}</dd></div><div><dt>P90</dt><dd data-er-stat="p90">{n(s.p90Finish)}{s.p90Finish == null ? '' : ' 分钟'}</dd></div><div><dt>样本量</dt><dd data-er-stat="sample">{n(s.finishSample)} 道</dd></div></dl>
        <DistributionChart items={analysis.distributions.finish} label="已完工偏差分布（道）" />
        {s.finishSample === 0 && <p className="er-empty">没有可比较的已完工样本；偏差不是 0。</p>}
        <p className="er-method">偏差 = 实际整道完工 − 计划完工；正值为延后，未确认完成的工序不计入。</p>
      </ERSection>
      <ERSection id="er-aging-title" title="距计划完成时间已过多久" detail={'未确认完成 ' + n(s.unclosedDue) + ' 道 · 已超时 ' + n(s.lateOpen) + ' 道'} className="er-aging"
        actions={<ERReportButton onClick={() => go('delivery', { focus: 'unclosed' })}>未确认完成明细</ERReportButton>}>
        <DistributionChart items={analysis.aging} label="距计划完成时间已过多久（道）" />
        <p className="er-method">这是从计划完成时间到数据截至时间已过的时长，不是实际完工偏差；超过 {n(analysis.toleranceMinutes)} 分钟才计入超时。未确认完成不等于未生产。</p>
      </ERSection>
    </div>
    <ERResources analysis={analysis} go={go} state={state} onChange={onChange} />
  </React.Fragment>;
}

function EROperations({ analysis, state, onChange, onGantt, onExport }) {
  const { DataTable, ControlButton, TransferButton } = window.APSWorkbenchUI, { Icon } = window.APSAnalysisUI;
  const model = window.APSReportWorkbench, api = window.APSExecutionAnalysis;
  const sorted = model.sortRows(analysis.rows, state.sort, state.direction), pager = model.paginate(sorted, state.page, state.pageSize);
  const change = patch => onChange({ page: 1, selected: null, ...patch });
  const columns = [
    { key: 'batch', title: '批次 / 工序', width: 230, render: row => <div className="er-stack"><strong>{row.batch}</strong><span>{row.op} · {row.name}</span></div> },
    { key: 'planEnd', title: '计划完工 / 整道完工', width: 160, render: row => <div className="er-stack"><span>{model.time(row.planEnd)}</span><span>{row.actualEnd ? model.time(row.actualEnd) : '未整道完工'}</span></div> },
    { key: 'status', title: '执行情况', width: 140, render: row => <div className="er-stack"><span className={'er-status er-' + row.status}>{row.statusLabel}</span><small className={row.finishLate ? 'er-danger' : row.unclosed ? 'er-warning' : ''}>{row.unclosed ? '到期未确认完成' : row.finishLate ? '晚完工超过 ' + analysis.toleranceMinutes + ' 分钟' : row.confirmedDue ? '到期已确认完成' : '计划完成时间未到'}</small></div> },
    { key: 'endDelta', title: '整道完工偏差', width: 130, render: row => row.endDelta == null ? '尚不可比较' : model.delta(row.endDelta) },
    { key: 'hours', title: '有效工时 / 待补', width: 130, render: row => <div className="er-stack"><span>{row.hours == null ? '工时未知' : api.formatNumber(row.hours) + ' h'}</span><small>{row.unknownHours} 条工时待补</small></div> },
    { key: 'action', title: '定位', width: 80, render: row => <ControlButton size="sm" className="er-icon-button" data-er-task={row.id} aria-label={'定位实际甘特 ' + row.id} aria-pressed={state.selected === row.id} title="定位实际甘特" onClick={() => { onChange({ selected: row.id }); onGantt(row); }}><Icon name="arrow-up-right" /></ControlButton> }
  ].map(column => ({ ...column, sortable: false, filterable: false }));
  return <ERSection id="er-operations-title" title="范围内工序" detail={analysis.rows.length + ' 道工序'} className="er-operations" actions={
    <div className="er-table-controls"><label>排序<select name="er-sort" value={state.sort} onChange={event => change({ sort: event.target.value })}>{[['planEnd', '计划完工'], ['batch', '批次编号'], ['endDelta', '整道完工偏差'], ['hours', '有效工时']].map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <label>顺序<select name="er-direction" value={state.direction} onChange={event => change({ direction: event.target.value })}><option value="asc">升序</option><option value="desc">降序</option></select></label>
      <TransferButton kind="export" disabled={!analysis.rows.length} onClick={onExport}>导出汇总</TransferButton></div>}>
    {pager.rows.length > 0 ? <div className="er-table-scroll" data-analysis-scroll="review-table"><DataTable className="er-operation-table" columns={columns} rows={pager.rows} rowKey="id" /></div> : <p className="er-empty">没有符合当前条件的工序。</p>}
    <div className="er-pagination"><span>共 {pager.total} 道 · 第 {pager.page} / {pager.pages} 页</span><label>每页<select name="er-page-size" value={state.pageSize} onChange={event => change({ pageSize: Number(event.target.value) })}>{[10, 20, 50].map(size => <option key={size} value={size}>{size} 道</option>)}</select></label>
      <ControlButton className="er-icon-button" size="sm" aria-label="复盘上一页" title="上一页" disabled={pager.page <= 1} onClick={() => onChange({ page: pager.page - 1, selected: null })}><Icon name="chevron-left" /></ControlButton>
      <ControlButton className="er-icon-button" size="sm" aria-label="复盘下一页" title="下一页" disabled={pager.page >= pager.pages} onClick={() => onChange({ page: pager.page + 1, selected: null })}><Icon name="chevron-right" /></ControlButton>
    </div>
  </ERSection>;
}

function ExecutionReviewContent({ onNav, scope, onScopeChange, initialContext }) {
  const [localScope, setLocalScope] = React.useState(null), [notice, setNotice] = React.useState(null);
  const [, refresh] = React.useReducer(value => value + 1, 0);
  const api = window.APSExecutionAnalysis, ui = window.APSAnalysisUI, workbench = window.APSWorkbenchUI;
  const { ScopeBar, Icon, useWorkspaceState } = ui, { ControlButton } = workbench;
  const contextScope = JSON.stringify(initialContext && initialContext.scope), previousContextScope = React.useRef(contextScope);
  const contextChanged = previousContextScope.current !== contextScope;
  if (contextChanged) { previousContextScope.current = contextScope; if (localScope) setLocalScope(null); }
  let activeScope = (onScopeChange && scope) || (!contextChanged && localScope) || scope || (initialContext && initialContext.scope), analysis = null, error = '';
  try { activeScope = activeScope || api.defaults('current'); analysis = api.build(activeScope); }
  catch (failure) { error = failure.message; }
  activeScope = analysis ? analysis.scope : activeScope;
  const workspace = useWorkspaceState('review', { topic: 'delivery', sort: 'planEnd', direction: 'asc', page: 1, pageSize: 20,
    selected: null, chartsOpen: false, filtersOpen: false, resourceKind: 'machines', resourcePage: 1 }, activeScope, initialContext);
  const change = next => {
    const value = { ...activeScope, ...next };
    setNotice(null); setLocalScope(value); if (onScopeChange) onScopeChange(value);
  };
  const returnTo = row => ({ view: 'review', context: { ...workspace.snapshot(), ...(row ? { selected: row.id } : {}), scope: api.linkScope(analysis), returning: true } });
  const go = (topic, patch = {}) => onNav('reports', { scope: api.linkScope(analysis, patch), topic, returnTo: returnTo() });
  const goGantt = row => onNav('fieldgantt', { scope: api.linkScope(analysis), taskId: row && row.id, returnTo: returnTo(row) });
  const exportSummary = () => {
    try { const file = api.summaryCSV(analysis); window.APSReportWorkbench.download(file); setNotice({ text: '当前筛选汇总已生成并交给浏览器下载。', error: false }); }
    catch (failure) { setNotice({ text: '导出失败：' + failure.message, error: true }); }
  };
  return <section className="er-workbench" aria-label="执行复盘" data-source={activeScope ? activeScope.source : 'current'} data-ready={analysis ? 'true' : 'false'} data-selected={workspace.state.selected || ''} ref={workspace.rootRef}>
    <header className="er-header"><div><h2>执行复盘</h2><p>{analysis ? analysis.source.provenance : '当前范围不可读取'}{analysis && <span className="er-asof">数据截至 {analysis.asOfLabel}</span>}</p></div><div className="er-actions">
      <ControlButton className="er-icon-button" size="sm" aria-label="重新计算执行复盘" title="重新读取当前数据" onClick={() => { refresh(); setNotice(null); }}><Icon name="refresh-cw" /></ControlButton>
      <ERReportButton disabled={!analysis} onClick={() => go(workspace.state.topic)}>报表中心</ERReportButton>
      <ERReportButton disabled={!analysis || !analysis.rows.length} onClick={() => goGantt()}>查看实际甘特</ERReportButton>
      {initialContext && initialContext.returnTo && <ControlButton size="sm" onClick={() => onNav(initialContext.returnTo.view, initialContext.returnTo.context)}>返回{initialContext.returnTo.view === 'reports' ? '报表中心' : '来源页面'}</ControlButton>}
    </div></header>
    <div className="er-scope"><ScopeBar analysis={analysis} scope={activeScope || { source: 'current', dateFrom: '', dateTo: '', batch: '', resourceType: 'all', resource: '', search: '', focus: 'all' }} onChange={change} idPrefix="er" expanded={workspace.state.filtersOpen} onExpandedChange={filtersOpen => workspace.update({ filtersOpen })} /></div>
    {notice && <p className="er-notice" role={notice.error ? 'alert' : 'status'}>{notice.text}</p>}
    {error ? <p className="er-error" role="alert">数据未能读取：{error}</p> : <React.Fragment>
      {analysis.warnings.length > 0 && <div className="er-warnings" role="status" aria-label="数据范围警告"><ul>{analysis.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></div>}
      {!analysis.rows.length && <p className="er-empty" role="status">当前筛选没有工序；分母为 0 的比率显示为“—”。</p>}
      <ERMetrics analysis={analysis} />
      <p className="er-basis">按计划完工日期选工序。按时：提前完成或延后不超过 {analysis.toleranceMinutes} 分钟；到期未确认完成 {analysis.summary.unclosedDue} 道，未确认完成不等于未生产。未知工时未计入合计。</p>
      <EROperations analysis={analysis} state={workspace.state} onChange={workspace.update} onGantt={goGantt} onExport={exportSummary} />
      <details className="er-chart-disclosure" open={workspace.state.chartsOpen} onToggle={event => { if (event.currentTarget.open !== workspace.state.chartsOpen) workspace.update({ chartsOpen: event.currentTarget.open }); }}><summary>趋势、偏差与资源分析</summary>
        <EROverview analysis={analysis} go={go} state={workspace.state} onChange={workspace.update} />
      </details>
      <details className="er-limitations" data-analysis-disclosure="review-limitations"><summary>数据范围与计算方法</summary><ul>{analysis.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details>
    </React.Fragment>}
  </section>;
}
function ExecutionReviewScreen(props) {
  if (!window.APSExecutionAnalysis || !window.APSAnalysisUI || !window.APSReportWorkbench || !window.APSWorkbenchUI) return <section className="er-workbench" data-ready="false" aria-label="执行复盘"><h2>执行复盘</h2><p role="alert">执行分析模型或共享界面未加载，无法生成复盘。</p></section>;
  return <ExecutionReviewContent {...props} />;
}
window.ExecutionReviewScreen = ExecutionReviewScreen;
