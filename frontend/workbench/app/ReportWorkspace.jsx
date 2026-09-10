(function () {
  'use strict';
  function Workspace({ adapter, mode = 'reports', initialContext = {}, onNav, onOpenOperation }) {
    const { Scope, Tabs, Sort, Page, Button, ErrorBox, useRead, Styles } = window.ReportControls;
    const { Table, Metrics } = window.ReportTable;
    const api = React.useMemo(() => adapter || window.ReportAPI.create(), [adapter]);
    const initialTopic = mode === 'review' ? 'delivery' : window.ReportAPI.topics.includes(initialContext.topic) ? initialContext.topic : 'delivery';
    const [scope, setScope] = React.useState(() => window.ReportAPI.scope(initialContext.scope || {}));
    const [state, setState] = React.useState({ topic: initialTopic, page: 1, size: 20, sort: window.ReportAPI.sorts[initialTopic][0], direction: 'asc', ...initialContext.table, snapshot_ref: initialContext.snapshot_ref });
    const [revision, refresh] = React.useReducer(value => value + 1, 0), [selected, setSelected] = React.useState(initialContext.selected || null),
      [notice, setNotice] = React.useState(''), [error, setError] = React.useState(null), [downloading, setDownloading] = React.useState(false), [format, setFormat] = React.useState('csv'),
      [catalog, setCatalog] = React.useState(!!initialContext.catalogOpen), [chartsOpen, setChartsOpen] = React.useState(!!initialContext.chartsOpen);
    const root = React.useRef(null), restored = React.useRef(false);
    const [scroll, setScroll] = React.useState(initialContext.scroll || {});
    const [resourceView, setResourceView] = React.useState(initialContext.resourceView || { kind: 'machine', page: 1 });
    const [lastChoices, setLastChoices] = React.useState({});
    const input = { ...scope, ...state };
    const request = useRead(signal => api.read(input, signal), JSON.stringify(input) + revision);
    const response = request.result, data = response && response.data;
    const captionPlan = !request.busy && !request.error && data && data.plan;
    const captionStatus = captionPlan && ({ official: captionPlan.is_current_official ? '当前正式采用' : '历史正式方案', candidate: '候选方案', scenario: '试调场景' })[captionPlan.kind];
    window.WorkbenchCaption.useCaption(captionStatus ? {
      reference: captionPlan.plan_ref, label: mode === 'review' ? '复盘计划' : '报表计划', name: captionPlan.display_name, status: captionStatus,
      version: captionPlan.kind === 'official' && Number.isSafeInteger(captionPlan.version) ? '正式 v' + captionPlan.version : undefined,
      range: data.scope.plan_finish_date_from && data.scope.plan_finish_date_to ? '计划完工 ' + data.scope.plan_finish_date_from + ' 至 ' + data.scope.plan_finish_date_to : undefined
    } : null);
    window.WorkbenchPageContext.useSnapshot(data ? {
      scope: window.ReportAPI.scope(data.scope), topic: data.topic, snapshot_ref: response.meta.snapshot_ref,
      table: { topic: data.topic, page: data.page.number, size: data.page.size, sort: data.page.sort[0].field,
        direction: data.page.sort[0].direction, snapshot_ref: response.meta.snapshot_ref }, selected, chartsOpen,
      catalogOpen: catalog, scroll, resourceView, returnTo: initialContext.returnTo
    } : null, !!data && !request.busy && !request.error);
    React.useEffect(() => {
      let frame = 0;
      const remember = event => {
        const node = root.current, table = node && node.querySelector('.rw-primary-table'), main = node && node.closest('.main-content');
        if (!node || ![table, main, document, window].includes(event.target)) return;
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => setScroll({ tableLeft: table ? table.scrollLeft : 0, tableTop: table ? table.scrollTop : 0,
          mainTop: main ? main.scrollTop : 0, windowTop: window.pageYOffset }));
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
        const table = root.current.querySelector('.rw-table-scroll'), main = root.current.closest('.main-content');
        if (table) { table.scrollLeft = initialContext.scroll.tableLeft || 0; table.scrollTop = initialContext.scroll.tableTop || 0; }
        if (main) main.scrollTop = initialContext.scroll.mainTop || 0;
        window.scrollTo(0, initialContext.scroll.windowTop || 0);
      });
      return () => cancelAnimationFrame(frame);
    }, [response]);
    const changeScope = next => { setScope(next); setState(old => ({ ...old, page: 1, snapshot_ref: undefined })); setSelected(null); setCatalog(false); setNotice(''); setError(null); };
    const changePage = patch => { setState(old => ({ ...old, ...patch, snapshot_ref: response ? response.meta.snapshot_ref : old.snapshot_ref })); setSelected(null); };
    const changeTopic = topic => changePage({ topic, sort: window.ReportAPI.sorts[topic][0], page: 1 });
    function reload() { setState(old => ({ ...old, page: 1, snapshot_ref: undefined })); setSelected(null); setCatalog(false); setNotice(''); setError(null); refresh(); }
    async function download() {
      setDownloading(true); setError(null);
      try { await api.download(data.exports.url, { ...input, snapshot_ref: response.meta.snapshot_ref, format }); setNotice('已导出当前筛选全部 ' + data.page.total + ' 项，文件已交给浏览器下载。'); }
      catch (failure) { setError(failure); } finally { setDownloading(false); }
    }
    const title = mode === 'review' ? '执行复盘' : '报表中心';
    const go = target => {
      if (initialContext.returnTo && initialContext.returnTo.view === target) return onNav(target, initialContext.returnTo.context);
      const table = root.current.querySelector('.rw-table-scroll'), main = root.current.closest('.main-content');
      const context = { scope: window.ReportAPI.scope(data.scope), topic: state.topic, snapshot_ref: response.meta.snapshot_ref };
      onNav(target, { ...context, returnTo: { view: mode, context: { ...context, table: state, selected, chartsOpen, resourceView, catalogOpen: catalog,
        scroll: { tableLeft: table ? table.scrollLeft : 0, tableTop: table ? table.scrollTop : 0, mainTop: main ? main.scrollTop : 0, windowTop: window.pageYOffset } } } });
    };
    function drill(topic, patch) {
      const table = root.current.querySelector('.rw-primary-table'), main = root.current.closest('.main-content');
      const origin = { scope: window.ReportAPI.scope(data.scope), topic: data.topic, table: state, snapshot_ref: response.meta.snapshot_ref,
        selected, chartsOpen, resourceView, catalogOpen: catalog, returnTo: initialContext.returnTo,
        scroll: { tableLeft: table ? table.scrollLeft : 0, tableTop: table ? table.scrollTop : 0, mainTop: main ? main.scrollTop : 0, windowTop: window.pageYOffset } };
      onNav('reports', { topic, scope: window.ReportAPI.scope({ ...data.scope, ...patch }), returnTo: { view: mode, context: origin } });
    }
    return <section ref={root} className={mode === 'review' ? 'er-workbench rw-workbench' : 'rw-workbench'} aria-label={title} data-source="production" data-ready={!!data}>
      <Styles />
      <header className="rw-header"><div><h2>{title}</h2><p>{data ? data.plan.display_name + ' · 当前正式计划与执行台账' : '当前正式计划'}{response && <span className="rw-asof">数据截至 {response.meta.as_of.replace('T', ' ')}</span>}</p></div>
        <div className="rw-actions">{initialContext.returnTo && initialContext.returnTo.view === 'calib' && <Button icon="arrow-left"
          disabled={typeof onNav !== 'function'} onClick={() => go('calib')}>返回工时校准</Button>}
          {initialContext.returnTo && ['reports', 'review'].includes(initialContext.returnTo.view) && <Button icon="arrow-left"
            disabled={typeof onNav !== 'function'} onClick={() => go(initialContext.returnTo.view)}>返回来源</Button>}
          <Button icon="refresh-cw" aria-label="刷新报表" busy={request.busy} onClick={reload} />
          <Button icon="arrow-right" disabled={!data} reason={typeof onNav !== 'function' ? '工作区导航尚未接合。' : ''} onClick={() => go(mode === 'review' ? 'reports' : 'review')}>{mode === 'review' ? '报表中心' : '执行复盘'}</Button></div></header>
      <Scope value={scope} onChange={changeScope} choices={lastChoices} busy={request.busy} />
      <ErrorBox error={request.error || error} />{request.error && <Button icon="refresh-cw" onClick={reload}>重新读取</Button>}
      {notice && <p className="rw-notice" role="status">{notice}</p>}
      {mode !== 'review' && <Tabs topic={state.topic} onChange={changeTopic} />}
      {request.busy && <p role="status">正在读取真实范围...</p>}
      {data && <div id="report-topic-panel" role={mode === 'review' ? undefined : 'tabpanel'} aria-labelledby={mode === 'review' ? undefined : 'report-tab-' + state.topic}>
        <Metrics summary={data.summary} topic={state.topic} />
        <p className="rw-basis">计划完工日选工序 · 延后超过 10 分钟才计晚完 · 未确认完成不等于未生产。</p>
        <div className="rw-table-heading"><div className="rw-table-title"><h3>{state.topic === 'records' ? '逐次报工与旧现场事件' : ['machines', 'people'].includes(state.topic) ? '实际资源记录' : '范围内工序'}</h3><span>{data.page.total} 项</span></div>
          <div className="rw-filters"><Sort topic={state.topic} state={state} onChange={changePage} />
            <label>格式<select aria-label="导出格式" value={format} onChange={event => setFormat(event.target.value)}><option value="csv">CSV</option><option value="xlsx">XLSX</option></select></label>
            <Button transfer="export" busy={downloading} disabled={request.busy} reason={!data.page.total ? '当前范围没有可导出的结果。' : ''} onClick={download}>导出范围</Button></div></div>
        <Table data={data} onDetail={setSelected} busy={request.busy} primary /><Page page={data.page} onChange={changePage} busy={request.busy} />
        {selected && <window.ReportDetail api={api} operationRef={selected} input={{ ...input, snapshot_ref: response.meta.snapshot_ref }} onClose={() => setSelected(null)} onOpenOperation={onOpenOperation} />}
        <window.ReviewCharts data={data} open={chartsOpen} onChange={setChartsOpen} resourceView={resourceView} onResourceView={setResourceView} onDrill={typeof onNav === 'function' ? drill : undefined} />
        <details className="rw-limitations"><summary>数据范围与缺口</summary><ul>{data.data_gaps.map(text => <li key={text}>{text}</li>)}</ul></details>
        <details className="rw-catalog" open={catalog} onToggle={event => setCatalog(event.currentTarget.open)}><summary>其他报表</summary>
          {catalog && <window.ReportCatalog api={api} scope={data.scope} snapshot={response.meta.snapshot_ref} />}</details>
      </div>}
    </section>;
  }
  function GuardedWorkspace(props) {
    try {
      window.ReportAPI.scope(props.initialContext && props.initialContext.scope || {});
      const value = props.initialContext && props.initialContext.resourceView;
      if (value !== undefined && (!value || !['machine', 'operator'].includes(value.kind) || !Number.isSafeInteger(value.page) || value.page < 1))
        throw window.APSResourceContract.failure('资源工时查看状态无效，未改选其他资源。');
    }
    catch (error) { return <section className="rw-workbench"><h2>{props.mode === 'review' ? '执行复盘' : '报表中心'}</h2><window.ResourceControls.ErrorBox error={error} /></section>; }
    return <Workspace {...props} />;
  }
  window.ReportWorkspace = GuardedWorkspace;
})();
