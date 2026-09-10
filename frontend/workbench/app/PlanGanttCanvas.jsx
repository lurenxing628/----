(function () {
  'use strict';
  const M = window.PlanGanttModel;
  function palette(node) {
    const style = getComputedStyle(node), value = key => style.getPropertyValue(key).trim();
    const colors = {};
    for (const tone of ['primary', 'critical', 'success', 'plan']) colors[tone] = {
      fill: value('--wb-gantt-' + tone + '-fill'), edge: value('--wb-gantt-' + tone + '-edge') };
    colors.gold = value('--wb-gantt-gold'); colors.text = value('--ui-text'); return colors;
  }
  function usePaint(ref, paint, deps) {
    React.useLayoutEffect(() => {
      const draw = () => {
        const node = ref.current, scale = window.devicePixelRatio || 1;
        const { width, height } = node.getBoundingClientRect();
        node.width = Math.max(1, Math.round(width * scale)); node.height = Math.max(1, Math.round(height * scale));
        const ctx = node.getContext('2d'); ctx.setTransform(scale, 0, 0, scale, 0, 0);
        paint(ctx, width, height, palette(node));
      };
      draw();
      const theme = new MutationObserver(draw); theme.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'class'] });
      const resize = new ResizeObserver(draw); resize.observe(ref.current);
      return () => { theme.disconnect(); resize.disconnect(); };
    }, deps);
  }
  function DenseRow({ row, model, width, viewport, left, selectedRef, risks, onSelect, onHover }) {
    const ref = React.useRef(null), scale = width / (model.end - model.start);
    const G = window.PointGanttModel;
    const items = row.point ? G.visible(row.items, model.start + left / scale, model.start + (left + viewport) / scale, scale)
      : M.visibleItems(row.items, model.start + left / scale, model.start + (left + viewport) / scale);
    usePaint(ref, (ctx, w, h, colors) => {
      for (const item of items) {
        const x = (item.start - model.start) * scale - left, barWidth = (item.end - item.start) * scale;
        const inset = Math.min(2, barWidth * 0.1), painted = Math.max(0, barWidth - inset * 2);
        const tone = row.before ? 'plan' : M.tone(item.task, model.conflicts, risks), y = row.before ? 9 : 7, height = row.before ? 8 : 40;
        if (row.point) {
          G.paint(ctx, x, row.before ? 13 : 27, colors[tone].fill, item.task.task_ref === selectedRef ? colors.gold : colors[tone].edge, item.task.task_ref === selectedRef);
          continue;
        }
        ctx.fillStyle = colors[tone].fill; ctx.fillRect(x + inset, y, painted, height);
        ctx.strokeStyle = item.task.task_ref === selectedRef ? colors.gold : colors[tone].edge;
        ctx.lineWidth = Math.min(item.task.task_ref === selectedRef ? 2 : 1, painted);
        ctx.setLineDash(row.before || model.conflicts.has(item.task.task_ref) ? [3, 2] : []);
        if (painted > 0) ctx.strokeRect(x + inset + ctx.lineWidth / 2, y + ctx.lineWidth / 2, painted - ctx.lineWidth, height - ctx.lineWidth);
        if (!row.before && painted > 60) {
          ctx.save(); ctx.beginPath(); ctx.rect(Math.max(0, x + inset + 3), y, Math.max(0, Math.min(w, x + barWidth - inset) - Math.max(0, x + inset + 3) - 3), height); ctx.clip();
          ctx.fillStyle = colors.text; ctx.font = '11px sans-serif';
          ctx.fillText(M.pieceLabel(item.task), Math.max(3, x + inset + 4), y + 16); ctx.restore();
        }
      }
    }, [items, selectedRef, width, left, viewport, risks]);
    function hit(event) {
      const box = ref.current.getBoundingClientRect(), at = model.start + (event.clientX - box.left + left) / scale;
      if (row.point) return G.hit(row.items, event.clientX - box.left, event.clientY - box.top, model, width, left, row.before ? 13 : 27);
      return M.visibleItems(row.items, at, at + 0.001)[0];
    }
    return <canvas ref={ref} className="plan-row-canvas" data-plan-dense-row data-point-row={row.point || undefined} role="button" tabIndex={0}
      style={{ left, width: viewport }} aria-label={row.label + '，' + row.items.length + '道' + (row.before ? '基线' : '安排')}
      onMouseMove={event => { const item = hit(event); onHover(item ? { task: item.task, before: row.before, x: event.clientX, y: event.clientY } : null); }}
      onMouseLeave={() => onHover(null)} onClick={event => { const item = hit(event); if (item) onSelect(item.task, row.before); }}
      onKeyDown={event => {
        if (!['Enter', ' ', 'ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault(); const index = row.items.findIndex(item => item.task.task_ref === selectedRef);
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? row.items.length - 1 : Math.max(0, Math.min(row.items.length - 1, index + (event.key === 'ArrowLeft' ? -1 : 1)));
        onSelect(row.items[next].task, row.before);
      }} />;
  }
  function Overview({ model, tasks, width, viewport, left, onPan }) {
    const ref = React.useRef(null);
    usePaint(ref, (ctx, w, h, colors) => {
      const bins = new Float64Array(Math.max(1, Math.ceil(w)) + 1);
      for (const task of tasks) {
        if (window.PointContract.isPoint(task)) continue;
        const start = Math.max(0, Math.floor((M.instant(task.start) - model.start) / (model.end - model.start) * w));
        const end = Math.min(bins.length - 1, Math.max(start + 1, Math.ceil((M.instant(task.end) - model.start) / (model.end - model.start) * w)));
        bins[start]++; bins[end]--;
      }
      let max = 1, count = 0; for (let x = 0; x < bins.length; x++) { count += bins[x]; bins[x] = count; max = Math.max(max, count); }
      ctx.fillStyle = colors.primary.edge;
      for (let x = 0; x < bins.length; x++) if (bins[x]) { const barHeight = 3 + bins[x] / max * (h - 8); ctx.fillRect(x, h - barHeight, 1, barHeight); }
      for (const task of tasks) if (window.PointContract.isPoint(task)) {
        const x = (M.instant(task.start) - model.start) / (model.end - model.start) * w;
        window.PointGanttModel.paint(ctx, x, 8, colors.plan.fill, colors.plan.edge, false);
      }
      ctx.strokeStyle = colors.gold; ctx.lineWidth = 2;
      ctx.strokeRect(left / width * w + 1, 1, Math.max(1, Math.min(w - 2, viewport / width * w - 2)), h - 2);
    }, [model.start, model.end, tasks, width, left, viewport]);
    return <div className="plan-global">
      <div className="plan-global-labels"><span>全局时间轴 · {M.timeLabel(M.wire(model.start))}</span><span>{M.timeLabel(M.wire(model.end))}</span></div>
      <canvas ref={ref} role="img" aria-label="真实安排时间分布" onClick={event => {
        const r = ref.current.getBoundingClientRect(); onPan((event.clientX - r.left) / r.width * width - viewport / 2);
      }} />
      <input type="range" aria-label="时间轴水平位置" min={0} max={Math.max(0, width - viewport)} step="any" value={Math.min(left, Math.max(0, width - viewport))}
        disabled={width <= viewport} onChange={event => onPan(Number(event.target.value))} />
    </div>;
  }
  window.PlanGanttCanvas = { DenseRow, Overview };
})();
