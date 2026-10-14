(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSPlanContract, S = window.APSResourceSession;
  const { Button, ErrorBox, Issues } = window.ResourceControls, { Catalog } = window.PlanCatalogUI;
  const M = window.PlanGanttModel, F = window.WorkbenchFormat, { TaskDetail, ProjectionTables, Conflicts } = window.PlanDetailsUI;
  const adapterIds = new WeakMap(); let nextAdapter = 0;
  function adapterId(adapter) { if (!adapterIds.has(adapter)) adapterIds.set(adapter, ++nextAdapter); return adapterIds.get(adapter); }
  // The three plan-centre tabs share the heading and task detail; the body differs: analysis = projection tables,
  // gantt = the gantt board, delay = projection tables plus resource overlap. Selecting a batch or a related task on a
  // tab without the gantt only selects it for the task detail; the gantt locates it when that tab is shown.
  function WorkspaceSession({ adapter, view = 'analysis', planRef, initialContext = {}, disabled = false, renderTrial, navigation, onNavigate }) {
    const [selection, setSelection] = React.useState(() => planRef || initialContext.plan_ref ? { plan_ref: planRef || initialContext.plan_ref, display_name: '指定计划' } : null);
    const [scope, setScope] = React.useState(() => {
      const result = {};
      for (const key of ['range_start', 'range_end', 'snapshot_ref']) if (initialContext[key] !== undefined) result[key] = initialContext[key];
      return result;
    });
    const [range, setRange] = React.useState({ start: scope.range_start || '', end: scope.range_end || '' });
    const [rangeOpen, setRangeOpen] = React.useState(false), [rangeError, setRangeError] = React.useState(null), [paused, setPaused] = React.useState(false);
    const [query, setQuery] = React.useState(typeof initialContext.query === 'string' ? initialContext.query : ''), [selected, setSelected] = React.useState(null);
    const [projectionTab, setProjectionTab] = React.useState(initialContext.projection_tab || 'risk');
    const [projectionPage, setProjectionPage] = React.useState(initialContext.projection_page || 0);
    const [relatedRef, setRelatedRef] = React.useState(null);
    const [detailsOpen, setDetailsOpen] = React.useState(!!initialContext.selected_task_ref);
    const detailsToggle = React.useRef(null);
    const initialTaskRef = React.useRef(typeof initialContext.selected_task_ref === 'string' ? initialContext.selected_task_ref : null);
    const read = S.useQuery(async signal => {
      if (typeof adapter.workspace !== 'function') throw C.failure('暂时无法读取计划，请稍后重试。');
      P.workspaceScope(selection.plan_ref, scope);
      return adapter.workspace(selection.plan_ref, scope, signal);
    }, [adapter, selection && selection.plan_ref, scope], !!selection && !paused);
    const result = read.result, data = result && result.data;
    const chosen = selected && selected.result === result ? selected : null;
    React.useEffect(() => {
      if (!data || read.loading || read.error) return;
      const target = relatedRef || initialTaskRef.current;
      // The saved task belongs to this session's first successful read only.
      initialTaskRef.current = null;
      if (!target) return;
      const task = data.tasks.find(row => row.task_ref === target);
      if (task) setSelected({ task, before: false, result, ...(relatedRef || view === 'gantt' ? { locate: true } : {}) });
      else setRangeError(C.failure(relatedRef ? '此计划中未找到相关工序。'
        : '要恢复的工序不在当前范围内。'));
      if (relatedRef) setRelatedRef(null);
    }, [relatedRef, result, read.loading, read.error]);
    const remembered = { ...initialContext, ...(selection ? { plan_ref: selection.plan_ref } : {}), query, projection_tab: projectionTab, projection_page: projectionPage };
    for (const key of ['range_start', 'range_end', 'snapshot_ref', 'selected_task_ref']) delete remembered[key];
    Object.assign(remembered, scope, chosen ? { selected_task_ref: chosen.task.task_ref } : {});
    window.WorkbenchPageContext.useSnapshot(remembered, !!data && !read.loading && !read.error && !paused);
    function choose(plan) {
      initialTaskRef.current = null;
      setSelection(plan); setScope({}); setRange({ start: '', end: '' }); setRangeOpen(false); setRangeError(null); setPaused(false); setQuery(''); setSelected(null); setRelatedRef(null); setProjectionPage(0); read.reload();
    }
    function refresh() {
      const next = { ...scope }; delete next.snapshot_ref; setScope(next); setPaused(false); setSelected(null); setProjectionPage(0); read.reload();
    }
    function selectTask(task, before = false, locate = false) { initialTaskRef.current = null; setSelected(task ? { task, before, result, ...(locate ? { locate: true } : {}) } : null); }
    function openResource(resource) {
      const task = data.tasks.find(row => row[resource.kind + '_ref'] === resource.resource_ref);
      onNavigate('gantt', { ...remembered, query: '', resource_kind: resource.kind,
        ...(task ? { selected_task_ref: task.task_ref } : {}) });
    }
    function collapseDetails() { setDetailsOpen(false); detailsToggle.current.querySelector('button').focus(); }
    function toggleRange() {
      if (!rangeOpen && data) setRange({ start: scope.range_start || data.time_scope.range_start, end: scope.range_end || data.time_scope.range_end });
      setRangeOpen(!rangeOpen);
    }
    function changeScope(next) {
      const changed = scope.range_start !== next.range_start || scope.range_end !== next.range_end;
      initialTaskRef.current = null;
      setScope(next); setRange({ start: next.range_start || '', end: next.range_end || '' });
      if (changed) setProjectionPage(0);
      setRangeOpen(false); setRangeError(null); setPaused(false); setSelected(null); read.reload();
    }
    function selectRelated(ref) {
      initialTaskRef.current = null;
      const task = data.tasks.find(row => row.task_ref === ref);
      setQuery(''); setRangeError(null);
      if (task) setSelected({ task, before: false, result, locate: true });
      else { setRelatedRef(ref); changeScope({}); }
    }
    function applyRange(event) {
      event.preventDefault();
      if (!selection || disabled) return;
      try {
        const time = window.WorkbenchDatePickerModel.factoryTime;
        const start = time(range.start), end = time(range.end);
        const unchanged = data && start === time(data.time_scope.range_start) && end === time(data.time_scope.range_end);
        const next = unchanged ? scope : P.workspaceScope(selection.plan_ref, { range_start: start, range_end: end });
        changeScope(next);
      } catch (error) { setRangeError(error); }
    }
    const matches = React.useMemo(() => {
      if (!data) return [];
      const labels = M.names(data), needle = query.trim().toLocaleLowerCase();
      return data.tasks.filter(task => !needle || M.searchText(task, labels).includes(needle));
    }, [data, query]);
    const risks = data && data.projections.delivery_risks.items;
    const ready = !!data && !disabled;
    const includesPlanEnd = data && data.scope.range_start === null && data.plan_span.end_inclusive === true;
    const scopeCaption = !data ? '' : includesPlanEnd && data.plan_span.start === data.plan_span.end
      ? `计划时刻：${M.timeLabel(data.plan_span.start)}`
      : `计划时间范围：${M.timeLabel(data.time_scope.range_start)} 至 ${M.timeLabel(data.time_scope.range_end)}（${includesPlanEnd ? '包含末端零工时工序' : '不含结束时刻'}）`;
    window.WorkbenchCaption.useCaption(data && !read.loading && !read.error && !paused ? {
      reference: data.plan.plan_ref, label: '正式计划', name: data.plan.display_name,
      status: data.plan.is_current_official ? window.WorkbenchTerms.current_official : data.plan.kind === 'official' ? window.WorkbenchTerms.historical_official
        : data.plan.kind === 'candidate' ? window.WorkbenchTerms.candidate : window.WorkbenchTerms.trial_scenario,
      ...(data.plan.kind === 'official' && data.plan.version !== null ? { version: window.WorkbenchTerms.plan_version(data.plan.version) } : {}),
    } : null);
    return <div className="plana plan-workspace" data-plan-workspace>
      <section className="plan-scope wb-surface" aria-label="方案与范围">
      <Catalog adapter={adapter} selectedRef={selection && selection.plan_ref} onSelect={choose} autoSelect={!planRef && Object.keys(initialContext).length === 0} disabled={disabled}
        navigation={navigation}
        actions={<>
          <Button icon="calendar-days" aria-label={data ? '编辑计划时间范围：' + scopeCaption : '编辑计划时间范围'} title={scopeCaption} aria-expanded={rangeOpen} onClick={toggleRange} disabled={!selection}>
            {data ? F.compactRange(data.time_scope.range_start, data.time_scope.range_end) : '时间范围'}</Button>
          {typeof renderTrial === 'function' && renderTrial({ planRef: selection && selection.plan_ref, scope, query, disabled: !ready || read.loading })}
          <window.PlanExportUI key={result ? result.meta.snapshot_ref : 'unavailable'} adapter={adapter} result={result} query={query} matched={matches.length} disabled={!ready} />
          <Button icon="refresh-cw" className="btn plan-icon" aria-label="刷新所选计划" disabled={!selection || disabled} busy={read.loading} onClick={refresh} />
          {read.loading && <Button icon="x" aria-label="取消计划读取" onClick={() => setPaused(true)}>取消读取</Button>}
        </>} />
      {rangeOpen && <form className="plan-range wb-surface-body wb-surface-divider" onSubmit={applyRange}>
        <label className="field"><span>开始（包含）</span><input type="text" data-picker-type="factory-local" placeholder="2026-10-12 08:30" spellCheck={false} aria-label="读取开始时间" value={range.start} onChange={event => setRange({ ...range, start: event.target.value })} /></label>
        <label className="field"><span>结束（不含）</span><input type="text" data-picker-type="factory-local" placeholder="2026-10-14 18:00" spellCheck={false} aria-label="读取结束时间" value={range.end} onChange={event => setRange({ ...range, end: event.target.value })} /></label>
        <Button type="submit" icon="check" disabled={disabled || read.loading}>应用范围</Button><Button icon="chart-gantt" disabled={disabled || read.loading} onClick={() => changeScope({})}>完整计划</Button>
        <p className="plan-muted plan-range-help">可保留秒和小数秒。结束时刻不计入所选范围；完整计划可包含末端零工时工序。</p>
      </form>}
      {data && <details className="plan-record-details"><summary>计划资料</summary><div className="plan-record-body">
        <p>{scopeCaption}</p><p>本次刷新时间：{F.dateTime(result.meta.as_of, { seconds: true, fractions: true })}</p>
        <window.PlanGanttSource data={data} />
        <window.PlanDetailsUI.Facts items={[
          ...(data.provenance.accepted_at ? [[data.provenance.source_kind === 'trial_adoption' ? '试调创建时间' : '排产提交时间', F.dateTime(data.provenance.accepted_at, { seconds: true, fractions: true })]] : []),
          ...(data.provenance.finished_at ? [[data.provenance.source_kind === 'trial_adoption' ? '试调保存时间' : '排产结束时间', F.dateTime(data.provenance.finished_at, { seconds: true, fractions: true })]] : []),
          ...(data.provenance.adopted_at ? [['采用时间', F.dateTime(data.provenance.adopted_at, { seconds: true, fractions: true })]] : [])
        ]} />
        <window.WorkbenchReference entries={{ '计划编号': data.plan.plan_ref, '来源编号': data.provenance.source_ref, '排产记录编号': data.provenance.run_ref, '数据版本编号': result.meta.snapshot_ref }} />
      </div></details>}
      {(rangeError || read.error || result && result.warnings.length > 0 || !data || paused) && <div className="wb-surface-body plan-read-state">
      <ErrorBox error={rangeError} /><ErrorBox error={read.error} />
      {result && <Issues issues={result.warnings} />}
      {!data && !read.error && <window.WorkbenchControls.EmptyState kind={read.loading ? 'loading' : 'empty'} title={read.loading ? '正在读取所选计划、工序安排和分析结果…' : paused ? '计划读取已取消。' : '请在计划列表里选一个可查看的计划。'} />}
      {(read.error || paused) && <Button icon="refresh-cw" onClick={refresh}>刷新重试</Button>}</div>}
      {data && <div className="statline wb-metrics" style={{ '--wb-columns': 4 }}>
          {[[data.task_count, '已安排工序', 'primary'], [risks.length, '关联批次', 'primary'], [risks.filter(row => row.risk === 'overdue').length, '预计超期批次', 'warn'], [risks.filter(row => row.risk === 'unknown').length, '交付待确认批次', 'warn']].map(([value, label, tone]) =>
            <div className="stat wb-metric" key={label} data-tone={tone === 'warn' && value === 0 ? 'neutral' : tone}><span className="sl wb-metric-label">{label}</span><span className="sv wb-metric-value">{value}</span></div>)}
        </div>}</section>
      {data && <div className={'plan-main' + (view === 'gantt' ? ' wb-gantt-detail-layout' : '')} data-details-open={(view === 'gantt' ? detailsOpen : !!chosen) || undefined}><div className={view === 'gantt' ? 'wb-gantt-main-column' : undefined}>
          {view === 'gantt' && <window.PlanGantt key={'gantt:' + data.plan.plan_ref} data={data} asOf={result.meta.as_of} selected={chosen} onSelect={selectTask} query={query} onQuery={setQuery} disabled={disabled} initialMode={initialContext.resource_kind}
            toolbarActions={<span ref={detailsToggle}><Button icon={detailsOpen ? 'panel-right-close' : 'panel-right-open'} aria-expanded={detailsOpen} aria-controls="plan-gantt-detail" onClick={() => setDetailsOpen(!detailsOpen)}>{detailsOpen ? '收起详情' : '详情'}</Button></span>} />}
          {view !== 'gantt' && <ProjectionTables key={'risk:' + result.meta.snapshot_ref} data={data} tab={projectionTab} onTab={setProjectionTab} page={projectionPage} onPage={setProjectionPage} onResource={openResource} onBatch={batch => { setQuery(batch); const task = data.tasks.find(row => row.batch_id === batch); if (task) selectTask(task, false, true); }} />}
          {view === 'delay' && <Conflicts key={'conflicts:' + result.meta.snapshot_ref} data={data} />}
        </div>{(view === 'gantt' ? detailsOpen : !!chosen) && <TaskDetail data={data} selected={chosen} onSelect={selectTask} onRelated={selectRelated}
          onCollapse={view === 'gantt' ? collapseDetails : undefined}
          renderTrial={renderTrial} scope={scope} query={query} disabled={!ready || read.loading || !!read.error} />}</div>}
    </div>;
  }
  function PlanWorkspace(props) {
    const adapter = React.useMemo(() => window.APSPlanAPI.adapter(props.adapter || window.APSPlanAPI.create()), [props.adapter]);
    const context = props.initialContext || {};
    const navigation = [props.planRef || context.plan_ref, context.range_start, context.range_end, context.snapshot_ref];
    return <WorkspaceSession key={adapterId(adapter) + ':' + JSON.stringify(navigation)} {...props} adapter={adapter} />;
  }
  window.PlanWorkspace = PlanWorkspace;
})();
