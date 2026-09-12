(function () {
  'use strict';
  const M = window.ActualGanttModel;
  function usePaint(ref, paint, deps) {
    React.useLayoutEffect(() => {
      const draw = () => {
        const node = ref.current, { width, height } = node.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
        node.width = Math.max(1, Math.round(width * dpr)); node.height = Math.max(1, Math.round(height * dpr));
        const ctx = node.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        const style = getComputedStyle(node), colors = {};
        for (const [kind, tone] of [['plan', 'plan'], ['plan-point', 'plan'], ['actual', 'primary'], ['point', 'primary'], ['remaining', 'primary']])
          colors[kind] = { fill: style.getPropertyValue('--wb-gantt-' + tone + '-fill').trim(), edge: style.getPropertyValue('--wb-gantt-' + tone + '-edge').trim() };
        colors.remaining.fill = style.getPropertyValue('--wb-gantt-reference-fill').trim();
        colors.selected = style.getPropertyValue('--wb-gantt-gold').trim(); paint(ctx, width, height, colors);
      };
      draw(); const theme = new MutationObserver(draw), resize = new ResizeObserver(draw);
      theme.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'class'] }); resize.observe(ref.current);
      return () => { theme.disconnect(); resize.disconnect(); };
    }, deps);
  }
  function DenseRow({ row, model, width, viewport, left, selected, onSelect, onHover, renderMark }) {
    const ref = React.useRef(null), marks = M.marks(row), scale = width / (model.end - model.start);
    const pointerFocus = React.useRef(false), [activeKey, setActiveKey] = React.useState(null), [focused, setFocused] = React.useState(false);
    const activeIndex = Math.max(0, marks.findIndex(mark => mark.key === activeKey)), active = marks[activeIndex];
    usePaint(ref, (ctx, w, h, colors) => {
      for (const mark of marks) {
        const x = (mark.start - model.start) * scale - left, size = (mark.end - mark.start) * scale;
        if (x > w + 12 || x + size < -12) continue;
        ctx.fillStyle = colors[mark.kind].fill; ctx.strokeStyle = selected === row.item.task.task_ref ? colors.selected : colors[mark.kind].edge;
        if (mark.kind === 'point' || mark.kind === 'plan-point') window.PointGanttModel.paint(ctx, x, mark.y + 12, ctx.fillStyle, ctx.strokeStyle, selected === row.item.task.task_ref);
        else { ctx.fillRect(x, mark.y, size, mark.height); ctx.lineWidth = Math.min(1, size); ctx.setLineDash(['plan', 'remaining'].includes(mark.kind) ? [3, 2] : []);
          if (size > 0) ctx.strokeRect(x + ctx.lineWidth / 2, mark.y + ctx.lineWidth / 2, size - ctx.lineWidth, mark.height - ctx.lineWidth); }
        if (focused && active && mark.key === active.key) {
          const box = window.ActualGanttWindow.markBox(mark, model, width, left);
          ctx.setLineDash([]); ctx.lineWidth = 2; ctx.strokeStyle = colors.selected;
          ctx.strokeRect(box.hitLeft - 2, mark.y - 2, box.hitWidth + 4, mark.height + 4);
        }
      }
    }, [row, width, viewport, left, selected, focused, active && active.key]);
    function reveal(mark) {
      if (!mark) return;
      const board = ref.current.closest('[data-actual-scroll]'); if (!board) return;
      const box = window.ActualGanttWindow.markBox(mark, model, width);
      if (box.hitLeft < board.scrollLeft + 12 || box.hitLeft + box.hitWidth > board.scrollLeft + viewport - 12)
        board.scrollLeft = Math.max(0, box.hitLeft - Math.max(12, (viewport - box.hitWidth) / 2));
      const frame = board.getBoundingClientRect(), canvas = ref.current.getBoundingClientRect();
      if (canvas.top < frame.top + 52) board.scrollTop += canvas.top - frame.top - 52;
      else if (canvas.bottom > frame.bottom) board.scrollTop += canvas.bottom - frame.bottom;
    }
    function keyDown(event) {
      if (!active) return;
      const offsets = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
      if (event.key in offsets || event.key === 'Home' || event.key === 'End') {
        event.preventDefault(); event.stopPropagation();
        const index = event.key === 'Home' ? 0 : event.key === 'End' ? marks.length - 1 : Math.max(0, Math.min(marks.length - 1, activeIndex + offsets[event.key]));
        setActiveKey(marks[index].key); reveal(marks[index]); onHover(null);
      } else if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault(); event.stopPropagation(); reveal(active); onSelect(row.item, active.report);
      }
    }
    function hit(event) {
      const rect = ref.current.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top;
      return window.ActualGanttWindow.hitMark(marks, model, width, left, x, y);
    }
    const label = active ? '第 ' + (activeIndex + 1) + ' / ' + marks.length + ' 个色块；' + M.markTitle(active, row.item, model.labels) + '；方向键切换色块，Home/End 跳到首末，Enter/空格查看详情'
      : M.describe(row.item, model.labels).join('；') + '；无可选择的时间色块';
    return <><canvas ref={ref} className="fg-row-canvas" data-actual-canvas data-active-mark={active && active.key} role="button" tabIndex={active ? 0 : -1} aria-disabled={!active} style={{ left, width: viewport }} aria-label={label}
      onMouseDown={() => { pointerFocus.current = true; }} onMouseUp={() => { pointerFocus.current = false; }}
      onFocus={() => { setFocused(true); if (!pointerFocus.current) reveal(active); pointerFocus.current = false; }} onBlur={() => { setFocused(false); onHover(null); }}
      onClick={e => { const mark = hit(e); if (mark) { setActiveKey(mark.key); onSelect(row.item, mark.report); } }}
      onMouseMove={e => { const mark = hit(e); onHover(mark ? { item: row.item, report: mark.report, title: M.markTitle(mark, row.item, model.labels), x: e.clientX, y: e.clientY } : null); }} onMouseLeave={() => onHover(null)}
      onKeyDown={keyDown} />
      {marks.filter(mark => (mark.kind === 'point' || mark.kind === 'plan-point') && (mark.start - model.start) * scale >= left - 12 && (mark.start - model.start) * scale <= left + viewport + 12)
        .map(mark => renderMark(mark, true))}</>;
  }
  window.ActualGanttCanvas = { DenseRow };
})();
