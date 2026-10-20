(function () {
  'use strict';
  const M = window.DashboardTimelineModel, V = window.GanttPresentation, { TimelineZoom, timelineZoomKey, timelineZoomStep } = window.ResourceControls, ZOOM_MAX = 64;
  function TaskBar({ item, model, width, selectedBatch, onSelect, onHover }) {
    const task = item.task, point = window.PointContract.isPoint(task), risk = model.risks.get(task.batch_ref);
    const title = M.title(task, risk), x = (item.start - model.start) / (model.end - model.start) * width;
    const size = (item.end - item.start) / (model.end - model.start) * width;
    const selected = selectedBatch === task.batch_ref, choose = () => { onHover(null); onSelect(task.batch_ref); };
    const hover = event => onHover(event, title);
    if (point) return <window.PointGantt.Marker task={task} x={x} top={15} title={title} selected={selected}
      tone={risk === 'overdue' ? 'critical' : ''} data-analysis-task={task.task_ref} data-analysis-batch={task.batch_ref}
      onSelect={choose} onHover={hover} onFocus={hover} onBlur={() => onHover(null)} />;
    const lines = V.taskLines({ sequence: task.sequence, process: task.process_label, batch: task.batch_id }, 'machine', size);
    return <button type="button" data-analysis-task={task.task_ref} data-analysis-batch={task.batch_ref}
      aria-label={title} title={title} aria-pressed={selected} data-delivery-risk={risk}
      className="dy-analysis-bar" style={{ left: x, width: size }} onClick={choose}
      onMouseEnter={hover} onMouseLeave={() => onHover(null)} onFocus={hover} onBlur={() => onHover(null)}>
      <span className="dy-analysis-bar-face" style={{ borderWidth: size < 4 ? 0 : 1 }}>
        {lines.primary && <><strong>{lines.primary}</strong>{lines.secondary && <small>{lines.secondary}</small>}
          {risk === 'on_time' && <i className="wb-gantt-on-time" title="预计按期" />}</>}
      </span>
    </button>;
  }
  function Timeline({ data, mode = 'delivery', selectedBatch, onSelect }) {
    const board = React.useRef(null), [zoom, setZoom] = React.useState(1), [hover, setHover] = React.useState(null), [focusTask, setFocusTask] = React.useState('');
    const [position, setPosition] = React.useState({ left: 0, top: 0, width: 900, height: 330 });
    const pendingCenter = React.useRef(null), selection = React.useRef(null), labelWidth = position.width < 550 ? 140 : 170;
    const viewport = Math.max(80, position.width - labelWidth), width = viewport * zoom;
    const prepared = React.useMemo(() => M.prepare(data), [data]);
    const grouped = React.useMemo(() => M.groupPrepared(prepared, mode), [prepared, mode]);
    const model = React.useMemo(() => M.layoutPrepared(grouped, width), [grouped, width]);
    const picker = React.useMemo(() => {
      const byRef = new Map(), firstByBatch = new Map(); let hasPoints = false;
      const options = model.tasks.map(task => {
        byRef.set(task.task_ref, task);
        if (!firstByBatch.has(task.batch_ref)) firstByBatch.set(task.batch_ref, task);
        if (window.PointContract.isPoint(task)) hasPoints = true;
        return <option key={task.task_ref} value={task.task_ref}>{task.batch_id} · {task.sequence} {task.process_label} · {M.timeLabel(task.start)}</option>;
      });
      return { byRef, firstByBatch, options, hasPoints };
    }, [model.tasks]);
    const measure = () => { const node = board.current; if (node) setPosition({ left: node.scrollLeft, top: node.scrollTop, width: node.clientWidth, height: node.clientHeight }); };
    React.useLayoutEffect(() => { measure(); const observer = new ResizeObserver(measure); observer.observe(board.current); return () => observer.disconnect(); }, []);
    React.useLayoutEffect(() => {
      if (pendingCenter.current !== null) {
        board.current.scrollLeft = Math.max(0, pendingCenter.current * width - viewport / 2);
        pendingCenter.current = null;
      }
      measure();
    }, [width]);
    React.useEffect(() => { setHover(null); }, [position.left, position.top, mode]);
    React.useEffect(() => {
      if (!selection.current || selection.current.batch !== selectedBatch || selection.current.task !== focusTask)
        selection.current = { batch: selectedBatch, task: focusTask, located: false };
      if (selection.current.located) return;
      const focused = picker.byRef.get(focusTask), task = focused && focused.batch_ref === selectedBatch ? focused : picker.firstByBatch.get(selectedBatch);
      const location = task && model.locations.get(task.task_ref);
      if (!location || !board.current) return;
      board.current.scrollTop = Math.max(0, location.top - 60);
      const left = (location.item.start - model.start) / (model.end - model.start) * width;
      if (left < position.left || left > position.left + viewport) board.current.scrollLeft = Math.max(0, left - viewport / 3);
      selection.current.located = true;
      // Wait for the selected task's page, then locate once; later data, zoom and resize keep the user's position.
    }, [selectedBatch, focusTask, picker, model]);
    const axis = V.axis({ start: model.start, end: model.end, width, left: position.left, viewport });
    const rows = M.visibleRows(model.rows, Math.max(0, position.top - 60), position.top + position.height + 60);
    const rangeStart = model.start + position.left / width * (model.end - model.start), rangeEnd = model.start + (position.left + viewport) / width * (model.end - model.start);
    function show(event, text) {
      if (!event) { setHover(null); return; }
      const rect = event.currentTarget.getBoundingClientRect(); setHover({ text, x: rect.left, y: rect.bottom });
    }
    function zoomTo(next) { pendingCenter.current = (position.left + viewport / 2) / width; setZoom(next); }
    function fit() { pendingCenter.current = .5; setZoom(1); if (board.current) { board.current.scrollLeft = 0; measure(); } }
    function zoomKeys(event) {
      const action = timelineZoomKey(event);
      if (!action) return;
      event.preventDefault();
      if (action === 'fit') fit(); else zoomTo(timelineZoomStep(zoom, action === 'in' ? 1 : -1, ZOOM_MAX));
    }
    return <section className="dy-timeline" aria-label={mode === 'downtime' ? '停机时段与计划安排' : '关联资源计划时间轴'} data-dashboard-timeline={mode} onKeyDown={zoomKeys}>
      <div className="dy-heading"><h3>{mode === 'downtime' ? '停机时段与计划安排' : '关联资源计划时间轴'}</h3><div className="dy-tools">
        <TimelineZoom zoom={zoom} max={ZOOM_MAX} scope="分析" onZoom={zoomTo} onFit={fit} />
      </div></div>
      <label className="dy-run-picker">定位工序<select aria-label="定位分析时间轴中的工序" value={picker.byRef.has(focusTask) && picker.byRef.get(focusTask).batch_ref === selectedBatch ? focusTask : ''} onChange={event => {
        const task = picker.byRef.get(event.target.value); setFocusTask(event.target.value); if (task) onSelect(task.batch_ref);
      }}><option value="">选择需要查看的工序</option>{picker.options}</select></label>
      <div className="dy-timeline-board" ref={board} onScroll={measure} tabIndex={0} style={{ '--dy-label-width': labelWidth + 'px', height: Math.max(120, Math.min(330, model.height + 52)) }}>
        <div className="dy-timeline-inner" style={{ width: labelWidth + width, height: Math.max(110, model.height + 52) }}>
          <div className="dy-timeline-axis"><div className="dy-timeline-corner">设备 / 工序</div><div className="dy-timeline-ticks" style={{ width }}>
            <window.GanttPresentationUI.Axis axis={axis} width={width} />
          </div></div>
          {rows.map(row => {
            const items = row.point ? window.PointGanttModel.visible(row.items, rangeStart, rangeEnd, width / (model.end - model.start)) : M.visibleItems(row.items, rangeStart, rangeEnd);
            return <div key={row.key} className="dy-timeline-row" data-analysis-row-kind={row.point ? 'point' : row.overlap ? 'overlap' : 'task'} style={{ top: row.top + 52, height: row.height, width: labelWidth + width }}>
              <div className="dy-timeline-label"><b>{row.label}</b><small>{row.items.length} 道{row.point ? '零工时工序' : '安排'}{!row.point && row.overlap > 0 ? ' · 时间重叠分行' : ''}</small></div>
              <div className="dy-timeline-track" style={{ width }}>{axis.ticks.map(tick => <i className="dy-timeline-grid" key={tick.at} style={{ left: tick.x }} />)}
                {mode === 'downtime' && (model.windows.get(row.id) || []).map(stop => {
                  const low = Math.max(model.start, stop.startAt), high = Math.min(model.end, stop.endAt);
                  const text = ['停机：' + (stop.reason || '原因未填写'), M.timeLabel(stop.start) + ' 至 ' + M.timeLabel(stop.end), '登记时间：' + M.timeLabel(stop.recorded_at)].join('\n');
                  return high > low ? <span key={stop.downtime_ref} role="img" tabIndex={0} aria-label={text} title={text} data-downtime-ref={stop.downtime_ref}
                    className="dy-downtime-window" style={{ left: (low - model.start) / (model.end - model.start) * width, width: (high - low) / (model.end - model.start) * width }}
                    onMouseEnter={event => show(event, text)} onMouseLeave={() => setHover(null)} onFocus={event => show(event, text)} onBlur={() => setHover(null)} /> : null;
                })}
                {items.map(item => <TaskBar key={item.task.task_ref} {...{ item, model, width, selectedBatch, onSelect }} onHover={show} />)}
              </div>
            </div>;
          })}
          {!model.rows.length && <window.WorkbenchListControls.EmptyState kind="empty" title="当前读取范围没有可显示的设备安排。" />}
        </div>
      </div>
      <div className="dy-timeline-legend" aria-label="分析时间轴图例"><span><i className="dy-plan-swatch" />计划工序</span>
        <span><i className="dy-risk-swatch" />批次预计超期</span><span><i className="dy-on-time-swatch" />预计按期</span><span><i className="dy-selected-swatch" />选中批次</span>
        {picker.hasPoints && <span><i className="dy-point-swatch" />零工时工序</span>}
        {mode === 'downtime' && <span><i className="dy-downtime-swatch" />停机时段</span>}</div>
      <div className="dy-context"><span title={'显示范围：' + window.WorkbenchFormat.dateTime(M.wire(model.start), { seconds: true, fractions: true }) + ' 至 ' + window.WorkbenchFormat.dateTime(M.wire(model.end), { seconds: true, fractions: true })}>{window.WorkbenchFormat.compactRange(M.wire(model.start), M.wire(model.end))}</span>
        <span>{data.pagination ? '本页关联 ' : ''}{model.tasks.length} 道计划工序{mode === 'downtime' ? ' · 阴影为已登记停机' : ''}</span></div>
      {hover && <div role="tooltip" className="dy-analysis-tooltip" style={{ left: Math.max(8, Math.min(hover.x, window.innerWidth - 368)), top: Math.max(8, Math.min(hover.y + 8, window.innerHeight - 220)) }}>{hover.text}</div>}
    </section>;
  }
  window.DashboardTimeline = Timeline;
})();
