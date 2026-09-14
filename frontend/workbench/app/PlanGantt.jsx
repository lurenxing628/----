(function () {
  'use strict';
  const M = window.PlanGanttModel, { Button, Icon, TimelineZoom, timelineZoomKey } = window.ResourceControls;
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
  function Bar({ item, model, width, selectedRef, risks, onSelect, onHover }) {
    const task = item.task, size = (item.end - item.start) / (model.end - model.start) * width;
    const title = (item.baseline ? '初始计划\n' : '') + M.taskTitle(task, model.labels, !item.baseline && model.conflicts.has(task.task_ref));
    if (window.PointContract.isPoint(task)) return <window.PointGantt.Marker task={task} data-plan-task={task.task_ref} data-before={item.baseline || undefined}
      title={title} x={(item.start - model.start) / (model.end - model.start) * width} top={item.baseline ? 1 : 15}
      selected={selectedRef === task.task_ref} tone={item.baseline ? 'before' : M.tone(task, model.conflicts, risks)}
      onSelect={() => onSelect(task, item.baseline)} onHover={event => onHover(event ? { task, before: item.baseline, x: event.clientX, y: event.clientY } : null)} />;
    return <button type="button" data-plan-task={task.task_ref} data-before={item.baseline || undefined}
      className={'plan-bar ' + (item.baseline ? 'before' : M.tone(task, model.conflicts, risks)) + (model.conflicts.has(task.task_ref) && !item.baseline ? ' conflict' : '')}
      aria-label={title} aria-pressed={selectedRef === task.task_ref} title={title}
      style={{ left: (item.start - model.start) / (model.end - model.start) * width, width: size }}
      onClick={() => onSelect(task, item.baseline)}
      onMouseEnter={event => onHover({ task, before: item.baseline, x: event.clientX, y: event.clientY })} onMouseLeave={() => onHover(null)}>
      <span className="plan-bar-face" style={{ padding: !item.baseline && size >= 28 ? 2 : 0, borderWidth: size < 4 ? 0 : 1 }}>{!item.baseline && size >= 28 && <><strong>{task.batch_id}</strong>
        {size >= 75 && <small>{task.sequence} {task.process_label} · {M.pieceLabel(task)}</small>}</>}</span>
    </button>;
  }
  function PlanGantt({ data, asOf, selected, onSelect, query, onQuery, disabled = false }) {
    const [mode, setMode] = React.useState('machine'), [baseline, setBaseline] = React.useState(false), [zoom, setZoom] = React.useState(1);
    const [changedOnly, setChangedOnly] = React.useState(false), [expanded, setExpanded] = React.useState(false);
    const [position, setPosition] = React.useState({ left: 0, top: 0, width: 1000, height: 440 }), [hover, setHover] = React.useState(null);
    const board = React.useRef(null), search = React.useRef(null), pending = React.useRef(null), frame = React.useRef(null), expandButton = React.useRef(null);
    const labelWidth = position.width < 550 ? 125 : 170, viewport = Math.max(100, position.width - labelWidth);
    const width = viewport * zoom, selectedRef = selected && selected.task.task_ref;
    const model = React.useMemo(() => M.layout(data, mode, query, baseline, width, changedOnly), [data, mode, query, baseline, width, changedOnly]);
    const risks = React.useMemo(() => new Map((data.projections.delivery_risks.items || []).map(row => [row.batch_id, row.risk])), [data]);
    const before = data.projections.baseline, showBaseline = before.state === 'available';
    const ticks = M.ticks(model.start, model.end, width, position.left, viewport);
    const today = M.instant(asOf.slice(0, 10) + 'T00:00:00'), now = M.instant(asOf);
    const timeX = at => (at - model.start) / (model.end - model.start) * width;
    const visibleRows = M.visibleRows(model.rows, Math.max(0, position.top - 90), position.top + position.height + 90);
    const rangeStart = model.start + position.left / width * (model.end - model.start);
    const rangeEnd = model.start + (position.left + viewport) / width * (model.end - model.start);
    const measure = () => {
      const el = board.current;
      if (el) setPosition({ left: el.scrollLeft, top: el.scrollTop, width: el.clientWidth, height: el.clientHeight });
    };
    React.useLayoutEffect(() => { measure(); const resize = new ResizeObserver(measure); resize.observe(board.current); return () => { resize.disconnect(); cancelAnimationFrame(frame.current); }; }, []);
    React.useLayoutEffect(() => {
      if (pending.current !== null) { board.current.scrollLeft = pending.current * width - viewport / 2; pending.current = null; }
      measure();
    }, [width, model]);
    React.useEffect(() => { setHover(null); }, [query, mode, baseline, changedOnly, expanded]);
    React.useEffect(() => {
      setHover(current => {
        if (!current) return null;
        const node = document.elementFromPoint(current.x, current.y), task = node && node.closest('[data-plan-task]');
        return task && task.dataset.planTask === current.task.task_ref && task.hasAttribute('data-before') === !!current.before ? current : null;
      });
    }, [position.top, position.left]);
    React.useEffect(() => {
      if (!expanded) return undefined;
      const overflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden'; board.current.focus();
      const close = event => { if (event.key === 'Escape') { event.preventDefault(); setExpanded(false); } };
      document.addEventListener('keydown', close);
      return () => { document.body.style.overflow = overflow; document.removeEventListener('keydown', close); if (expandButton.current) expandButton.current.focus(); };
    }, [expanded]);
    function changeZoom(next) {
      pending.current = (position.left + viewport / 2) / width; setZoom(Math.max(1, Math.min(ZOOM_MAX, next)));
    }
    function fit() { pending.current = 0.5; setZoom(1); board.current.scrollLeft = 0; measure(); }
    function locate(taskRef = selectedRef) {
      const location = model.locations.get(taskRef);
      if (!location) return;
      const { item, top } = location, el = board.current;
      el.scrollTop = Math.max(0, top - el.clientHeight / 3);
      el.scrollLeft = (item.start + item.end - 2 * model.start) / 2 / (model.end - model.start) * width - viewport / 2;
      measure();
    }
    const located = React.useRef(null);
    React.useEffect(() => {
      if (selected && selected.locate && located.current !== selected && model.locations.has(selectedRef)) {
        located.current = selected; locate(selectedRef);
      }
    }, [selected, model]);
    function select(task, beforeTask) { setHover(null); onSelect(task, beforeTask); }
    function move(direction) {
      const tasks = model.tasks, index = tasks.findIndex(task => task.task_ref === selectedRef);
      const next = tasks[Math.max(0, Math.min(tasks.length - 1, index < 0 ? 0 : index + direction))];
      if (next) { onSelect(next, false); locate(next.task_ref); }
    }
    const currentIndex = model.tasks.findIndex(task => task.task_ref === selectedRef);
    return <div className={'plan-gantt' + (expanded ? ' plan-expanded' : '')} data-plan-gantt onKeyDown={event => {
      if (disabled || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || event.target.closest('input,textarea,select,[role=dialog]')) return;
      if (event.key === '/') { event.preventDefault(); search.current.focus(); }
      const zoomAction = timelineZoomKey(event);
      if (zoomAction === 'in') { event.preventDefault(); changeZoom(zoom * 2); }
      if (zoomAction === 'out') { event.preventDefault(); changeZoom(zoom / 2); }
      if (zoomAction === 'fit') { event.preventDefault(); fit(); }
      if (event.key.toLowerCase() === 'l') { event.preventDefault(); locate(); }
    }}>
      <window.PointGantt.Styles /><div className="plan-toolbar">
        <Segment value={mode} options={Object.entries(M.kindLabels)} onChange={setMode} label="甘特分组" disabled={disabled} />
        <label className="plan-check" title={showBaseline ? '和初始计划对照' : before.reason || '初始计划暂无数据'}><input type="checkbox" aria-label="显示初始计划" checked={baseline && showBaseline} disabled={!showBaseline || disabled}
          onChange={event => setBaseline(event.target.checked)} />初始计划</label>
        <label className="plan-check" title={showBaseline ? '只看和初始计划不一样的安排' : before.reason || '初始计划暂无数据'}><input type="checkbox" aria-label="仅变更" checked={changedOnly && showBaseline} disabled={!showBaseline || disabled}
          onChange={event => setChangedOnly(event.target.checked)} />仅变更</label>
        <label className="search plan-search"><span className="ic"><Icon name="search" /></span><input ref={search} type="search" aria-label="搜索批次、工序、设备、人员" placeholder="批次、工序、资源" value={query}
          onChange={event => onQuery(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); move(event.shiftKey ? -1 : 1); } if (event.key === 'Escape') onQuery(''); }} /></label>
        <div className="plan-actions">
          <TimelineZoom zoom={zoom} max={ZOOM_MAX} onZoom={changeZoom} onFit={fit} disabled={disabled} className="btn plan-icon" />
          <Button icon="search" className="btn plan-icon" aria-label="定位选中任务" title="定位选中任务 (L)" disabled={!model.locations.has(selectedRef)} onClick={() => locate()} />
          <Button icon={expanded ? 'x' : 'chart-gantt'} className="btn plan-icon" aria-label={expanded ? '收起甘特' : '展开甘特'} title={expanded ? '返回完整工作区' : '展开甘特工作区'}
            aria-expanded={expanded} disabled={disabled} onClick={event => { expandButton.current = event.currentTarget; setExpanded(!expanded); }} />
        </div>
      </div>
      {!showBaseline && <div className="plan-note">初始计划：{before.reason || '暂无数据'}</div>}
      <div className="plan-board-frame">
        <Overview model={model} tasks={data.tasks} width={width} viewport={viewport} left={position.left} onPan={left => { board.current.scrollLeft = Math.max(0, left); measure(); }} />
        <div ref={board} className="plan-board" data-plan-scroll data-wb-scroll-key="plan-board" tabIndex={0} aria-label={M.kindLabels[mode] + '甘特时间轴'} onScroll={() => {
          if (frame.current) cancelAnimationFrame(frame.current); frame.current = requestAnimationFrame(measure);
        }} style={{ '--plan-label': labelWidth + 'px' }}>
          <div className="plan-board-inner" style={{ width: labelWidth + width, height: model.height + 52 }}>
            <div className="plan-axis"><div className="plan-corner">{M.kindLabels[mode]} / 工序<small className="plan-muted" style={{ display: 'block' }}>{model.groupCount} 组</small></div>
              <div className="plan-ticks" style={{ width }}>{ticks.map(tick => <div className="plan-tick" key={tick.at} style={{ left: tick.x }}>
                {M.timeLabel(tick.label).slice(0, 10)}<small>{M.timeLabel(tick.label).slice(11)}</small></div>)}</div></div>
            {visibleRows.map(row => {
              const items = row.point ? window.PointGanttModel.visible(row.items, rangeStart, rangeEnd, width / (model.end - model.start)) : M.visibleItems(row.items, rangeStart, rangeEnd);
              return <div key={row.key} className={'plan-lane' + (row.before ? ' baseline' : '')} style={{ top: row.top + 52, height: row.height, width: labelWidth + width }}>
                <div className="plan-resource" title={row.label + ' · ' + (row.before ? '初始计划' : row.tasks.length + ' 道安排 · 子轨 ' + (row.track + 1) + '/' + row.trackCount + (row.overlap ? ' · 存在重叠' : ''))}><strong>{row.label}</strong>{!row.before && <small>{row.tasks.length} 道安排{row.trackCount > 1 ? ' · 子轨 ' + (row.track + 1) + '/' + row.trackCount : ''}{row.overlap ? ' · 重叠' : ''}</small>}{row.before && <small>初始计划</small>}</div>
                <div className="plan-track" style={{ width }}>{ticks.map(tick => <i key={tick.at} className="plan-gridline" style={{ left: tick.x }} />)}
                  {items.length > 70 ? <DenseRow row={row} model={model} width={width} viewport={viewport} left={position.left} selectedRef={selectedRef} risks={risks} onSelect={select} onHover={setHover} /> :
                    items.map(item => <Bar key={item.task.task_ref} item={item} model={model} width={width} selectedRef={selectedRef} risks={risks} onSelect={select} onHover={setHover} />)}
                </div>
              </div>;
            })}
            {[['today', today, '今日零点（按数据日期）'], ['as-of', now, '数据时点']].filter(([, at]) => at >= model.start && at <= model.end).map(([kind, at, label]) =>
              <i key={kind} className={'plan-time-line ' + kind} data-plan-time-line={kind} data-time-value={M.wire(at)} aria-label={label + ' ' + M.timeLabel(M.wire(at))} title={label + ' ' + M.timeLabel(M.wire(at))}
                style={{ left: labelWidth + timeX(at), top: 52, height: model.height }} />)}
            {!model.rows.length && <div style={{ position: 'sticky', left: 0, width: position.width }}><window.WorkbenchControls.EmptyState kind={query || changedOnly ? 'filtered' : 'empty'} title={changedOnly ? '当前范围没有匹配的变更安排。' : query ? '没有匹配安排，完整计划的时间范围保持不变。' : '该读取范围没有安排。'}
              action={query || changedOnly ? <Button onClick={() => { onQuery(''); setChangedOnly(false); }}>清除筛选</Button> : undefined} /></div>}
          </div>
        </div>
        <div className="plan-footer"><span data-plan-search-count>{model.tasks.length} / {data.task_count} 道安排</span>
          <span className="plan-legend"><i className="plan-swatch" />安排</span><span className="plan-legend"><i className="plan-swatch success" />已确认准时</span>
          <span className="plan-legend"><i className="plan-swatch critical" />预计超期</span><span className="plan-legend"><i className="plan-swatch conflict" />资源重叠</span>
          <span className="plan-legend"><i className="plan-swatch before" />初始计划</span><span className="plan-legend"><i className="plan-swatch point" />零工时工序</span>
          <span className="plan-legend"><i className="plan-swatch today" />今日 / 数据时点</span>
          <span className="plan-actions"><Button className="btn plan-icon" icon="chevron-left" aria-label="上一匹配任务" disabled={currentIndex <= 0} onClick={() => move(-1)} />
            <span>{currentIndex < 0 ? '未选任务' : '第 ' + (currentIndex + 1) + ' 道匹配'}</span><Button className="btn plan-icon" icon="chevron-right" aria-label="下一匹配任务" disabled={!model.tasks.length || currentIndex >= model.tasks.length - 1} onClick={() => move(1)} /></span>
        </div>
      </div>
      {hover && <div role="tooltip" className="plan-tooltip" style={{ left: Math.max(8, Math.min(hover.x + 12, window.innerWidth - 335)), top: Math.max(8, Math.min(hover.y + 16, window.innerHeight - 300)), maxHeight: 'calc(100vh - 16px)', overflow: 'auto', overflowWrap: 'anywhere' }}>
        {(hover.before ? '初始计划\n' : '') + M.taskTitle(hover.task, model.labels, !hover.before && model.conflicts.has(hover.task.task_ref))}</div>}
    </div>;
  }
  window.PlanGantt = PlanGantt;
  window.PlanSegmentUI = Segment;
})();
