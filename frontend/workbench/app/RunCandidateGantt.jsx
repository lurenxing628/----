(function () {
  'use strict';
  const M = window.RunCandidateModel, B = window.RunBaselineModel, BC = window.RunBaselineControls, { Button } = window.RunCandidateControls;
  const { TimelineZoom, timelineZoomKey, timelineZoomStep } = window.ResourceControls, ZOOM_MAX = 128;
  function PointLane({ row, model, risks, width, left, viewport, printing, selected, baselineSelected, active, onSelect, onHover }) {
    const scale = width / (model.end - model.start), G = window.PointGanttModel;
    const items = G.visible(row.items, model.start + left / scale, model.start + (left + viewport) / scale, scale);
    return <div data-candidate-point-lane style={{ position: 'absolute', left, width: viewport, height: row.height, overflow: 'hidden' }}>
      {items.map(item => <window.PointGantt.Marker key={item.task.row_ref} task={item.task} title={M.title(item.task)}
        data-gantt-critical={active.critical.has(item.task.row_ref) || undefined} data-gantt-related={active.related.has(item.task.row_ref) || undefined} data-gantt-muted={!!active.target && !active.related.has(item.task.row_ref) && !active.critical.has(item.task.row_ref) || undefined}
        x={printing ? (item.start - model.start) / (model.end - model.start) * 100 + '%' : (item.start - model.start) * scale - left} top={15}
        tone={risks.get(item.task.batch_ref) === 'overdue' ? 'critical' : ''} selected={!baselineSelected && selected && selected.row_ref === item.task.row_ref}
        onSelect={() => onSelect(item.task)} onHover={event => onHover(event ? { taskRef: item.task.row_ref, text: M.title(item.task), x: event.clientX, y: event.clientY } : null)} />)}
    </div>;
  }
  function Lane({ row, model, mode, risks, width, left, viewport, printing, selected, baselineSelected, active, onSelect, onBaselineSelect, onHover, reference }) {
    const ref = React.useRef(null), scale = width / (model.end - model.start);
    const items = row.baselinePoint ? window.PointGanttModel.visible(row.items, model.start + left / scale, model.start + (left + viewport) / scale, scale)
      : M.visibleItems(row.items, model.start + left / scale, model.start + (left + viewport) / scale);
    React.useLayoutEffect(() => {
      function paint() {
        const node = ref.current, ratio = devicePixelRatio || 1, w = Math.max(1, viewport), h = row.height;
        node.width = Math.round(w * ratio); node.height = h * ratio;
        const ctx = node.getContext('2d'); ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        const P = window.GanttPresentation, colors = P.palette(node);
        for (const item of items) {
          const x = (item.start - model.start) * scale - left, barWidth = (item.end - item.start) * scale;
          if (row.baseline) {
            const chosen = baselineSelected && baselineSelected.comparison.operation_ref === item.comparison.operation_ref;
            if (row.baselinePoint) { window.PointGanttModel.paint(ctx, x, 15, colors.plan.fill, chosen ? colors.gold : colors.plan.edge, chosen); continue; }
            P.paintBar(ctx, { x, y: 11, width: barWidth, height: 7, fill: 'transparent', edge: chosen ? colors.gold : colors.plan.edge,
              lineWidth: chosen ? 2 : 1, dashed: true, viewport: w });
            continue;
          }
          const external = item.task.source === 'external', risk = risks.get(item.task.batch_ref);
          const colorsForTask = colors[risk === 'overdue' ? 'critical' : 'primary'];
          const chosen = !baselineSelected && item.task.row_ref === (selected && selected.row_ref);
          const related = active.related.has(item.task.row_ref), critical = active.critical.has(item.task.row_ref);
          const lines = P.taskLines({ sequence: M.number(item.task.sequence), process: item.task.process_label || '工序未记录',
            batch: item.task.batch_label || '批次未记录', piece: M.pieceLabel(item.task),
            resource: [item.task.machine && item.task.machine.label, item.task.operator && item.task.operator.label].filter(Boolean).join(' / ') || '资源未记录' }, mode, barWidth);
          P.paintBar(ctx, { x, y: 7, width: barWidth, height: 40, fill: colorsForTask.fill,
            edge: chosen || related || critical ? colors.gold : colorsForTask.edge, lineWidth: chosen || critical ? 2 : related ? 1.5 : 1,
            dashed: external, texture: external ? 'external' : item.overlap ? 'overlap' : null, textureColor: external ? colors.plan.edge : colors.overlap.edge,
            textColor: colorsForTask.ink, font: colors.font, lines, viewport: w,
            critical, criticalColor: colors.gold, muted: !!active.target && !related && !critical,
            onTime: risk === 'on_time', locked: item.task.locked, statusColor: colors.success.edge });
        }
      }
      paint(); const theme = new MutationObserver(paint), media = typeof matchMedia === 'function' ? matchMedia('print') : null;
      theme.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'class'] });
      if (media) {
        if (typeof media.addEventListener === 'function') media.addEventListener('change', paint);
        else media.addListener(paint);
      }
      return () => {
        theme.disconnect();
        if (media) {
          if (typeof media.removeEventListener === 'function') media.removeEventListener('change', paint);
          else media.removeListener(paint);
        }
      };
    }, [row, model, mode, risks, width, left, viewport, printing, selected, baselineSelected, active]);
    function hit(event) { const box = ref.current.getBoundingClientRect(), at = model.start + (event.clientX - box.left + left) / scale;
      return row.baselinePoint ? window.PointGanttModel.hit(row.items, event.clientX - box.left, event.clientY - box.top, model, width, left, 15) : M.visibleItems(row.items, at, at + 0.001)[0]; }
    const choose = item => row.baseline ? onBaselineSelect(item) : onSelect(item.task);
    const selectedItem = row.items.find(item => !row.baseline && selected && item.task.row_ref === selected.row_ref);
    return <canvas ref={ref} data-candidate-lane={row.baseline ? undefined : true} data-baseline-lane={row.baseline ? true : undefined} data-item-count={row.items.length} role="button" tabIndex={0} aria-label={row.label + '，' + M.laneLabel(row, reference) + '，' + row.items.length + ' 道安排' + (selectedItem ? '\n' + M.title(selectedItem.task) : '')}
      style={{ position: 'absolute', left, width: viewport, height: row.height }}
      onMouseMove={event => { const item = hit(event); onHover(item ? { taskRef: row.baseline ? null : item.task.row_ref, text: row.baseline ? B.title(item) : M.title(item.task), x: event.clientX, y: event.clientY } : null); }} onMouseLeave={() => onHover(null)}
      onClick={event => { const item = hit(event); if (item) choose(item); }}
      onKeyDown={event => {
        if (!row.items.length || !['Enter', ' ', 'Home', 'End', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
        event.preventDefault(); const index = row.items.findIndex(i => row.baseline ? i.segment.row_ref === (baselineSelected && baselineSelected.segment && baselineSelected.segment.row_ref) : i.task.row_ref === (selected && selected.row_ref));
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? row.items.length - 1 : ['Enter', ' '].includes(event.key) ? Math.max(0, index) : Math.max(0, Math.min(row.items.length - 1, index + (event.key === 'ArrowLeft' ? -1 : 1)));
        choose(row.items[next]);
      }} />;
  }
  function TaskCells({ task: t, planned, onDetails, print }) {
    const Cell = print ? 'td' : 'span';
    return <><Cell role="cell" title={(t.batch_label || '未记录') + '\n' + (t.part_label || '未记录')}>{t.batch_label || '未记录'}<small>{t.part_label || '未记录'}</small></Cell>
      <Cell role="cell" title={M.number(t.sequence) + ' ' + (t.process_label || '未记录') + '\n' + M.pieceLabel(t)}>{M.pieceLabel(t)}<small>{M.number(t.sequence)} {t.process_label || '未记录'}</small></Cell>
      <Cell role="cell" title={planned ? M.title(t) : t.reason.message}>{planned ? <>{window.WorkbenchFormat.dateTime(t.start)}<small>{window.PointContract.isPoint(t) ? '零工时工序 · 不占设备人员' : window.WorkbenchFormat.dateTime(t.end)}</small></> : t.reason.message}</Cell>
      <Cell role="cell" title={planned ? (t.machine && t.machine.label || '未记录') + '\n' + (t.operator && t.operator.label || '未记录') : ''}>{planned ? <>{t.machine && t.machine.label || '未记录'}<small>{t.operator && t.operator.label || '未记录'}</small></> : t.execution_at_generation ? M.executionValue(t.execution_at_generation.execution_state) : '未记录'}</Cell>
      {!print && <Cell role="cell"><Button icon="search" className="mini" aria-label={'工序详情 ' + (t.batch_label || '批次未记录') + ' ' + M.number(t.sequence) + ' ' + (t.process_label || '工序未记录') + ' ' + M.pieceLabel(t)} onClick={() => onDetails(t)}>详情</Button></Cell>}</>;
  }
  function TaskList({ tasks, selected, onDetails, planned }) {
    const printing = BC.usePrintLayout(), [top, setTop] = React.useState(0), height = 44;
    const first = printing ? 0 : Math.max(0, Math.floor(top / height) - 3), end = printing ? tasks.length : Math.min(tasks.length, first + 16);
    const head = React.useRef(null), labels = ['批次 / 零件', '工序', planned ? '开始 / 结束' : '状态 / 原因', planned ? '设备 / 人员' : '生成时执行'];
    if (printing) return <>
      <div className="rc-print-tables" data-candidate-task-list data-print-row-count={tasks.length}>
        {Array.from({ length: Math.ceil(tasks.length / 12) }, (_, chunk) => {
          const rows = tasks.slice(chunk * 12, (chunk + 1) * 12);
          return <table key={chunk} className="rc-print-table rc-print-chunk" data-print-chunk={chunk + 1}
            aria-label={(planned ? '候选任务安排' : '候选未安排明细') + '，第 ' + (chunk + 1) + ' 组'} aria-rowcount={rows.length + 1} aria-colcount={4}>
            <thead><tr>{labels.map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>{rows.map(t => <tr key={t.row_ref || t.operation_ref}
              data-row-ref={t.row_ref || undefined} data-operation-ref={t.operation_ref} aria-selected={selected && (t.row_ref ? selected.row_ref === t.row_ref : selected.operation_ref === t.operation_ref)}>
              <TaskCells task={t} planned={planned} print /></tr>)}</tbody>
          </table>;
        })}
      </div>
      {!tasks.length && <window.WorkbenchListControls.EmptyState title="当前范围没有匹配记录" />}</>;
    return <>
      <div className="rc-virtual-table" role="table" aria-label={planned ? '候选任务安排' : '候选未安排明细'} aria-rowcount={tasks.length + 1} aria-colcount={5}>
      <div className="rc-list-head" ref={head} role="rowgroup"><div className="rc-list-row rc-muted" role="row" aria-rowindex={1}>{labels.concat('详情').map(label => <span role="columnheader" key={label}>{label}</span>)}</div></div>
      <div className="rc-list" data-candidate-task-list role="rowgroup" tabIndex={0} aria-label={planned ? '候选任务安排滚动区' : '候选未安排明细滚动区'} onScroll={e => { setTop(e.currentTarget.scrollTop); if (head.current) head.current.scrollLeft = e.currentTarget.scrollLeft; }}>
        <div role="presentation" style={{ height: tasks.length * height, position: 'relative', minWidth: 720 }}>
          {tasks.slice(first, end).map((t, i) => <div key={t.row_ref || t.operation_ref} className="rc-list-row" data-row-ref={t.row_ref || undefined} data-operation-ref={t.operation_ref}
            role="row" aria-rowindex={first + i + 2} aria-selected={selected && (t.row_ref ? selected.row_ref === t.row_ref : selected.operation_ref === t.operation_ref)} style={{ position: 'absolute', top: (first + i) * height, left: 0, right: 0 }}>
            <TaskCells task={t} planned={planned} onDetails={onDetails} /></div>)}
        </div></div></div>{!tasks.length && <window.WorkbenchListControls.EmptyState title="当前范围没有匹配记录" />}</>;
  }
  function RunCandidateGantt({ data, comparison, query, onQuery, selected, onSelect, resourceFocus, toolbarActions }) {
    const [mode, setMode] = React.useState(resourceFocus && resourceFocus.kind === 'operator' ? 'operator' : 'machine'), [zoom, setZoom] = React.useState(1), [viewport, setViewport] = React.useState(600);
    const [scroll, setScroll] = React.useState({ left: 0, top: 0 }), [hover, setHover] = React.useState(null), host = React.useRef(null), owner = React.useRef(null);
    const [chainEnabled, setChainEnabled] = React.useState(false), [changedOnly, setChangedOnly] = React.useState(false);
    const [viewportHeight, setViewportHeight] = React.useState(310), expansion = window.GanttPresentationUI.useExpanded();
    const search = React.useRef(null);
    const [inspection, setInspection] = React.useState(null);
    const printing = BC.usePrintLayout();
    const printState = React.useRef(false), savedScroll = React.useRef(null), restoreScroll = React.useRef(null);
    if (printing && !printState.current) savedScroll.current = scroll;
    if (!printing && printState.current) restoreScroll.current = savedScroll.current;
    printState.current = printing;
    const canCompare = !!comparison && comparison.baseline.comparison_available;
    const inspectedRef = inspection && inspection.candidateRef === data.candidate.candidate_ref ? inspection.operationRef : null;
    const baseline = BC.useBaseline(data, canCompare || !!inspectedRef), [selection, setSelection] = React.useState(null), result = baseline.result;
    const changed = React.useMemo(() => new Set(comparison ? comparison.operations.changed_operation_refs : []), [comparison]);
    const unknown = React.useMemo(() => new Set(comparison ? comparison.operations.unknown_operation_refs : []), [comparison]);
    const problems = React.useMemo(() => comparison ? comparison.operations.issues.filter(row => unknown.has(row.operation_ref)) : [], [comparison, unknown]);
    const displayChangedOnly = canCompare && changedOnly;
    const operationRefs = displayChangedOnly ? changed : null;
    const inspected = React.useMemo(() => {
      const row = result && inspectedRef && result.data.comparisons.find(row => row.operation_ref === inspectedRef);
      return row ? { comparison: row, segment: row.baseline_segments[0] || null } : null;
    }, [result, inspectedRef]);
    const selectedItem = selection && selection.result === result ? selection.item : inspected;
    const chosen = selectedItem && (!operationRefs || operationRefs.has(selectedItem.comparison.operation_ref))
      && B.matching([selectedItem.comparison], query).length ? selectedItem : null;
    // Draw the complete print range once; CSS maps this normalized axis onto the paper width.
    const labelWidth = 156, width = printing ? 640 : Math.max(1, viewport) * zoom;
    const candidate = React.useMemo(() => M.prepare(resourceFocus ? { ...data, tasks: data.tasks.filter(task => M.resourceMatches(task, resourceFocus)) } : data, mode, query, operationRefs), [data, mode, query, operationRefs, resourceFocus && resourceFocus.ref, resourceFocus && resourceFocus.kind]);
    const displayedBaseline = React.useMemo(() => result && resourceFocus ? { ...result.data, comparisons: result.data.comparisons.map(row => ({ ...row, baseline_segments: row.baseline_segments.filter(segment => M.resourceMatches(segment, resourceFocus)) })) } : result && result.data, [result, resourceFocus && resourceFocus.ref, resourceFocus && resourceFocus.kind]);
    const prepared = React.useMemo(() => B.prepare(candidate, displayedBaseline, mode, query, operationRefs), [candidate, displayedBaseline, mode, query, operationRefs]);
    const model = React.useMemo(() => B.layoutPrepared(prepared, width), [prepared, width]);
    const risks = React.useMemo(() => new Map(data.delivery_risks.items.map(row => [row.batch_ref, row.risk])), [data]);
    const graph = React.useMemo(() => window.GanttGraph.create(data.gantt_graph), [data.gantt_graph]);
    const targetRef = hover && hover.taskRef || !chosen && selected && selected.row_ref || null;
    const active = React.useMemo(() => window.GanttGraph.selection(graph, { enabled: chainEnabled, targetRef }), [graph, chainEnabled, targetRef]);
    const graphLocations = React.useMemo(() => window.GanttGraph.locations(model, { candidate: true }), [model]);
    const locationIndex = React.useMemo(() => window.GanttGraph.locationIndex(graphLocations), [graphLocations]);
    function selectBaseline(item) { setSelection(item ? { item, result } : null); if (item) onSelect(null); else setInspection(null); setHover(null); }
    function selectCandidate(task) { setInspection(null); setSelection(null); setHover(null); onSelect(task); }
    function inspectProblem(operationRef) {
      setInspection({ candidateRef: data.candidate.candidate_ref, operationRef }); setSelection(null); setChangedOnly(false);
      onQuery(''); onSelect(null); setHover(null); baseline.toggle(true);
    }
    function filterChanges(value) {
      setChangedOnly(value); setHover(null);
      if (value) setInspection(null);
      if (value && selected && !changed.has(selected.operation_ref)) onSelect(null);
      if (value && chosen && !changed.has(chosen.comparison.operation_ref)) setSelection(null);
    }
    React.useEffect(() => { if (!canCompare) setChangedOnly(false); }, [canCompare]);
    React.useEffect(() => {
      // Route and delivery links can select a task outside the current change filter.
      if (selected && !changed.has(selected.operation_ref)) setChangedOnly(false);
    }, [selected]);
    React.useEffect(() => { setHover(null); if (expansion.expanded) owner.current.focus(); }, [expansion.expanded]);
    React.useLayoutEffect(() => {
      const measure = () => {
        if (printState.current || window.matchMedia('print').matches) return;
        setViewport(Math.max(1, owner.current.clientWidth - labelWidth));
        setViewportHeight(owner.current.clientHeight);
      };
      const observe = new ResizeObserver(measure); observe.observe(host.current); observe.observe(owner.current);
      return () => observe.disconnect();
    }, []);
    React.useLayoutEffect(() => {
      if (printing || !restoreScroll.current) return;
      const position = restoreScroll.current;
      const restore = () => { owner.current.scrollLeft = position.left; owner.current.scrollTop = position.top; setScroll(position); };
      restore(); restoreScroll.current = null;
      const frame = requestAnimationFrame(restore); return () => cancelAnimationFrame(frame);
    }, [printing]);
    React.useLayoutEffect(() => { if (owner.current) { owner.current.scrollTop = 0; owner.current.scrollLeft = 0; } setScroll({ left: 0, top: 0 }); setHover(null); }, [mode, query, data, result, displayChangedOnly]);
    React.useLayoutEffect(() => {
      if (!resourceFocus || selected || chosen || printing) return;
      const row = model.rows.find(item => item.id === resourceFocus.ref), node = owner.current;
      if (row && node) node.scrollTop = Math.max(0, row.top - node.clientHeight / 3);
    }, [resourceFocus && resourceFocus.ref, model, selected, chosen, printing]);
    React.useLayoutEffect(() => {
      const loc = chosen && chosen.segment ? model.baselineLocations.get(chosen.segment.row_ref) : selected && model.locations.get(selected.row_ref), node = owner.current;
      if (!node || !loc || printing || restoreScroll.current) return;
      if (loc.top < node.scrollTop || loc.top + model.rows[loc.row].height > node.scrollTop + viewportHeight) node.scrollTop = loc.top;
      const x = (loc.item.start - model.start) / (model.end - model.start) * width;
      if (x < node.scrollLeft || x > node.scrollLeft + viewport) node.scrollLeft = Math.max(0, x - viewport / 3);
    }, [selected, chosen, model, width, viewport, viewportHeight, printing]);
    function pan(left) { if (owner.current) owner.current.scrollLeft = Math.max(0, Math.min(width - viewport, left)); }
    function fit() { setZoom(1); pan(0); }
    function locate(task) {
      const loc = task ? model.locations.get(task.row_ref) : chosen && chosen.segment ? model.baselineLocations.get(chosen.segment.row_ref)
        : selected && model.locations.get(selected.row_ref), node = owner.current;
      if (!node || !loc) return;
      node.scrollTop = Math.max(0, loc.top - node.clientHeight / 3);
      pan((loc.item.start + loc.item.end - 2 * model.start) / 2 / (model.end - model.start) * width - viewport / 2);
    }
    function move(direction) {
      const index = model.tasks.findIndex(task => selected && task.row_ref === selected.row_ref);
      const task = model.tasks[Math.max(0, Math.min(model.tasks.length - 1, index < 0 ? 0 : index + direction))];
      if (task) { selectCandidate(task); locate(task); }
    }
    function zoomKeys(event) {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || event.target.closest('input,textarea,select,[role=dialog]')) return;
      if (event.key === '/') { event.preventDefault(); search.current.focus(); }
      if (event.key.toLowerCase() === 'l') { event.preventDefault(); locate(); }
      const action = timelineZoomKey(event);
      if (!action) return;
      event.preventDefault();
      if (action === 'fit') fit(); else setZoom(z => timelineZoomStep(z, action === 'in' ? 1 : -1, ZOOM_MAX));
    }
    const renderLeft = printing ? 0 : scroll.left, renderViewport = printing ? width : viewport;
    const geometry = React.useMemo(() => window.GanttGraph.paths(active, model, width, {
      left: renderLeft, top: printing ? 0 : scroll.top, width: renderViewport, height: printing ? model.height : viewportHeight
    }, { locationIndex }), [active, model, width, renderLeft, renderViewport, scroll.top, viewportHeight, printing, locationIndex]);
    const visible = printing ? model.rows : M.visibleRows(model.rows, scroll.top - 56, scroll.top + viewportHeight + 56);
    const currentIndex = model.tasks.findIndex(task => selected && task.row_ref === selected.row_ref);
    const axis = window.GanttPresentation.axis({ start: model.start, end: model.end, width, left: renderLeft, viewport: renderViewport });
    return <section ref={host} className={'rc-gantt' + (expansion.expanded ? ' rc-expanded' : '')} aria-label="候选甘特图" onKeyDown={zoomKeys}>
      <div className="rc-gantt-toolbar"><window.PlanSegmentUI value={mode} options={Object.entries(M.kindLabels)} onChange={setMode} label="候选甘特维度" />
        {canCompare && <><BC.Toggle state={baseline} />
          <label className="rb-toggle" title="只显示和原安排相比，时间或资源有变化的工序">
            <input type="checkbox" aria-label="只看有变化的工序" checked={displayChangedOnly} onChange={event => filterChanges(event.target.checked)} />只看有变化的工序</label></>}
        <label className="search plan-search"><span className="ic"><window.ResourceControls.Icon name="search" /></span><input ref={search} type="search" aria-label="搜索候选工序" placeholder="批次、工序、资源" value={query}
          onChange={event => onQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); move(event.shiftKey ? -1 : 1); } if (event.key === 'Escape') onQuery(''); }} /></label>
        <div className="rc-tools"><TimelineZoom zoom={zoom} max={ZOOM_MAX} scope="候选" onZoom={setZoom} onFit={fit} />
          <Button icon="search" aria-label="定位选中候选任务" title="定位选中任务 (L)" disabled={!(chosen && chosen.segment && model.baselineLocations.has(chosen.segment.row_ref)) && !(selected && model.locations.has(selected.row_ref))} onClick={() => locate()} />
          <Button icon={expansion.expanded ? 'x' : 'chart-gantt'} aria-label={expansion.expanded ? '收起甘特' : '展开甘特'} title={expansion.expanded ? '返回完整工作区' : '展开甘特工作区'} aria-expanded={expansion.expanded} onClick={expansion.toggle}>{expansion.expanded ? '收起' : '展开'}</Button>
          {toolbarActions}
        </div></div>
      {!data.reference && baseline.enabled && <BC.Source workspace={data} comparison={comparison} />}
      <BC.Problems workspace={data} issues={problems} onInspect={inspectProblem} />
      <BC.Panel state={baseline} rows={(model.comparisons || []).filter(row => !inspectedRef || unknown.has(row.operation_ref))} chosen={chosen} onChoose={selectBaseline} workspace={data}
        inspecting={!!inspectedRef} onShowAll={canCompare ? () => setInspection(null) : undefined} />
      <window.GanttGraphLayer.Controls graph={data.gantt_graph} enabled={chainEnabled} onChange={setChainEnabled} active={active} geometry={geometry} onClear={() => { setHover(null); onSelect(null); }} />
      {model.unplottableTasks.length > 0 && <p className="rc-muted">{model.unplottableTasks.length} 道安排的时间缺项或无效，请在下方任务安排表或工序详情核对。</p>}
      <div className="rc-axis-row"><div className="rc-axis-corner">{M.kindLabels[mode]} / 工序<small>{model.groupCount} 组</small></div><div className="rc-axis"><window.GanttPresentationUI.Axis axis={axis} width={width} offset={renderLeft} printing={printing} /></div></div>
      <div ref={owner} className="rc-scroll" data-candidate-gantt-scroll role="region" aria-label="候选时间安排" tabIndex={0}
        onScroll={e => { if (!printState.current && !window.matchMedia('print').matches) setScroll({ left: e.currentTarget.scrollLeft, top: e.currentTarget.scrollTop }); setHover(null); }}>
        <div style={{ position: 'relative', width: width + labelWidth, height: Math.max(120, model.height) }}>
          {visible.map(row => <div key={row.key} className="rc-lane" data-candidate-track={row.baseline ? undefined : row.key} data-baseline-track={row.baseline ? row.key : undefined}
            data-gantt-row-kind={row.baseline ? 'original' : row.point ? 'point' : row.normalLaneCount > 1 ? 'overlap' : 'current'} data-gantt-subrow={row.lane + 1}
            style={{ top: row.top, height: row.height }}><div className="rc-lane-label" style={{ height: row.height - 1, paddingTop: row.baseline ? 5 : 7 }} title={row.label + ' · ' + M.laneLabel(row, data.reference)}>
              <strong>{row.label}</strong>{row.baseline ? <span className="rc-lane-kind"> · {M.laneLabel(row, data.reference)}</span> : <small><span className="rc-lane-kind">{M.laneLabel(row, data.reference)}</span> · {row.items.length} 道</small>}</div>
            <div className="rc-bar-space" style={{ width, height: row.height, overflow: 'hidden' }}>{React.createElement(row.point ? PointLane : Lane, { row, model, mode, risks, width, left: renderLeft, viewport: renderViewport, printing, selected, baselineSelected: chosen, active, reference: data.reference, onSelect: selectCandidate, onBaselineSelect: selectBaseline, onHover: setHover })}</div>
            {printing && <window.GanttGraphLayer.Lines geometry={geometry} width={width} height={row.height} labelWidth={labelWidth} rowTop={row.top} />}</div>)}
          {!printing && <window.GanttGraphLayer.Lines geometry={geometry} width={width} height={model.height} labelWidth={labelWidth} />}
          {!model.rows.length && <div className="rc-empty">{model.unplottableTasks.length > 0 ? '安排时间缺项，请在下方任务安排表核对。' : displayChangedOnly ? '当前范围没有匹配的变更安排。' : '当前范围没有可绘制的安排。'}</div>}</div></div>
      {zoom > 1 && <input type="range" aria-label="候选时间轴水平位置" style={{ width: '100%' }} min="0" max={Math.max(0, width - viewport)} step="any" value={Math.min(scroll.left, Math.max(0, width - viewport))} onChange={e => pan(Number(e.target.value))} />}
      <div className="rc-legend rc-muted"><span><i />安排</span>
        <span><i className="rc-risk" />预计超期</span><span><i className="rc-on-time" />预计按期</span><span><i className="rc-fixed" />保存锁定标记</span><span><i className="rc-external" />外协工序</span>
        <span><i className="rc-overlap" />同时段安排分子行显示</span><span>◇ 零工时点独立行，不占资源</span><span className="rc-tools"><Button icon="chevron-left" aria-label="上一匹配候选任务" disabled={currentIndex <= 0} onClick={() => move(-1)} />
          {currentIndex >= 0 && <span>第 {currentIndex + 1} 道匹配</span>}<Button icon="chevron-right" aria-label="下一匹配候选任务" disabled={!model.tasks.length || currentIndex >= model.tasks.length - 1} onClick={() => move(1)} /></span></div>
      {window.PointContract.isPoint(selected) && <dl className="rc-meta" data-candidate-point-facts><div><dt>安排类型</dt><dd>零工时工序</dd></div><div><dt>发生时间</dt><dd title={M.timeLabel(selected.start)}>{window.WorkbenchFormat.dateTime(selected.start)}</dd></div><div><dt>本工序占用</dt><dd>0 小时 · 不占设备人员</dd></div></dl>}
      {hover && <div role="tooltip" className="rc-tooltip" style={{ left: Math.max(8, Math.min(innerWidth - 358, hover.x + 12)), top: Math.max(8, Math.min(innerHeight - 238, hover.y + 14)) }}>{hover.text}</div>}
    </section>;
  }
  RunCandidateGantt.TaskList = TaskList;
  window.RunCandidateGantt = RunCandidateGantt;
})();
