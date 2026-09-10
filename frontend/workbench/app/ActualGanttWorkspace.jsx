(function () {
  'use strict';
  const M = window.ActualGanttModel, C = window.ActualGanttContract;
  const { Button, ErrorBox, Modal } = window.ResourceControls;
  const { Styles, Toolbar, Range, describe } = window.ActualGanttControls;
  const sessions = new Map();
  function initial(context) {
    const input = { ...(context.scope || {}) }, scope = {};
    for (const key of ['source', 'range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref', 'batch_ids'])
      if (context[key] !== undefined && input[key] === undefined) input[key] = context[key];
    const allowed = ['plan_ref', 'source', 'range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref', 'batch_ids', 'query', 'focus', 'as_of', 'snapshot_ref', 'kind', 'baseline_ref'];
    let issue = Object.keys(input).some(key => !allowed.includes(key)) ? '来源范围含未知条件，未忽略筛选。' : null;
    if (input.baseline_ref && input.baseline_ref !== (context.plan_ref || input.plan_ref)) issue = '现场实际甘特以所选计划为基线，未替换为另一个基线版本。';
    if (input.query !== undefined && (typeof input.query !== 'string' || input.query.length > 200)) issue = '来源搜索条件无效。';
    if (context.return_to && !['gantt', 'field', 'analysis', 'reports', 'dashboard'].includes(context.return_to.view)) issue = '返回来源不是已登记的工作台页面。';
    for (const key of ['plan_ref', 'source', 'range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref', 'batch_ids'])
      if (input[key] !== undefined && input[key] !== null && input[key] !== '') scope[key] = input[key];
    if (context.plan_ref) scope.plan_ref = context.plan_ref;
    return { scope, issue, query: typeof input.query === 'string' ? input.query : typeof context.query === 'string' ? context.query : '', selected: context.task_ref || context.entity_ref || null };
  }
  function Content({ onNavigate, initialContext = {}, adapter: supplied }) {
    const seed = React.useMemo(() => initial(initialContext), []), key = JSON.stringify(initialContext), saved = sessions.get(key);
    const api = React.useMemo(() => supplied || window.ActualGanttAPI.create(), [supplied]);
    const [scope, setScope] = React.useState(saved ? saved.scope : seed.scope), [refresh, setRefresh] = React.useState(0);
    const [result, setResult] = React.useState(null), [loading, setLoading] = React.useState(false), [error, setError] = React.useState(null);
    const [view, setView] = React.useState(saved ? saved.view : { mode: seed.scope.resource_type || 'machine', query: seed.query, selected: seed.selected,
      report: null, late: 'all', collapsed: {}, onlySelected: false, details: false, chain: false });
    const [zoom, setZoom] = React.useState(saved ? saved.zoom : 1), [position, setPosition] = React.useState({ left: 0, top: 0, width: 1000, height: 480 });
    const [hover, setHover] = React.useState(null), [exporting, setExporting] = React.useState(false), [exportBusy, setExportBusy] = React.useState(false);
    const [exportError, setExportError] = React.useState(null), [restore, setRestore] = React.useState(saved ? saved.position : null);
    const board = React.useRef(null), frame = React.useRef(null), pending = React.useRef(null), downloadController = React.useRef(null);
    const patch = change => setView(previous => ({ ...previous, ...change }));
    React.useEffect(() => {
      const controller = new AbortController(); let active = true;
      setLoading(true); setResult(null); setError(null);
      (async () => {
        try {
          if (seed.issue) throw window.APSResourceContract.failure(seed.issue);
          let input = scope;
          if (input.source && input.source !== 'production') throw window.APSResourceContract.failure('现场实际甘特只读取生产数据，未将演示范围替换为生产范围。');
          if (!input.plan_ref) {
            if (Object.keys(input).some(k => k !== 'source')) throw window.APSResourceContract.failure('来源范围缺少明确计划，未自动扩大范围。');
            const catalog = await window.APSPlanAPI.create().catalog({ collection: 'history', size: 20 }, controller.signal);
            const current = catalog.data.plans.filter(p => p.is_current_official && p.capabilities.view);
            if (current.length !== 1) throw window.APSResourceContract.failure('没有唯一可读取的当前正式计划，请先选择计划。');
            if (active) setScope({ plan_ref: current[0].plan_ref });
            return;
          }
          input = C.scope(input);
          const response = C.workspace(await api.load(input, controller.signal), input);
          if (active) setResult(response);
        } catch (failure) { if (active) setError(failure); }
        finally { if (active) setLoading(false); }
      })();
      return () => { active = false; controller.abort(); };
    }, [api, scope, refresh]);
    React.useEffect(() => () => { if (downloadController.current) downloadController.current.abort(); cancelAnimationFrame(frame.current); }, []);
    const data = result && result.data;
    const model = React.useMemo(() => data ? M.layout(data, view, result.meta.as_of) : null, [data, view, result]);
    const measure = () => { const node = board.current; if (node) setPosition({ left: node.scrollLeft, top: node.scrollTop, width: node.clientWidth, height: node.clientHeight }); };
    React.useLayoutEffect(() => {
      if (!board.current) return;
      measure(); const resize = new ResizeObserver(measure); resize.observe(board.current);
      return () => resize.disconnect();
    }, [data]);
    const labelWidth = position.width < 550 ? 160 : 292, viewport = Math.max(80, position.width - labelWidth), width = viewport * zoom;
    React.useLayoutEffect(() => {
      const node = board.current; if (!node || !model) return;
      if (restore) { node.scrollLeft = restore.left; node.scrollTop = restore.top; setRestore(null); }
      if (pending.current) {
        if (pending.current.task) {
          const reportRow = model.reportLocations.get(view.report);
          const row = reportRow && reportRow.item.task.task_ref === pending.current.task ? reportRow : model.locations.get(pending.current.task);
          if (row) { const report = row.item.execution && row.item.execution.reports.find(r => r.report_ref === view.report), at = report && report.actual_start || row.item.task.start;
            node.scrollTop = Math.max(0, row.top - node.clientHeight / 3); node.scrollLeft = (M.instant(at) - model.start) / (model.end - model.start) * width - viewport / 3; }
        } else node.scrollLeft = pending.current.center * width - viewport / 2;
        pending.current = null;
      }
      measure();
    }, [width, model, restore]);
    React.useEffect(() => { sessions.set(key, { scope, view, zoom, position }); }, [key, scope, view, zoom, position]);
    React.useEffect(() => setHover(null), [view, position.top, position.left]);
    function zoomTo(next) { pending.current = { center: (position.left + viewport / 2) / width }; setZoom(Math.max(1, Math.min(1024, next))); }
    function pan(left) { if (board.current) { board.current.scrollLeft = Math.max(0, left); measure(); } }
    function locate(taskRef = view.selected) {
      if (!model || !model.items.some(item => item.task.task_ref === taskRef)) return;
      const collapsed = { ...view.collapsed };
      model.groups.filter(g => g.members.has(taskRef)).forEach(g => delete collapsed[g.id]);
      pending.current = { task: taskRef }; patch({ selected: taskRef, collapsed });
    }
    function apply(next) { try { C.scope(next); setScope(next); patch({ collapsed: {} }); setError(null); } catch (failure) { setError(failure); } }
    function select(item, report) { patch({ selected: item.task.task_ref, report: report ? report.report_ref : null }); }
    const selected = data && data.items.find(item => item.task.task_ref === view.selected);
    const stats = data && M.metrics(data);
    const report = selected && selected.execution && selected.execution.reports.find(r => r.report_ref === view.report);
    const viewScope = () => ({ ...scope, snapshot_ref: result.meta.snapshot_ref, format: 'csv', local_query: view.query.trim(), late_filter: view.late,
      ...(view.onlySelected ? { selected_task_ref: view.selected } : {}) });
    async function download() {
      const controller = new AbortController(); downloadController.current = controller; setExportBusy(true); setExportError(null);
      try {
        const output = await api.export(C.scope(viewScope(), true), controller.signal);
        if (controller.signal.aborted) return;
        if (!output || !output.blob || !output.blob.size || output.contentType.split(';')[0] !== 'text/csv' || !/^attachment;/i.test(output.disposition)) throw window.APSResourceContract.failure('下载不是有效的 CSV 附件。');
        const url = URL.createObjectURL(output.blob), a = document.createElement('a');
        try { a.href = url; a.download = '现场实际甘特-' + result.meta.as_of.replace(/:/g, '') + '.csv'; document.body.appendChild(a); a.click(); }
        finally { a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
        setExporting(false);
      } catch (failure) { if (!controller.signal.aborted) setExportError(failure); }
      finally { if (downloadController.current === controller) { downloadController.current = null; setExportBusy(false); } }
    }
    function navigate(viewName) {
      const returnContext = { plan_ref: scope.plan_ref, task_ref: view.selected, scope: { ...scope, query: view.query } };
      sessions.set(JSON.stringify(returnContext), { scope, view, zoom, position });
      if (typeof onNavigate === 'function') onNavigate(viewName, { plan_ref: scope.plan_ref, task_ref: view.selected,
        operation_ref: selected ? selected.task.operation_ref : undefined,
        scope: { ...scope, query: view.query }, return_to: { view: 'fieldgantt', context: returnContext } });
    }
    return <div className="plana fg-page fg-live" data-actual-gantt><Styles />
      <div className="fg-heading"><div><h2>现场实际甘特</h2><span className="fg-muted">{data ? data.plan.display_name + ' · 数据截至 ' + M.time(result.meta.as_of) : loading ? '正在读取计划与执行事实' : '计划与执行事实'}</span></div>
        <div className="wb-actions"><Button icon="refresh-cw" aria-label="刷新实际甘特" busy={loading} onClick={() => { const next = { ...scope }; delete next.snapshot_ref; setScope(next); setRefresh(n => n + 1); }} />
          {onNavigate && <><Button icon="chart-gantt" onClick={() => navigate('gantt')}>计划甘特</Button><Button icon="arrow-right" onClick={() => navigate('field')}>现场报工</Button></>}
          {onNavigate && initialContext.return_to && <Button icon="chevron-left" onClick={() => { const target = initialContext.return_to; if (['gantt', 'field', 'analysis', 'reports', 'dashboard'].includes(target.view)) onNavigate(target.view, target.context || {}); }}>回来源</Button>}</div></div>
      <ErrorBox error={error} />
      {!data && !loading && onNavigate && <Button icon="chart-gantt" onClick={() => onNavigate('analysis', {})}>选择计划</Button>}
      {data && <><Range scope={scope} resources={data.resources} onApply={apply} busy={loading} />
        {data.availability.state !== 'available' && <div role="status" className="fg-note">{data.availability.reason}</div>}
        <dl className="fg-metrics"><div><dt>整道已完工</dt><dd>{stats.complete === null ? '不可用' : stats.complete}</dd></div>
          <div><dt>已报工 · 未整道完工</dt><dd>{stats.reported === null ? '不可用' : stats.reported}</dd></div>
          <div><dt>待报工</dt><dd>{stats.pending === null ? '不可用' : stats.pending}</dd></div>
          <div title="仅统计有确认完工时间的已完工工序"><dt>平均整道完工偏差</dt><dd>{stats.average === null ? '未核实' : (stats.average > 0 ? '+' : '') + Math.round(stats.average) + 'm'}</dd></div></dl>
        <section className="gb-workspace fg-workspace" aria-label="现场实际甘特工作区"><Toolbar {...{ view, patch, model, data, zoom }} onZoom={zoomTo}
          onFit={() => { pending.current = { center: .5 }; setZoom(1); pan(0); }} onLocate={() => locate()} onExport={() => { setExportError(null); setExporting(true); }} busy={exportBusy} />
          {data.critical_chain.state === 'unavailable' && <div className="fg-note" role="status">关键链不可用：{data.critical_chain.reason}</div>}
          {view.chain && data.critical_chain.state === 'available' && <div className="fg-chain-strip">{data.critical_chain.task_refs.map(ref => { const item = data.items.find(i => i.task.task_ref === ref); return <Button key={ref} icon="search" onClick={() => locate(ref)}>{item.task.batch_id + ' · ' + item.task.process_label}</Button>; })}</div>}
          {view.selected && !model.items.some(i => i.task.task_ref === view.selected) && <div role="status" className="fg-note">选中工序不在当前筛选范围，未扩大来源条件。</div>}
          {view.details && <div className="fg-details" aria-label="工序详情">{selected ? <>{describe(selected, model.labels, report).map((line, i) => <span key={i}>{line}</span>)}
            {selected.execution && <><div className="fg-report-selector"><label>逐次报工 <select aria-label="选择报工详情" value={view.report || ''} onChange={e => patch({ report: e.target.value || null })}><option value="">整道工序</option>{selected.execution.reports.map(r => <option key={r.report_ref} value={r.report_ref}>{r.report_no}</option>)}</select></label>
              <Button className="fg-icon-button" icon="search" aria-label="定位本次报工" disabled={!report || !report.actual_start} onClick={() => locate()} /></div>
              {selected.execution.remaining_plan && <span>剩余安排：{M.time(selected.execution.remaining_plan.start)} → {M.time(selected.execution.remaining_plan.end)}</span>}
              {selected.execution.data_gaps.map((gap, i) => <span key={'gap' + i}>{gap.message || '执行记录待核对'}</span>)}
              {report && <span>登记：{M.time(report.recorded_at)} · 历史版本 {report.correction_history.length} 条</span>}</>}</> : <span>未选中工序</span>}</div>}
          <div className="fg-board" ref={board} data-actual-scroll tabIndex={0} aria-label="分次报工甘特" style={{ '--fg-label': labelWidth + 'px' }} onScroll={() => { cancelAnimationFrame(frame.current); frame.current = requestAnimationFrame(measure); }}>
            <div className="fg-board-inner" style={{ width: labelWidth + width, height: model.height + 52 }}><div className="fg-axis"><div className="fg-corner">{M.views[view.mode]} / 工序<small className="fg-muted" style={{ display: 'block' }}>工厂本地时间 · 连续跨夜</small></div>
              <div className="fg-ticks" style={{ width }}>{M.ticks(model, width, position.left, viewport).map(tick => <div className="fg-tick" key={tick.at} title={M.time(tick.label)} style={{ left: tick.x, width: Math.min(134, width - tick.x) }}>{tick.x + 110 <= width && <>{tick.label.slice(0, 10)}<small>{tick.label.slice(11, 19)}</small></>}</div>)}
                <i className="fg-clock" style={{ left: (model.asOf - model.start) / (model.end - model.start) * width }} title={'数据时点 ' + M.time(result.meta.as_of)} aria-hidden="true" /></div></div>
              <window.ActualGanttRows {...{ model, view, width, viewport, labelWidth, patch }} left={position.left} top={position.top} height={position.height} dense={data.task_count >= 1000} onSelect={select} onHover={setHover} />
              {!model.items.length && <div className="fg-empty" role="status">当前范围没有匹配的工序。</div>}</div></div>
          <div className="fg-foot"><span>{M.time(M.wire(model.start))}</span><input type="range" aria-label="时间轴水平位置" min={0} max={Math.max(0, width - viewport)} value={Math.min(position.left, width - viewport)} step="any" onChange={e => pan(Number(e.target.value))} disabled={zoom === 1} /><span>{M.time(M.wire(model.end))}</span></div>
        </section></>}
      {hover && model && <div className="fg-tip" role="tooltip" style={{ left: Math.max(8, Math.min(hover.x + 12, window.innerWidth - 368)), top: Math.max(8, Math.min(hover.y + 12, window.innerHeight - 360)) }}>{hover.title || describe(hover.item, model.labels, hover.report).join('\n')}</div>}
      {exporting && data && <Modal title="导出现场实际甘特" icon="download" onClose={() => { if (downloadController.current) downloadController.current.abort(); setExporting(false); }} footer={<><Button onClick={() => setExporting(false)} disabled={exportBusy}>取消</Button><Button transfer="export" busy={exportBusy} onClick={download}>下载 CSV</Button></>}>
        <div style={{ padding: 16 }}><p>按当前查询范围和本次读取的数据导出全部 {model.items.length} 道匹配工序及其逐次报工，不受滚动、折叠和详情开关影响。</p>
          <p>本地搜索：{view.query.trim() || '无'}；晚期：{M.lateLabels[view.late]}；仅选中：{view.onlySelected ? '是' : '否'}。未知数量和工时保持空值，旧执行事实另列。</p>
          <p>计划完工日期：{scope.plan_finish_date_from || '不限'} 至 {scope.plan_finish_date_to || '不限'}；数据截至 {M.time(result.meta.as_of)}。数据变化时下载会要求刷新。</p><ErrorBox error={exportError} /></div></Modal>}
    </div>;
  }
  function ActualGanttWorkspace(props) { return <Content key={JSON.stringify(props.initialContext || {})} {...props} />; }
  window.ActualGanttWorkspace = ActualGanttWorkspace;
})();
