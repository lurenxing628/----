function RWIcon({ name }) {
  const { Icon } = window.APSAnalysisUI;
  return <Icon name={name} />;
}
function RWStatus({ row }) {
  return <span className={'rw-status rw-' + row.status}>{row.statusLabel}</span>;
}
function RWTabs({ options, value, onChange, label, prefix }) {
  return <div className="rw-tabs" role="tablist" aria-label={label}>{options.map(([id, text], i) => <button key={id} id={prefix + '-' + id} type="button" role="tab" aria-selected={value === id} aria-controls={prefix + '-panel'} tabIndex={value === id ? 0 : -1} onClick={() => onChange(id)} onKeyDown={e => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
    e.preventDefault(); const n = e.key === 'Home' ? 0 : e.key === 'End' ? options.length - 1 : (i + (e.key === 'ArrowRight' ? 1 : -1) + options.length) % options.length;
    onChange(options[n][0]); document.getElementById(prefix + '-' + options[n][0]).focus();
  }}>{text}</button>)}</div>;
}
function RWDetail({ row, source, toleranceMinutes, onClose, onNav, onGantt, recordPage, onRecordPage, focusOnOpen }) {
  const api = window.APSReportWorkbench, { DataTable, ControlButton } = window.APSWorkbenchUI;
  const startField = React.useRef(null);
  React.useEffect(() => { if (focusOnOpen) startField.current.focus(); }, [row.id]);
  const records = row.summary.reports;
  const flags = row.flags.filter(flag => flag === 'finishLate' ? row.finishLate : flag === 'unclosedLate' ? row.lateOpen : flag === 'startLate' ? row.startDelta > toleranceMinutes : true);
  const pager = api.paginate(records, recordPage, 10);
  const columns = [
    { key: 'reportNo', title: '报工编号', render: r => <span className="rw-code">{r.reportNo}</span> },
    { key: 'qty', title: '本次数量', render: r => api.number(r.qty) + (r.qty == null ? '' : ' 件') },
    { key: 'start', title: '实际开工 / 本次结束', render: r => <div className="rw-stack"><span>{api.time(r.start)}</span><small>{api.time(r.end)}</small></div> },
    { key: 'hours', title: '有效工时', render: r => api.number(r.hours) + (r.hours == null ? '' : ' h') },
    { key: 'machine', title: '实际设备 / 人员', render: r => <div className="rw-stack"><span>{r.machine || '未填写'}</span><small>{r.person || '未填写'}</small></div> },
    { key: 'remark', title: '作业备注 / 录入信息', render: r => <div className="rw-stack"><span>{r.remark || '无备注'}</span><small>{api.time(r.recorded)} · 修订 {r.revision || 0} 次</small>{api.recordGaps(r).length > 0 && <small className="rw-warning">待补：{api.recordGaps(r).join('、')}</small>}</div> }
  ].map(c => ({ ...c, sortable: false, filterable: false }));
  const goField = () => {
    const state = window.APSFieldReports.model.state;
    state.filter = 'all'; state.search = row.batch; state.selected = row.id; state.expanded = row.id;
    onNav('field');
  };
  return <section className="rw-detail" id="rw-detail" aria-label="工序报表详情" ref={startField} tabIndex="-1" onKeyDown={e => { if (e.key === 'Escape') onClose(); }}>
    <div className="rw-section-heading"><div><h3>{row.batch} · {row.op}</h3><p>{row.name} · {row.statusLabel}</p></div><div className="rw-actions">
      {source === 'current' && <ControlButton size="sm" onClick={goField}>查看现场记录</ControlButton>}
      <ControlButton size="sm" onClick={() => onGantt(row)}>查看实际甘特<RWIcon name="arrow-up-right" /></ControlButton>
      <ControlButton className="rw-icon-button" size="sm" aria-label="关闭工序详情" title="关闭详情" onClick={onClose}><RWIcon name="x" /></ControlButton>
    </div></div>
    <dl className="rw-detail-facts"><div><dt>累计数量</dt><dd>{api.number(row.qty)} / {row.target} 件</dd></div><div><dt>待报数量</dt><dd>{row.remaining} 件</dd></div><div><dt>计划跨度</dt><dd>{row.planSpan == null ? '不可计算' : api.number(row.planSpan) + ' h'}</dd></div><div><dt>已报有效工时</dt><dd>{row.hours == null ? '未报' : api.number(row.hours) + ' h'}</dd></div></dl>
    <div className="rw-detail-notes"><span>{flags.length ? flags.map(f => f === 'finishLate' ? '晚完工超过 ' + toleranceMinutes + ' 分钟' : f === 'unclosedLate' ? '距计划完成时间已超过 ' + toleranceMinutes + ' 分钟，尚未确认完成' : f === 'startLate' ? '晚开工超过 ' + toleranceMinutes + ' 分钟' : api.anomalies[f]).join(' · ') : '当前可比较数据未发现超过 ' + toleranceMinutes + ' 分钟的时间延后或资源变更'}</span><span>计划跨度不是定额工时；本次结束不代表整道完工。</span></div>
    {records.length ? <div className="rw-table-scroll" data-analysis-scroll="records"><DataTable className="rw-record-detail" columns={columns} rows={pager.rows} rowKey="id" /></div> : <div className="rw-empty">尚无报工记录。</div>}
    {pager.pages > 1 && <div className="rw-pagination"><span>共 {records.length} 次报工 · 第 {pager.page} / {pager.pages} 页</span>
      <ControlButton size="sm" className="rw-icon-button" aria-label="工序记录上一页" title="上一页" disabled={pager.page <= 1} onClick={() => onRecordPage(pager.page - 1)}><RWIcon name="chevron-left" /></ControlButton>
      <ControlButton size="sm" className="rw-icon-button" aria-label="工序记录下一页" title="下一页" disabled={pager.page >= pager.pages} onClick={() => onRecordPage(pager.page + 1)}><RWIcon name="chevron-right" /></ControlButton>
    </div>}
  </section>;
}
const RW_TOPICS = [['delivery', '工序完成情况'], ['records', '报工记录'], ['machines', '设备工时'], ['people', '人员工时'], ['quality', '数据完整性']];
function rwTopic(context) {
  const topic = context && context.topic;
  return RW_TOPICS.some(([id]) => id === topic) ? topic : 'delivery';
}
const rwDefaultSort = topic => topic === 'records' ? 'start' : ['machines', 'people'].includes(topic) ? 'resource' : 'batch';
function rwPlanGaps(row) {
  return [['planStart', '计划开工'], ['planEnd', '计划完工'], ['machine', '计划设备'], ['person', '计划人员']]
    .filter(([key]) => !row[key]).map(([, label]) => label);
}
function RWDataWarnings({ analysis }) {
  const { warnings } = analysis;
  return warnings.length ? <ul className="rw-data-warnings" role="status" aria-label="当前数据缺口">{warnings.map(text => <li key={text}>{text}</li>)}</ul> : null;
}
function RWTopicSummary({ analysis, topic }) {
  const { MetricStrip, Metric } = window.APSWorkbenchUI, api = window.APSExecutionAnalysis, s = analysis.summary;
  const hours = ['已报有效工时', api.formatNumber(s.knownHours), '未知工时未计入合计', s.knownHours == null ? '' : 'h'];
  const values = topic === 'delivery' ? [
    ['到期工序完成率', api.formatPercent(s.fulfilledRate), s.confirmedDue + ' 已确认 / ' + s.due + ' 计划已到期工序'],
    ['到期工序按时完成率', api.formatPercent(s.ontimeRate), s.dueOnTime + ' 按时 / ' + s.due + ' 计划已到期工序'],
    ['到期未确认完成', s.unclosedDue, s.lateOpen + ' 道距计划完成已超过 ' + analysis.toleranceMinutes + ' 分钟'],
    ['完工偏差中位数', api.formatNumber(s.medianFinish), '样本 ' + s.finishSample + ' 道 · P90 ' + api.formatNumber(s.p90Finish) + ' 分钟', s.medianFinish == null ? '' : '分钟']
  ] : topic === 'quality' ? [
    ['字段待补工序', s.incompleteOperations, '与未报工工序分别列示'],
    ['未报工工序', s.unreported, s.operations + ' 道范围内工序'],
    ['字段待补记录', s.missingRecords, s.records + ' 条报工记录'],
    ['计划字段待补', analysis.rows.filter(r => r.planMissing).length, '计划时间、设备或人员缺项']
  ] : topic === 'records' ? [
    ['报工记录', s.records, s.operations + ' 道范围内工序'],
    ['已报工序', s.operations - s.unreported, s.unreported + ' 道未报工'], hours,
    ['工时待补记录', s.unknownHourRecords, s.missingRecords + ' 条记录存在字段缺项']
  ] : [
    [topic === 'machines' ? '实际设备分组' : '实际人员分组', analysis.resources[topic].length, '包含未填写实际资源的分组'],
    ['报工记录', s.records, s.operations + ' 道范围内工序'], hours,
    ['工时待补记录', s.unknownHourRecords, '未知工时不按零工时处理']
  ];
  return <MetricStrip columns={4} className="rw-metrics">{values.map(([label, value, helper, unit]) => <Metric key={label} label={label} value={value} helper={helper} unit={unit} />)}</MetricStrip>;
}
function RWTopicCharts({ analysis, topic }) {
  const { TrendChart, DistributionChart } = window.APSAnalysisUI, api = window.APSReportWorkbench;
  const records = analysis.rows.flatMap(r => r.summary.reports);
  const recordGaps = ['实际开工', '本次结束', '数量', '工时', '设备', '人员'].map(label => ({
    id: label, label, count: records.filter(r => api.recordGaps(r).includes(label)).length, tone: 'warning'
  }));
  let charts;
  if (topic === 'delivery') charts = <><TrendChart points={analysis.trend} label="所选工序计划 / 实际累计完工" /><DistributionChart items={analysis.distributions.finish} label={'整道完工偏差 · ' + analysis.summary.finishSample + ' 道有效样本'} /></>;
  else if (topic === 'quality') charts = <><DistributionChart items={recordGaps} label="实际记录字段缺项次数" /><DistributionChart items={['计划开工', '计划完工', '计划设备', '计划人员'].map(label => ({ id: label, label, count: analysis.rows.filter(r => rwPlanGaps(r).includes(label)).length, tone: 'warning' }))} label="范围内工序计划字段缺项数" /></>;
  else if (topic === 'records') charts = <><DistributionChart items={[
    { id: 'complete', label: '字段齐全', count: records.filter(r => !api.recordGaps(r).length).length, tone: 'success' },
    { id: 'incomplete', label: '字段待补', count: records.filter(r => api.recordGaps(r).length).length, tone: 'warning' }
  ]} label="报工记录完整性" /><DistributionChart items={recordGaps} label="记录待补字段分布" /></>;
  else {
    const groups = api.sortRows(analysis.resources[topic], 'hours', 'desc');
    charts = <><DistributionChart items={groups.filter(r => r.hours != null).slice(0, 8).map(r => ({ id: r.id, label: r.resource, count: r.hours, tone: 'info' }))} label="已知有效工时 · 前 8 组（h）" /><DistributionChart items={api.sortRows(groups, 'unknownHours', 'desc').filter(r => r.unknownHours > 0).slice(0, 8).map(r => ({ id: r.id, label: r.resource, count: r.unknownHours, tone: 'warning' }))} label="工时待补记录 · 前 8 组" /></>;
  }
  return <div className="rw-charts" data-rw-charts={topic}>{charts}</div>;
}
function ReportCenterContent({ onNav, scope, onScopeChange, initialContext }) {
  const api = window.APSReportWorkbench;
  const analysisApi = window.APSExecutionAnalysis, { ScopeBar, useWorkspaceState } = window.APSAnalysisUI;
  const { DataTable, TransferButton, ControlButton } = window.APSWorkbenchUI;
  const [localScope, setLocalScope] = React.useState(null);
  const [notice, setNotice] = React.useState(''), [, refresh] = React.useReducer(n => n + 1, 0);
  const contextScope = JSON.stringify(initialContext && initialContext.scope);
  const opener = React.useRef(null), focusDetail = React.useRef(false), contextRef = React.useRef(contextScope);
  const contextChanged = contextRef.current !== contextScope;
  if (contextChanged) { contextRef.current = contextScope; if (localScope) setLocalScope(null); }
  let analysis = null, error = '';
  const requestedScope = (onScopeChange && scope) || (!contextChanged && localScope) || scope || (initialContext && initialContext.scope) || { source: 'current' };
  try { analysis = analysisApi.build(requestedScope); } catch (e) { error = e.message; }
  const currentScope = analysis ? analysis.scope : requestedScope, sourceId = currentScope.source;
  const workspace = useWorkspaceState('reports', { topic: rwTopic(initialContext), sort: rwDefaultSort(rwTopic(initialContext)), direction: 'asc',
    page: 1, pageSize: 20, selected: null, recordPage: 1, chartsOpen: false, filtersOpen: false }, currentScope, initialContext && { ...initialContext, topic: rwTopic(initialContext) });
  const { topic, sort, direction, page, pageSize, selected, recordPage, chartsOpen } = workspace.state, set = workspace.update;
  const src = analysis && analysis.source, rows = analysis ? analysis.rows : [];
  const activeKind = topic === 'delivery' || topic === 'quality' ? 'operations' : topic === 'records' ? 'reports' : topic;
  const reportRows = api.reportRows(rows, activeKind), sorted = api.sortRows(reportRows, sort, direction), pager = api.paginate(sorted, page, pageSize);
  const detail = rows.find(r => r.id === selected), isResource = ['machines', 'people'].includes(activeKind);
  const reset = () => { set({ page: 1, selected: null, recordPage: 1 }); setNotice(''); };
  const changeTopic = value => { if (value !== topic) { set({ topic: value, sort: rwDefaultSort(value), direction: 'asc' }); reset(); } };
  const update = patch => {
    const next = { ...currentScope, ...patch };
    setLocalScope(next); if (typeof onScopeChange === 'function') onScopeChange(next);
    reset();
  };
  const open = (row, event) => { opener.current = event.currentTarget; focusDetail.current = true; set({ selected: row.taskId || row.id, recordPage: 1 }); };
  const close = () => {
    const target = opener.current && opener.current.isConnected ? opener.current : [...workspace.rootRef.current.querySelectorAll('[data-rw-detail]')].find(node => node.dataset.rwDetail === selected);
    set({ selected: null }); if (target) target.focus({ preventScroll: true });
  };
  const returnTo = row => ({ view: 'reports', context: { ...workspace.snapshot(), ...(row ? { selected: row.id, recordPage: selected === row.id ? recordPage : 1 } : {}), scope: analysisApi.linkScope(analysis), returning: true } });
  const goGantt = row => onNav('fieldgantt', { scope: analysisApi.linkScope(analysis), taskId: row && row.id, returnTo: returnTo(row) });
  const date = value => value ? api.time(value).slice(5) : '未填写';
  const inspect = r => <div className="rw-row-actions"><button type="button" className="rw-text-action" data-rw-detail={r.taskId || r.id} aria-expanded={selected === (r.taskId || r.id)} aria-controls="rw-detail" onClick={e => open(r, e)}>详情</button>
    <ControlButton size="sm" className="rw-icon-button" aria-label={'定位实际甘特 ' + (r.taskId || r.id)} title="定位实际甘特" onClick={() => goGantt(rows.find(row => row.id === (r.taskId || r.id)))}><RWIcon name="arrow-up-right" /></ControlButton></div>;
  const stack = (a, b) => <div className="rw-stack"><span>{a}</span><small>{b}</small></div>;
  const columns = (topic === 'quality' ? [
    { key: 'batch', title: '批次 / 工序', width: 218, render: r => stack(r.batch, r.op + ' · ' + r.name) },
    { key: 'integrity', title: '完整性', width: 120, render: r => <span className={r.integrity === 'complete' ? 'rw-success' : 'rw-warning'}>{api.integrityLabel(r.integrity)}</span> },
    { key: 'planMissing', title: '计划字段缺项', width: 155, render: r => rwPlanGaps(r).join('、') || '字段齐全' },
    { key: 'missingRecords', title: '待补 / 全部记录', width: 132, render: r => r.missingRecords + ' / ' + r.summary.reports.length },
    { key: 'gaps', title: '实际记录待补字段', width: 190, render: r => r.summary.reports.length ? [...new Set(r.summary.reports.flatMap(api.recordGaps))].join('、') || '字段齐全' : '尚无报工记录' },
    { key: 'unknownHours', title: '工时待补记录', width: 118, align: 'right' },
    { key: 'detail', title: '操作', width: 86, render: inspect }
  ] : activeKind === 'operations' ? [
    { key: 'batch', title: '批次 / 工序', width: 218, render: r => <div className="rw-stack"><span className="rw-code">{r.batch}</span><span>{r.op} · {r.name}</span></div> },
    { key: 'qty', title: '数量 / 待报', width: 112, render: r => stack(api.number(r.qty) + ' / ' + r.target + ' 件', '待报 ' + r.remaining + ' 件') },
    { key: 'planStart', title: '计划开工 / 完工', width: 146, render: r => stack(date(r.planStart), date(r.planEnd)) },
    { key: 'actualStart', title: '实际开工 / 整道完工', width: 150, render: r => stack(date(r.actualStart), r.actualEnd ? date(r.actualEnd) : '未整道完工') },
    { key: 'endDelta', title: '整道完工偏差', width: 122, render: r => <div className="rw-stack"><span className={r.finishLate ? 'rw-danger' : r.endDelta == null ? 'rw-muted' : ''}>{r.endDelta == null ? '尚不可比较' : api.delta(r.endDelta)}</span>{r.lateOpen && <small className="rw-warning">已超时未确认完成</small>}</div> },
    { key: 'status', title: '完成情况 / 到期', width: 118, render: r => <div className="rw-stack"><RWStatus row={r} /><small>{r.due ? r.confirmedDue ? '已到期 · 已确认完成' : '到期未确认完成' : '计划完成时间未到'}</small></div> },
    { key: 'detail', title: '操作', width: 86, render: inspect }
  ] : activeKind === 'reports' ? [
    { key: 'reportNo', title: '报工编号', width: 210, render: r => <span className="rw-code">{r.reportNo}</span> },
    { key: 'batch', title: '批次 / 工序', width: 195, render: r => stack(r.batch, r.op) },
    { key: 'qty', title: '本次数量', width: 88, render: r => api.number(r.qty) + (r.qty == null ? '' : ' 件') },
    { key: 'start', title: '实际开工 / 本次结束', width: 160, render: r => stack(date(r.start), date(r.end)) },
    { key: 'hours', title: '有效工时', width: 92, align: 'right', render: r => api.number(r.hours) + (r.hours == null ? '' : ' h') },
    { key: 'machine', title: '实际设备 / 人员', width: 132, render: r => stack(r.machine || '未填写', r.person || '未填写') },
    { key: 'gaps', title: '记录完整性', width: 120, render: r => r.gaps.length ? <span className="rw-warning">待补 {r.gaps.join('、')}</span> : '字段齐全' },
    { key: 'detail', title: '操作', width: 86, render: inspect }
  ] : [
    { key: 'resource', title: activeKind === 'machines' ? '实际设备' : '实际人员', width: 190 },
    { key: 'operations', title: '涉及工序', align: 'right', width: 110 },
    { key: 'batches', title: '涉及批次', align: 'right', width: 110 },
    { key: 'records', title: '报工条数', align: 'right', width: 110 },
    { key: 'hours', title: '已报有效工时', render: r => { const max = Math.max(0, ...reportRows.filter(v => v.hours != null).map(v => v.hours)); return <div className="rw-hours"><strong>{api.number(r.hours)}{r.hours == null ? '' : ' h'}</strong>{r.hours != null && <span className="rw-hours-track" aria-hidden="true"><i style={{ width: (max ? r.hours / max * 100 : 0) + '%' }} /></span>}</div>; } },
    { key: 'unknownHours', title: '工时待补记录', align: 'right', width: 132, render: r => <span className={r.unknownHours ? 'rw-warning' : ''}>{r.unknownHours}</span> }
  ]).map(c => ({ ...c, sortable: false, filterable: false }));
  const exportRows = () => {
    try {
      const file = analysisApi.tableCSV(analysis, activeKind, sorted);
      api.download(file); setNotice('已生成 ' + file.count + ' 条范围内结果并交给浏览器下载。');
    }
    catch (e) { setNotice('导出失败：' + e.message); }
  };
  const sortOptions = isResource ? [['resource', '资源编号'], ['hours', '已报工时'], ['records', '报工条数']] : topic === 'quality' ? [['batch', '批次编号'], ['missingRecords', '字段待补记录'], ['unknownHours', '工时待补记录']] : activeKind === 'reports' ? [['start', '实际开工'], ['batch', '批次编号'], ['hours', '有效工时']] : [['batch', '批次编号'], ['planEnd', '计划完工'], ['endDelta', '整道完工偏差'], ['hours', '已报工时']];
  const topicLabel = RW_TOPICS.find(([id]) => id === topic)[1];
  return <section className="rw-workbench" aria-label="报表中心" data-source={sourceId} data-topic={topic} data-selected={selected || ''} ref={workspace.rootRef}>
    <header className="rw-header"><div><h2>报表中心</h2><p>{src ? src.provenance : '数据源不可用'}{analysis && <span className="rw-asof">数据截至 {analysis.asOfLabel}</span>}</p></div><div className="rw-actions">
      <ControlButton size="sm" className="rw-icon-button" aria-label="重新计算报表" title="重新读取当前数据" onClick={() => { refresh(); setNotice(''); }}><RWIcon name="refresh-cw" /></ControlButton>
      <ControlButton size="sm" disabled={!analysis} onClick={() => onNav('review', { scope: analysisApi.linkScope(analysis), topic, returnTo: returnTo() })}>查看执行复盘<RWIcon name="arrow-up-right" /></ControlButton>
      <ControlButton size="sm" disabled={!analysis || !rows.length} onClick={() => goGantt()}>查看实际甘特<RWIcon name="arrow-up-right" /></ControlButton>
      {initialContext && initialContext.returnTo && <ControlButton size="sm" onClick={() => onNav(initialContext.returnTo.view, initialContext.returnTo.context)}>返回{initialContext.returnTo.view === 'review' ? '执行复盘' : '来源页面'}</ControlButton>}
    </div></header>
    <RWTabs options={RW_TOPICS} value={topic} onChange={changeTopic} label="报表专题" prefix="rw-topic" />
    <ScopeBar analysis={analysis} scope={currentScope} onChange={update} idPrefix="rw" expanded={workspace.state.filtersOpen} onExpandedChange={filtersOpen => set({ filtersOpen })} />
    {analysis && <RWDataWarnings analysis={analysis} />}
    <div id="rw-topic-panel" role="tabpanel" aria-labelledby={'rw-topic-' + topic}>
      {analysis && <><RWTopicSummary analysis={analysis} topic={topic} />
        <p className="rw-basis">按计划完工日期选工序。{topic === 'quality' ? '完整性统计字段缺项，不代表生产质量合格率；同一记录可缺多个字段。' : isResource ? '已报工时不是利用率或人员效率；按关联工序筛选，包含其全部实际记录。' : topic === 'delivery' ? '按时：提前完成或延后不超过 ' + analysis.toleranceMinutes + ' 分钟；未确认完成不等于未生产，工序完成不等于批次交付。' : '包含所选工序全部报工记录；本次结束不代表整道完工。'}</p>
      </>}
      <div className="rw-table-heading"><div className="rw-table-title"><h3>{topicLabel}明细</h3><span>{analysis ? sorted.length + ' 条明细 · ' + rows.length + ' 道工序 / ' + analysis.summary.batches + ' 个批次' : '范围不可计算'}</span></div><div className="rw-filters">
        <label>排序<select name="rw-sort" value={sort} onChange={e => { set({ sort: e.target.value }); reset(); }}>{sortOptions.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
        <label>顺序<select name="rw-direction" value={direction} onChange={e => { set({ direction: e.target.value }); reset(); }}><option value="asc">升序</option><option value="desc">降序</option></select></label>
        <TransferButton kind="export" disabled={!!error || !sorted.length} onClick={exportRows}>导出 CSV</TransferButton>
      </div></div>
      {notice && <p className="rw-notice" role="status">{notice}</p>}
      {error ? <div className="rw-empty" role="alert">数据未能读取：{error}</div> : sorted.length ? <div className="rw-table-scroll" data-analysis-scroll="report-table"><DataTable key={topic} className={'rw-table' + (isResource ? ' rw-resource-table' : '')} columns={columns} rows={pager.rows} rowKey="id" /></div> : <div className="rw-empty">没有符合当前条件的记录。</div>}
      <div className="rw-pagination"><span>共 {pager.total} 条 · 第 {pager.page} / {pager.pages} 页</span><label>每页<select name="rw-page-size" value={pageSize} onChange={e => { set({ pageSize: Number(e.target.value) }); reset(); }}>{[10, 20, 50].map(n => <option key={n} value={n}>{n} 条</option>)}</select></label>
        <ControlButton className="rw-icon-button" size="sm" aria-label="报表上一页" title="上一页" disabled={pager.page <= 1} onClick={() => set({ page: pager.page - 1, selected: null })}><RWIcon name="chevron-left" /></ControlButton>
        <ControlButton className="rw-icon-button" size="sm" aria-label="报表下一页" title="下一页" disabled={pager.page >= pager.pages} onClick={() => set({ page: pager.page + 1, selected: null })}><RWIcon name="chevron-right" /></ControlButton>
      </div>
      {detail && <RWDetail row={detail} source={sourceId} toleranceMinutes={analysis.toleranceMinutes} onClose={close} onNav={onNav} onGantt={goGantt} recordPage={recordPage} onRecordPage={value => set({ recordPage: value })} focusOnOpen={focusDetail.current} />}
      {analysis && <>
        <details className="rw-chart-disclosure" open={chartsOpen} onToggle={e => { if (e.currentTarget.open !== chartsOpen) set({ chartsOpen: e.currentTarget.open }); }}><summary>趋势与分布</summary><RWTopicCharts analysis={analysis} topic={topic} /></details>
        {analysis.limitations.length > 0 && <details className="rw-limitations" data-analysis-disclosure="report-limitations"><summary>数据范围与计算方法</summary><ul>{analysis.limitations.map(text => <li key={text}>{text}</li>)}</ul></details>}
      </>}
      <details className="rw-catalog" data-analysis-disclosure="report-catalog"><summary>其他报表 · 数据接入状态</summary><div className="rw-catalog-list">{api.capabilities.map(item => <section key={item.id}><div><h4>{item.name}</h4><span className="rw-muted">{item.available} · 当前不可生成</span></div><dl><dt>所需数据</dt><dd>{item.basis}</dd><dt>当前缺口</dt><dd>{item.gap}</dd></dl><p>{item.boundary}</p></section>)}</div></details>
    </div>
  </section>;
}
function ReportsScreen(props) {
  if (!window.APSExecutionAnalysis || !window.APSAnalysisUI || !window.APSReportWorkbench || !window.APSWorkbenchUI) {
    return <section className="rw-workbench" aria-label="报表中心"><h2>报表中心</h2><p className="rw-empty" role="alert">执行分析模型或共享界面未加载，无法生成报表。</p></section>;
  }
  return <ReportCenterContent {...props} />;
}
window.ReportsScreen = ReportsScreen;
