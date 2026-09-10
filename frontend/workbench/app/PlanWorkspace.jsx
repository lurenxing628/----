(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSPlanContract, S = window.APSResourceSession;
  const { Button, ErrorBox, Issues } = window.ResourceControls, { Catalog, Identity } = window.PlanCatalogUI;
  const M = window.PlanGanttModel, { TaskDetail, ProjectionTables, Conflicts } = window.PlanDetailsUI;
  const adapterIds = new WeakMap(); let nextAdapter = 0;
  function adapterId(adapter) { if (!adapterIds.has(adapter)) adapterIds.set(adapter, ++nextAdapter); return adapterIds.get(adapter); }
  function WorkspaceSession({ adapter, view, onNavigate, planRef, initialContext = {}, disabled = false, renderTrial }) {
    const [selection, setSelection] = React.useState(() => planRef || initialContext.plan_ref ? { plan_ref: planRef || initialContext.plan_ref, display_name: '指定计划' } : null);
    const [scope, setScope] = React.useState(() => {
      const result = {};
      for (const key of ['range_start', 'range_end', 'snapshot_ref']) if (initialContext[key] !== undefined) result[key] = initialContext[key];
      return result;
    });
    const [range, setRange] = React.useState({ start: scope.range_start || '', end: scope.range_end || '' });
    const [rangeOpen, setRangeOpen] = React.useState(false), [rangeError, setRangeError] = React.useState(null), [paused, setPaused] = React.useState(false);
    const [query, setQuery] = React.useState(typeof initialContext.query === 'string' ? initialContext.query : ''), [selected, setSelected] = React.useState(null);
    const [relatedRef, setRelatedRef] = React.useState(null);
    const read = S.useQuery(async signal => {
      if (typeof adapter.workspace !== 'function') throw C.failure('暂时无法读取计划，请稍后重试。');
      P.workspaceScope(selection.plan_ref, scope);
      return P.workspace(await adapter.workspace(selection.plan_ref, scope, signal), selection.plan_ref, scope);
    }, [adapter, selection && selection.plan_ref, scope], !!selection && !paused);
    const result = read.result, data = result && result.data;
    const chosen = selected && selected.result === result ? selected : null;
    React.useEffect(() => {
      if (!relatedRef || !data || read.loading || read.error) return;
      const task = data.tasks.find(row => row.task_ref === relatedRef);
      if (task) setSelected({ task, before: false, result, locate: true });
      else setRangeError(C.failure('同一完整计划中未找到该关系任务，未定位到替代任务。'));
      setRelatedRef(null);
    }, [relatedRef, result, read.loading, read.error]);
    React.useEffect(() => {
      if (!data || selected || typeof initialContext.selected_task_ref !== 'string') return;
      const task = data.tasks.find(row => row.task_ref === initialContext.selected_task_ref);
      if (task) setSelected({ task, before: false, result });
    }, [result, selected]);
    const remembered = { ...initialContext, ...(selection ? { plan_ref: selection.plan_ref } : {}), query };
    for (const key of ['range_start', 'range_end', 'snapshot_ref', 'selected_task_ref']) delete remembered[key];
    Object.assign(remembered, scope, chosen ? { selected_task_ref: chosen.task.task_ref } : {});
    window.WorkbenchPageContext.useSnapshot(remembered, !!data && !read.loading && !read.error && !paused);
    function choose(plan) {
      setSelection(plan); setScope({}); setRange({ start: '', end: '' }); setRangeError(null); setPaused(false); setQuery(''); setSelected(null); setRelatedRef(null); read.reload();
    }
    function refresh() {
      const next = { ...scope }; delete next.snapshot_ref; setScope(next); setPaused(false); setSelected(null); read.reload();
    }
    function selectTask(task, before = false) { setSelected({ task, before, result }); }
    function selectRelated(ref) {
      const task = data.tasks.find(row => row.task_ref === ref);
      setQuery(''); setRangeError(null);
      if (task) setSelected({ task, before: false, result, locate: true });
      else { setRelatedRef(ref); setSelected(null); setScope({}); setRange({ start: '', end: '' }); setPaused(false); read.reload(); }
    }
    function applyRange(event) {
      event.preventDefault();
      if (!selection || disabled) return;
      try {
        const seconds = value => value && value.length === 16 ? value + ':00' : value;
        const next = P.workspaceScope(selection.plan_ref, { range_start: seconds(range.start), range_end: seconds(range.end) });
        setScope(next); setRangeError(null); setPaused(false); setSelected(null); read.reload();
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
      ? `计划时间点：${M.timeLabel(data.plan_span.start)}`
      : `计划时间范围：${M.timeLabel(data.time_scope.range_start)} → ${M.timeLabel(data.time_scope.range_end)}（${includesPlanEnd ? '包含末端计划点' : '不含结束时刻'}）`;
    window.WorkbenchCaption.useCaption(data && !read.loading && !read.error && !paused ? {
      reference: data.plan.plan_ref, label: '当前方案', name: data.plan.display_name,
      status: data.plan.is_current_official ? '当前正式' : data.plan.kind === 'official' ? '历史正式' : data.plan.kind === 'candidate' ? '候选预览' : '场景预览',
      ...(data.plan.kind === 'official' && data.plan.version !== null ? { version: '正式 v' + data.plan.version } : {}),
      range: scopeCaption,
    } : null);
    return <div className="plana plan-workspace" data-plan-workspace>
      <window.PlanLayout />
      <div className="plan-heading"><div><h2>{view === 'gantt' ? '设备 / 人员 / 批次甘特' : view === 'delay' ? '交付风险' : '选择排产方案'}</h2>
        <div className="plan-muted">{data ? data.plan.display_name : selection ? selection.display_name : '尚未选择计划'}{data && <> · <Identity plan={data.plan} /></>}</div></div>
        <div className="plan-actions">
          {onNavigate && <Button icon="arrow-right" disabled={!selection} onClick={() => onNavigate(view === 'gantt' ? 'analysis' : 'gantt', { plan_ref: selection.plan_ref, ...scope, ...(result ? { snapshot_ref: result.meta.snapshot_ref } : {}) })}>{view === 'gantt' ? '选择方案' : '查看甘特'}</Button>}
          {onNavigate && <Button icon="circle-alert" disabled={!selection} onClick={() => onNavigate(view === 'delay' ? 'analysis' : 'delay', remembered)}>{view === 'delay' ? '返回方案' : '交付风险'}</Button>}
          {typeof renderTrial === 'function' && renderTrial({ planRef: selection && selection.plan_ref, scope, query, disabled: !ready || read.loading })}
          <window.PlanExportUI key={result ? result.meta.snapshot_ref : 'unavailable'} adapter={adapter} result={result} query={query} matched={matches.length} disabled={!ready} />
        </div>
      </div>
      <Catalog adapter={adapter} selectedRef={selection && selection.plan_ref} onSelect={choose} disabled={disabled} />
      <div className="plan-heading"><div><h3>计划工作区</h3>{data && <div className="plan-muted">读取于 {M.timeLabel(result.meta.as_of)} · 工厂本地时间</div>}</div>
        <div className="plan-actions"><Button icon="calendar-days" aria-expanded={rangeOpen} onClick={() => setRangeOpen(!rangeOpen)} disabled={!selection}>读取范围</Button>
          <Button icon="refresh-cw" className="btn plan-icon" aria-label="刷新所选计划" disabled={!selection || disabled} busy={read.loading} onClick={refresh} />
          {read.loading && <Button icon="x" aria-label="取消计划读取" onClick={() => setPaused(true)}>取消读取</Button>}</div>
      </div>
      {rangeOpen && <form className="plan-range" onSubmit={applyRange}>
        <label className="field"><span>开始（包含）</span><input type="datetime-local" step="1" aria-label="读取开始时间" value={range.start} onChange={event => setRange({ ...range, start: event.target.value })} /></label>
        <label className="field"><span>结束（不含）</span><input type="datetime-local" step="1" aria-label="读取结束时间" value={range.end} onChange={event => setRange({ ...range, end: event.target.value })} /></label>
        <Button type="submit" icon="check" disabled={disabled || read.loading}>应用范围</Button><Button icon="chart-gantt" disabled={disabled || read.loading} onClick={() => { setScope({}); setRange({ start: '', end: '' }); setRangeError(null); setPaused(false); read.reload(); }}>完整计划</Button>
      </form>}
      <ErrorBox error={rangeError} /><ErrorBox error={read.error} />
      {result && <Issues issues={result.warnings} />}
      {!data && <div className="plan-empty" role="status">{read.loading ? '正在读取所选计划、工序安排和分析结果…' : paused ? '计划读取已取消，未显示上次读取的内容。' : read.error ? '所选计划未读取成功，没有替换成其他计划。' : '从目录中选择一个可查看的计划。'}</div>}
      {(read.error || paused) && <Button icon="refresh-cw" onClick={refresh}>重新读取所选计划</Button>}
      {data && <>
        <div className="statline wb-metrics" style={{ '--wb-columns': 4, marginBottom: 12 }}>
          {[[data.task_count, '范围内安排', 'primary'], [risks.length, '关联批次', 'primary'], [risks.filter(row => row.risk === 'overdue').length, '已核实预计超期', 'warn'], [risks.filter(row => row.risk === 'unknown').length, '交付风险待核实', 'warn']].map(([value, label, tone]) =>
            <div className="stat wb-metric" key={label} data-tone={tone === 'warn' && value === 0 ? 'neutral' : tone}><span className="sl wb-metric-label">{label}</span><span className="sv wb-metric-value">{value}</span></div>)}
        </div>
        <div className="plan-note" style={{ marginBottom: 10 }}>{scopeCaption}
          {data.scope.range_start !== null && <span> · 只列出与此时间段有重叠的工序安排，每道安排的起止时间完整保留，不代表整份计划</span>}{query.trim() && <span> · 搜索找到 {matches.length} / {data.task_count} 道工序安排，只影响甘特图显示；分析表和导出仍包含此时间范围内的全部 {data.task_count} 道安排</span>}</div>
        <div className="plan-main"><div>
          {view === 'delay' && <ProjectionTables key={'risk-first:' + result.meta.snapshot_ref} data={data} onResource={setQuery} onBatch={batch => { setQuery(batch); const task = data.tasks.find(row => row.batch_id === batch); if (task) selectTask(task); }} />}
          {view === 'delay' && <Conflicts key={'conflicts:' + result.meta.snapshot_ref} data={data} />}
          <window.PlanGantt key={'gantt:' + result.meta.snapshot_ref} data={data} selected={chosen} onSelect={selectTask} query={query} onQuery={setQuery} disabled={disabled} />
          {view !== 'delay' && <ProjectionTables key={'risk-last:' + result.meta.snapshot_ref} data={data} onResource={setQuery} onBatch={batch => { setQuery(batch); const task = data.tasks.find(row => row.batch_id === batch); if (task) selectTask(task); }} />}
        </div><TaskDetail data={data} selected={chosen} onSelect={selectTask} onRelated={selectRelated}
          renderTrial={renderTrial} scope={scope} query={query} disabled={!ready || read.loading || !!read.error} /></div>
      </>}
    </div>;
  }
  function PlanWorkspace(props) {
    const adapter = React.useMemo(() => props.adapter || (window.APSPlanAPI ? window.APSPlanAPI.create() : {}), [props.adapter]);
    const context = props.initialContext || {};
    const navigation = [props.planRef || context.plan_ref, context.range_start, context.range_end, context.snapshot_ref];
    return <WorkspaceSession key={adapterId(adapter) + ':' + JSON.stringify(navigation)} {...props} adapter={adapter} />;
  }
  window.PlanWorkspace = PlanWorkspace;
})();
