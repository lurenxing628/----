(function () {
  'use strict';
  // Axis numbers encode factory-local wall-clock fields; UTC extraction must not shift them to the browser timezone.
  const U = window.TrialControls, { TimelineZoom } = window.ResourceControls, ZOOM_MAX = 8, wall = window.PlanGanttModel.instant;
  const EMPTY_SCOPE = {};
  const pieceLabel = t => t.piece_id === null ? '共同工序' : '分件 ' + t.piece_id;
  const taskLabel = t => t.batch_id + ' · ' + t.sequence + ' ' + t.process_label + ' · ' + pieceLabel(t);
  function resourceNames(data) {
    const names = new Map(); ['machines', 'operators'].forEach(k => data.resources[k].forEach(r => names.set(r.ref, r.business_code + ' · ' + (r.label || '名称未填写'))));
    return ref => ref === null ? '无内部资源' : names.get(ref) || '原资源名称不可读';
  }
  const matchesScope = (task, scope, batchRefs) => (!scope.range_start || window.PointContract.overlaps(task, scope.range_start, scope.range_end))
    && (!batchRefs || batchRefs.has(task.batch_ref))
    && (!scope.resource_ref || (scope.resource_type === 'batch' ? task.batch_ref : task[scope.resource_type + '_ref']) === scope.resource_ref);
  const matchesQuery = (task, needle, name) => !needle
    || [task.batch_id, task.part_no, task.part_name, task.process_label, task.piece_id, name(task.machine_ref), name(task.operator_ref)].join(' ').toLowerCase().includes(needle);
  function matching(data, scope, query, changed, name, batchRefs) {
    const needle = query.trim().toLowerCase();
    return data.tasks.filter(t => (!changed || t.changed) && matchesScope(t, scope, batchRefs) && matchesQuery(t, needle, name));
  }
  function Gantt({ data, selected, onSelect, detailsOpen, onToggleDetails }) {
    const V = window.TrialViewState, preferences = V.useView(data);
    // When the local preference cannot be read, the gantt still renders with defaults and view changes stay on this page.
    const [local, setLocal] = React.useState(null), values = preferences.value || local || V.defaults(data);
    // A trial compares with its own original arrangements, not the official plan at creation.
    const hasOriginal = data.tasks.length > 0;
    const view = values.mode, baseline = hasOriginal && values.baseline, changed = hasOriginal && values.only_changed, query = values.query;
    const update = patch => { if (!preferences.change(patch)) setLocal({ ...values, ...patch }); };
    const setView = mode => update({ mode }), setBaseline = baseline => update({ baseline });
    const setChanged = only_changed => update({ only_changed }), setQuery = query => update({ query });
    const [limit, setLimit] = React.useState(true);
    const [page, setPage] = React.useState(1), [zoom, setZoom] = React.useState(1);
    const { expanded, toggle: toggleExpanded } = window.GanttPresentationUI.useExpanded();
    const [chart, setChart] = React.useState({ width: 1000, viewport: 1000, left: 0 });
    const [hover, setHover] = React.useState(null);
    const name = React.useMemo(() => resourceNames(data), [data.resources]);
    const scope = limit ? data.scope : EMPTY_SCOPE;
    const batchRefs = React.useMemo(() => scope.batch_refs ? new Set(scope.batch_refs) : null, [scope.batch_refs]);
    const filtered = React.useMemo(() => matching(data, scope, query, changed, name, batchRefs), [data, scope, query, changed, name, batchRefs]);
    const key = view === 'batch' ? 'batch_ref' : view + '_ref', board = React.useRef(null), axisHost = React.useRef(null);
    const rows = React.useMemo(() => {
      const entries = [];
      filtered.forEach(t => {
        entries.push({ t, group: t[key], ghost: false });
        if (baseline && view !== 'batch' && t.original[key] !== t[key]) entries.push({ t, group: t.original[key], ghost: true });
      });
      return entries.sort((a, b) => String(a.group).localeCompare(String(b.group)) || a.t.start.localeCompare(b.t.start) || a.t.task_ref.localeCompare(b.t.task_ref));
    }, [filtered, view, baseline]);
    const current = Math.min(page, Math.max(1, Math.ceil(rows.length / 30))), visible = rows.slice((current - 1) * 30, current * 30);
    const bounds = React.useMemo(() => {
      let start = Infinity, end = -Infinity;
      data.tasks.forEach(t => { start = Math.min(start, wall(t.start), wall(t.original.start)); end = Math.max(end, wall(t.end), wall(t.original.end)); });
      const pad = Math.max(60000, (end - start) * .025); return { start: start - pad, end: end + pad };
    }, [data]);
    const axis = window.GanttPresentation.axis({ ...bounds, ...chart });
    const measure = () => {
      const node = board.current, track = axisHost.current;
      if (node && track) setChart({ width: track.clientWidth, viewport: node.clientWidth - node.querySelector('.tt-corner').getBoundingClientRect().width, left: node.scrollLeft });
    };
    React.useLayoutEffect(() => {
      measure(); const observer = new ResizeObserver(measure); observer.observe(board.current); observer.observe(axisHost.current);
      return () => observer.disconnect();
    }, []);
    const position = t => ({ left: (wall(t.start) - bounds.start) / (bounds.end - bounds.start) * 100 + '%', width: (wall(t.end) - wall(t.start)) / (bounds.end - bounds.start) * 100 + '%' });
    const pointTitle = (t, original) => (original ? '原安排 · ' : '') + taskLabel(t) + '\n'
      + U.timeLabel((original ? t.original : t).start) + '\n零工时工序 · 0 小时 · 不占设备人员';
    function pointMarker(t, original) {
      const value = original ? t.original : t, title = pointTitle(t, original);
      return <window.PointGantt.Marker task={original ? { ...t, start: value.start, end: value.end } : t} data-task-ref={original ? undefined : t.task_ref} data-baseline-ref={original ? t.task_ref : undefined}
        title={title} x={position(value).left} top={original ? 46 : 15} tone={original ? 'before' : t.issues.length ? 'critical' : t.locked ? 'success' : ''}
        selected={selected === t.task_ref} onSelect={() => { setHover(null); onSelect(t.task_ref); }}
        onHover={event => setHover(event ? { title, x: event.clientX, y: event.clientY } : null)} />;
    }
    const { selectedIndex, hiddenSelectedTask } = React.useMemo(() => {
      const selectedIndex = selected ? rows.findIndex(row => !row.ghost && row.t.task_ref === selected) : -1;
      return { selectedIndex, hiddenSelectedTask: selected && selectedIndex < 0 ? data.tasks.find(task => task.task_ref === selected) || null : null };
    }, [rows, selected, data.tasks]);
    React.useEffect(() => {
      if (selectedIndex >= 0) setPage(Math.floor(selectedIndex / 30) + 1);
    }, [selected, selectedIndex]);
    function showSelected() {
      const patch = {};
      if (changed && !hiddenSelectedTask.changed) patch.only_changed = false;
      if (!matchesQuery(hiddenSelectedTask, query.trim().toLowerCase(), name)) patch.query = '';
      if (Object.keys(patch).length) update(patch);
      if (limit && !matchesScope(hiddenSelectedTask, scope, batchRefs)) setLimit(false);
    }
    function bar(t) {
      const width = (wall(t.end) - wall(t.start)) / (bounds.end - bounds.start) * chart.width;
      const lines = window.GanttPresentation.taskLines({ sequence: t.sequence, process: t.process_label, batch: t.batch_id,
        piece: pieceLabel(t), resource: name(t.machine_ref) }, view, width);
      return <button type="button" className={'tt-bar' + (t.issues.length ? ' conflict' : '') + (t.locked ? ' locked' : '')}
        data-task-ref={t.task_ref} aria-label={'安排时段 ' + taskLabel(t)} aria-pressed={selected === t.task_ref}
        title={taskLabel(t) + '\n本工序目标量 ' + U.number(t.quantity) + ' · 整批量 ' + U.number(t.batch_quantity) + '\n' + U.timeLabel(t.start) + ' 至 ' + U.timeLabel(t.end)} style={position(t)} onClick={() => onSelect(t.task_ref)}>
        <span className="tt-bar-face"><strong>{lines.primary}</strong>{lines.secondary && <small>{lines.secondary}</small>}{t.locked && <i className="tt-lock-mark" aria-hidden="true" />}</span>
      </button>;
    }
    return <section className={'tt-gantt' + (expanded ? ' tt-expanded' : '')} aria-label="试调甘特">
      <V.Notice state={preferences} label="试调甘特查看偏好" /><div className="tt-tools tt-gantt-tools"><U.Tabs value={view} label="甘特分组"
      options={[["machine", '设备'], ['operator', '人员'], ['batch', '批次']]} onChange={v => { setView(v); setPage(1); }} />
      {hasOriginal && <><label className="tt-check"><input type="checkbox" checked={baseline} onChange={e => setBaseline(e.target.checked)} />对照原安排</label>
      <label className="tt-check"><input type="checkbox" checked={changed} onChange={e => { setChanged(e.target.checked); setPage(1); }} />仅变更</label></>}
      {!!Object.keys(data.scope).length && <label className="tt-check"><input type="checkbox" checked={limit} onChange={e => { setLimit(e.target.checked); setPage(1); }} />原显示范围</label>}
      <input type="search" aria-label="搜索试调工序" placeholder="批次 / 工序 / 资源" maxLength={200} value={query} onChange={e => { setQuery(e.target.value); setPage(1); }} />
      <TimelineZoom zoom={zoom} max={ZOOM_MAX} scope="试调" onZoom={setZoom} onFit={() => setZoom(1)} />
      <U.Button icon="chart-gantt" aria-label={expanded ? '收起甘特' : '展开甘特'} aria-expanded={expanded} onClick={toggleExpanded}>{expanded ? '收起' : '展开'}</U.Button>
      {onToggleDetails && <U.Button icon={detailsOpen ? 'panel-right-close' : 'panel-right-open'} aria-expanded={detailsOpen} aria-controls="trial-gantt-detail" onClick={onToggleDetails}>{detailsOpen ? '收起详情' : '详情'}</U.Button>}</div>
      {hiddenSelectedTask && <div className="tt-notice" role="status"><span>选中工序在当前筛选范围外。</span><U.Button icon="eye" onClick={showSelected}>显示并定位选中工序</U.Button></div>}
      <div className="tt-board" ref={board} onScroll={() => { setHover(null); measure(); }}><div className="tt-timeline" style={{ width: zoom === 1 ? '100%' : zoom * 100 + '%' }}>
        <div className="tt-axis"><div className="tt-corner">工序 / 资源</div><div className="tt-ticks" ref={axisHost}><window.GanttPresentationUI.Axis axis={axis} width={chart.width} /></div></div>
        {visible.map((r, i) => <React.Fragment key={r.t.task_ref + ':' + r.ghost}>{(i === 0 || visible[i - 1].group !== r.group) && <div className="tt-group">{view === 'batch' ? r.t.batch_id + ' · ' + (r.t.part_name || '零件名称未填写') : name(r.group)}</div>}
          <div className={'tt-gantt-row' + (selected === r.t.task_ref ? ' selected' : '')} data-trial-task={r.t.task_ref} data-show-baseline={baseline || undefined}>
            <button type="button" className="tt-task-label" onClick={() => onSelect(r.t.task_ref)} aria-pressed={selected === r.t.task_ref}
              aria-label={'选择工序 ' + taskLabel(r.t)} title={taskLabel(r.t) + '\n本工序目标量 ' + U.number(r.t.quantity) + ' · 整批量 ' + U.number(r.t.batch_quantity)}>
              <strong>{r.t.sequence} {r.t.process_label}</strong><small>{r.t.batch_id} · {pieceLabel(r.t)}{r.ghost ? ' · 原资源' : ''}</small></button>
            <div className="tt-track">{axis.ticks.map(tick => <i key={tick.at} className="tt-gridline" style={{ left: tick.x / chart.width * 100 + '%' }} />)}
              {!r.ghost && (window.PointContract.isPoint(r.t) ? pointMarker(r.t, false) : bar(r.t))}
              {baseline && (view === 'batch' || r.ghost || r.t.original[key] === r.group) && (window.PointContract.isPoint(r.t) ? pointMarker(r.t, true) : <span className="tt-baseline" data-baseline-ref={r.t.task_ref} role="img"
                style={position(r.t.original)} aria-label={'原安排 ' + taskLabel(r.t) + '，' + U.timeLabel(r.t.original.start) + ' 至 ' + U.timeLabel(r.t.original.end)} title={'原安排 ' + taskLabel(r.t) + '\n' + U.timeLabel(r.t.original.start) + ' 至 ' + U.timeLabel(r.t.original.end)} />)}</div></div></React.Fragment>)}
        {!visible.length && <div className="tt-empty">当前显示范围没有匹配工序</div>}</div></div>
      <div className="tt-heading"><div className="tt-legend"><span><i />试调安排</span>{baseline && <span><i className="baseline" />原安排</span>}<span><i className="conflict" />约束问题</span><span><i className="locked" />已锁定</span></div>
        <span className="tt-muted">{filtered.length === data.task_count ? '已安排 ' + data.task_count + ' 道工序' : '显示 ' + filtered.length + ' / ' + data.task_count + ' 道工序'}</span></div>
      <U.Pager page={{ number: current, size: 30, total: rows.length }} label="甘特" onPage={setPage} />
      {hover && <div role="tooltip" className="tt-point-tooltip" style={{ left: Math.max(8, Math.min(innerWidth - 335, hover.x + 12)), top: Math.max(8, Math.min(innerHeight - 160, hover.y + 14)) }}>{hover.title}</div>}
    </section>;
  }
  window.TrialGantt = Gantt; window.TrialGantt.resourceNames = resourceNames;
})();
