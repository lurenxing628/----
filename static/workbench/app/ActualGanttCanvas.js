(function () {
  'use strict';

  const M = window.ActualGanttModel;
  function usePaint(ref, paint, deps) {
    React.useLayoutEffect(() => {
      const draw = () => {
        const node = ref.current,
          {
            width,
            height
          } = node.getBoundingClientRect(),
          dpr = window.devicePixelRatio || 1;
        node.width = Math.max(1, Math.round(width * dpr));
        node.height = Math.max(1, Math.round(height * dpr));
        const ctx = node.getContext('2d');
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        const style = getComputedStyle(node),
          colors = {};
        for (const [kind, tone] of [['plan', 'plan'], ['plan-point', 'plan'], ['actual', 'primary'], ['point', 'primary'], ['remaining', 'primary']]) colors[kind] = {
          fill: style.getPropertyValue('--wb-gantt-' + tone + '-fill').trim(),
          edge: style.getPropertyValue('--wb-gantt-' + tone + '-edge').trim()
        };
        colors.remaining.fill = style.getPropertyValue('--wb-gantt-reference-fill').trim();
        colors.selected = style.getPropertyValue('--wb-gantt-gold').trim();
        paint(ctx, width, height, colors);
      };
      draw();
      const theme = new MutationObserver(draw),
        resize = new ResizeObserver(draw);
      theme.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-theme', 'class']
      });
      resize.observe(ref.current);
      return () => {
        theme.disconnect();
        resize.disconnect();
      };
    }, deps);
  }
  function DenseRow({
    row,
    model,
    width,
    viewport,
    left,
    selected,
    onSelect,
    onHover,
    renderMark
  }) {
    const ref = React.useRef(null),
      marks = M.marks(row),
      scale = width / (model.end - model.start);
    usePaint(ref, (ctx, w, h, colors) => {
      for (const mark of marks) {
        const x = (mark.start - model.start) * scale - left,
          size = (mark.end - mark.start) * scale;
        if (x > w + 12 || x + size < -12) continue;
        ctx.fillStyle = colors[mark.kind].fill;
        ctx.strokeStyle = selected === row.item.task.task_ref ? colors.selected : colors[mark.kind].edge;
        if (mark.kind === 'point' || mark.kind === 'plan-point') window.PointGanttModel.paint(ctx, x, mark.y + 12, ctx.fillStyle, ctx.strokeStyle, selected === row.item.task.task_ref);else {
          ctx.fillRect(x, mark.y, size, mark.height);
          ctx.lineWidth = Math.min(1, size);
          ctx.setLineDash(['plan', 'remaining'].includes(mark.kind) ? [3, 2] : []);
          if (size > 0) ctx.strokeRect(x + ctx.lineWidth / 2, mark.y + ctx.lineWidth / 2, size - ctx.lineWidth, mark.height - ctx.lineWidth);
        }
      }
    }, [row, width, viewport, left, selected]);
    function hit(event) {
      const rect = ref.current.getBoundingClientRect(),
        x = event.clientX - rect.left,
        y = event.clientY - rect.top;
      return marks.find(mark => {
        const start = (mark.start - model.start) * scale - left,
          end = (mark.end - model.start) * scale - left;
        return mark.kind === 'point' || mark.kind === 'plan-point' ? Math.abs(x - start) <= 12 && y >= mark.y && y <= mark.y + 24 : x >= start && x < end && y >= mark.y && y < mark.y + mark.height;
      });
    }
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("canvas", {
      ref: ref,
      className: "fg-row-canvas",
      "data-actual-canvas": true,
      role: "button",
      tabIndex: 0,
      style: {
        left,
        width: viewport
      },
      "aria-label": M.describe(row.item, model.labels).join('；'),
      onClick: e => {
        const mark = hit(e);
        if (mark) onSelect(row.item, mark.report);
      },
      onMouseMove: e => {
        const mark = hit(e);
        onHover(mark ? {
          item: row.item,
          report: mark.report,
          title: M.markTitle(mark, row.item, model.labels),
          x: e.clientX,
          y: e.clientY
        } : null);
      },
      onMouseLeave: () => onHover(null),
      onKeyDown: e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(row.item, row.reports[0]);
        }
      }
    }), marks.filter(mark => (mark.kind === 'point' || mark.kind === 'plan-point') && (mark.start - model.start) * scale >= left - 12 && (mark.start - model.start) * scale <= left + viewport + 12).map(mark => renderMark(mark, true)));
  }
  window.ActualGanttCanvas = {
    DenseRow
  };
})();
