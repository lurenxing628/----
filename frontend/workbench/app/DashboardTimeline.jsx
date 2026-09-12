(function () {
  'use strict';
  const M = window.DashboardTimelineModel, { Button } = window.ResourceControls;
  function Timeline({ data, mode = 'delivery', selectedBatch, onSelect }) {
    const board = React.useRef(null), [zoom, setZoom] = React.useState(1), [hover, setHover] = React.useState(null), [focusTask, setFocusTask] = React.useState('');
    const [position, setPosition] = React.useState({ left: 0, top: 0, width: 900, height: 330 });
    const labelWidth = 150, viewport = Math.max(200, position.width - labelWidth), width = Math.max(640, viewport) * zoom;
    const model = React.useMemo(() => M.layout(data, mode, width), [data, mode, width]);
    const measure = () => { const node = board.current; if (node) setPosition({ left: node.scrollLeft, top: node.scrollTop, width: node.clientWidth, height: node.clientHeight }); };
    React.useLayoutEffect(() => { measure(); const observer = new ResizeObserver(measure); observer.observe(board.current); return () => observer.disconnect(); }, []);
    React.useEffect(() => { setHover(null); }, [position.left, position.top, mode]);
    React.useEffect(() => {
      const task = model.tasks.find(row => row.task_ref === focusTask && row.batch_ref === selectedBatch) || model.tasks.find(row => row.batch_ref === selectedBatch), location = task && model.locations.get(task.task_ref);
      if (!location || !board.current) return;
      board.current.scrollTop = Math.max(0, location.top - 60);
      const left = (location.item.start - model.start) / (model.end - model.start) * width;
      if (left < position.left || left > position.left + viewport) board.current.scrollLeft = Math.max(0, left - viewport / 3);
    }, [selectedBatch, focusTask, model]);
    const ticks = M.ticks(model.start, model.end, width, position.left, viewport);
    const rows = M.visibleRows(model.rows, Math.max(0, position.top - 60), position.top + position.height + 60);
    const rangeStart = model.start + position.left / width * (model.end - model.start), rangeEnd = model.start + (position.left + viewport) / width * (model.end - model.start);
    function show(event, text) { const rect = event.currentTarget.getBoundingClientRect(); setHover({ text, x: rect.left, y: rect.bottom }); }
    return <section className="dy-timeline" aria-label={mode === 'downtime' ? '检修窗口与原计划时间轴' : '关联资源关键时段'} data-dashboard-timeline={mode}>
      <div className="dy-heading"><h3>{mode === 'downtime' ? '检修窗口与原计划' : '关联资源的关键时段'}</h3><div className="dy-tools">
        <Button icon="minus" aria-label="缩小分析时间轴" disabled={zoom <= 1} onClick={() => setZoom(Math.max(1, zoom / 2))} />
        <span>{zoom}×</span><Button icon="plus" aria-label="放大分析时间轴" disabled={zoom >= 64} onClick={() => setZoom(Math.min(64, zoom * 2))} />
        <Button icon="unfold-vertical" aria-label="显示完整分析时间轴" onClick={() => { setZoom(1); board.current.scrollLeft = 0; }} />
      </div></div>
      <label className="dy-run-picker">定位工序<select aria-label="定位分析时间轴中的工序" value={model.tasks.some(row => row.task_ref === focusTask && row.batch_ref === selectedBatch) ? focusTask : ''} onChange={event => {
        const task = model.tasks.find(row => row.task_ref === event.target.value); setFocusTask(event.target.value); if (task) onSelect(task.batch_ref);
      }}><option value="">选择需要查看的工序</option>{model.tasks.map(task => <option key={task.task_ref} value={task.task_ref}>{task.batch_id} · {task.sequence} {task.process_label} · {M.timeLabel(task.start)}</option>)}</select></label>
      <div className="dy-timeline-board" ref={board} onScroll={measure} tabIndex={0} style={{ '--dy-label-width': labelWidth + 'px', height: Math.max(120, Math.min(330, model.height + 48)) }}>
        <div className="dy-timeline-inner" style={{ width: labelWidth + width, height: Math.max(110, model.height + 48) }}>
          <div className="dy-timeline-axis"><div className="dy-timeline-corner">设备 / 工序</div><div className="dy-timeline-ticks" style={{ width }}>
            {ticks.map(tick => <div key={tick.at} style={{ left: tick.x }}>{window.WorkbenchFormat.dateTime(tick.label, { seconds: true }).slice(0, 10)}<small>{window.WorkbenchFormat.dateTime(tick.label, { seconds: true }).slice(11)}</small></div>)}
          </div></div>
          {rows.map(row => {
            const items = row.point ? window.PointGanttModel.visible(row.items, rangeStart, rangeEnd, width / (model.end - model.start)) : M.visibleItems(row.items, rangeStart, rangeEnd);
            return <div key={row.key} className="dy-timeline-row" style={{ top: row.top + 48, height: row.height, width: labelWidth + width }}>
              <div className="dy-timeline-label"><b>{row.label}</b><small>{row.tasks.length} 道安排{row.trackCount > 1 ? ' · 子轨 ' + (row.track + 1) : ''}</small></div>
              <div className="dy-timeline-track" style={{ width }}>{ticks.map(tick => <i className="dy-timeline-grid" key={tick.at} style={{ left: tick.x }} />)}
                {mode === 'downtime' && (model.windows.get(row.id) || []).map(stop => {
                  const low = Math.max(model.start, M.instant(stop.start)), high = Math.min(model.end, M.instant(stop.end));
                  const text = ['检修：' + (stop.reason || '原因未记录'), M.timeLabel(stop.start) + ' 至 ' + M.timeLabel(stop.end), '登记时间（原存值）：' + M.timeLabel(stop.recorded_at)].join('\n');
                  return high > low ? <span key={stop.downtime_ref} role="img" tabIndex={0} aria-label={text} title={text} data-downtime-ref={stop.downtime_ref}
                    className="dy-downtime-window" style={{ left: (low - model.start) / (model.end - model.start) * width, width: (high - low) / (model.end - model.start) * width }}
                    onMouseEnter={event => show(event, text)} onMouseLeave={() => setHover(null)} onFocus={event => show(event, text)} onBlur={() => setHover(null)} /> : null;
                })}
                {items.map(item => {
                  const task = item.task, point = task.start === task.end, title = M.title(task), pixels = Math.max(point ? 10 : 2, (item.end - item.start) / (model.end - model.start) * width);
                  return <button type="button" key={task.task_ref} data-analysis-task={task.task_ref} data-analysis-batch={task.batch_ref}
                    aria-label={title} title={title} aria-pressed={selectedBatch === task.batch_ref}
                    className={'dy-analysis-bar' + (point ? ' point' : '') + (selectedBatch === task.batch_ref ? ' selected' : '')}
                    style={{ left: (item.start - model.start) / (model.end - model.start) * width - (point ? 5 : 0), width: pixels }}
                    onMouseEnter={event => show(event, title)} onMouseLeave={() => setHover(null)} onFocus={event => show(event, title)} onBlur={() => setHover(null)}
                    onClick={() => { setHover(null); onSelect(task.batch_ref); }}>{pixels >= 65 && <span>{task.batch_id} · {task.process_label}</span>}</button>;
                })}
              </div>
            </div>;
          })}
          {!model.rows.length && <window.WorkbenchListControls.EmptyState kind="empty" title="当前读取范围没有可显示的设备安排。" />}
        </div>
      </div>
      <div className="dy-context"><span>{M.timeLabel(M.wire(model.start))} 至 {M.timeLabel(M.wire(model.end))} · 工厂本地</span>
        <span>{mode === 'downtime' ? '检修窗口 / 原计划工序' : '原计划工序'} · {model.tasks.length} 道</span></div>
      {hover && <div role="tooltip" className="dy-analysis-tooltip" style={{ left: Math.max(8, Math.min(hover.x, window.innerWidth - 368)), top: Math.max(8, Math.min(hover.y + 8, window.innerHeight - 220)) }}>{hover.text}</div>}
    </section>;
  }
  window.DashboardTimeline = Timeline;
})();
