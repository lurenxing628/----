(function () {
  'use strict';
  const M = window.RunCandidateModel, B = window.RunBaselineModel, BC = window.RunBaselineControls, { Button } = window.RunCandidateControls;
  function PointLane({ row, model, width, left, viewport, selected, baselineSelected, onSelect, onHover }) {
    const scale = width / (model.end - model.start), G = window.PointGanttModel;
    const items = G.visible(row.items, model.start + left / scale, model.start + (left + viewport) / scale, scale);
    return <div data-candidate-point-lane style={{ position: 'absolute', left, width: viewport, height: row.height, overflow: 'hidden' }}>
      {items.map(item => <window.PointGantt.Marker key={item.task.row_ref} task={item.task} title={M.title(item.task)}
        x={(item.start - model.start) * scale - left} selected={baselineSelected ? baselineSelected.comparison.operation_ref === item.task.operation_ref : selected && selected.row_ref === item.task.row_ref}
        onSelect={() => onSelect(item.task)} onHover={event => onHover(event ? { text: M.title(item.task), x: event.clientX, y: event.clientY } : null)} />)}
    </div>;
  }
  function Lane({ row, model, width, left, viewport, selected, baselineSelected, onSelect, onBaselineSelect, onHover }) {
    const ref = React.useRef(null), scale = width / (model.end - model.start);
    const items = M.visibleItems(row.items, model.start + left / scale, model.start + (left + viewport) / scale);
    React.useLayoutEffect(() => {
      function paint() {
        const node = ref.current, ratio = devicePixelRatio || 1, w = Math.max(1, viewport), h = row.height;
        node.width = Math.round(w * ratio); node.height = h * ratio;
        const ctx = node.getContext('2d'); ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        const styles = getComputedStyle(node), value = k => styles.getPropertyValue(k).trim();
        for (const item of items) {
          const x = (item.start - model.start) * scale - left, barWidth = (item.end - item.start) * scale;
          if (row.baseline) {
            const chosen = baselineSelected ? baselineSelected.comparison.operation_ref === item.comparison.operation_ref : selected && selected.operation_ref === item.comparison.operation_ref;
            ctx.save(); ctx.beginPath(); ctx.rect(x, 0, barWidth, h); ctx.clip();
            ctx.strokeStyle = value(chosen ? '--wb-gantt-gold' : '--ui-text'); ctx.lineWidth = chosen ? 2 : 1; ctx.setLineDash([4, 3]);
            ctx.strokeRect(x + Math.min(barWidth, ctx.lineWidth) / 2, 11, Math.max(0, barWidth - Math.min(barWidth, ctx.lineWidth)), 7); ctx.restore();
            continue;
          }
          const tone = item.task.source === 'external' ? 'plan' : row.normalLaneCount > 1 ? 'critical' : 'primary';
          const chosen = baselineSelected ? baselineSelected.comparison.operation_ref === item.task.operation_ref : item.task.row_ref === (selected && selected.row_ref);
          ctx.fillStyle = value('--wb-gantt-' + tone + '-fill'); ctx.fillRect(x, 7, barWidth, 33);
          ctx.strokeStyle = value(chosen ? '--wb-gantt-gold' : '--wb-gantt-' + tone + '-edge');
          ctx.lineWidth = Math.min(barWidth, chosen ? 2 : 1);
          ctx.strokeRect(x + ctx.lineWidth / 2, 7 + ctx.lineWidth / 2, Math.max(0, barWidth - ctx.lineWidth), 33 - ctx.lineWidth);
          if (barWidth > 80) {
            ctx.save(); ctx.beginPath(); ctx.rect(Math.max(0, x + 4), 9, Math.max(0, Math.min(w, x + barWidth) - Math.max(0, x + 4) - 4), 28); ctx.clip();
            ctx.fillStyle = value('--ui-text'); ctx.font = '11px sans-serif';
            ctx.fillText(M.pieceLabel(item.task) + ' · ' + (item.task.batch_label || '未记录') + ' · ' + M.number(item.task.sequence), Math.max(4, x + 5), 28); ctx.restore();
          }
        }
      }
      paint(); const theme = new MutationObserver(paint); theme.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'class'] });
      return () => theme.disconnect();
    }, [row, model, width, left, viewport, selected, baselineSelected]);
    function hit(event) { const box = ref.current.getBoundingClientRect(), at = model.start + (event.clientX - box.left + left) / scale; return M.visibleItems(row.items, at, at + 0.001)[0]; }
    const choose = item => row.baseline ? onBaselineSelect(item) : onSelect(item.task);
    const selectedItem = row.items.find(item => !row.baseline && selected && item.task.row_ref === selected.row_ref);
    return <canvas ref={ref} data-candidate-lane={row.baseline ? undefined : true} data-baseline-lane={row.baseline ? true : undefined} data-item-count={row.items.length} role="button" tabIndex={0} aria-label={(row.baseline ? '初始计划 ' : '') + row.label + '，第 ' + (row.lane + 1) + ' 轨，' + row.items.length + ' 道安排' + (selectedItem ? '\n' + M.title(selectedItem.task) : '')}
      style={{ position: 'absolute', left, width: viewport, height: row.height }}
      onMouseMove={event => { const item = hit(event); onHover(item ? { text: row.baseline ? B.title(item) : M.title(item.task), x: event.clientX, y: event.clientY } : null); }} onMouseLeave={() => onHover(null)}
      onClick={event => { const item = hit(event); if (item) choose(item); }}
      onKeyDown={event => {
        if (!['Enter', ' ', 'Home', 'End', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
        event.preventDefault(); const index = row.items.findIndex(i => row.baseline ? i.segment.row_ref === (baselineSelected && baselineSelected.segment && baselineSelected.segment.row_ref) : i.task.row_ref === (selected && selected.row_ref));
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? row.items.length - 1 : ['Enter', ' '].includes(event.key) ? Math.max(0, index) : Math.max(0, Math.min(row.items.length - 1, index + (event.key === 'ArrowLeft' ? -1 : 1)));
        choose(row.items[next]);
      }} />;
  }
  function TaskList({ tasks, selected, onSelect, planned }) {
    const [top, setTop] = React.useState(0), height = 44, first = Math.max(0, Math.floor(top / height) - 3), end = Math.min(tasks.length, first + 16);
    return <><div className="rc-muted">{tasks.length} 道{planned ? '安排' : '未安排工序'}</div>
      <div className="rc-list-row rc-muted" aria-hidden="true"><span>批次 / 零件</span><span>工序</span><span>{planned ? '开始 / 结束' : '状态 / 原因'}</span><span>{planned ? '设备 / 人员' : '生成时执行'}</span><span>详情</span></div>
      <div className="rc-list" data-candidate-task-list role="region" aria-label={planned ? '候选任务安排' : '候选未安排明细'} onScroll={e => setTop(e.currentTarget.scrollTop)}>
        <div style={{ height: tasks.length * height, position: 'relative', minWidth: 720 }}>
          {tasks.slice(first, end).map((t, i) => <div key={t.row_ref || t.operation_ref} className="rc-list-row" data-row-ref={t.row_ref || undefined} data-operation-ref={t.operation_ref}
            aria-selected={selected && (t.row_ref ? selected.row_ref === t.row_ref : selected.operation_ref === t.operation_ref)} style={{ position: 'absolute', top: (first + i) * height, left: 0, right: 0 }}>
            <span title={(t.batch_label || '未记录') + '\n' + (t.part_label || '未记录')}>{t.batch_label || '未记录'}<small>{t.part_label || '未记录'}</small></span>
            <span title={M.number(t.sequence) + ' ' + (t.process_label || '未记录') + '\n' + M.pieceLabel(t)}>{M.pieceLabel(t)}<small>{M.number(t.sequence)} {t.process_label || '未记录'}</small></span>
            <span title={planned ? M.title(t) : t.reason.message}>{planned ? <>{M.timeLabel(t.start)}<small>{window.PointContract.isPoint(t) ? '时间点 · 0 h · 不占用资源' : M.timeLabel(t.end)}</small></> : t.reason.message}</span>
            <span title={planned ? (t.machine && t.machine.label || '未记录') + '\n' + (t.operator && t.operator.label || '未记录') : ''}>{planned ? <>{t.machine && t.machine.label || '设备未记录'}<small>{t.operator && t.operator.label || '人员未记录'}</small></> : t.execution_at_generation ? M.executionValue(t.execution_at_generation.execution_state) : '未记录'}</span>
            <Button icon="search" className="mini" aria-label={'工序详情 ' + (t.row_ref || t.operation_ref)} onClick={() => onSelect(t)}>详情</Button></div>)}
        </div>{!tasks.length && <div className="rc-empty">当前预览没有匹配记录。</div>}</div></>;
  }
  function RunCandidateGantt({ data, query, selected, onSelect }) {
    const [mode, setMode] = React.useState('machine'), [zoom, setZoom] = React.useState(1), [viewport, setViewport] = React.useState(600);
    const [scroll, setScroll] = React.useState({ left: 0, top: 0 }), [hover, setHover] = React.useState(null), host = React.useRef(null), owner = React.useRef(null);
    const baseline = BC.useBaseline(data), [selection, setSelection] = React.useState(null), result = baseline.result;
    const chosen = selection && selection.result === result && B.matching([selection.item.comparison], query).length ? selection.item : null;
    const labelWidth = 156, width = Math.max(1, viewport) * zoom;
    const candidate = React.useMemo(() => M.layout(data, mode, query, width), [data, mode, query, width]);
    const model = React.useMemo(() => window.PointGanttModel.candidateRows(B.compose(candidate, result && result.data, mode, query), width), [candidate, result, mode, query, width]);
    function selectBaseline(item) { setSelection(item ? { item, result } : null); if (item) onSelect(null); setHover(null); }
    function selectCandidate(task) { setSelection(null); onSelect(task); }
    React.useLayoutEffect(() => {
      const observe = new ResizeObserver(() => setViewport(Math.max(1, owner.current.clientWidth - labelWidth))); observe.observe(host.current); observe.observe(owner.current);
      return () => observe.disconnect();
    }, []);
    React.useLayoutEffect(() => { if (owner.current) { owner.current.scrollTop = 0; owner.current.scrollLeft = 0; } setScroll({ left: 0, top: 0 }); setHover(null); }, [mode, query, data, result]);
    React.useLayoutEffect(() => {
      const loc = chosen && chosen.segment ? model.baselineLocations.get(chosen.segment.row_ref) : selected && model.locations.get(selected.row_ref), node = owner.current;
      if (!node || !loc) return;
      if (loc.top < node.scrollTop || loc.top + 48 > node.scrollTop + 288) node.scrollTop = loc.top;
      const x = (loc.item.start - model.start) / (model.end - model.start) * width;
      if (x < node.scrollLeft || x > node.scrollLeft + viewport) node.scrollLeft = Math.max(0, x - viewport / 3);
    }, [selected, chosen, model, width, viewport]);
    function pan(left) { if (owner.current) owner.current.scrollLeft = Math.max(0, Math.min(width - viewport, left)); }
    const visible = M.visibleRows(model.rows, scroll.top - 48, scroll.top + 384);
    const tickRows = model.start === null ? [] : M.ticks(model.start, model.end, width, scroll.left, viewport);
    return <section ref={host} className="rc-gantt" aria-label="候选甘特预览"><window.PointGantt.Styles /><style>{`
      .rc-gantt{min-width:0}.rc-gantt .rc-axis{height:40px;overflow:hidden;border-bottom:1px solid var(--ui-border);position:relative;margin-left:156px}.rc-gantt .rc-tick{position:absolute;top:0;white-space:nowrap;color:var(--ui-info-muted);font-size:10px;line-height:18px;border-left:1px solid var(--ui-border);padding-left:4px}
      .rc-gantt .rc-scroll{height:310px;overflow:auto;position:relative;border-bottom:1px solid var(--ui-border);outline-offset:-2px}.rc-gantt .rc-lane{position:absolute;left:0;right:0;border-bottom:1px solid var(--ui-border);height:48px}.rc-gantt .rc-lane-label{position:sticky;left:0;width:156px;height:47px;padding:7px 8px;background:var(--ui-surface);border-right:1px solid var(--ui-border);z-index:2;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.rc-gantt .rc-lane-label small{white-space:nowrap}.rc-gantt .rc-bar-space{position:absolute;left:156px;top:0;height:48px}
      .rc-gantt .rc-overview{width:100%;height:32px;border-bottom:1px solid var(--ui-border)}.run-candidate-workspace .rc-tooltip{position:fixed;pointer-events:none;z-index:10030;max-width:350px;max-height:calc(100vh - 16px);overflow:auto;padding:10px 12px;border:1px solid var(--ui-border);border-radius:4px;background:var(--ui-surface);color:var(--ui-text);white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;line-height:1.6;box-shadow:0 3px 12px #0002}
    `}</style><div className="rc-heading"><div role="group" className="rc-tabs" aria-label="候选甘特维度">{Object.entries(M.kindLabels).map(([key, label]) =>
      <Button key={key} aria-pressed={mode === key} onClick={() => setMode(key)}>{label}</Button>)}</div>
      <div className="rc-tools"><BC.Toggle state={baseline} /><Button icon="minus" aria-label="缩小候选时间轴" disabled={zoom <= 1} onClick={() => setZoom(z => Math.max(1, z / 2))} />
        <input type="range" aria-label="候选时间轴缩放" min="1" max="128" step="1" value={zoom} style={{ width: 100 }} onChange={e => setZoom(Number(e.target.value))} />
        <Button icon="plus" aria-label="放大候选时间轴" disabled={zoom >= 128} onClick={() => setZoom(z => Math.min(128, z * 2))} />
        <Button icon="chart-gantt" aria-label="适配完整候选时间轴" disabled={zoom === 1} onClick={() => { setZoom(1); pan(0); }} /></div></div>
      <BC.Panel state={baseline} rows={model.comparisons || []} chosen={chosen} onChoose={selectBaseline} workspace={data} />
      <div className="rc-muted">{model.groupCount} 组 · {model.rows.length} 轨 · 重叠拆轨（不等同于业务冲突结论） · 外协独立色</div>
      {model.start !== null && <div className="rc-heading rc-muted"><span>{M.timeLabel(M.wire(model.start))}</span><span>{M.timeLabel(M.wire(model.end))}</span></div>}
      <div className="rc-axis">{tickRows.map(t => <span key={t.at} className="rc-tick" style={{ left: t.x - scroll.left }}>{t.label.slice(5, 10)}<br />{t.label.slice(11)}</span>)}</div>
      <div ref={owner} className="rc-scroll" data-candidate-gantt-scroll role="region" aria-label="候选时间安排" tabIndex={0}
        onScroll={e => { setScroll({ left: e.currentTarget.scrollLeft, top: e.currentTarget.scrollTop }); setHover(null); }}>
        <div style={{ position: 'relative', width: width + labelWidth, height: Math.max(288, model.height) }}>
          {visible.map(row => <div key={row.key} className="rc-lane" data-candidate-track={row.baseline ? undefined : row.key} data-baseline-track={row.baseline ? row.key : undefined} style={{ top: row.top, height: row.height }}><div className="rc-lane-label" style={{ height: row.height - 1, paddingTop: row.baseline ? 5 : 7 }} title={row.label + (row.baseline ? ' · 初始计划' : '')}>{row.label}{row.baseline ? ' · 初始' : <small>第 {row.lane + 1} / {row.laneCount} 轨 · {row.items.length} 道安排</small>}</div>
            <div className="rc-bar-space" style={{ width, height: row.height, overflow: 'hidden' }}>{React.createElement(row.point ? PointLane : Lane, { row, model, width, left: scroll.left, viewport, selected, baselineSelected: chosen, onSelect: selectCandidate, onBaselineSelect: selectBaseline, onHover: setHover })}</div></div>)}
          {!model.rows.length && <div className="rc-empty">没有可绘制的匹配安排；未安排与失败记录仍保留在明细中。</div>}</div></div>
      <input type="range" aria-label="候选时间轴水平位置" style={{ width: '100%' }} min="0" max={Math.max(0, width - viewport)} step="any" value={Math.min(scroll.left, Math.max(0, width - viewport))} disabled={zoom === 1} onChange={e => pan(Number(e.target.value))} />
      {window.PointContract.isPoint(selected) && <dl className="rc-meta" data-candidate-point-facts><div><dt>安排类型</dt><dd>时间点</dd></div><div><dt>发生时间</dt><dd>{M.timeLabel(selected.start)}</dd></div><div><dt>本工序占用</dt><dd>0 h · 不占用资源</dd></div></dl>}
      {hover && <div role="tooltip" className="rc-tooltip" style={{ left: Math.max(8, Math.min(innerWidth - 358, hover.x + 12)), top: Math.max(8, Math.min(innerHeight - 238, hover.y + 14)) }}>{hover.text}</div>}
    </section>;
  }
  RunCandidateGantt.TaskList = TaskList;
  window.RunCandidateGantt = RunCandidateGantt;
})();
