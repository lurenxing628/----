import React from './shared/runtime/react.js';
import { Scope, Tabs, Sort, Page, Button, ErrorBox, useRead } from './ReportControls.jsx';
import { Table, Metrics } from './ReportTable.jsx';
import ReportAPI from './ReportAPI.js';
import WorkbenchTerms from './WorkbenchTerms.js';
import WorkbenchCaption from './WorkbenchCaption.jsx';
import WorkbenchPageContext from './WorkbenchPageContext.jsx';
import WorkbenchFormat from './WorkbenchFormat.js';
import FieldContract from './FieldContract.js';
import APSResourceContract from './resource-contract.js';
import ReviewCharts from './ReviewCharts.jsx';
import { NoFeedback } from './ReportEvidence.jsx';
import ReportDetail from './ReportDetail.jsx';
import ReportCatalog from './ReportCatalog.jsx';
import { EmptyState } from './ResourceControls.jsx';

let pendingViewFocus = null;

function Workspace({ mode = 'reports', initialContext, initialScope, initialState, onNav }) {
  const [scope, setScope] = React.useState(initialScope);
  const [state, setState] = React.useState(initialState);
  const [revision, refresh] = React.useReducer(value => value + 1, 0), [selected, setSelected] = React.useState(initialContext.selected === undefined ? null : initialContext.selected),
    [notice, setNotice] = React.useState(''), [error, setError] = React.useState(null), [downloading, setDownloading] = React.useState(false), [format, setFormat] = React.useState('csv'),
    [catalog, setCatalog] = React.useState(!!initialContext.catalogOpen), [chartsOpen, setChartsOpen] = React.useState(!!initialContext.chartsOpen);
  const root = React.useRef(null), restored = React.useRef(false);
  const [scroll, setScroll] = React.useState(initialContext.scroll === undefined ? {} : initialContext.scroll);
  const [resourceView, setResourceView] = React.useState(initialContext.resourceView || { kind: 'machine', page: 1 });
  const [detailView, setDetailView] = React.useState(initialContext.detailView || { page: 1, size: 10 });
  const [lastChoices, setLastChoices] = React.useState({});
  const lastScope = React.useRef(initialScope), lastSnapshotRef = React.useRef(null);
  const input = { ...scope, ...state };
  const request = useRead(signal => ReportAPI.readView(input, signal), JSON.stringify(input) + revision);
  const response = request.result, data = response && response.data;
  if (data) { lastScope.current = data.scope; lastSnapshotRef.current = response.meta.snapshot_ref; }
  else if (!request.busy) lastSnapshotRef.current = null;
  const captionPlan = !request.busy && !request.error && data && data.plan;
  const captionStatus = captionPlan && (captionPlan.is_current_official ? WorkbenchTerms.current_official : WorkbenchTerms.historical_official);
  WorkbenchCaption.useCaption(captionStatus ? {
    reference: captionPlan.plan_ref, label: mode === 'review' ? '复盘计划' : '报表计划', name: captionPlan.display_name, status: captionStatus,
    version: Number.isSafeInteger(captionPlan.version) ? WorkbenchTerms.plan_version(captionPlan.version) : undefined,
    range: data.scope.plan_finish_date_from && data.scope.plan_finish_date_to ? '计划完工 ' + data.scope.plan_finish_date_from + ' 至 ' + data.scope.plan_finish_date_to : undefined
  } : null);
  function pageContext(currentScroll = scroll) {
    return {
      scope: ReportAPI.scope(data.scope), topic: data.topic,
      table: {
        topic: data.topic, page: data.page.number, size: data.page.size, sort: data.page.sort[0].field,
        direction: data.page.sort[0].direction
      }, selected, chartsOpen,
      catalogOpen: catalog, scroll: currentScroll, resourceView, detailView,
      ...(initialContext.returnTo !== undefined ? { returnTo: initialContext.returnTo } : {})
    };
  }
  WorkbenchPageContext.useSnapshot(data ? pageContext() : null, !!data && !request.busy && !request.error);
  React.useEffect(() => {
    let frame = 0;
    const remember = event => {
      const node = root.current, main = document.querySelector('.main-content'), table = node && (node.querySelector('.rw-primary-table') || node.querySelector('.rw-table-scroll'));
      if (event.target !== document && event.target !== window && event.target !== main && (!table || event.target !== table)) return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const current = root.current; if (!current) return;
        const activeMain = document.querySelector('.main-content'), activeTable = current.querySelector('.rw-primary-table') || current.querySelector('.rw-table-scroll');
        const next = {
          mainTop: activeMain ? activeMain.scrollTop : 0, windowTop: pageYOffset,
          tableLeft: activeTable ? activeTable.scrollLeft : 0, tableTop: activeTable ? activeTable.scrollTop : 0
        };
        setScroll(old => old && old.mainTop === next.mainTop && old.windowTop === next.windowTop && old.tableLeft === next.tableLeft && old.tableTop === next.tableTop ? old : next);
      });
    };
    document.addEventListener('scroll', remember, true);
    return () => { cancelAnimationFrame(frame); document.removeEventListener('scroll', remember, true); };
  }, []);
  React.useEffect(() => { if (data) setLastChoices(data.choices); }, [response]);
  React.useEffect(() => {
    if (!data || restored.current) return;
    restored.current = true;
    if (!initialContext.scroll) return;
    const frame = requestAnimationFrame(() => {
      const node = root.current; if (!node) return;
      const table = node.querySelector('.rw-primary-table') || node.querySelector('.rw-table-scroll');
      if (table) { table.scrollLeft = initialContext.scroll.tableLeft || 0; table.scrollTop = initialContext.scroll.tableTop || 0; }
    });
    return () => cancelAnimationFrame(frame);
  }, [response]);
  const changeScope = next => { lastSnapshotRef.current = null; setScope(next); setState(old => ({ ...old, page: 1, snapshot_ref: undefined })); setSelected(null); setCatalog(false); setNotice(''); setError(null); };
  const changePage = patch => { setState(old => ({ ...old, ...patch, snapshot_ref: response ? response.meta.snapshot_ref : old.snapshot_ref })); setSelected(null); };
  const changeTopic = topic => changePage({ topic, sort: ReportAPI.sorts[topic][0], page: 1 });
  function reload() { if (data) setScope(ReportAPI.scope(data.scope)); setState(old => ({ ...old, snapshot_ref: undefined })); setNotice(''); setError(null); refresh(); }
  async function download() {
    setDownloading(true); setError(null); setNotice('');
    try {
      const result = await ReportAPI.download(data.exports.url, { ...ReportAPI.scope(data.scope), ...ReportAPI.table(state, data.topic), snapshot_ref: response.meta.snapshot_ref, format });
      setNotice(WorkbenchTerms.download_started(result.filename) + '（当前筛选全部 ' + data.page.total + ' 项）。');
    }
    catch (failure) { setError(failure); } finally { setDownloading(false); }
  }
  // 执行复盘以图表分析为主体：图表直接展开放最前，不显示报表子页签和导出范围，表格放在后面；报表中心保持原样。
  const review = mode === 'review';
  const title = review ? '执行复盘' : '报表中心';
  React.useLayoutEffect(() => {
    if (pendingViewFocus !== mode) return;
    const tab = document.getElementById('analytics-view-' + mode);
    if (tab && !tab.disabled) { tab.focus(); pendingViewFocus = null; }
  }, [mode, !!data]);
  function currentContext() {
    const node = root.current, main = document.querySelector('.main-content'), table = node && (node.querySelector('.rw-primary-table') || node.querySelector('.rw-table-scroll'));
    return pageContext({ mainTop: main ? main.scrollTop : 0, windowTop: pageYOffset, tableLeft: table ? table.scrollLeft : 0, tableTop: table ? table.scrollTop : 0 });
  }
  const go = (target, resume = false) => {
    if (!resume && initialContext.returnTo && initialContext.returnTo.view === target) return onNav(target, initialContext.returnTo.context);
    const context = { scope: ReportAPI.scope(data.scope), topic: state.topic };
    onNav(target, { ...context, returnTo: { view: mode, context: currentContext() } }, resume);
  };
  function drill(topic, patch) {
    onNav('reports', { topic, scope: ReportAPI.scope({ ...data.scope, ...patch }), returnTo: { view: mode, context: currentContext() } });
  }
  function navigateOperation(operationRef, original, row, target = 'field', reportRef = null) {
    if (!data || !response) return;
    if (!row || row.operation_ref !== operationRef || !FieldContract.ref(row.task_ref) || !data.plan.is_current_official
      || data.scope.source !== 'production' || original.snapshot_ref !== response.meta.snapshot_ref || !['field', 'fieldgantt'].includes(target)
      || reportRef !== null && !FieldContract.ref(reportRef)) { setError(APSResourceContract.failure('来源任务、记录或计划没有通过核对，没有改指其他工序。')); return; }
    const targetScope = { plan_ref: data.plan.plan_ref };
    for (const key of ['plan_finish_date_from', 'plan_finish_date_to']) if (data.scope[key]) targetScope[key] = data.scope[key];
    onNav(target, {
      plan_ref: data.plan.plan_ref, task_ref: row.task_ref, operation_ref: operationRef, scope: targetScope,
      ...(reportRef ? { report_ref: reportRef } : {}), return_to: { view: mode, context: currentContext() }
    });
  }
  return <section ref={root} className={review ? 'er-workbench rw-workbench' : 'rw-workbench'} aria-label={title} data-source="production" data-ready={!!data}>
    <header className="rw-header"><div><h2 className="wb-page-title">{title}</h2><p className="wb-page-context">{data ? data.plan.display_name + ' · 当前正式计划与报工记录' : '当前正式计划'}{response && <span className="rw-asof">{WorkbenchTerms.data_as_of(WorkbenchFormat.dateTime(response.meta.as_of))}</span>}</p></div>
      <div className="rw-actions">{initialContext.returnTo && initialContext.returnTo.view === 'calib' && <Button icon="arrow-left"
        onClick={() => go('calib')}>返回工时校准</Button>}
        {initialContext.returnTo && ['reports', 'review'].includes(initialContext.returnTo.view) && <Button icon="arrow-left"
          onClick={() => go(initialContext.returnTo.view)}>返回来源</Button>}
        <Button icon="refresh-cw" aria-label="刷新报表" busy={request.busy} onClick={reload} /></div></header>
    <div className="rw-query wb-surface"><div className="wb-view-tabs" role="tablist" aria-label="统计分析视图">
      {[['reports', '报表中心'], ['review', '执行复盘']].map(([target, label], index) => <button type="button" key={target} role="tab" id={'analytics-view-' + target}
        aria-selected={mode === target} aria-controls="analytics-view-panel" tabIndex={mode === target ? 0 : -1} disabled={!data}
        onClick={() => target !== mode && go(target, true)} onKeyDown={event => {
          if (event.altKey || event.ctrlKey || event.metaKey) return;
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault(); const next = event.key === 'Home' ? 'reports' : event.key === 'End' ? 'review' : index === 0 ? 'review' : 'reports';
          const button = document.getElementById('analytics-view-' + next); if (button && !button.disabled) { button.focus(); if (next !== mode) { pendingViewFocus = next; go(next, true); } }
        }}>{label}</button>)}
    </div>
      <Scope value={scope} onChange={changeScope} choices={lastChoices} busy={request.busy} /></div>
    <div id="analytics-view-panel" role="tabpanel" aria-labelledby={'analytics-view-' + mode}>
      {review && <ReviewCharts data={data} loading={request.busy && !data} expanded resourceView={resourceView} onResourceView={setResourceView} onDrill={drill} />}
      <div className="rw-results wb-surface">
        {!review && <Tabs topic={state.topic} onChange={changeTopic} />}
        <ErrorBox error={request.error || error} />{request.error && <Button icon="refresh-cw" onClick={reload}>刷新报表数据</Button>}
        {notice && <p className="rw-notice" role="status">{notice}</p>}
        {request.busy && <EmptyState kind="loading" title="正在读取当前范围" />}
        <div id="report-topic-panel" role={review ? undefined : 'tabpanel'} aria-labelledby={review ? undefined : 'report-tab-' + state.topic}>
          {data && <div className="rw-summary"><Metrics summary={data.summary} topic={state.topic} />
            <NoFeedback summary={data.summary} /></div>}
          <div className="rw-table-heading wb-surface-row wb-surface-divider"><div className="rw-table-title"><h3>{state.topic === 'records' ? '逐次报工记录' : ['machines', 'people'].includes(state.topic) ? '实际资源记录' : '范围内工序'}</h3>{data && <span>{data.page.total} 项</span>}</div>
            <div className="rw-filters"><Sort topic={state.topic} state={state} onChange={changePage} />
              {!review && <><label>格式<select aria-label="导出格式" value={format} disabled={request.busy || !data} onChange={event => setFormat(event.target.value)}><option value="csv">CSV</option><option value="xlsx">XLSX</option></select></label>
                <Button transfer="export" busy={downloading} disabled={request.busy || !data} reasonDisplay="inline" reason={data && !data.page.total ? '当前范围没有可导出的结果。' : ''} onClick={download}>导出范围</Button></>}</div></div>
          <div className={'rw-result-content' + (selected && (data || (request.busy && lastSnapshotRef.current)) ? ' wb-detail-layout' : '')}><div className="rw-list-pane">
            {data && <Table data={data} onDetail={ref => { setSelected(ref); setDetailView({ page: 1, size: 10 }); }} busy={request.busy} primary />}
            <Page page={data ? data.page : { number: state.page, size: state.size }} onChange={changePage} busy={request.busy || !data} /></div>
            {selected && (data || (request.busy && lastSnapshotRef.current)) && <ReportDetail operationRef={selected} input={{ ...ReportAPI.scope(data ? data.scope : lastScope.current), ...ReportAPI.table(state, data ? data.topic : state.topic), snapshot_ref: response ? response.meta.snapshot_ref : lastSnapshotRef.current }} busy={request.busy || !data} onClose={() => setSelected(null)}
              initialView={detailView} onView={setDetailView} onOpenOperation={navigateOperation} />}</div>
        </div>
      </div>
      {!review && <ReviewCharts data={data} loading={request.busy && !data} open={chartsOpen} onChange={setChartsOpen} resourceView={resourceView} onResourceView={setResourceView} onDrill={drill} />}
      <div className="rw-support"><details className="rw-limitations"><summary>统计说明与待补资料</summary>{data ? <ul>{data.data_gaps.map(text => <li key={text}>{text}</li>)}</ul> : <p className="rw-muted">正在读取统计说明与待补资料。</p>}</details>
        <details className="rw-catalog" open={catalog} onToggle={event => setCatalog(event.currentTarget.open)}><summary>其他报表</summary>
          {catalog && <ReportCatalog scope={data ? data.scope : lastScope.current} snapshot={response ? response.meta.snapshot_ref : undefined} />}</details></div>
    </div>
  </section>;
}

// 侧栏直接进入时 main.jsx 传空对象作为定位上下文。
function GuardedWorkspace({ initialContext, ...props }) {
  let initialScope, initialState;
  try {
    initialScope = ReportAPI.scope(initialContext.scope);
    const topic = props.mode === 'review' || initialContext.topic === undefined ? 'delivery' : initialContext.topic;
    if (!ReportAPI.topics.includes(topic)) throw APSResourceContract.failure('原报表专题无效，未改用默认专题。');
    initialState = ReportAPI.table(initialContext.table, topic);
    if (initialContext.selected !== undefined && initialContext.selected !== null && !/^[0-9a-f]{48}$/.test(initialContext.selected))
      throw APSResourceContract.failure('原工序编号无效，没有改选其他工序。');
    const value = initialContext.resourceView;
    if (value !== undefined && (!value || !['machine', 'operator'].includes(value.kind) || !Number.isSafeInteger(value.page) || value.page < 1))
      throw APSResourceContract.failure('资源工时查看状态无效，未改选其他资源。');
    const detail = initialContext.detailView;
    if (detail !== undefined && (!detail || !Number.isSafeInteger(detail.page) || detail.page < 1 || ![10, 20, 50].includes(detail.size)))
      throw APSResourceContract.failure('报表记录详情分页无效，未改选其他记录。');
  }
  catch (error) { return <section className="rw-workbench"><h2 className="wb-page-title">{props.mode === 'review' ? '执行复盘' : '报表中心'}</h2><ErrorBox error={error} /></section>; }
  return <Workspace {...props} initialContext={initialContext} initialScope={initialScope} initialState={initialState} />;
}

const ReportWorkspace = GuardedWorkspace;

export { ReportWorkspace, GuardedWorkspace, Workspace };
export default ReportWorkspace;
