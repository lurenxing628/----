(function () {
  'use strict';
  const A = window.RunCandidateAPI, N = window.RunCandidateAnalysisAPI, D = window.RunDecisionAPI, C = window.RunCandidateControls;
  function useRead(load, deps, enabled) {
    const read = window.APSResourceSession.useQuery(load, deps, enabled);
    return { ...read, busy: read.loading };
  }
  function returnContext(value) {
    const result = {};
    for (const key of ['run_ref', 'candidate_ref', 'plan_ref', 'batch_ref']) if (value && A.ref(value[key])) result[key] = value[key];
    for (const key of ['range_start', 'range_end']) if (value && A.time(value[key])) result[key] = value[key];
    return result;
  }
  // One 导出 button opens the format dialog, the same walk as the plan, trial and actual-gantt exports.
  function Export({ result, scope, query }) {
    const [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null), [done, setDone] = React.useState(''), [format, setFormat] = React.useState(null);
    const active = React.useRef(null);
    React.useEffect(() => () => { if (active.current) active.current.abort(); }, []);
    const d = result.data, allowed = d.capabilities.export === true && d.candidate.capabilities.export === true;
    function cancel() { if (active.current) active.current.abort(); active.current = null; setBusy(false); setFormat(null); }
    async function save() {
      if (!allowed || active.current || !format) return;
      const fmt = format, controller = new AbortController(); active.current = controller; setBusy(true); setError(null); setDone('');
      try {
        const file = A.download(await A.export(d.candidate.candidate_ref, scope, result.meta.snapshot_ref, fmt, controller.signal), result);
        if (controller.signal.aborted) return;
        window.APSWorkbenchTransport.saveBlob(file.filename, file.blob);
        setDone(window.WorkbenchTerms.download_started(file.filename) + '，共 ' + file.row_count + ' 条记录（安排 ' + d.task_count + '，未安排 ' + d.unplanned_operation_count + '）。');
        setFormat(null);
      } catch (e) { if (!controller.signal.aborted) setError(e); }
      finally { if (!controller.signal.aborted) { active.current = null; setBusy(false); } }
    }
    return <div><div className="rc-tools"><C.Button transfer="export" reason={allowed ? '' : '当前还不能导出这个候选方案。'} reasonDisplay="tooltip" busy={busy} onClick={() => { setFormat('csv'); setError(null); setDone(''); }}>导出</C.Button></div>
      {query.trim() && <small>搜索不改变导出范围</small>}{done && <small role="status">{done}</small>}
      {format && <window.ResourceControls.Modal title="导出候选方案" icon="download" onClose={cancel} footer={<>
        <C.Button onClick={cancel}>{busy ? '取消导出' : '取消'}</C.Button><C.Button transfer="export" className="btn primary" busy={busy} onClick={save}>下载 {format.toUpperCase()}</C.Button></>}>
        <div className="modal-b rc-export-summary"><div role="radiogroup" aria-label="候选导出格式" className="rc-export-format">{[['csv', 'CSV'], ['xlsx', 'XLSX']].map(([key, text]) =>
          <label key={key}><input type="radio" name="rc-export-format" value={key} checked={format === key} disabled={busy} onChange={() => setFormat(key)} />{text}</label>)}</div>
          <p><strong>{d.candidate.label || window.WorkbenchTerms.name_missing}</strong></p>
          <p>导出当前读取范围全部安排与未安排记录：安排 {d.task_count} 道，未安排 {d.unplanned_operation_count} 道。搜索不改变导出范围。</p>
          <C.ErrorBox error={error} /></div></window.ResourceControls.Modal>}
    </div>;
  }
  function Session({ view, initialContext, onNavigate, renderAdoption, renderTrial, navigation, runHistoryReturn }) {
    const M = window.RunCandidateModel, F = window.WorkbenchFormat, Analysis = window.RunCandidateAnalysis;
    const historyReturn = initialContext.return_decision_history_context || initialContext.return_decision_context && initialContext.return_decision_context.return_decision_history_context;
    const historyOrigin = historyReturn ? { return_decision_history_context: historyReturn } : {};
    const isReference = initialContext.reference_view === true;
    const invalid = initialContext.run_ref !== undefined && !A.ref(initialContext.run_ref) || initialContext.candidate_ref !== undefined && !A.ref(initialContext.candidate_ref) || isReference && !A.ref(initialContext.run_ref);
    const [runRef, setRunRef] = React.useState(initialContext.run_ref === undefined ? null : initialContext.run_ref), [candidateRef, setCandidateRef] = React.useState(initialContext.candidate_ref === undefined ? null : initialContext.candidate_ref);
    const [catalogQuery, setCatalogQuery] = React.useState({}), [scope, setScope] = React.useState(() => {
      const value = {}; for (const key of ['range_start', 'range_end', 'batch_ref', 'sort', 'order']) if (initialContext[key] !== undefined) value[key] = initialContext[key]; return value;
    });
    const [range, setRange] = React.useState({ start: scope.range_start === undefined ? '' : scope.range_start, end: scope.range_end === undefined ? '' : scope.range_end }), [rangeOpen, setRangeOpen] = React.useState(false);
    const [rangeError, setRangeError] = React.useState(null), [query, setQuery] = React.useState(typeof initialContext.query === 'string' ? initialContext.query : ''), [selected, setSelected] = React.useState(null);
    const [pendingRow, setPendingRow] = React.useState(A.ref(initialContext.selected_row_ref) ? initialContext.selected_row_ref : null);
    const [pendingOperation, setPendingOperation] = React.useState(A.ref(initialContext.operation_ref) ? initialContext.operation_ref : null);
    const [tab, setTab] = React.useState((view === 'delay' ? ['tasks', 'unplanned'] : ['tasks', 'unplanned', 'delivery', 'history']).includes(initialContext.candidate_tab) ? initialContext.candidate_tab : 'tasks'), [revision, refresh] = React.useReducer(v => v + 1, 0);
    const [analysisPaused, setAnalysisPaused] = React.useState(false), [historyPaused, setHistoryPaused] = React.useState(false);
    const [detailsOpen, setDetailsOpen] = React.useState(view === 'gantt' && (A.ref(initialContext.operation_ref) || A.ref(initialContext.selected_row_ref)));
    const detailsToggle = React.useRef(null);
    const directory = useRead(signal => A.catalog(runRef, catalogQuery, signal),
      [runRef, catalogQuery, revision], !!runRef && !invalid && !isReference);
    const read = useRead(async signal => { const v = isReference ? await D.referenceWorkspace(runRef, { ...scope, selected_candidate_ref: candidateRef, comparison_mode: 'admission_official', resource_view: initialContext.resource_view, plan_ref: initialContext.plan_ref }, signal) : await A.workspace(candidateRef, scope, signal);
      A.check(!initialContext.run_ref || v.data.candidate.run_ref === initialContext.run_ref, '候选方案不属于所选排产记录。'); return v; },
      [candidateRef, scope, revision, isReference, isReference ? runRef : null], !!candidateRef && !invalid);
    const result = read.result, data = result && result.data;
    React.useEffect(() => { if (data && !runRef) setRunRef(data.candidate.run_ref); }, [data, runRef]);
    const shown = data && data.capabilities.view === true && data.candidate.capabilities.view === true ? data : null;
    const analysisRead = useRead(signal => N.analysis(candidateRef, runRef, signal),
      [candidateRef, revision, analysisPaused], !!candidateRef && !invalid && !analysisPaused && !isReference);
    const historyRead = useRead(signal => N.adoptions(candidateRef, runRef, signal),
      [candidateRef, revision, result && result.meta.snapshot_ref], !!shown && tab === 'history' && !historyPaused && !isReference);
    const analysis = shown && !analysisPaused && analysisRead.result && analysisRead.result.data.run_ref === shown.candidate.run_ref ? analysisRead.result.data : null;
    const ownershipError = readState => shown && readState.result && readState.result.data.run_ref !== shown.candidate.run_ref
      ? new Error('读到的数据不属于所选候选方案的排产记录。') : readState.error;
    window.WorkbenchCaption.useCaption(shown && !read.busy && !read.error && shown.candidate.label ? {
      reference: isReference ? shown.plan_ref || shown.reference.baseline_ref : shown.candidate.candidate_ref, label: isReference ? '排产时的正式计划' : '当前候选', name: shown.candidate.label,
      status: isReference ? '已保存的正式安排 · 只读' : window.WorkbenchTerms.candidate + ' · ' + (window.WorkbenchTerms.candidate_statuses[shown.candidate.status] || '状态待确认'),
    } : null);
    const resourceFocus = A.ref(initialContext.resource_ref) ? { ref: initialContext.resource_ref, kind: initialContext.resource_kind === 'operator' ? 'operator' : 'machine' } : null;
    const prepared = React.useMemo(() => {
      if (!shown) return null;
      const facts = M.prepare(shown); facts.graph = window.GanttGraph.create(shown.gantt_graph); return facts;
    }, [shown]);
    const tasks = React.useMemo(() => prepared ? M.matching(prepared, query, resourceFocus) : [], [prepared, query, resourceFocus && resourceFocus.ref, resourceFocus && resourceFocus.kind]);
    const unplanned = React.useMemo(() => prepared ? M.matching(prepared, query, resourceFocus, true) : [], [prepared, query, resourceFocus && resourceFocus.ref, resourceFocus && resourceFocus.kind]);
    const filteredView = !!(scope.range_start || scope.batch_ref || resourceFocus || query.trim());
    const chosen = selected && selected.result === result ? selected.task : null;
    React.useEffect(() => {
      if (!shown || !pendingRow && !pendingOperation) return;
      const pendingFact = pendingRow && prepared.taskIndex.get(pendingRow);
      const exact = pendingFact && (!pendingOperation || pendingFact.task.operation_ref === pendingOperation) && pendingFact.task;
      const task = exact || pendingOperation && shown.tasks.find(row => row.operation_ref === pendingOperation);
      const unplannedTask = !task && pendingOperation && shown.unplanned_operations.find(row => row.operation_ref === pendingOperation);
      if (task || unplannedTask) { setSelected({ task: task || unplannedTask, result }); setPendingRow(null); setPendingOperation(null); setDetailsOpen(true); if (unplannedTask) setTab('unplanned'); }
      else if (!scope.range_start && !scope.batch_ref) { setRangeError(new Error('完整保存范围中缺少这道工序，请核对明细中的定位编号。')); setPendingRow(null); setPendingOperation(null); }
      else setRangeError(new Error('这道工序位于当前查看范围之外，请打开完整保存范围定位。'));
    }, [result, pendingRow, pendingOperation]);
    const remembered = { ...initialContext, ...(runRef ? { run_ref: runRef } : {}), ...(candidateRef ? { candidate_ref: candidateRef } : {}), query, candidate_tab: tab };
    for (const key of ['range_start', 'range_end', 'batch_ref', 'sort', 'order', 'snapshot_ref', 'selected_row_ref', 'operation_ref']) delete remembered[key];
    Object.assign(remembered, scope, chosen ? { operation_ref: chosen.operation_ref, ...(chosen.row_ref ? { selected_row_ref: chosen.row_ref } : {}) } : {});
    window.WorkbenchPageContext.useSnapshot(remembered, !!shown && !read.busy && !read.error && !invalid);
    function choose(candidate) { setCandidateRef(candidate.candidate_ref); setScope({}); setRange({ start: '', end: '' }); setRangeError(null); setQuery(''); setSelected(null); setPendingRow(null); setPendingOperation(null); setAnalysisPaused(false); setHistoryPaused(false); }
    function select(task) { setSelected({ task, result }); }
    function collapseDetails() { setDetailsOpen(false); const button = detailsToggle.current && detailsToggle.current.querySelector('button'); if (button) button.focus(); }
    function lastOperation(task) {
      setQuery('');
      const fact = prepared.taskIndex.get(task.row_ref), visible = fact && fact.task;
      if (visible) select(visible);
      else { setPendingRow(task.row_ref); setScope({}); setRange({ start: '', end: '' }); setSelected(null); }
    }
    function reload() { setCatalogQuery(q => { const value = { ...q }; delete value.snapshot_ref; return value; }); setSelected(null); setAnalysisPaused(false); setHistoryPaused(false); refresh(); }
    function rangeSubmit(e) {
      e.preventDefault();
      try {
        const time = window.WorkbenchDatePickerModel.factoryTime;
        const next = A.workspaceScope(candidateRef, { ...scope, range_start: time(range.start), range_end: time(range.end) });
        setScope(next); setRangeError(null); setSelected(null);
      } catch (error) { setRangeError(error); }
    }
    const historyError = tab === 'history' && !historyPaused ? ownershipError(historyRead) : null;
    return <div className="plana run-candidate-workspace" data-run-candidate-workspace>
      <h2 className="wb-page-title">{isReference ? '排产时的正式计划甘特' : view === 'delay' ? '候选交付风险' : view === 'gantt' ? '候选甘特' : '候选排产结果'}</h2>
      <div className="rc-heading scheduling-page-tools">{navigation}<div className="rc-tools">
        <div className="rc-nav">
          {(initialContext.return_decision_context || initialContext.reference_candidate_ref || initialContext.comparison_mode) && <C.Button icon="chevron-left" className="btn link" onClick={() => onNavigate('analysis', initialContext.return_decision_context || { run_ref: runRef, candidate_ref: candidateRef, reference_candidate_ref: initialContext.reference_candidate_ref, comparison_mode: initialContext.comparison_mode || 'candidates', ...scope })}>返回方案对比</C.Button>}
          <C.Button icon="chevron-left" className="btn link" onClick={() => onNavigate(runHistoryReturn.view, runHistoryReturn.context)}>返回排产记录</C.Button>
          {initialContext.return_plan_context && A.ref(initialContext.return_plan_context.plan_ref) && <C.Button icon="chevron-left" className="btn link" onClick={() => onNavigate('analysis', returnContext(initialContext.return_plan_context))}>返回正式计划</C.Button>}</div>
        <div className="rc-actions">
          {!isReference && renderAdoption(candidateRef, { candidateDisplay: shown && shown.candidate.candidate_ref === candidateRef ? { candidate_ref: candidateRef, label: shown.candidate.label || '候选名称未填写' } : undefined, candidateCatalog: directory.result ? directory.result.data.candidates : [] })}
          {!isReference && renderTrial({ candidateRef, scope, query, disabled: !shown || read.busy || invalid })}
          <C.Button icon="refresh-cw" aria-label="刷新候选方案" disabled={invalid || !runRef && !candidateRef} busy={read.busy || directory.busy} onClick={reload} /></div></div></div>
      {invalid && <C.ErrorBox error={new Error('记录编号无效，请从排产记录重新打开。')} />}
      {!runRef && !candidateRef && <div className="rc-empty" role="status">请从排产记录里打开候选方案。</div>}
      {runRef && !isReference && <><C.ErrorBox error={directory.error} /><C.Catalog result={directory.result} selectedRef={candidateRef} busy={directory.busy} query={catalogQuery}
        onQuery={(change, paging) => setCatalogQuery(q => ({ ...q, ...change, page: paging ? change.page : 1, snapshot_ref: paging ? directory.result.meta.snapshot_ref : undefined }))} onSelect={choose} /></>}
      <C.ErrorBox error={read.error} />{(read.busy || directory.busy) && <p className="rc-muted" role="status">{isReference ? '正在读取排产时的正式计划。' : '正在读取这个候选方案。'}</p>}
      {read.error && <div className="rc-empty">候选方案读取失败，可通过“读取范围”调整日期后重新读取，或点击刷新重试。</div>}
      {(analysisRead.busy || historyRead.busy) && <div className="rc-tools"><span role="status">正在核对这个候选方案的完整依据。</span><C.Button icon="x" aria-label="取消候选比较读取" onClick={() => { if (analysisRead.busy) setAnalysisPaused(true); if (historyRead.busy) setHistoryPaused(true); }}>取消读取</C.Button></div>}
      {(analysisPaused || tab === 'history' && historyPaused) && <div className="rc-tools"><span role="status">候选比较读取已取消。</span><C.Button icon="refresh-cw" onClick={reload}>刷新候选比较</C.Button></div>}
      {runRef && !candidateRef && <div className="rc-empty">尚未选择这次排产里的候选方案。</div>}
      {data && !shown && <div className="rc-notice">当前不能查看这个候选方案。<C.Reasons rows={data.blocked_reasons} /></div>}
      {initialContext.drill_range_adjusted && <p className="rc-muted" role="status">定位时间窗已覆盖目标安排；返回方案对比后恢复原查看窗。</p>}
      {resourceFocus && <p className="rc-muted" role="status">当前按指定{M.kindLabels[resourceFocus.kind]}查看安排。<window.WorkbenchReference value={resourceFocus.ref} /></p>}
      {shown && <>{isReference ? <details className="rc-reasons"><summary>来源与记录编号</summary><div>提交试排时保存的正式计划：{shown.candidate.label}</div><div>本次刷新：{M.timeLabel(result.meta.as_of)}</div><window.WorkbenchReference entries={{ '正式计划编号': shown.plan_ref || shown.reference.baseline_ref, '来源候选': shown.reference.source_candidate_ref }} /></details> : <C.Generation key={shown.candidate.candidate_ref} data={shown} analysis={analysis} meta={result.meta} />}<C.Reasons rows={result.warnings} />
        <C.ErrorBox error={analysisPaused ? null : ownershipError(analysisRead)} /></>}
      {A.ref(candidateRef) && !invalid && <>
        <div className="rc-heading"><span><span title={scope.range_start ? M.timeLabel(scope.range_start) + ' 至 ' + M.timeLabel(scope.range_end) + '（不含结束时刻）' : '全部保存时间'}>查看范围：{scope.range_start ? F.compactRange(scope.range_start, scope.range_end) : '全部时间'}{scope.batch_ref && ' · 指定批次'}</span>
          {shown && ' · 当前显示 ' + tasks.length + ' 道安排'}</span>
        <div className="rc-tools"><C.Button icon="calendar-days" aria-expanded={rangeOpen} onClick={() => setRangeOpen(!rangeOpen)}>读取范围</C.Button>
          {shown && !isReference && <Export key={result.meta.snapshot_ref} result={result} scope={scope} query={query} />}</div></div>
        {rangeOpen && <form className="rc-range" onSubmit={rangeSubmit}><label>开始（包含）<input type="text" data-picker-type="factory-local" placeholder="2026-10-12 08:30" spellCheck={false} aria-label="候选读取开始" value={range.start} onChange={e => setRange({ ...range, start: e.target.value })} /></label>
          <label>结束（不含）<input type="text" data-picker-type="factory-local" placeholder="2026-10-14 18:00" spellCheck={false} aria-label="候选读取结束" value={range.end} onChange={e => setRange({ ...range, end: e.target.value })} /></label>
          <C.Button icon="check" type="submit">应用范围</C.Button><C.Button icon="chart-gantt" onClick={() => { setScope({}); setRange({ start: '', end: '' }); setRangeError(null); }}>完整候选</C.Button></form>}
        <C.ErrorBox error={rangeError} />{rangeError && (pendingRow || pendingOperation) && <C.Button onClick={() => { setScope({}); setRange({ start: '', end: '' }); setRangeError(null); }}>完整保存范围定位</C.Button>}
      </>}
      {shown && <><details className="rc-reasons"><summary>范围与导出说明</summary><div>全方案共 {shown.candidate_task_count} 道安排；当前读取范围 {shown.task_count} 道安排。</div>
          <div>未安排工序：{shown.unplanned_operation_count} 道。这些工序没有时间区间，按批次范围读取，保留在未安排明细。</div>
          <div>时间边界：{scope.range_start ? M.timeLabel(scope.range_start) + ' 至 ' + M.timeLabel(scope.range_end) + '（不含结束时刻）' : '全部保存时间'}。时间筛选保留相交安排的完整起止。零工时工序按发生时刻筛选，结束边界不包含。</div>
          {scope.batch_ref && <window.WorkbenchReference entries={{ '筛选批次编号': scope.batch_ref }} />}<div>导出当前读取范围的全部安排与未安排记录。搜索和指定资源只筛选页面显示。</div></details>
        {view === 'delay' && <C.Delivery data={shown.delivery_risks} onLast={lastOperation} />}
        <div className={'rc-main' + (view === 'gantt' ? ' wb-gantt-detail-layout' : '')} data-details-open={view === 'gantt' && detailsOpen && !['delivery', 'history'].includes(tab) || undefined}
          data-single-column={['delivery', 'history'].includes(tab) || view === 'gantt' && !detailsOpen ? 'true' : undefined}><div className={view === 'gantt' ? 'wb-gantt-main-column' : undefined}>
          <window.RunCandidateGantt key={shown.candidate.candidate_ref} data={shown} prepared={prepared} comparison={analysis} query={query} onQuery={setQuery} selected={chosen} onSelect={select} resourceFocus={resourceFocus}
            toolbarActions={view === 'gantt' && !['delivery', 'history'].includes(tab) && <span ref={detailsToggle}><C.Button icon={detailsOpen ? 'panel-right-close' : 'panel-right-open'} aria-expanded={detailsOpen} aria-controls="candidate-gantt-detail" onClick={() => setDetailsOpen(!detailsOpen)}>{detailsOpen ? '收起详情' : '详情'}</C.Button></span>} />
          <section aria-label="候选明细"><div className="rc-heading"><div role="tablist" className="rc-tabs" aria-label="候选明细类别" onKeyDown={event => {
            if (event.altKey || event.ctrlKey || event.metaKey) return;
            const tabs = Array.from(event.currentTarget.querySelectorAll('[role="tab"]')), index = tabs.indexOf(document.activeElement);
            const target = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : -1;
            if (target >= 0) { event.preventDefault(); tabs[target].focus(); tabs[target].click(); }
          }}>
            {['tasks', 'unplanned', ...(view === 'delay' || isReference ? [] : ['delivery', 'history'])].map(t => <C.Button key={t} role="tab" id={'rc-detail-tab-' + t} aria-controls="rc-detail-panel" tabIndex={tab === t ? 0 : -1} icon={t === 'tasks' ? 'chart-gantt' : t === 'history' ? 'history' : 'circle-alert'} aria-selected={tab === t} onClick={() => setTab(t)}>{t === 'tasks' ? '任务安排' : t === 'delivery' ? '交付风险' : t === 'history' ? '采用记录' : '未安排明细'}</C.Button>)}</div></div>
            <div role="tabpanel" id="rc-detail-panel" aria-labelledby={'rc-detail-tab-' + tab}>{tab === 'history' ? <><C.ErrorBox error={historyError} />{!historyPaused && historyRead.result && !historyError && <Analysis.History data={historyRead.result.data}
              onPlan={plan => onNavigate('analysis', { ...historyOrigin, plan_ref: plan.plan_ref })} />}</> :
              tab === 'delivery' ? analysis && <Analysis.Batches key={analysis.candidate_ref} data={analysis} onLast={task => { lastOperation(task); setTab('tasks'); }}
                onBatch={row => onNavigate('gantt', { ...historyOrigin, run_ref: analysis.run_ref, candidate_ref: analysis.candidate_ref, batch_ref: row.batch_ref, candidate_tab: 'tasks' })} /> : tab === 'unplanned' && shown.unplanned_operations === null ? <div className="rc-notice">未记录排产时的未排工序明细。</div> :
              <window.RunCandidateGantt.TaskList key={tab + ':' + query + ':' + result.meta.snapshot_ref} tasks={tab === 'tasks' ? tasks : unplanned} selected={chosen}
                onDetails={task => { setSelected({ task, result }); setDetailsOpen(true); }} planned={tab === 'tasks'} />}</div></section>
        </div>{!['delivery', 'history'].includes(tab) && (view !== 'gantt' || detailsOpen) && <C.Detail task={chosen} data={shown} prepared={prepared} onRelated={taskRef => lastOperation({ row_ref: taskRef })}
          onCollapse={view === 'gantt' ? collapseDetails : undefined} onClose={() => setSelected(null)} />}</div>
        {analysis && (filteredView ? <details className="rc-reasons"><summary>全方案交付与变化</summary><Analysis.Overview data={analysis} /></details> : <Analysis.Overview data={analysis} />)}</>}
    </div>;
  }
  function RunCandidateWorkspace(props) {
    const context = props.initialContext, identity = [context.run_ref, context.candidate_ref, context.range_start, context.range_end, context.batch_ref, context.operation_ref, context.selected_row_ref, context.reference_view, context.plan_ref, context.comparison_mode, context.resource_view, context.resource_kind, context.resource_ref];
    return props.view === 'analysis' ? <window.RunDecisionComparison.Workspace key={JSON.stringify(identity)} {...props} />
      : <Session key={JSON.stringify(identity)} {...props} />;
  }
  window.RunCandidateWorkspace = RunCandidateWorkspace;
})();
