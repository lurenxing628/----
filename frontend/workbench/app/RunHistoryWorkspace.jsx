(function () {
  'use strict';
  const A = window.RunHistoryAPI, C = window.RunHistoryControls;
  const adapterIds = new WeakMap(); let nextAdapter = 0;
  let focusTopic = null;
  function useRead(adapter, query, revision) {
    const api = React.useMemo(() => A.adapter(adapter), [adapter]);
    const read = window.APSResourceSession.useQuery(async signal => {
      return api.catalog(query, signal);
    }, [adapter, query, revision]);
    return { ...read, busy: read.loading };
  }
  function TopicTabs({ value, onChange }) {
    const choices = [['run_catalog', '记录列表'], ['decision_history', '指标走势']];
    React.useLayoutEffect(() => { if (focusTopic === value) { const target = document.getElementById('dh-topic-' + value); if (target) target.focus({ preventScroll: true }); focusTopic = null; } }, [value]);
    function change(topic) { focusTopic = topic; onChange(topic); }
    return <div className="rc-tabs dh-topic-tabs" role="tablist" aria-label="排产记录内容" onKeyDown={event => {
      const index = choices.findIndex(row => row[0] === value), next = event.key === 'ArrowRight' || event.key === 'ArrowLeft' ? 1 - index : event.key === 'Home' ? 0 : event.key === 'End' ? 1 : null;
      if (next !== null) { event.preventDefault(); change(choices[next][0]); }
    }}>{choices.map(([key, label]) => <C.Button key={key} role="tab" id={'dh-topic-' + key} aria-selected={value === key} aria-controls="dh-history-content" tabIndex={value === key ? 0 : -1} onClick={() => change(key)}>{label}</C.Button>)}</div>;
  }
  function Session({ adapter, start, onNavigate, navigation, pageContext }) {
    const [query, setQuery] = React.useState(start.query), [revision, refresh] = React.useReducer(v => v + 1, 0);
    const read = useRead(adapter, query, revision), result = read.result, data = result && result.data;
    const remembered = { ...pageContext, source: 'run_history', history_topic: 'run_catalog', history_query: { ...A.returnContext(query, start.returnPlan), ...(result ? { snapshot_ref: result.meta.snapshot_ref } : {}) } };
    window.WorkbenchPageContext.useSnapshot(remembered);
    function reload() { setQuery(q => { const next = { ...q, page: 1 }; delete next.snapshot_ref; return next; }); refresh(); }
    function apply(q) { setQuery(q); refresh(); }
    function change(patch, paging) {
      const q = { ...query, ...patch }; delete q.snapshot_ref;
      if (paging && result) q.snapshot_ref = result.meta.snapshot_ref;
      apply(A.scope(q));
    }
    function open(run) {
      const context = { run_ref: run.run_ref, return_history_context: A.returnContext(query, start.returnPlan) };
      if (Object.keys(start.returnPlan).length) context.return_plan_context = start.returnPlan;
      onNavigate('analysis', context);
    }
    return <div className="plana run-history-workspace" data-run-history-workspace aria-busy={read.busy}>
      <h2 className="wb-page-title">排产记录</h2>
      <header className="rh-heading scheduling-page-tools">{navigation}<div className="rh-tools">
        <C.Button icon="chevron-left" aria-label="返回正式计划" onClick={() => onNavigate('analysis', start.returnPlan)}>返回正式计划</C.Button>
        <C.Button icon="refresh-cw" aria-label="刷新排产记录" busy={read.busy} onClick={reload} /></div></header>
      <TopicTabs value="run_catalog" onChange={topic => onNavigate('analysis', { ...remembered, history_topic: topic })} />
      <div id="dh-history-content" role="tabpanel" aria-labelledby="dh-topic-run_catalog"><C.Filters value={query} busy={read.busy} onApply={apply} />
      <C.ErrorBox error={read.error} />
      {read.error && <C.Button icon="refresh-cw" onClick={reload}>重新查询</C.Button>}
      {read.busy && <window.WorkbenchListControls.EmptyState kind="loading" title="正在读取排产记录" hint="当前筛选的结果还没读到" />}
      {data && <><div className="rh-source"><span>共 {window.WorkbenchFormat.number(data.run_count, { digits: 0 })} 次排产</span>
        <details><summary>查询说明</summary><div>本次刷新：{window.WorkbenchFormat.dateTime(result.meta.as_of, { seconds: true, fractions: true })}</div><div>提交日期包含起止日。安排数为各候选方案的安排条数合计；同一道工序在多个候选方案中会分别计数。</div><div>打开候选方案查看工序安排与交付风险。</div></details></div>
        {result.warnings.map((w, i) => <div key={i} className="rh-notice" role="status">{w.message}</div>)}
        {data.runs.length ? <C.Table runs={data.runs} onOpen={open} /> : <window.WorkbenchListControls.EmptyState kind={data.run_count === 0 ? 'empty' : 'filtered'}
          title={data.run_count === 0 ? '尚无排产记录' : data.page.total === 0 ? '当前筛选没有匹配的排产记录' : '当前页没有排产记录'}
          hint={data.run_count === 0 ? '排产提交后会保留在这个列表里。' : data.page.total === 0 ? '其他排产没有包含在当前筛选里。' : '翻页位置已失效，请回到第 1 页重新查询。'}
          action={data.run_count > 0 && <C.Button icon="chevron-left" onClick={() => data.page.total > 0 ? change({ page: 1 }, true) : apply(A.scope({ size: query.size }))}>{data.page.total > 0 ? '返回第 1 页' : '清除全部筛选'}</C.Button>} />}
        <C.Pager page={data.page} busy={read.busy} onChange={change} /></>}</div>
    </div>;
  }
  function RunHistoryWorkspace({ initialContext = {}, pageContext = {}, onNavigate, adapter, navigation }) {
    const fallback = React.useMemo(() => A.create(), []), active = adapter || fallback;
    if (pageContext.history_topic === 'decision_history') return <window.DecisionHistoryWorkspace initialContext={pageContext.decision_history_context || {}} pageContext={pageContext}
      onNavigate={onNavigate} navigation={navigation} renderTopics={context => <TopicTabs value="decision_history" onChange={topic => onNavigate('analysis', { ...context, history_topic: topic })} />} />;
    let start;
    try { start = A.context(initialContext); }
    catch (error) { return <div className="plana run-history-workspace" data-run-history-workspace><h2 className="wb-page-title">排产记录</h2><C.ErrorBox error={error} /></div>; }
    if (!adapterIds.has(active)) adapterIds.set(active, ++nextAdapter);
    return <Session key={adapterIds.get(active) + ':' + JSON.stringify(start)} adapter={active} start={start} pageContext={pageContext} onNavigate={onNavigate} navigation={navigation} />;
  }
  window.RunHistoryWorkspace = RunHistoryWorkspace;
})();
