import React from './shared/runtime/react.js';
import ActualGanttModel from './ActualGanttModel.js';
import ActualGanttContract from './ActualGanttContract.js';
import ActualGanttWindow from './ActualGanttWindow.js';
import ResourceControls from './ResourceControls.jsx';
import ActualGanttControls from './ActualGanttControls.jsx';
import APSResourceContract from './resource-contract.js';
import APSPlanAPI from './PlanAPI.js';
import ActualGanttAPI from './ActualGanttAPI.js';
import WorkbenchTerms from './WorkbenchTerms.js';
import WorkbenchCaption from './WorkbenchCaption.jsx';
import GanttGraph from './GanttGraph.js';
import WorkbenchPageContext from './WorkbenchPageContext.jsx';
import GanttPresentation from './GanttPresentation.js';
import APSWorkbenchTransport from './shared/network/transport.js';
import FieldContract from './FieldContract.js';
import WorkbenchControls from './WorkbenchControls.jsx';
import WorkbenchFormat from './WorkbenchFormat.js';
import GanttGraphLayer from './GanttGraphLayer.jsx';
import GanttPresentationUI from './GanttPresentationUI.jsx';
import ActualGanttRows from './ActualGanttRows.jsx';
import GanttRouteList from './GanttRouteList.jsx';

const M = ActualGanttModel, C = ActualGanttContract, W = ActualGanttWindow;
const { Button, ErrorBox, Modal } = ResourceControls;
const { Toolbar, Range, Chain } = ActualGanttControls;
function savedView(value) {
  if (value === undefined) return null;
  const object = item => item !== null && typeof item === 'object' && !Array.isArray(item);
  const reference = item => item === null || typeof item === 'string' && /^[0-9a-f]{48}$/.test(item);
  const valid = object(value) && object(value.view) && object(value.position) && Number.isFinite(value.zoom) && value.zoom >= 1 && value.zoom <= 1024;
  if (!valid) throw new Error('现场实际甘特的查看状态无效，没有改选其他工序。');
  const v = value.view;
  if (!Object.prototype.hasOwnProperty.call(M.views, v.mode) || !Object.prototype.hasOwnProperty.call(M.lateLabels, v.late)
    || typeof v.query !== 'string' || v.query.length > 200 || !reference(v.selected) || !reference(v.report)
    || !['onlySelected', 'details', 'chain'].every(key => typeof v[key] === 'boolean')
    || !object(v.collapsed) || !Object.values(v.collapsed).every(item => typeof item === 'boolean')
    || !Number.isFinite(value.position.centerAt) || !Number.isFinite(value.position.windowSpan) || value.position.windowSpan <= 0
    || !Number.isFinite(value.position.top) || value.position.top < 0)
    throw new Error('现场实际甘特的查看状态无效，没有改选其他工序。');
  return value;
}
function initial(context) {
  const input = { ...context.scope }, scope = {};
  const taskRef = context.task_ref;
  for (const key of ['source', 'range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref', 'batch_ids'])
    if (context[key] !== undefined && input[key] === undefined) input[key] = context[key];
  const allowed = ['plan_ref', 'source', 'range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref', 'batch_ids', 'query', 'focus', 'as_of', 'snapshot_ref', 'kind', 'baseline_ref'];
  let issue = Object.keys(input).some(key => !allowed.includes(key)) ? '查询条件无效，请清除筛选后重试。' : null;
  if (input.baseline_ref && input.baseline_ref !== (context.plan_ref || input.plan_ref)) issue = '现场实际甘特以所选计划为对比基准，没有换成另一个计划版本。';
  if (input.query !== undefined && (typeof input.query !== 'string' || input.query.length > 200)) issue = '来源搜索条件无效。';
  if (context.report_ref !== undefined && !C.ref(context.report_ref)) issue = '来源报工编号无效，请从现场记录重新打开。';
  if (context.report_ref !== undefined && !C.ref(taskRef)) issue = '报工关联的任务资料缺失，请刷新后重选。';
  for (const key of ['plan_ref', 'source', 'range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref', 'batch_ids'])
    if (input[key] !== undefined && input[key] !== null && input[key] !== '') scope[key] = input[key];
  if (context.plan_ref) scope.plan_ref = context.plan_ref;
  let persisted = null;
  try { persisted = savedView(context.actual_view); } catch (failure) { issue = failure.message; }
  return { scope, issue, persisted, query: typeof input.query === 'string' ? input.query : typeof context.query === 'string' ? context.query : '',
    selected: taskRef === undefined ? null : taskRef, report: context.report_ref === undefined ? null : context.report_ref };
}
function Content({ onNavigate, initialContext }) {
  const seed = React.useMemo(() => initial(initialContext), []);
  const [scope, setScope] = React.useState(seed.scope), [refresh, setRefresh] = React.useState(0);
  const [result, setResult] = React.useState(null), [loading, setLoading] = React.useState(false), [error, setError] = React.useState(null);
  const [view, setView] = React.useState(seed.persisted ? seed.persisted.view : { mode: seed.scope.resource_type || 'machine', query: seed.query, selected: seed.selected,
    report: seed.report, late: 'all', collapsed: {}, onlySelected: false, details: false, chain: false });
  const [zoom, setZoom] = React.useState(seed.persisted ? seed.persisted.zoom : 1), [position, setPosition] = React.useState({ left: 0, top: 0, width: 1000, height: 480 });
  const [hover, setHover] = React.useState(null), [exporting, setExporting] = React.useState(false), [exportBusy, setExportBusy] = React.useState(false);
  const [chainTarget, setChainTarget] = React.useState(null);
  const [locateNotice, setLocateNotice] = React.useState(''), [navigationNotice, setNavigationNotice] = React.useState(null);
  const [exportError, setExportError] = React.useState(null), [exportNotice, setExportNotice] = React.useState(''), [restore, setRestore] = React.useState(seed.persisted ? seed.persisted.position : null);
  const [chainOpen, setChainOpen] = React.useState(false);
  const board = React.useRef(null), detailsPanel = React.useRef(null), frame = React.useRef(null), pending = React.useRef(!seed.persisted && seed.report && seed.selected ? { task: seed.selected } : null), downloadController = React.useRef(null);
  const defaultWindowApplied = React.useRef(!!seed.persisted);
  const measuredWidth = React.useRef(null), zoomRef = React.useRef(zoom), restoreRef = React.useRef(restore);
  zoomRef.current = zoom; restoreRef.current = restore;
  const { labelWidth, viewport } = W.dimensions(position.width);
  const patch = change => setView(previous => ({ ...previous, ...change }));
  React.useEffect(() => {
    if (view.details && detailsPanel.current && window.innerWidth <= 1050) detailsPanel.current.scrollIntoView({ block: 'nearest' });
  }, [view.details]);
  function collapseDetails() {
    patch({ details: false });
    const button = document.querySelector('[aria-controls="actual-gantt-detail"]');
    if (button) button.focus();
  }
  React.useEffect(() => {
    const controller = new AbortController(); let active = true;
    setLoading(true); setResult(null); setError(null);
    (async () => {
      try {
        if (seed.issue) throw APSResourceContract.failure(seed.issue);
        if (scope.source && scope.source !== 'production') throw APSResourceContract.failure('数据来源无效，请重新打开现场实际甘特。');
        if (!scope.plan_ref) {
          if (Object.keys(scope).some(k => k !== 'source')) throw APSResourceContract.failure('来源范围缺少计划，请选择计划。');
          const catalog = await APSPlanAPI.catalog({ collection: 'history', size: 20 }, controller.signal);
          const current = catalog.data.plans.filter(p => p.is_current_official && p.capabilities.view);
          if (current.length !== 1) throw APSResourceContract.failure('没有唯一可读取的当前正式计划，请先选择计划。');
          if (active) setScope({ plan_ref: current[0].plan_ref });
          return;
        }
        const response = await ActualGanttAPI.load(scope, controller.signal);
        if (initialContext.operation_ref && seed.selected) {
          const task = response.data.items.find(item => item.task.task_ref === seed.selected);
          if (task && task.task.operation_ref !== initialContext.operation_ref) throw APSResourceContract.failure('来源工序与所选计划任务不一致，请重新选择工序。');
        }
        if (active) setResult(response);
      } catch (failure) { if (active) setError(failure); }
      finally { if (active) setLoading(false); }
    })();
    return () => { active = false; controller.abort(); };
  }, [scope, refresh]);
  React.useEffect(() => () => { if (downloadController.current) downloadController.current.abort(); cancelAnimationFrame(frame.current); }, []);
  const lastResultRef = React.useRef(null);
  if (result && scope.plan_ref) lastResultRef.current = { planRef: scope.plan_ref, result };
  else if (!loading || !scope.plan_ref || (lastResultRef.current && lastResultRef.current.planRef !== scope.plan_ref)) lastResultRef.current = null;
  const displayResult = result || (loading && scope.plan_ref && lastResultRef.current && lastResultRef.current.planRef === scope.plan_ref ? lastResultRef.current.result : null);
  const data = displayResult && displayResult.data;
  const captionPlan = !loading && !error && data && data.plan;
  const captionStatus = captionPlan && (captionPlan.is_current_official ? WorkbenchTerms.current_official : WorkbenchTerms.historical_official);
  WorkbenchCaption.useCaption(captionStatus ? {
    reference: captionPlan.plan_ref, label: '对照计划', name: captionPlan.display_name, status: captionStatus,
    version: Number.isSafeInteger(captionPlan.version) ? WorkbenchTerms.plan_version(captionPlan.version) : undefined,
    range: data.scope.plan_finish_date_from && data.scope.plan_finish_date_to ? '计划完工 ' + data.scope.plan_finish_date_from + ' 至 ' + data.scope.plan_finish_date_to : undefined
  } : null);
  const selectedFilter = view.onlySelected ? view.selected : null;
  const prepared = React.useMemo(() => {
    if (!data) return null;
    const facts = M.prepare(data, displayResult.meta.as_of); facts.graph = GanttGraph.create(data.gantt_graph); return facts;
  }, [data, displayResult && displayResult.meta.as_of]);
  const grouped = React.useMemo(() => prepared ? M.groupPrepared(prepared, view.mode) : null, [prepared, view.mode]);
  const visible = React.useMemo(() => grouped ? M.selectPrepared(grouped, view) : null,
    [grouped, view.query, view.late, view.onlySelected, selectedFilter]);
  const model = React.useMemo(() => visible ? M.layoutPrepared(visible, view.collapsed) : null, [visible, view.collapsed]);
  const stats = React.useMemo(() => data ? M.metrics(data) : null, [data]);
  const taskIndex = prepared && prepared.taskIndex;
  const snapshotPosition = model ? W.capture(position, viewport, model, zoom) : null;
  function pageContext() {
    return {
      plan_ref: scope.plan_ref, task_ref: view.selected, scope: { ...scope, query: view.query },
      ...(snapshotPosition ? { actual_view: { view, zoom, position: snapshotPosition } } : {}),
      ...(initialContext.return_to ? { return_to: initialContext.return_to } : {})
    };
  }
  WorkbenchPageContext.useSnapshot(data ? pageContext() : null, !!data && !loading && !error && !seed.issue && !restore);
  const measure = () => {
    const node = board.current; if (!node) return;
    const previousWidth = measuredWidth.current;
    if (previousWidth !== null && previousWidth !== node.clientWidth && defaultWindowApplied.current && !restoreRef.current && !pending.current) {
      const previousViewport = W.dimensions(previousWidth).viewport;
      pending.current = { center: (node.scrollLeft + previousViewport / 2) / (previousViewport * zoomRef.current) };
    }
    measuredWidth.current = node.clientWidth;
    setPosition({ left: node.scrollLeft, top: node.scrollTop, width: node.clientWidth, height: node.clientHeight });
  };
  React.useLayoutEffect(() => {
    if (!board.current) return;
    measure(); const resize = new ResizeObserver(measure); resize.observe(board.current);
    return () => resize.disconnect();
  }, [data]);
  const width = viewport * zoom;
  React.useLayoutEffect(() => {
    const node = board.current; if (!node || !model || loading) return;
    if (!defaultWindowApplied.current) {
      defaultWindowApplied.current = true;
      const next = W.initial(model);
      if (!pending.current) pending.current = { center: next.center };
      setZoom(next.zoom);
      if (next.zoom !== zoom) return;
    }
    // Restore only after the measured width is rendered; the initial width can clamp scrollLeft.
    if (restore && position.width !== node.clientWidth) { measure(); return; }
    if (restore) {
      const nextZoom = W.restoreZoom(restore, model);
      if (nextZoom !== zoom) { setZoom(nextZoom); return; }
      node.scrollLeft = W.restoreLeft(restore, viewport, model, zoom); node.scrollTop = restore.top; setRestore(null);
    }
    if (pending.current) {
      if (pending.current.task) {
        const reportRow = model.reportLocations.get(view.report);
        const row = reportRow && reportRow.item.task.task_ref === pending.current.task ? reportRow : model.locations.get(pending.current.task);
        if (row) { const fact = model.taskIndex.get(pending.current.task), report = fact.reportIndex.get(view.report), at = report && Number.isFinite(report.start) ? report.start : fact.baseline.start;
          node.scrollTop = Math.max(0, row.top - node.clientHeight / 3); node.scrollLeft = (at - model.start) / (model.end - model.start) * width - viewport / 3; }
      } else node.scrollLeft = pending.current.center * width - viewport / 2;
      pending.current = null;
    }
    measure();
  }, [width, model, restore, position.width, loading]);
  React.useEffect(() => { setHover(null); setChainTarget(null); }, [view, position.top, position.left]);
  function zoomTo(next) { pending.current = { center: W.anchor(model, view.selected, view.report) }; setZoom(Math.max(1, Math.min(1024, next))); }
  function fitView() { pending.current = { center: .5 }; setZoom(1); pan(0); }
  function zoomKeys(event) {
    const action = ResourceControls.timelineZoomKey(event);
    if (!action) return;
    event.preventDefault();
    if (action === 'fit') fitView(); else zoomTo(ResourceControls.timelineZoomStep(zoom, action === 'in' ? 1 : -1, 1024));
  }
  function pan(left) { if (board.current) { board.current.scrollLeft = Math.max(0, left); measure(); } }
  function locate(taskRef = view.selected) {
    if (!model) return;
    if (!taskIndex.has(taskRef)) {
      setLocateNotice('这道工序不在当前日期、资源或批次范围内，请调整范围后定位。'); return;
    }
    setLocateNotice('');
    const hidden = !model.shownRefs.has(taskRef);
    const collapsed = { ...view.collapsed };
    model.groups.filter(g => g.members.has(taskRef)).forEach(g => delete collapsed[g.id]);
    pending.current = { task: taskRef }; patch({ selected: taskRef, report: taskRef === view.selected ? view.report : null, collapsed: hidden ? {} : collapsed,
      ...(hidden ? { query: '', late: 'all', onlySelected: false } : {}) });
  }
  function apply(next) {
    try {
      C.scope(next); defaultWindowApplied.current = false; pending.current = null; setRestore(null); setNavigationNotice(null);
      setResult(null); setLoading(true); setScope(next); patch({ collapsed: {} }); setError(null); setExportNotice('');
    } catch (failure) { setError(failure); }
  }
  function reload() {
    if (snapshotPosition) setRestore(snapshotPosition);
    pending.current = null;
    const next = { ...scope }; delete next.snapshot_ref;
    setResult(null); setLoading(true); setScope(next); setRefresh(n => n + 1); setExportNotice('');
  }
  function select(item, report) { setLocateNotice(''); patch({ selected: item.task.task_ref, report: report ? report.report_ref : null }); }
  const selectedFact = taskIndex && taskIndex.get(view.selected), selected = selectedFact && selectedFact.item;
  const report = selectedFact && view.report ? selectedFact.reportIndex.get(view.report)?.report || null : null;
  const selectedLines = React.useMemo(
    () => view.details && selected && model ? M.describe(selected, model.labels, report).map((line, i) => <p key={i}>{line}</p>) : null,
    [view.details, selected, model && model.labels, report]
  );
  const reportOptions = React.useMemo(
    () => view.details && selected && selected.execution ? selected.execution.reports.map(r => <option key={r.report_ref} value={r.report_ref}>{r.report_no}</option>) : null,
    [view.details, selected && selected.execution && selected.execution.reports]
  );
  const gapReportButtons = React.useMemo(
    () => view.details && selectedFact && selected && selected.execution ? selectedFact.gapReports.map(row => <Button key={row.report_ref} icon="search"
      onClick={() => patch({ report: row.report_ref })}>查看待补报工 {row.report_no}</Button>) : null,
    [view.details, selectedFact && selectedFact.gapReports, selected && selected.execution]
  );
  const hoverTip = React.useMemo(
    () => !hover || !model ? '' : hover.title || M.describe(hover.item, model.labels, hover.report).join('\n'),
    [hover && hover.title, hover && hover.item, hover && hover.report, model && model.labels]
  );
  const graph = prepared && prepared.graph;
  const targetRef = chainTarget && chainTarget[0] || view.selected;
  const active = React.useMemo(() => graph ? GanttGraph.selection(graph, { enabled: view.chain, targetRef }) : null, [graph, view.chain, targetRef]);
  const graphLocations = React.useMemo(() => model ? M.graphLocations(model) : null, [model]);
  const locationIndex = React.useMemo(() => graphLocations ? GanttGraph.locationIndex(graphLocations) : null, [graphLocations]);
  const geometry = React.useMemo(() => model ? GanttGraph.paths(active, model, width, {
    top: Math.max(0, position.top - 52), height: position.height, left: position.left, width: viewport
  }, { locationIndex }) : null, [active, model, width, position.top, position.left, position.height, viewport, locationIndex]);
  const axis = React.useMemo(() => model ? GanttPresentation.axis({ start: model.start, end: model.end, width, left: position.left, viewport }) : null,
    [model && model.start, model && model.end, width, position.left, viewport]);
  function clearTarget() { setHover(null); setChainTarget(null); patch({ selected: null, report: null, onlySelected: false }); }
  const hoverMark = value => { setHover(value); setChainTarget(value && value.item ? [value.item.task.task_ref] : null); };
  const viewScope = () => ({ ...scope, snapshot_ref: displayResult.meta.snapshot_ref, format: 'csv', local_query: view.query.trim(), late_filter: view.late,
    ...(view.onlySelected ? { selected_task_ref: view.selected } : {}) });
  async function download() {
    const controller = new AbortController(); downloadController.current = controller; setExportBusy(true); setExportError(null);
    try {
      const output = await ActualGanttAPI.export(viewScope(), controller.signal);
      if (controller.signal.aborted) return;
      APSWorkbenchTransport.saveBlob(output.filename, output.blob);
      setExporting(false); setExportNotice(WorkbenchTerms.download_started(output.filename));
    } catch (failure) { if (!controller.signal.aborted) setExportError(failure); }
    finally { if (downloadController.current === controller) { downloadController.current = null; setExportBusy(false); } }
  }
  function returnTarget() {
    return { view: 'fieldgantt', context: pageContext() };
  }
  function openField() {
    // 现场实际甘特可按 10000 个批次读取，现场记录只接受 FieldContract.batchLimit 个；超出时原样保留批次范围，请用户先缩小。
    const limit = FieldContract.batchLimit;
    if (scope.batch_ids && scope.batch_ids.length > limit) {
      setNavigationNotice({ message: '现场记录最多按 ' + limit + ' 个批次查看，当前范围有 ' + scope.batch_ids.length + ' 个批次。请先缩小批次范围，再打开现场记录。' }); return;
    }
    const destinationScope = { ...scope, query: view.query };
    // Actual uses [] for all batches; Field represents that scope by omission.
    if (destinationScope.batch_ids !== undefined && destinationScope.batch_ids.length === 0) delete destinationScope.batch_ids;
    const query = view.query.trim().toLowerCase();
    const task = selected && M.fieldSearchText(selected, model.labels).includes(query) ? selected.task : null;
    onNavigate('field', { plan_ref: scope.plan_ref, ...(task ? { task_ref: task.task_ref, operation_ref: task.operation_ref } : {}),
      scope: destinationScope, return_to: returnTarget() });
  }
  // 正式计划甘特只按计划时段读取：完工日期、资源和非空批次条件带不过去，先列出来，用户确认后才按时段（无时段时按完整计划）打开。
  // 有选中工序时只带定位、不带搜索词（计划页定位即清空搜索）；空 batch_ids 表示全部批次，不算受限。
  function openPlan(confirmed) {
    const limits = [...(scope.plan_finish_date_from ? ['计划完工日期 ' + scope.plan_finish_date_from + ' 至 ' + scope.plan_finish_date_to] : []),
      ...(scope.resource_ref ? ['指定' + M.views[scope.resource_type]] : []), ...(scope.batch_ids && scope.batch_ids.length ? ['指定的 ' + scope.batch_ids.length + ' 个批次'] : [])];
    if (limits.length && !confirmed) {
      setNavigationNotice({ plan: true, message: '计划甘特只按计划时段读取，带不过去这些条件：' + limits.join('、') + '。确认后按'
        + (scope.range_start ? '当前时段' : '完整计划') + '打开' + (view.selected ? '，并定位所选工序' : '') + '。' }); return;
    }
    onNavigate('gantt', { plan_ref: scope.plan_ref, ...(scope.range_start ? { range_start: scope.range_start, range_end: scope.range_end } : {}),
      ...(view.selected ? { selected_task_ref: view.selected } : view.query ? { query: view.query } : {}), return_to: returnTarget() });
  }
  return <div className="plana fg-page fg-live" data-actual-gantt>
    <div className="fg-heading"><div><h2 className="wb-page-title">现场实际甘特</h2><span className="fg-muted wb-page-context">{result ? data.plan.display_name + ' · ' + WorkbenchTerms.data_as_of(M.time(result.meta.as_of)) : loading ? '正在读取计划与现场记录' : '计划与现场记录'}</span></div>
      <div className="wb-actions"><Button icon="refresh-cw" aria-label="刷新实际甘特" busy={loading} onClick={reload} />
        <Button icon="chart-gantt" onClick={() => openPlan(false)}>计划甘特</Button><Button icon="arrow-right" onClick={openField}>现场记录</Button>
        {initialContext.return_to && <Button icon="chevron-left" onClick={() => onNavigate(initialContext.return_to.view, initialContext.return_to.context)}>返回</Button>}</div></div>
    <ErrorBox error={error} />{navigationNotice && <><p className="fg-note" role="status">{navigationNotice.message}</p>{navigationNotice.plan && <span className="wb-actions">
      <Button icon="chart-gantt" onClick={() => openPlan(true)}>确认打开计划甘特</Button><Button icon="x" onClick={() => setNavigationNotice(null)}>取消</Button></span>}</>}
    {scope.plan_ref && <Range scope={scope} resources={data ? data.resources : null} onApply={apply} busy={loading} />}
    {!data && <WorkbenchControls.EmptyState kind={loading ? 'loading' : error ? 'error' : 'empty'} title={loading ? '正在读取计划与现场记录…' : error ? '现场实际甘特未读取成功' : '暂无现场实际甘特数据'}
      action={error && !loading ? <Button icon="refresh-cw" onClick={reload}>刷新</Button> : undefined} />}
    {!data && !loading && <Button icon="chart-gantt" onClick={() => onNavigate('analysis', {})}>选择计划</Button>}
    {data && <>{data.availability.state !== 'available' && <div role="status" className="fg-note">{data.availability.reason}</div>}
      <dl className="fg-metrics" aria-label="当前范围概况"><div><dt>整道已完工</dt><dd>{stats.complete === null ? '报工数据不可用' : stats.complete}</dd></div>
        <div><dt>已报工 · 未整道完工</dt><dd>{stats.reported === null ? '报工数据不可用' : stats.reported}</dd></div>
        <div><dt>待报工</dt><dd>{stats.pending === null ? '报工数据不可用' : stats.pending}</dd></div>
        <div title="仅统计有确认完工时间的已完工工序"><dt>平均整道完工偏差</dt><dd>{stats.average === null ? stats.complete === null ? '报工数据不可用' : stats.complete ? '完工时间待核对' : '尚无已完工工序' : (stats.average > 0 ? '+' : '') + WorkbenchFormat.number(Math.round(stats.average) + 0, { digits: 0 }) + ' 分钟'}</dd></div></dl>
      {exportNotice && <p className="fg-note" role="status">{exportNotice}</p>}
      <div className="wb-gantt-detail-layout" data-details-open={view.details}><div className="wb-gantt-main-column"><section className="gb-workspace fg-workspace" aria-label="现场实际甘特工作区" onKeyDown={zoomKeys}><Toolbar {...{ view, patch, model, data, zoom, width }} onZoom={zoomTo}
        onFit={fitView} onLocate={() => locate()} onExport={() => { setExportError(null); setExportNotice(''); setExporting(true); }} busy={exportBusy} />
        <GanttGraphLayer.Controls graph={data.gantt_graph} enabled={view.chain} onChange={chain => patch({ chain })}
          active={active} geometry={geometry} onClear={clearTarget} />
        {locateNotice && <p className="fg-note" role="status">{locateNotice}</p>}
        {view.selected && !model.shownRefs.has(view.selected) && <div role="status" className="fg-note">选中工序在当前筛选范围外，请调整筛选。</div>}
        {view.report && selected && !report && <div role="alert" className="fg-note">原报工记录不在所选工序中，未改指其他记录。</div>}
        <div className="fg-board" ref={board} data-actual-scroll tabIndex={0} aria-label="分次报工甘特" style={{ '--fg-label': labelWidth + 'px' }} onScroll={() => { cancelAnimationFrame(frame.current); frame.current = requestAnimationFrame(measure); }}>
          <div className="fg-board-inner" style={{ width: labelWidth + width, height: model.height + 52 }}><div className="fg-axis"><div className="fg-corner">{M.views[view.mode]} / 工序<small className="fg-muted fg-corner-note">含夜间</small></div>
            <div className="fg-ticks" style={{ width }}><GanttPresentationUI.Axis axis={axis} width={width} />
              <i className="fg-clock" style={{ left: (model.asOf - model.start) / (model.end - model.start) * width }} title={'数据截至 ' + M.time(displayResult.meta.as_of)} aria-hidden="true" /></div></div>
            <ActualGanttRows {...{ model, view, width, viewport, labelWidth, patch }} left={position.left} top={position.top} height={position.height} dense={data.task_count >= 1000}
              onSelect={select} onHover={hoverMark} onChainTarget={setChainTarget} active={active} />
            <GanttGraphLayer.Lines geometry={geometry} width={width} height={model.height} labelWidth={labelWidth} top={52} />
            {!model.items.length && <WorkbenchControls.EmptyState kind={view.query || view.late !== 'all' || view.onlySelected ? 'filtered' : 'empty'} title="当前范围没有匹配的工序。"
              action={view.query || view.late !== 'all' || view.onlySelected ? <Button onClick={() => patch({ query: '', late: 'all', onlySelected: false })}>清除筛选</Button> : undefined} />}</div></div>
        <div className="fg-foot"><span>{M.time(M.wire(model.start))}</span><input type="range" aria-label="时间轴水平位置" min={0} max={Math.max(0, width - viewport)} value={Math.min(position.left, width - viewport)} step="any" onChange={e => pan(Number(e.target.value))} disabled={zoom === 1} /><span>{M.time(M.wire(model.end))}</span></div>
      </section></div>{view.details && <aside ref={detailsPanel} className="wb-gantt-detail-panel fg-detail-panel" id="actual-gantt-detail" aria-label="工序详情">
        <header className="wb-gantt-detail-header"><h3>工序详情</h3><Button icon="x" aria-label="收起工序详情" onClick={collapseDetails} /></header>
        <div className="wb-gantt-detail-body">{selected ? <>
          <details className="wb-gantt-detail-section" open><summary>执行与完工偏差</summary><div className="wb-gantt-detail-section-body fg-detail-facts">
            {selectedLines}
            {selected.execution && <><label className="fg-report-selector">逐次报工 <select aria-label="选择报工详情" value={view.report === null ? '' : view.report} onChange={e => patch({ report: e.target.value === '' ? null : e.target.value })}><option value="">整道工序</option>{reportOptions}</select></label>
              <Button icon="search" disabled={!report || !report.actual_start} onClick={() => locate()}>定位本次报工</Button>
              {selected.execution.remaining_plan && <p>剩余安排：{M.time(selected.execution.remaining_plan.start)} 至 {M.time(selected.execution.remaining_plan.end)}</p>}
              {gapReportButtons}
              {report && <p>登记：{M.time(report.recorded_at)} · 历史版本 {report.correction_history.length} 条</p>}</>}
            <Button icon="arrow-right" onClick={openField}>到现场记录核对或补齐</Button>
          </div></details>
          <details className="wb-gantt-detail-section" open><summary>完整工艺路线</summary><div className="wb-gantt-detail-section-body">
            <GanttRouteList index={graph} targetRef={selected.task.task_ref} loadedRefs={model.shownRefs}
              onSelect={ref => { locate(ref); }} />
          </div></details>
          {data.gantt_graph.state === 'available' && data.gantt_graph.critical_task_refs.length > 0 && <details className="wb-gantt-detail-section" open={chainOpen} onToggle={e => setChainOpen(e.currentTarget.open)}><summary>计划关键链</summary>{chainOpen && <div className="wb-gantt-detail-section-body">
            <Chain index={graph} model={model} onLocate={locate} /></div>}</details>}
        </> : <p className="fg-muted">点击工序查看详情与完整工艺路线。</p>}</div>
      </aside>}</div></>}
    {hover && model && <div className="fg-tip" role="tooltip" style={{ left: Math.max(8, Math.min(hover.x + 12, window.innerWidth - 368)), top: Math.max(8, Math.min(hover.y + 12, window.innerHeight - 360)) }}>{hoverTip}</div>}
    {exporting && data && <Modal title="导出现场实际甘特" icon="download" onClose={() => { if (downloadController.current) downloadController.current.abort(); setExporting(false); }} footer={<><Button onClick={() => setExporting(false)} disabled={exportBusy}>取消</Button><Button transfer="export" busy={exportBusy} onClick={download}>下载 CSV</Button></>}>
      <div className="modal-b"><p>按当前查询范围和本次读取的数据导出全部 {model.items.length} 道匹配工序及其逐次报工，不受滚动、折叠和详情开关影响。</p>
        <p>本地搜索：{view.query.trim() || '无'}；{WorkbenchTerms.overdue}：{M.lateLabels[view.late]}；仅选中：{view.onlySelected ? '是' : '否'}。</p>
        <p>计划完工日期：{scope.plan_finish_date_from || '不限'} 至 {scope.plan_finish_date_to || '不限'}；数据截至 {M.time(displayResult.meta.as_of)}。数据变化时下载会要求刷新。</p><ErrorBox error={exportError} /></div></Modal>}
  </div>;
}
// 侧栏直接进入时 main.jsx 传空对象作为定位上下文。
function ActualGanttWorkspace({ initialContext, ...props }) { return <Content key={JSON.stringify(initialContext)} {...props} initialContext={initialContext} />; }
export { ActualGanttWorkspace, Content as ActualGanttSession };
export default ActualGanttWorkspace;
