(function () {
  'use strict';
  const M = window.ActualGanttModel, { Button } = window.ResourceControls;
  function emptyReports(row, mode) {
    const execution = row.item.execution;
    if (!execution) return '报工记录不可用';
    if (mode !== 'batch') {
      const resource = M.views[mode];
      if (execution.reports.length) {
        const field = 'actual_' + mode + '_ref', bound = execution.reports.some(report => report[field]);
        const unbound = execution.reports.some(report => !report[field]);
        return '本' + resource + '暂无报工；报工在' + (bound ? '其他' + resource + (unbound ? '及' : '') : '') + (unbound ? '“' + resource + '未填写”分组' : '下');
      }
      return '本' + resource + '暂无报工' + (execution.legacy_facts.length ? '；工序有历史现场记录，不是逐次报工' : '');
    }
    return execution.legacy_facts.length ? '历史现场记录保留，不是逐次报工' : '暂无实际报工';
  }
  function Bar({ mark, row, model, width, selected, onSelect, onHover, canvasPainted = false }) {
    const box = window.ActualGanttWindow.markBox(mark, model, width), { x, size } = box;
    const kind = { actual: 'act', plan: 'plan', remaining: 'remaining' }[mark.kind];
    const title = M.markTitle(mark, row.item, model.labels);
    function atPointer(event) {
      const track = event.currentTarget.closest('.fg-track').getBoundingClientRect();
      return window.ActualGanttWindow.hitMark(M.marks(row), model, width, 0, event.clientX - track.left, event.clientY - track.top);
    }
    function hover(event) {
      if (!event) { onHover(null); return; }
      const target = event.type === 'focus' ? mark : atPointer(event);
      if (!target) { onHover(null); return; }
      const rect = event.currentTarget.getBoundingClientRect();
      onHover({ item: row.item, report: target.report, title: M.markTitle(target, row.item, model.labels), x: rect.right, y: rect.top });
    }
    if (mark.kind === 'plan-point' || mark.kind === 'point') return <window.PointGantt.Marker
      task={mark.report ? { task_ref: mark.report.report_ref, start: mark.report.actual_start } : row.item.task}
      x={x} top={mark.y} title={title} tone={(mark.kind === 'plan-point' ? 'plan' : '') + (canvasPainted ? ' fg-canvas-point' : '')} selected={selected === row.item.task.task_ref}
      data-actual-mark={mark.kind} data-report-ref={mark.report && mark.report.report_ref} data-task-ref={row.item.task.task_ref}
      onSelect={() => onSelect(row.item, mark.report)} onHover={hover} onFocus={hover} onBlur={() => onHover(null)} />;
    return <button className={'fg-mark fg-' + kind} data-actual-mark={mark.kind} data-report-ref={mark.report && mark.report.report_ref} data-task-ref={row.item.task.task_ref}
      data-duration-ms={mark.end - mark.start} data-duration-width={size}
      style={{ left: box.hitLeft, width: box.hitWidth, top: mark.y, height: mark.height }}
      title={title} aria-label={title} aria-pressed={selected === row.item.task.task_ref} onClick={event => {
        const target = event.detail === 0 ? mark : atPointer(event); if (target) onSelect(row.item, target.report);
      }} onMouseEnter={hover} onMouseMove={hover} onMouseLeave={() => onHover(null)} onFocus={hover} onBlur={() => onHover(null)}>
      <span className="fg-mark-face" style={{ left: box.faceLeft, width: size }}>{size >= 55 && mark.kind !== 'plan' && <><span>{mark.report ? mark.report.report_no : '剩余 ' + M.number(row.item.execution.remaining_quantity) + ' 件'}</span>
        {size >= 150 && <span>{mark.report ? M.number(mark.report.completed_quantity) + ' 件 · ' + M.hours(mark.report.effective_processing_hours) : M.time(row.item.execution.remaining_plan.start)}</span>}</>}</span>
    </button>;
  }
  function ChainLines({ chain, model, width, labelWidth, top, height }) {
    const paths = chain.edges.flatMap(edge => {
      const from = model.locations.get(edge.from_task_ref), to = model.locations.get(edge.to_task_ref);
      if (!from || !to || !from.baseline || !to.baseline || Math.min(from.top, to.top) > top + height || Math.max(from.top, to.top) + 88 < top) return [];
      const x = value => (M.instant(value) - model.start) / (model.end - model.start) * width;
      const a = x(from.item.task.end), b = x(to.item.task.start), middle = Math.max(a + 8, (a + b) / 2);
      return [{ ...edge, d: 'M' + a + ',' + (from.top + 78) + ' H' + middle + ' V' + (to.top + 78) + ' H' + b }];
    });
    return <svg className="fg-chain-lines" style={{ left: labelWidth, top: 52 }} width={width} height={model.height} role="img" aria-label="当前计划关键链连线">
      {paths.map(edge => <path key={edge.from_task_ref + ':' + edge.to_task_ref} d={edge.d} data-chain-edge={edge.edge_type}
        strokeDasharray={edge.edge_type === 'process' ? undefined : '4 3'}><title>{edge.reason} · 间隔 {edge.gap_minutes} 分钟</title></path>)}
    </svg>;
  }
  function Rows({ model, view, width, viewport, left, top, height, labelWidth, dense, onSelect, onHover, onChainTarget, chain, patch }) {
    const visible = M.visibleRows(model.rows, Math.max(0, top - 100), top + height + 100), ticks = M.ticks(model, width, left, viewport);
    return <>{visible.map(row => {
      const style = { top: row.top + 52, height: row.height, width: width + labelWidth };
      if (row.kind === 'group') return <div key={row.key} className="fg-virtual-row fg-group-row" style={style} data-resource={row.group.id}>
        <div className="fg-frozen" onMouseEnter={() => onChainTarget(Array.from(row.group.members.keys()))} onMouseLeave={() => onChainTarget(null)}><Button className="fg-icon-button" icon={view.collapsed[row.group.id] ? 'chevron-right' : 'chevron-down'} aria-label={(view.collapsed[row.group.id] ? '展开 ' : '折叠 ') + row.group.label}
          aria-expanded={!view.collapsed[row.group.id]} onClick={() => patch({ collapsed: { ...view.collapsed, [row.group.id]: !view.collapsed[row.group.id] } })} />
          <strong className="fg-resource-label" title={row.group.label}>{row.group.label}</strong></div><div className="fg-group-summary">{row.group.members.size} 道工序 · {model.executionAvailable ? row.group.reportCount + ' 次报工 · ' + (row.group.knownHours === null ? '实报工时未知' : '已知实报工时 ' + M.hours(row.group.knownHours)) + (row.group.unknownHours ? ' · ' + row.group.unknownHours + ' 条工时待补' : '') + (row.group.legacyCount ? ' · ' + row.group.legacyCount + ' 条历史记录' : '') : '报工记录不可用'}</div></div>;
      const { item } = row, e = item.execution, t = item.task, marks = M.marks(row);
      const renderMark = (mark, canvasPainted = false) => <Bar key={mark.key} {...{ mark, row, model, width, onSelect, onHover, canvasPainted }} selected={view.selected} />;
      const pending = window.PointContract.isPoint(t) ? '零工时工序已安排 · 完成待确认' : '待续排';
      const nowX = (model.asOf - model.start) / (model.end - model.start) * width;
      const timing = M.deadlines(item, M.wire(model.asOf));
      return <div key={row.key} className={'fg-virtual-row' + (view.selected === t.task_ref ? ' is-selected' : '')} data-task-row={t.task_ref} data-kind={row.kind} style={style}>
        <div className="fg-frozen"><button className="fg-task-select" title={M.taskLabel(t)} onClick={() => onSelect(item, row.reports[0])}
          onMouseEnter={() => onChainTarget([t.task_ref])} onMouseLeave={() => onChainTarget(null)} onFocus={() => onChainTarget([t.task_ref])} onBlur={() => onChainTarget(null)}>{M.taskLabel(t)}</button>
          <span className="fg-row-caption" title={'计划应做 ' + M.number(t.quantity) + ' 件 · 批次 ' + M.number(t.batch_quantity) + ' 件'}>{row.kind === 'remaining' ? '执行剩余 ' + M.number(e.remaining_quantity) + ' 件' : e ? M.states[e.execution_state] + ' · 已知 ' + M.number(e.known_completed_quantity) + ' / 计划 ' + M.number(t.quantity) : '计划应做 ' + M.number(t.quantity) + ' 件 · 报工记录不可用'}</span>
          <span className="fg-row-caption" title={!row.reports.length && row.kind === 'actual' ? emptyReports(row, view.mode) : undefined}>{row.kind === 'remaining' ? e.remaining_plan ? '已有剩余安排' : pending : row.reports.length ? row.reports.length + ' 次报工' + (row.trackCount > 1 ? ' · 分行 ' + row.track + '/' + row.trackCount : '') : emptyReports(row, view.mode)}</span>
          {row.kind !== 'remaining' && (timing.finishLate || timing.unclosed || timing.forecastLate) && <span className="fg-row-caption">{timing.finishLate ? '已晚完成' : timing.unclosed ? '到期未确认完成' : '剩余安排预计晚完成'}</span>}</div>
        <div className="fg-track" style={{ width }}>
          {ticks.map(tick => <i className="fg-gridline" key={tick.at} style={{ left: tick.x }} />)}
          {nowX >= 0 && nowX <= width && <i className="fg-now" style={{ left: nowX }} aria-hidden="true" />}
          {row.kind === 'actual' && !window.PointContract.isPoint(t) && (row.baseline || row.reports.length > 0) && <i className="fg-baseline-end" data-plan-end={t.end} style={{ left: (M.instant(t.end) - model.start) / (model.end - model.start) * width }} title={'计划完工 ' + M.time(t.end)} aria-hidden="true" />}
          {(dense || marks.length > 50) ? <window.ActualGanttCanvas.DenseRow {...{ row, model, width, viewport, left, onSelect, onHover, renderMark }} selected={view.selected} /> :
            marks.filter(mark => (mark.end - model.start) / (model.end - model.start) * width >= left - 12 && (mark.start - model.start) / (model.end - model.start) * width <= left + viewport + 12)
              .map(mark => renderMark(mark))}
          {row.kind === 'remaining' && !e.remaining_plan && <span className="fg-wait">{pending} · {M.number(e.remaining_quantity)} 件</span>}
          {row.kind === 'actual' && !row.reports.length && <span className="fg-wait">{emptyReports(row, view.mode)}</span>}
          {row.reports.some(r => !r.actual_start) && <span className="fg-wait">本次开工待补，未绘制时段</span>}
        </div></div>;
    })}{chain && view.chainLines !== false && <ChainLines {...{ chain, model, width, labelWidth, top, height }} />}</>;
  }
  window.ActualGanttRows = Rows;
  window.ActualGanttBar = Bar;
})();
