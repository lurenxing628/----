(function () {
  'use strict';
  const A = window.RunCandidateAPI, C = window.RunCandidateControls;
  const adapterIds = new WeakMap(); let nextAdapter = 0;
  function useRead(load, deps, enabled) {
    const identity = React.useMemo(() => ({}), deps);
    const [state, setState] = React.useState({ result: null, error: null, busy: false });
    React.useEffect(() => {
      const controller = new AbortController(); let active = true;
      setState({ identity, result: null, error: null, busy: enabled });
      if (enabled) Promise.resolve().then(() => load(controller.signal)).then(result => { if (active) setState({ identity, result, error: null, busy: false }); })
        .catch(error => { if (active) setState({ identity, result: null, error, busy: false }); });
      return () => { active = false; controller.abort(); };
    }, deps);
    return state.identity === identity ? state : { result: null, error: null, busy: enabled };
  }
  function returnContext(value) {
    const result = {};
    for (const key of ['run_ref', 'candidate_ref', 'plan_ref', 'batch_ref']) if (value && A.ref(value[key])) result[key] = value[key];
    for (const key of ['range_start', 'range_end']) if (value && A.time(value[key])) result[key] = value[key];
    return result;
  }
  function Export({ adapter, result, scope, query }) {
    const [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null), [done, setDone] = React.useState('');
    const active = React.useRef(null);
    React.useEffect(() => () => { if (active.current) active.current.abort(); }, []);
    const d = result.data, allowed = d.capabilities.export === true && d.candidate.capabilities.export === true && typeof adapter.export === 'function';
    async function save(fmt) {
      if (!allowed || active.current) return;
      const controller = new AbortController(); active.current = controller; setBusy(true); setError(null); setDone('');
      try {
        const file = A.download(await adapter.export(d.candidate.candidate_ref, scope, result.meta.snapshot_ref, fmt, controller.signal), result, fmt);
        if (controller.signal.aborted) return;
        const url = URL.createObjectURL(file.blob), link = document.createElement('a'); link.href = url; link.download = file.filename;
        document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
        setDone('已下载 ' + file.row_count + ' 条记录（安排 ' + d.task_count + '，未安排 ' + (d.unplanned_operation_count === null ? '未知' : d.unplanned_operation_count) + '）。');
      } catch (e) { if (!controller.signal.aborted) setError(e); }
      finally { if (!controller.signal.aborted) { active.current = null; setBusy(false); } }
    }
    return <div><div className="rc-tools">{['csv', 'xlsx'].map(fmt => <C.Button key={fmt} icon="download" title="导出当前读取范围全部安排与未安排记录" disabled={!allowed} busy={busy} onClick={() => save(fmt)}>{fmt.toUpperCase()}</C.Button>)}</div>
      {query.trim() && <small>搜索不改变导出范围</small>}<C.ErrorBox error={error} />{done && <small role="status">{done}</small>}</div>;
  }
  function Session({ adapter, view = 'analysis', initialContext = {}, onNavigate, renderAdoption, renderTrial }) {
    const M = window.RunCandidateModel;
    const invalid = initialContext.run_ref !== undefined && !A.ref(initialContext.run_ref) || initialContext.candidate_ref !== undefined && !A.ref(initialContext.candidate_ref);
    const [runRef, setRunRef] = React.useState(initialContext.run_ref || null), [candidateRef, setCandidateRef] = React.useState(initialContext.candidate_ref || null);
    const [catalogQuery, setCatalogQuery] = React.useState({}), [scope, setScope] = React.useState(() => {
      const value = {}; for (const key of ['range_start', 'range_end', 'batch_ref', 'sort', 'order']) if (initialContext[key] !== undefined) value[key] = initialContext[key]; return value;
    });
    const [range, setRange] = React.useState({ start: scope.range_start || '', end: scope.range_end || '' }), [rangeOpen, setRangeOpen] = React.useState(false);
    const [rangeError, setRangeError] = React.useState(null), [query, setQuery] = React.useState(typeof initialContext.query === 'string' ? initialContext.query : ''), [selected, setSelected] = React.useState(null);
    const [pendingRow, setPendingRow] = React.useState(A.ref(initialContext.selected_row_ref) ? initialContext.selected_row_ref : null);
    const [tab, setTab] = React.useState((view === 'delay' ? ['tasks', 'unplanned'] : ['tasks', 'unplanned', 'delivery']).includes(initialContext.candidate_tab) ? initialContext.candidate_tab : 'tasks'), [revision, refresh] = React.useReducer(v => v + 1, 0);
    const directory = useRead(async signal => { const v = await adapter.catalog(runRef, catalogQuery, signal); A.catalog(v, runRef, catalogQuery); return v; },
      [adapter, runRef, catalogQuery, revision], !!runRef && !invalid);
    const read = useRead(async signal => { const v = await adapter.workspace(candidateRef, scope, signal); A.workspace(v, candidateRef, scope, initialContext.run_ref); return v; },
      [adapter, candidateRef, scope, revision], !!candidateRef && !invalid);
    const result = read.result, data = result && result.data;
    React.useEffect(() => { if (data && !runRef) setRunRef(data.candidate.run_ref); }, [data, runRef]);
    const shown = data && data.capabilities.view === true && data.candidate.capabilities.view === true ? data : null;
    window.WorkbenchCaption.useCaption(shown && !read.busy && !read.error && shown.candidate.label ? {
      reference: shown.candidate.candidate_ref, label: '当前候选', name: shown.candidate.label,
      status: '候选预览 · ' + ({ completed: '已完成', partial: '部分完成', failed: '失败', skipped: '已跳过' }[shown.candidate.status] || '状态待核实'),
      range: (scope.range_start ? M.timeLabel(scope.range_start) + ' 至 ' + M.timeLabel(scope.range_end) + '（不含结束）' : '完整候选范围')
        + ' · ' + shown.task_count + ' / ' + shown.candidate_task_count + ' 道安排',
    } : null);
    const tasks = React.useMemo(() => shown ? M.matching(shown.tasks, query) : [], [shown, query]);
    const unplanned = React.useMemo(() => shown ? M.matching(shown.unplanned_operations || [], query) : [], [shown, query]);
    const chosen = selected && selected.result === result ? selected.task : null;
    React.useEffect(() => {
      if (!shown || !pendingRow) return;
      const task = shown.tasks.find(row => row.row_ref === pendingRow);
      if (task) { setSelected({ task, result }); setPendingRow(null); }
      else if (!scope.range_start && !scope.batch_ref) { setRangeError(new Error('指定末端工序不在完整候选中，未替换为其他工序。')); setPendingRow(null); }
    }, [result, pendingRow]);
    const remembered = { ...initialContext, ...(runRef ? { run_ref: runRef } : {}), ...(candidateRef ? { candidate_ref: candidateRef } : {}), query, candidate_tab: tab };
    for (const key of ['range_start', 'range_end', 'batch_ref', 'sort', 'order', 'snapshot_ref', 'selected_row_ref']) delete remembered[key];
    Object.assign(remembered, scope, chosen ? { selected_row_ref: chosen.row_ref } : {});
    window.WorkbenchPageContext.useSnapshot(remembered, !!shown && !read.busy && !read.error && !invalid);
    function choose(candidate) { setCandidateRef(candidate.candidate_ref); setScope({}); setRange({ start: '', end: '' }); setRangeError(null); setQuery(''); setSelected(null); }
    function select(task) { setSelected({ task, result }); }
    function lastOperation(task) {
      setQuery('');
      const visible = shown.tasks.find(row => row.row_ref === task.row_ref);
      if (visible) select(visible);
      else { setPendingRow(task.row_ref); setScope({}); setRange({ start: '', end: '' }); setSelected(null); }
    }
    function reload() { setCatalogQuery(q => { const value = { ...q }; delete value.snapshot_ref; return value; }); setSelected(null); refresh(); }
    function rangeSubmit(e) {
      e.preventDefault();
      try {
        const seconds = value => value.length === 16 ? value + ':00' : value;
        const next = A.workspaceScope(candidateRef, { ...scope, range_start: seconds(range.start), range_end: seconds(range.end) });
        setScope(next); setRangeError(null); setSelected(null);
      } catch (error) { setRangeError(error); }
    }
    return <div className="plana run-candidate-workspace" data-run-candidate-workspace><C.Styles />
      <div className="rc-heading"><div className="rc-tools"><h2>{view === 'delay' ? '候选交付风险' : view === 'gantt' ? '候选甘特' : '候选排产结果'}</h2><span className="rc-muted">已保存的候选方案</span></div><div className="rc-tools">
        {onNavigate && <C.Button icon="chevron-left" onClick={() => onNavigate('run', { ...returnContext(initialContext.return_run_context), ...(runRef ? { run_ref: runRef } : {}) })}>返回运行页</C.Button>}
        {onNavigate && initialContext.return_plan_context && A.ref(initialContext.return_plan_context.plan_ref) && <C.Button icon="chevron-left" onClick={() => onNavigate('analysis', returnContext(initialContext.return_plan_context))}>返回正式方案</C.Button>}
        {onNavigate && <C.Button icon="circle-alert" disabled={!shown || read.busy} onClick={() => onNavigate(view === 'delay' ? 'analysis' : 'delay', remembered)}>{view === 'delay' ? '返回比较' : '交付风险'}</C.Button>}
        {onNavigate && view !== 'gantt' && <C.Button icon="chart-gantt" disabled={!shown || read.busy} onClick={() => onNavigate('gantt', remembered)}>查看甘特</C.Button>}
        {typeof renderAdoption === 'function' ? renderAdoption(candidateRef) : <C.Button icon="check" reason="正式采用入口未接入，请先核对完整候选方案。">采用方案</C.Button>}
        {typeof renderTrial === 'function' ? renderTrial({ candidateRef, scope, query, disabled: !shown || read.busy || invalid }) :
          <C.Button icon="square-pen" reason="试调入口未接入，请先核对完整候选方案。">试调</C.Button>}
        <C.Button icon="refresh-cw" aria-label="刷新指定候选来源" disabled={invalid || !runRef && !candidateRef} busy={read.busy || directory.busy} onClick={reload} /></div></div>
      {invalid && <C.ErrorBox error={new Error('记录编号无效，未改查其他运行或最新候选。')} />}
      {!runRef && !candidateRef && <div className="rc-empty" role="status">尚未指定运行或候选来源。请从运行记录打开候选，未自动选择最新运行。</div>}
      {runRef && <><C.ErrorBox error={directory.error} /><C.Catalog result={directory.result} selectedRef={candidateRef} busy={directory.busy} query={catalogQuery}
        onQuery={(change, paging) => setCatalogQuery(q => ({ ...q, ...change, page: paging ? change.page : 1, snapshot_ref: paging ? directory.result.meta.snapshot_ref : undefined }))} onSelect={choose} /></>}
      <C.ErrorBox error={read.error} />{(read.busy || directory.busy) && <p className="rc-muted" role="status">正在读取指定候选来源。</p>}
      {read.error && <div className="rc-empty">指定候选未读取成功，未显示其他候选或上次内容。</div>}
      {runRef && !candidateRef && <div className="rc-empty">尚未选择此运行中的候选。</div>}
      {data && !shown && <div className="rc-notice">接口未授权查看该候选。<C.Reasons rows={data.blocked_reasons} /></div>}
      {shown && <><C.Generation key={shown.candidate.candidate_ref} data={shown} /><C.Reasons rows={result.warnings} /><div className="rc-heading"><div className="rc-tools"><h3>候选工作区</h3><span className="rc-muted">读取于 {M.timeLabel(result.meta.as_of)} · 工厂本地时间</span></div>
        <div className="rc-tools"><input type="search" aria-label="搜索候选工序" placeholder="批次、工序、设备、人员" value={query} onChange={e => setQuery(e.target.value)} />
          <span className="rc-muted">匹配安排 {tasks.length} / {shown.task_count}</span></div>
        <div className="rc-tools"><C.Button icon="calendar-days" aria-expanded={rangeOpen} onClick={() => setRangeOpen(!rangeOpen)}>读取范围</C.Button>
          <Export key={result.meta.snapshot_ref} adapter={adapter} result={result} scope={scope} query={query} /></div></div>
        {rangeOpen && <form className="rc-range" onSubmit={rangeSubmit}><label>开始（包含）<input type="datetime-local" step="1" aria-label="候选读取开始" value={range.start} onChange={e => setRange({ ...range, start: e.target.value })} /></label>
          <label>结束（不含）<input type="datetime-local" step="1" aria-label="候选读取结束" value={range.end} onChange={e => setRange({ ...range, end: e.target.value })} /></label>
          <C.Button icon="check" type="submit">应用范围</C.Button><C.Button icon="chart-gantt" onClick={() => { setScope({}); setRange({ start: '', end: '' }); setRangeError(null); }}>完整候选</C.Button></form>}
        <C.ErrorBox error={rangeError} /><div className="rc-scope"><span>读取范围：{scope.range_start ? M.timeLabel(scope.range_start) + ' 至 ' + M.timeLabel(scope.range_end) + '（不含结束）' : '全部时间'}{scope.batch_ref && ' · 指定批次 ' + scope.batch_ref}
          {' · 安排 ' + shown.task_count + ' / 候选共 ' + shown.candidate_task_count + ' 道 · 未安排 ' + (shown.unplanned_operation_count === null ? '未知（未记录）' : shown.unplanned_operation_count + ' 道')}</span>
          <details><summary>范围与导出口径</summary><div>时间筛选按重叠读取，保留每道安排完整起止；未安排项没有时间区间，仍随范围保留。搜索仅影响预览和明细，不改变导出范围。导出当前读取范围全部安排与未安排记录。</div></details></div>
        {view === 'delay' && <C.Delivery data={shown.delivery_risks} onLast={lastOperation} />}
        <div className="rc-main"><div><window.RunCandidateGantt data={shown} query={query} selected={chosen} onSelect={select} />
          <section aria-label="候选明细"><div className="rc-heading"><div role="tablist" className="rc-tabs" aria-label="候选明细类别">
            {['tasks', 'unplanned', ...(view === 'delay' ? [] : ['delivery'])].map(t => <C.Button key={t} role="tab" icon={t === 'tasks' ? 'chart-gantt' : 'circle-alert'} aria-selected={tab === t} onClick={() => setTab(t)}>{t === 'tasks' ? '任务安排' : t === 'delivery' ? '交付风险' : '未安排明细'}</C.Button>)}</div></div>
            {tab === 'delivery' ? view !== 'delay' && <C.Delivery data={shown.delivery_risks} onLast={lastOperation} /> : tab === 'unplanned' && shown.unplanned_operations === null ? <div className="rc-notice">生成时未保留可核实的未安排明细，不能当成零项。</div> :
              <window.RunCandidateGantt.TaskList key={tab + ':' + query + ':' + result.meta.snapshot_ref} tasks={tab === 'tasks' ? tasks : unplanned} selected={chosen} onSelect={select} planned={tab === 'tasks'} />}</section>
        </div><C.Detail task={chosen} onClose={() => setSelected(null)} /></div></>}
    </div>;
  }
  function RunCandidateWorkspace(props) {
    const adapter = React.useMemo(() => props.adapter || A.create(), [props.adapter]);
    if (!adapterIds.has(adapter)) adapterIds.set(adapter, ++nextAdapter);
    const context = props.initialContext || {}, identity = [context.run_ref, context.candidate_ref, context.range_start, context.range_end, context.batch_ref];
    return <Session key={adapterIds.get(adapter) + ':' + JSON.stringify(identity)} {...props} adapter={adapter} />;
  }
  window.RunCandidateWorkspace = RunCandidateWorkspace;
})();
