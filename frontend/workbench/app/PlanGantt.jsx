(function () {
  'use strict';
  const M = window.PlanGanttModel, F = window.WorkbenchFormat, V = window.GanttPresentation, { Button, Icon, TimelineZoom, timelineZoomKey } = window.ResourceControls;
  const ZOOM_MAX = 1024;
  const { DenseRow, Overview } = window.PlanGanttCanvas;
  function Segment({ value, options, onChange, label, disabled = false }) {
    return <div className="plan-segment" role="group" aria-label={label} onKeyDown={event => {
      if (disabled || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault(); const index = options.findIndex(([id]) => id === value);
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : (index + (event.key === 'ArrowLeft' ? -1 : 1) + options.length) % options.length;
      onChange(options[next][0]); event.currentTarget.querySelectorAll('button')[next].focus();
    }}>{options.map(([id, text]) => <Button key={id} className="plan-segment-button" disabled={disabled} aria-pressed={value === id} tabIndex={value === id ? 0 : -1} onClick={() => onChange(id)}>{text}</Button>)}</div>;
  }
  function PrintTasks({ items, labels }) {
    return <section className="plan-print-tasks" aria-label="打印任务明细"><h3>任务明细（图中编号）</h3>
      {Array.from({ length: Math.ceil(items.length / 10) }, (_, chunk) => <table key={chunk} className="plan-print-table plan-print-chunk">
        <colgroup><col style={{ width: '8%' }} /><col style={{ width: '27%' }} /><col style={{ width: '22%' }} /><col style={{ width: '25%' }} /><col style={{ width: '18%' }} /></colgroup>
        <thead><tr>{['编号', '批次 / 分件', '工序', '开始 / 结束', '设备 / 人员'].map(label => <th key={label}>{label}</th>)}</tr></thead>
        <tbody>{items.slice(chunk * 10, (chunk + 1) * 10).map(({ task, baseline }, index) => <tr key={task.task_ref} data-plan-print-task={task.task_ref}>
          <td>{chunk * 10 + index + 1}{baseline && <small>原</small>}</td>
          <td>{task.batch_id}<small>{M.pieceLabel(task)}</small></td>
          <td>{task.sequence} {task.process_label}{window.PointContract.isPoint(task) && <small>零工时工序</small>}</td>
          <td>{F.compactDateTime(task.start)}<small>{F.compactDateTime(task.end)}</small></td>
          <td>{M.resourceLabel(task, 'machine', labels)}<small>{M.resourceLabel(task, 'operator', labels)}</small></td>
        </tr>)}</tbody></table>)}
    </section>;
  }
  function Bar({ item, model, width, printing, printNumbers, selectedRef, selectedBefore, active, risks, onSelect, onHover }) {
    const task = item.task, size = (item.end - item.start) / (model.end - model.start) * width;
    const at = value => (value - model.start) / (model.end - model.start) * (printing ? 100 : width);
    const left = printing ? at(item.start) + '%' : at(item.start);
    const title = (item.baseline ? '原安排\n' : '') + M.taskTitle(task, model.labels, !item.baseline && model.conflicts.has(task.task_ref));
    const lines = V.taskLines({ sequence: task.sequence, process: task.process_label, batch: task.batch_id, piece: M.pieceLabel(task),
      resource: M.resourceLabel(task, 'machine', model.labels) + ' / ' + M.resourceLabel(task, 'operator', model.labels) }, model.mode, size);
    const chosen = selectedRef === task.task_ref && !!item.baseline === !!selectedBefore;
    const critical = !item.baseline && active.critical.has(task.task_ref), related = !item.baseline && active.related.has(task.task_ref);
    if (window.PointContract.isPoint(task)) return <window.PointGantt.Marker task={task} data-plan-task={task.task_ref} data-before={item.baseline || undefined}
      data-gantt-critical={critical || undefined} data-gantt-related={related || undefined} data-gantt-muted={!item.baseline && active.target && !related && !critical || undefined}
      title={title} x={left} top={item.baseline ? 1 : 15}
      selected={chosen} tone={item.baseline ? 'before' : M.tone(task, risks)}
      onSelect={() => onSelect(task, item.baseline)} onHover={event => onHover(event ? { task, before: item.baseline, x: event.clientX, y: event.clientY } : null)} />;
    return <button type="button" data-plan-task={task.task_ref} data-before={item.baseline || undefined}
      data-gantt-critical={critical || undefined} data-gantt-related={related || undefined} data-gantt-muted={!item.baseline && active.target && !related && !critical || undefined}
      className={'plan-bar ' + (item.baseline ? 'before' : M.tone(task, risks)) + (model.conflicts.has(task.task_ref) && !item.baseline ? ' conflict' : '')}
      aria-label={title} aria-pressed={chosen} title={title}
      style={{ left, width: printing ? at(item.end) - at(item.start) + '%' : size }}
      onClick={() => onSelect(task, item.baseline)}
      onMouseEnter={event => onHover({ task, before: item.baseline, x: event.clientX, y: event.clientY })} onMouseLeave={() => onHover(null)}>
      <span className="plan-bar-face" style={{ padding: !item.baseline && size >= 28 ? 2 : 0, borderWidth: size < 4 ? 0 : 1 }}>{printing && !item.baseline ? <strong>{printNumbers.get(task.task_ref)}</strong> : !item.baseline && size >= 28 && <><strong>{lines.primary}</strong>
        {lines.secondary && <small>{lines.secondary}</small>}{risks.get(task.batch_id) === 'on_time' && <i className="wb-gantt-on-time" title="预计按期" />}</>}</span>
    </button>;
  }
  function Source({ data }) {
    const p = data.provenance, baseline = data.projections.baseline;
    const algorithm = p.algorithm, captured = p.baseline;
    const identity = plan => [plan.kind === 'official' ? '正式计划' : plan.kind === 'candidate' ? window.WorkbenchTerms.candidate : window.WorkbenchTerms.trial_scenario,
      plan.display_name, plan.version === null ? null : 'v' + plan.version].filter(Boolean).join(' · ');
    return <div className="wb-gantt-comparison-source" data-gantt-comparison-source>
      <div><strong>当前安排：{identity(data.plan)}</strong>{p.state === 'available'
        ? p.source_kind === 'candidate_adoption'
          ? <>，采用算法生成的候选「{p.source_label || '未命名'}」；算法：{algorithm.mode_label || algorithm.mode || '未记录'}{algorithm.strategy_label && ' · ' + algorithm.strategy_label}。</>
          : <>，采用保存的试调方案「{p.source_label || '未命名'}」。</>
        : '，' + p.reason}</div>
      {baseline.state === 'available' ? <div><strong>原安排：{identity(baseline.baseline_plan)}</strong>，{captured
        ? (captured.kind === 'admission_official' ? '提交该次试排时' : '创建该次试调时') + '自动保存'
        : baseline.basis === 'scenario_base' ? '创建试调时保存的基础安排' : '生成此方案时记录的对照安排'}。
        </div>
        : <div>原安排：{baseline.reason}</div>}
    </div>;
  }
  function PlanGantt({ data, prepared: facts, asOf, selected, onSelect, query, onQuery, disabled = false, toolbarActions, initialMode, initialBaseline = false }) {
    const [mode, setMode] = React.useState(initialMode === 'operator' ? 'operator' : 'machine'), [baseline, setBaseline] = React.useState(initialBaseline), [zoom, setZoom] = React.useState(1);
    const [changedOnly, setChangedOnly] = React.useState(false), { expanded, toggle } = window.GanttPresentationUI.useExpanded();
    const [position, setPosition] = React.useState({ left: 0, top: 0, width: 1000, height: 440 }), [hover, setHover] = React.useState(null);
    const [chainEnabled, setChainEnabled] = React.useState(false);
    const printing = window.WorkbenchControls.usePrintLayout();
    const board = React.useRef(null), search = React.useRef(null), pending = React.useRef(null), frame = React.useRef(null), overviewCache = React.useRef(null);
    const printState = React.useRef(false), printPosition = React.useRef(null), restorePosition = React.useRef(null);
    if (printing && !printState.current) printPosition.current = position;
    if (!printing && printState.current) restorePosition.current = printPosition.current;
    printState.current = printing;
    const labelWidth = position.width < 550 ? 125 : 170, viewport = Math.max(100, position.width - labelWidth);
    const before = data.projections.baseline, showBaseline = before.state === 'available';
    const displayBaseline = showBaseline && baseline, displayChangedOnly = showBaseline && changedOnly;
    // Print uses a normalized axis for tick/point layout; CSS maps its percentages to the actual paper width.
    // It must not inherit a wide screen or expanded board's pixel width.
    const width = printing ? 640 : viewport * zoom, selectedRef = selected && selected.task.task_ref;
    const renderLeft = printing ? 0 : position.left, renderViewport = printing ? width : viewport;
    const grouped = React.useMemo(() => M.groupPrepared(facts, mode), [facts, mode]);
    const prepared = React.useMemo(() => M.selectPrepared(grouped, query, displayChangedOnly, displayBaseline), [grouped, query, displayChangedOnly, displayBaseline]);
    const model = React.useMemo(() => M.layoutPrepared(prepared, width), [prepared, width]);
    const graph = facts.graph;
    const targetRef = hover && !hover.before ? hover.task.task_ref : selected && !selected.before ? selectedRef : null;
    const active = React.useMemo(() => window.GanttGraph.selection(graph, { enabled: chainEnabled, targetRef }), [graph, chainEnabled, targetRef]);
    const graphLocations = React.useMemo(() => window.GanttGraph.locations(model), [model]);
    const locationIndex = React.useMemo(() => window.GanttGraph.locationIndex(graphLocations), [graphLocations]);
    const geometry = React.useMemo(() => window.GanttGraph.paths(active, model, width, {
      left: renderLeft, top: printing ? 0 : position.top, width: renderViewport, height: printing ? model.height : position.height - 52
    }, { locationIndex }), [active, model, width, renderLeft, renderViewport, position.top, position.height, printing, locationIndex]);
    const printItems = printing ? model.rows.flatMap(row => row.items) : [];
    const printNumbers = new Map(printItems.map((item, index) => [item.task.task_ref, index + 1]));
    const risks = React.useMemo(() => new Map(data.projections.delivery_risks.items.map(row => [row.batch_id, row.risk])), [data]);
    const axis = V.axis({ start: model.start, end: model.end, width, left: renderLeft, viewport: renderViewport }), ticks = axis.ticks;
    const refreshedAt = React.useMemo(() => M.instant(asOf), [asOf]);
    const timeX = at => (at - model.start) / (model.end - model.start) * width;
    const axisLeft = at => printing ? timeX(at) / width * 100 + '%' : timeX(at);
    const visibleRows = React.useMemo(() => printing ? model.rows : M.visibleRows(model.rows, Math.max(0, position.top - 90), position.top + position.height + 90), [model, printing, position.top, position.height]);
    const rangeStart = model.start + renderLeft / width * (model.end - model.start);
    const rangeEnd = model.start + (renderLeft + renderViewport) / width * (model.end - model.start);
    const visible = React.useMemo(() => visibleRows.map(row => ({ row, items: row.point
      ? window.PointGanttModel.visible(row.items, rangeStart, rangeEnd, width / (model.end - model.start))
      : M.visibleItems(row.items, rangeStart, rangeEnd) })), [visibleRows, rangeStart, rangeEnd, width, model.start, model.end]);
    const measure = () => {
      const el = board.current;
      if (printState.current || typeof window.matchMedia === 'function' && window.matchMedia('print').matches) return;
      if (el && restorePosition.current) {
        el.scrollLeft = restorePosition.current.left; el.scrollTop = restorePosition.current.top; restorePosition.current = null;
      }
      if (el) setPosition({ left: el.scrollLeft, top: el.scrollTop, width: el.clientWidth, height: el.clientHeight });
    };
    React.useLayoutEffect(() => { measure(); const resize = new ResizeObserver(measure); resize.observe(board.current); return () => { resize.disconnect(); cancelAnimationFrame(frame.current); }; }, []);
    React.useLayoutEffect(() => {
      if (printing) return;
      if (pending.current !== null) { board.current.scrollLeft = pending.current * width - viewport / 2; pending.current = null; }
      measure();
      if (restorePosition.current) frame.current = requestAnimationFrame(measure);
    }, [width, model, printing]);
    React.useEffect(() => { setHover(null); }, [query, mode, baseline, changedOnly, expanded]);
    React.useEffect(() => {
      if (!showBaseline) { setBaseline(false); setChangedOnly(false); }
    }, [showBaseline]);
    React.useEffect(() => {
      setHover(current => {
        if (!current) return null;
        const node = document.elementFromPoint(current.x, current.y), task = node && node.closest('[data-plan-task]');
        return task && task.dataset.planTask === current.task.task_ref && task.hasAttribute('data-before') === !!current.before ? current : null;
      });
    }, [position.top, position.left]);
    React.useEffect(() => { if (expanded) board.current.focus(); }, [expanded]);
    function changeZoom(next) {
      pending.current = (position.left + viewport / 2) / width; setZoom(Math.max(1, Math.min(ZOOM_MAX, next)));
    }
    function fit() { pending.current = 0.5; setZoom(1); board.current.scrollLeft = 0; measure(); }
    function locate(taskRef = selectedRef, beforeTask = !!(selected && selected.before)) {
      const location = (beforeTask ? model.baselineLocations : model.locations).get(taskRef);
      if (!location) return;
      const { item, top } = location, el = board.current;
      el.scrollTop = Math.max(0, top - el.clientHeight / 3);
      el.scrollLeft = (item.start + item.end - 2 * model.start) / 2 / (model.end - model.start) * width - viewport / 2;
      measure();
    }
    const located = React.useRef(null);
    React.useEffect(() => {
      if (!selected || !selected.locate || located.current === selected) return;
      const locations = selected.before ? model.baselineLocations : model.locations;
      if (!locations.has(selectedRef)) { if (!selected.before && displayChangedOnly) setChangedOnly(false); return; }
      located.current = selected; locate(selectedRef, selected.before);
    }, [selected, model]);
    function select(task, beforeTask) { setHover(null); onSelect(task, beforeTask); }
    function move(direction) {
      const tasks = model.tasks, index = tasks.findIndex(task => task.task_ref === selectedRef);
      const next = tasks[Math.max(0, Math.min(tasks.length - 1, index < 0 ? 0 : index + direction))];
      if (next) { onSelect(next, false); locate(next.task_ref, false); }
    }
    const currentIndex = model.tasks.findIndex(task => task.task_ref === selectedRef);
    return <div className={'plan-gantt' + (expanded ? ' plan-expanded' : '')} data-plan-gantt data-printing={printing || undefined} onKeyDown={event => {
      if (disabled || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || event.target.closest('input,textarea,select,[role=dialog]')) return;
      if (event.key === '/') { event.preventDefault(); search.current.focus(); }
      const zoomAction = timelineZoomKey(event);
      if (zoomAction === 'in') { event.preventDefault(); changeZoom(zoom * 2); }
      if (zoomAction === 'out') { event.preventDefault(); changeZoom(zoom / 2); }
      if (zoomAction === 'fit') { event.preventDefault(); fit(); }
      if (event.key.toLowerCase() === 'l') { event.preventDefault(); locate(); }
    }}>
      <div className="plan-toolbar">
        <Segment value={mode} options={Object.entries(M.kindLabels)} onChange={setMode} label="甘特分组" disabled={disabled} />
        {showBaseline && <label className="plan-check" title="显示保存的原安排"><input type="checkbox" aria-label="显示原安排" checked={displayBaseline} disabled={disabled}
          onChange={event => setBaseline(event.target.checked)} />显示原安排</label>}
        {showBaseline && <label className="plan-check" title="筛选起止时间、设备或人员发生变化，以及新增、移除的工序"><input type="checkbox" aria-label="只看有变化的工序" checked={displayChangedOnly} disabled={disabled}
          onChange={event => setChangedOnly(event.target.checked)} />只看有变化的工序</label>}
        <label className="search plan-search"><span className="ic"><Icon name="search" /></span><input ref={search} type="search" aria-label="搜索批次、工序、设备、人员" placeholder="批次、工序、资源" value={query}
          onChange={event => onQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); move(event.shiftKey ? -1 : 1); } if (event.key === 'Escape') onQuery(''); }} /></label>
        <div className="plan-actions">
          <TimelineZoom zoom={zoom} max={ZOOM_MAX} onZoom={changeZoom} onFit={fit} disabled={disabled} className="btn plan-icon" />
          <Button icon="search" className="btn plan-icon" aria-label="定位选中任务" title="定位选中任务 (L)" disabled={!(selected && selected.before ? model.baselineLocations : model.locations).has(selectedRef)} onClick={() => locate()} />
          <Button icon={expanded ? 'x' : 'chart-gantt'} className="btn" aria-label={expanded ? '收起甘特' : '展开甘特'} title={expanded ? '返回完整工作区' : '展开甘特工作区'}
            aria-expanded={expanded} disabled={disabled} onClick={toggle}>{expanded ? '收起' : '展开'}</Button>
          {toolbarActions}
        </div>
      </div>
      <window.GanttGraphLayer.Controls graph={data.gantt_graph} enabled={chainEnabled} onChange={setChainEnabled} active={active} geometry={geometry} onClear={() => { setHover(null); onSelect(null); }} disabled={disabled} />
      <div className="plan-board-frame">
        {!printing && width > viewport && <Overview model={model} tasks={data.tasks} prepared={facts} cache={overviewCache} width={width} viewport={renderViewport} left={renderLeft} onPan={left => { board.current.scrollLeft = Math.max(0, left); measure(); }} />}
        <div ref={board} className="plan-board" data-plan-scroll data-wb-scroll-key="plan-board" tabIndex={0} aria-label={M.kindLabels[mode] + '甘特时间轴'} onScroll={() => {
          if (frame.current) cancelAnimationFrame(frame.current); frame.current = requestAnimationFrame(measure);
        }} style={{ '--plan-label': labelWidth + 'px' }}>
          <div className="plan-board-inner" style={{ width: labelWidth + width, height: model.height + 52 }}>
            <div className="plan-axis"><div className="plan-corner">{M.kindLabels[mode]} / 工序<small className="plan-muted plan-corner-count">{model.groupCount} 组</small></div>
              <div className="plan-ticks" style={{ width }}><window.GanttPresentationUI.Axis axis={axis} width={width} printing={printing} /></div></div>
            {visible.map(({ row, items }) => {
              const meta = row.before ? '原安排' : [row.code, row.tasks.length + ' 道工序', row.point ? '零工时节点 · 不占资源' : row.trackCount > 1 ? '重叠子行 ' + row.subrow + '/' + row.trackCount : null].filter(Boolean).join(' · ');
              const summary = row.occupancy ? '全时段已占 ' + F.hours(row.occupancy.occupied_hours, { digits: 1, trim: true })
                + (row.occupancy.utilization === null ? '' : ' · 班内占用 ' + F.percent(row.occupancy.utilization, { digits: 0 })) : '';
              return <div key={row.key} className={'plan-lane' + (row.before ? ' baseline' : '')} data-gantt-row-kind={row.before ? 'original' : row.point ? 'point' : row.trackCount > 1 ? 'overlap' : 'current'} data-gantt-subrow={row.subrow} style={{ top: row.top + 52, height: row.height, width: labelWidth + width }}>
                <div className="plan-resource" title={[row.label, meta, summary, row.overlap ? '同一组存在同时进行的安排，已上下分行' : null].filter(Boolean).join(' · ')}>{row.before
                  ? <small className="plan-resource-meta">{row.tasks.length ? '原安排' : row.label + ' · 原安排'}</small>
                  : <><strong>{row.label}{!row.point && row.trackCount > 1 && <em className="wb-gantt-subrow-badge">{row.subrow}/{row.trackCount}</em>}</strong><small className="plan-resource-meta">{meta}</small>{summary && <small className="plan-resource-summary">{summary}</small>}</>}</div>
                <div className="plan-track" style={{ width }}>{ticks.map(tick => <i key={tick.at} className="plan-gridline" style={{ left: axisLeft(tick.at) }} />)}
                  {items.length > 70 ? <DenseRow row={row} items={items} model={model} width={width} printing={printing} printNumbers={printNumbers} viewport={renderViewport} left={renderLeft} selectedRef={selectedRef} selectedBefore={selected && selected.before} active={active} risks={risks} onSelect={select} onHover={setHover} /> :
                    items.map(item => <Bar key={item.task.task_ref} item={item} model={model} width={width} printing={printing} printNumbers={printNumbers} selectedRef={selectedRef} selectedBefore={selected && selected.before} active={active} risks={risks} onSelect={select} onHover={setHover} />)}
                </div>
                {printing && <window.GanttGraphLayer.Lines geometry={geometry} width={width} height={row.height} labelWidth={labelWidth} rowTop={row.top} />}
              </div>;
            })}
            {!printing && <window.GanttGraphLayer.Lines geometry={geometry} width={width} height={model.height} labelWidth={labelWidth} top={52} />}
            {refreshedAt >= model.start && refreshedAt <= model.end && <i className="plan-time-line as-of" data-plan-time-line="as-of" data-time-value={asOf} role="img" tabIndex={0}
              aria-label={'本次刷新时间 ' + F.compactDateTime(asOf)} title={'本次刷新时间 ' + F.compactDateTime(asOf)}
              style={{ left: printing ? 'calc(' + labelWidth * (1 - timeX(refreshedAt) / width) + 'px + ' + axisLeft(refreshedAt) + ')' : labelWidth + timeX(refreshedAt), top: 52, height: model.height }} />}
            {!model.rows.length && <div style={{ position: 'sticky', left: 0, width: position.width }}><window.WorkbenchControls.EmptyState kind={query || displayChangedOnly ? 'filtered' : 'empty'} title={displayChangedOnly ? '当前范围没有匹配的变更安排。' : query ? '没有匹配安排，完整计划的时间范围保持不变。' : '该读取范围没有安排。'}
              action={query || displayChangedOnly ? <Button onClick={() => { onQuery(''); setChangedOnly(false); }}>清除筛选</Button> : undefined} /></div>}
          </div>
        </div>
        <div className="plan-footer">{(query.trim() || displayChangedOnly) && <span data-plan-search-count>匹配 {model.tasks.length} / {data.task_count} 道安排</span>}
          <span className="plan-legend"><i className="plan-swatch" />计划安排</span>
          <span className="plan-legend"><i className="wb-gantt-status-dot" />预计按期</span>
          <span className="plan-legend"><i className="plan-swatch critical" />预计超期</span><span className="plan-legend"><i className="plan-swatch conflict" />资源冲突</span>
          {displayBaseline && <span className="plan-legend"><i className="plan-swatch before" />原安排</span>}<span className="plan-legend"><i className="plan-swatch point" />零工时工序</span>
          <span className="plan-legend" title={'本次刷新时间 ' + F.compactDateTime(asOf)}><i className="plan-swatch as-of" />本次刷新时间</span>
          <span className="plan-actions"><Button className="btn plan-icon" icon="chevron-left" aria-label="上一匹配任务" disabled={currentIndex <= 0} onClick={() => move(-1)} />
            <span>{currentIndex < 0 ? '未选任务' : '第 ' + (currentIndex + 1) + ' 道匹配'}</span><Button className="btn plan-icon" icon="chevron-right" aria-label="下一匹配任务" disabled={!model.tasks.length || currentIndex >= model.tasks.length - 1} onClick={() => move(1)} /></span>
        </div>
      </div>
      {printing && printItems.length > 0 && <PrintTasks items={printItems} labels={model.labels} />}
      {hover && <div role="tooltip" className="plan-tooltip" style={{ left: Math.max(8, Math.min(hover.x + 12, window.innerWidth - 335)), top: Math.max(8, Math.min(hover.y + 16, window.innerHeight - 300)), maxHeight: 'calc(100vh - 16px)', overflow: 'auto', overflowWrap: 'anywhere' }}>
        {(hover.before ? '原安排\n' : '') + M.taskTitle(hover.task, model.labels, !hover.before && model.conflicts.has(hover.task.task_ref))}</div>}
    </div>;
  }
  window.PlanGantt = PlanGantt;
  window.PlanGanttSource = Source;
  window.PlanSegmentUI = Segment;
})();
