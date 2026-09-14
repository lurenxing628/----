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
      <header className="rh-heading"><div><h2 className="wb-page-title">排产记录</h2><span className="rh-muted wb-page-context">历次排产 · 只读</span></div><div className="rh-tools">
        {typeof onNavigate === 'function' && <C.Button icon="chevron-left" aria-label="返回正式计划" onClick={() => onNavigate('analysis', start.returnPlan)}>返回正式计划</C.Button>}
        <C.Button icon="refresh-cw" aria-label="刷新排产记录" busy={read.busy} onClick={reload} /></div></header>
      <C.Filters value={query} busy={read.busy} onApply={apply} />
      <C.ErrorBox error={read.error} />
      {read.error && <C.Button icon="refresh-cw" onClick={reload}>重新查询</C.Button>}
      {read.busy && <window.WorkbenchListControls.EmptyState kind="loading" title="正在读取排产记录" hint="当前筛选的结果还没读到" />}
      {data && <><div className="rh-source"><span>共 {window.WorkbenchFormat.number(data.run_count, { digits: 0 })} 次排产 · 提交日期含起止日</span>
        <span>读取于 {C.timeLabel(result.meta.as_of)}</span></div>
        {result.warnings.map((w, i) => <div key={i} className="rh-notice" role="status">{w.message}</div>)}
        {data.runs.length ? <C.Table runs={data.runs} canNavigate={typeof onNavigate === 'function'} onOpen={open} /> : <window.WorkbenchListControls.EmptyState kind={data.run_count === 0 ? 'empty' : 'filtered'}
          title={data.run_count === 0 ? '尚无排产记录' : data.page.total === 0 ? '当前筛选没有匹配的排产记录' : '当前页没有排产记录'}
          hint={data.run_count === 0 ? '排产提交后会保留在这个列表里。' : data.page.total === 0 ? '其他排产没有包含在当前筛选里。' : '翻页位置已失效，请回到第 1 页重新查询。'}
          action={data.run_count > 0 && <C.Button icon="chevron-left" onClick={() => data.page.total > 0 ? change({ page: 1 }, true) : apply(A.scope({ size: query.size }))}>{data.page.total > 0 ? '返回第 1 页' : '清除全部筛选'}</C.Button>} />}
        <C.Pager page={data.page} busy={read.busy} onChange={change} />
        <div className="rh-muted">安排行数是各候选方案已保存行的合计，不是不重复的工序道数。计算完成只表示排产结束；约束和任务内容要在候选方案里核对。</div></>}
    </div>;
  }
  function RunHistoryWorkspace({ initialContext = {}, onNavigate, adapter }) {
    const fallback = React.useMemo(() => A.create(), []), active = adapter || fallback;
    let start;
    try { start = A.context(initialContext); A.check(active && typeof active.catalog === 'function', 'dependency not wired: adapter.catalog'); }
    catch (error) { return <div className="plana run-history-workspace" data-run-history-workspace><C.Styles /><h2 className="wb-page-title">排产记录</h2><C.ErrorBox error={error} /></div>; }
    if (!adapterIds.has(active)) adapterIds.set(active, ++nextAdapter);
    return <Session key={adapterIds.get(active) + ':' + JSON.stringify(start)} adapter={active} start={start} onNavigate={onNavigate} />;
  }
  window.RunHistoryWorkspace = RunHistoryWorkspace;
})();
