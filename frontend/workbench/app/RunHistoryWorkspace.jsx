(function () {
  'use strict';
  const A = window.RunHistoryAPI, C = window.RunHistoryControls;
  const adapterIds = new WeakMap(); let nextAdapter = 0;
  function useRead(adapter, query, revision) {
    const identity = React.useMemo(() => ({}), [adapter, query, revision]);
    const [state, setState] = React.useState({});
    React.useEffect(() => {
      const controller = new AbortController(); let active = true;
      setState({ identity, busy: true, result: null, error: null });
      Promise.resolve().then(() => adapter.catalog(query, controller.signal)).then(result => {
        A.catalog(result, query); if (active) setState({ identity, busy: false, result, error: null });
      }).catch(error => { if (active) setState({ identity, busy: false, result: null, error }); });
      return () => { active = false; controller.abort(); };
    }, [identity]);
    return state.identity === identity ? state : { busy: true, result: null, error: null };
  }
  function Session({ adapter, start, onNavigate }) {
    const [query, setQuery] = React.useState(start.query), [revision, refresh] = React.useReducer(v => v + 1, 0);
    const read = useRead(adapter, query, revision), result = read.result, data = result && result.data;
    const stale = read.error && read.error.code === 'snapshot_stale';
    function reload() { setQuery(q => { const next = { ...q, page: 1 }; delete next.snapshot_ref; return next; }); refresh(); }
    function apply(q) { setQuery(q); refresh(); }
    function change(patch, paging) {
      const q = { ...query, ...patch }; delete q.snapshot_ref;
      if (paging && result) q.snapshot_ref = result.meta.snapshot_ref;
      apply(A.scope(q));
    }
    function open(run) {
      if (typeof onNavigate !== 'function') return;
      const context = { run_ref: run.run_ref, return_history_context: A.returnContext(query, start.returnPlan) };
      if (Object.keys(start.returnPlan).length) context.return_plan_context = start.returnPlan;
      onNavigate('analysis', context);
    }
    return <div className="plana run-history-workspace" data-run-history-workspace aria-busy={read.busy}><C.Styles />
      <header className="rh-heading"><div><h2>排产历史</h2><span className="rh-muted">运行记录 · 只读</span></div><div className="rh-tools">
        {typeof onNavigate === 'function' && <C.Button icon="chevron-left" aria-label="返回方案页" onClick={() => onNavigate('analysis', start.returnPlan)}>返回方案</C.Button>}
        <C.Button icon="refresh-cw" aria-label="刷新排产历史" busy={read.busy} onClick={reload} /></div></header>
      <C.Filters value={query} busy={read.busy} onApply={apply} />
      <C.ErrorBox error={read.error} />
      {read.error && <C.Button icon="refresh-cw" onClick={reload}>{stale ? '明确重读历史' : '重新读取历史'}</C.Button>}
      {read.busy && <div className="rh-empty" role="status"><strong>正在读取排产历史</strong>当前筛选结果尚未返回</div>}
      {data && <><div className="rh-source"><span>目录共 {data.run_count.toLocaleString('zh-CN')} 次 · 受理日期按工厂本地时间，含起止日</span>
        <span>读取于 {C.timeLabel(result.meta.as_of)}</span></div>
        {result.warnings.map((w, i) => <div key={i} className="rh-notice" role="status">{w.message}</div>)}
        {data.runs.length ? <C.Table runs={data.runs} canNavigate={typeof onNavigate === 'function'} onOpen={open} /> : <div className="rh-empty" role="status">
          <strong>{data.run_count === 0 ? '尚无排产运行记录' : data.page.total === 0 ? '当前筛选没有匹配的运行记录' : '当前页没有运行记录'}</strong>
          {data.run_count === 0 ? '排产运行受理后会保留在此目录。' : data.page.total === 0 ? '其他运行未包含在当前筛选中。' : '当前页超出结果范围。'}
          {data.page.total > 0 && <C.Button icon="chevron-left" onClick={() => change({ page: 1 }, true)}>返回第一页</C.Button>}</div>}
        <C.Pager page={data.page} busy={read.busy} onChange={change} />
        <div className="rh-muted">安排行数是各候选已保存行的合计，不是去重工序数。计算完成仅表示运行结束；约束与任务内容须在候选中核对。</div></>}
    </div>;
  }
  function RunHistoryWorkspace({ initialContext = {}, onNavigate, adapter }) {
    const fallback = React.useMemo(() => A.create(), []), active = adapter || fallback;
    let start;
    try { start = A.context(initialContext); A.check(active && typeof active.catalog === 'function', '排产历史读取适配器不可用。'); }
    catch (error) { return <div className="plana run-history-workspace" data-run-history-workspace><C.Styles /><h2>排产历史</h2><C.ErrorBox error={error} /></div>; }
    if (!adapterIds.has(active)) adapterIds.set(active, ++nextAdapter);
    return <Session key={adapterIds.get(active) + ':' + JSON.stringify(start)} adapter={active} start={start} onNavigate={onNavigate} />;
  }
  window.RunHistoryWorkspace = RunHistoryWorkspace;
})();
