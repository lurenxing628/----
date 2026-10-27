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
      return '本' + resource + '暂无报工' + (execution.legacy_facts.length ? '；有历史现场记录' : '');
    }
    return execution.legacy_facts.length ? '仅有历史现场记录' : '暂无实际报工';
  }
  function Bar({ mark, row, visibleMarks, model, width, selected, active, onSelect, onHover, canvasPainted }) {
    const box = window.ActualGanttWindow.markBox(mark, model, width), { x, size } = box;
    const kind = { actual: 'act', legacy: 'act', plan: 'plan', remaining: 'remaining' }[mark.kind];
    const title = M.markTitle(mark, row.item, model.labels);
    const critical = active.critical.has(row.item.task.task_ref), related = active.related.has(row.item.task.task_ref);
    const emphasis = { 'data-gantt-critical': critical || undefined, 'data-gantt-related': related || undefined,
      'data-gantt-muted': active.target && !critical && !related || undefined };
    function atPointer(event) {
      const track = event.currentTarget.closest('.fg-track').getBoundingClientRect();
      return window.ActualGanttWindow.hitMark(visibleMarks, model, width, 0, event.clientX - track.left, event.clientY - track.top);
    }
    function hover(event) {
      if (!event) { onHover(null); return; }
      const target = event.type === 'focus' ? mark : atPointer(event);
      if (!target) { onHover(null); return; }
      const rect = event.currentTarget.getBoundingClientRect();
      onHover({ item: row.item, report: target.report, title: M.markTitle(target, row.item, model.labels), x: rect.right, y: rect.top });
    }
    if (mark.kind === 'plan-point' || mark.kind === 'point' || mark.kind === 'legacy-point') return <window.PointGantt.Marker {...emphasis}
      task={mark.legacy ? { task_ref: mark.key, start: M.wire(mark.start) } : mark.report ? { task_ref: mark.report.report_ref, start: mark.report.actual_start } : row.item.task}
      x={x} top={mark.y} title={title} tone={(mark.kind === 'plan-point' ? 'plan' : '') + (canvasPainted ? ' fg-canvas-point' : '')} selected={selected === row.item.task.task_ref}
      data-actual-mark={mark.kind} data-report-ref={mark.report && mark.report.report_ref} data-task-ref={row.item.task.task_ref}
      onSelect={() => onSelect(row.item, mark.report)} onHover={hover} onFocus={hover} onBlur={() => onHover(null)} />;
    return <button type="button" className={'fg-mark fg-' + kind} {...emphasis} data-actual-mark={mark.kind} data-report-ref={mark.report && mark.report.report_ref} data-task-ref={row.item.task.task_ref}
      data-duration-ms={mark.end - mark.start} data-duration-width={size}
      style={{ left: box.hitLeft, width: box.hitWidth, top: mark.y, height: mark.height }}
      title={title} aria-label={title} aria-pressed={selected === row.item.task.task_ref} onClick={event => {
        const target = event.detail === 0 ? mark : atPointer(event); if (target) onSelect(row.item, target.report);
      }} onMouseEnter={hover} onMouseMove={hover} onMouseLeave={() => onHover(null)} onFocus={hover} onBlur={() => onHover(null)}>
      <span className="fg-mark-face" style={{ left: box.faceLeft, width: size }}>{size >= 55 && mark.kind !== 'plan' && <><span>{mark.legacy ? '历史事件记录 · 有效工时未记录' : mark.report ? mark.report.report_no : '剩余 ' + M.number(row.item.execution.remaining_quantity) + ' 件'}</span>
        {size >= 150 && <span>{mark.legacy ? '旧已知累计 ' + M.number(mark.legacy.quantity_done) + ' 件' : mark.report ? M.number(mark.report.completed_quantity) + ' 件 · ' + M.hours(mark.report.effective_processing_hours) : M.time(row.item.execution.remaining_plan.start)}</span>}</>}</span>
    </button>;
  }
  function Rows({ model, view, width, viewport, left, top, height, labelWidth, dense, active, onSelect, onHover, onChainTarget, patch }) {
    const scale = width / (model.end - model.start), nowX = (model.asOf - model.start) * scale;
    const visible = React.useMemo(() => M.visibleRows(model.rows, Math.max(0, top - 100), top + height + 100).map(row => ({ row,
      visibleMarks: row.kind === 'group' ? [] : row.marks.filter(mark => (mark.end - model.start) * scale >= left - 12 && (mark.start - model.start) * scale <= left + viewport + 12)
    })), [model, top, height, width, left, viewport]);
    const ticks = React.useMemo(() => M.ticks(model, width, left, viewport), [model.start, model.end, width, left, viewport]);
    return <>{visible.map(({ row, visibleMarks }) => {
      const style = { top: row.top + 52, height: row.height, width: width + labelWidth };
      if (row.kind === 'group') return <div key={row.key} className="fg-virtual-row fg-group-row" style={style} data-resource={row.group.id}>
        <div className="fg-frozen"><Button className="fg-icon-button" icon={view.collapsed[row.group.id] ? 'chevron-right' : 'chevron-down'} aria-label={(view.collapsed[row.group.id] ? '展开 ' : '折叠 ') + row.group.label}
          aria-expanded={!view.collapsed[row.group.id]} onClick={() => patch({ collapsed: { ...view.collapsed, [row.group.id]: !view.collapsed[row.group.id] } })} />
          <strong className="fg-resource-label" title={row.group.label}>{row.group.label}</strong></div><div className="fg-group-summary">{row.group.members.size} 道工序 · {model.executionAvailable ? row.group.reportCount + ' 次报工 · ' + (row.group.knownHours === null ? row.group.reportCount ? '本组报工未填写有效工时' : '本组暂无逐次报工工时' : '已知实报工时 ' + M.hours(row.group.knownHours)) + (row.group.unknownHours ? ' · ' + row.group.unknownHours + ' 条工时待补' : '') + (row.group.legacyCount ? ' · ' + row.group.legacyCount + ' 条历史记录' : '') : '报工记录不可用'}</div></div>;
      const { item } = row, e = item.execution, t = item.task, marks = row.marks;
      const hasLegacy = !row.reports.length && marks.some(mark => mark.legacy);
      const emptyText = row.kind === 'actual' && !row.reports.length && !hasLegacy ? emptyReports(row, view.mode) : '';
      const renderMark = (mark, canvasPainted = false) => <Bar key={mark.key} {...{ mark, row, visibleMarks, model, width, active, onSelect, onHover, canvasPainted }} selected={view.selected} />;
      const point = window.PointContract.isPoint(t);
      const pending = point ? '零工时工序已安排 · 完成待确认' : '剩余数量还没安排';
      const timing = row.kind !== 'remaining' ? M.deadlines(item) : null, deviation = row.kind !== 'remaining' ? M.finishDeviation(item) : '';
      return <div key={row.key} className={'fg-virtual-row' + (view.selected === t.task_ref ? ' is-selected' : '')} data-task-row={t.task_ref} data-kind={row.kind}
        data-gantt-critical={active.critical.has(t.task_ref) || undefined} style={style}>
        <div className="fg-frozen"><button type="button" className="fg-task-select" title={M.taskLabel(t)} onClick={() => onSelect(item, row.reports[0])}
          onMouseEnter={() => onChainTarget([t.task_ref])} onMouseLeave={() => onChainTarget(null)} onFocus={() => onChainTarget([t.task_ref])} onBlur={() => onChainTarget(null)}>{M.taskLabel(t)}</button>
          <span className="fg-row-caption" title={'计划应做 ' + M.number(t.quantity) + ' 件 · 批次 ' + M.number(t.batch_quantity) + ' 件'}>{row.kind === 'remaining' ? '执行剩余 ' + M.number(e.remaining_quantity) + ' 件' : e ? M.states[e.execution_state] + ' · 已知 ' + M.number(e.known_completed_quantity) + ' / 计划 ' + M.number(t.quantity) : '计划应做 ' + M.number(t.quantity) + ' 件 · 报工记录不可用'}</span>
          <span className="fg-row-caption" title={emptyText || undefined}>{row.kind === 'remaining' ? e.remaining_plan ? '已有剩余安排' : pending : row.reports.length ? row.reports.length + ' 次报工' + (row.trackCount > 1 ? ' · 分行 ' + row.track + '/' + row.trackCount : '') : hasLegacy ? '0 次报工 · 历史现场记录' : emptyText}</span>
          {row.kind !== 'remaining' && (deviation || timing.unclosed || timing.forecastLate) && <span className="fg-row-caption" title={deviation || undefined} data-finish-deviation={deviation || undefined}>{timing.unclosed ? '未完工 · 到期未确认完成' : timing.forecastLate ? '未完工 · 剩余安排预计晚完成' : deviation}</span>}</div>
        <div className="fg-track" style={{ width }}>
          {ticks.map(tick => <i className="fg-gridline" key={tick.at} style={{ left: tick.x }} />)}
          {nowX >= 0 && nowX <= width && <i className="fg-now" style={{ left: nowX }} aria-hidden="true" />}
          {row.kind === 'actual' && !point && (row.baseline || row.reports.length > 0) && <i className="fg-baseline-end" data-plan-end={t.end} style={{ left: (row.planEnd - model.start) * scale }} title={'计划完工 ' + M.time(t.end)} aria-hidden="true" />}
          {(dense || marks.length > 50) ? <window.ActualGanttCanvas.DenseRow {...{ row, marks, visibleMarks, model, width, viewport, left, onSelect, onHover, renderMark }} graphActive={active} selected={view.selected} /> :
            visibleMarks.map(mark => renderMark(mark))}
          {row.kind === 'remaining' && !e.remaining_plan && <span className="fg-wait">{pending} · {M.number(e.remaining_quantity)} 件</span>}
          {emptyText && <span className="fg-wait">{emptyText}</span>}
          {row.reports.some(r => !r.actual_start) && <span className="fg-wait">本次开工待补，未绘制时段</span>}
        </div></div>;
    })}</>;
  }
  window.ActualGanttRows = Rows;
  window.ActualGanttBar = Bar;
})();
