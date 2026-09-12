(function () {
  'use strict';

  const M = window.ActualGanttModel;
  function dimensions(width) {
    const labelWidth = width < 550 ? 160 : 292;
    return {
      labelWidth,
      viewport: Math.max(80, width - labelWidth)
    };
  }
  function capture(position, viewport, model, zoom) {
    const windowSpan = (model.end - model.start) / zoom;
    return {
      left: position.left,
      top: position.top,
      viewport,
      windowSpan,
      centerAt: model.start + (position.left / viewport + .5) * windowSpan
    };
  }
  function restoreZoom(position, model, zoom) {
    return position.windowSpan === undefined ? zoom : Math.max(1, Math.min(1024, (model.end - model.start) / position.windowSpan));
  }
  function restoreLeft(position, viewport, model, zoom) {
    if (position.centerAt !== undefined) return ((position.centerAt - model.start) / (model.end - model.start) * zoom - .5) * viewport;
    return position.viewport === undefined ? position.left : position.left * viewport / position.viewport;
  }
  function range(values) {
    const points = values.filter(Number.isFinite);
    if (!points.length) return null;
    let start = points[0],
      end = points[0];
    points.forEach(at => {
      start = Math.min(start, at);
      end = Math.max(end, at);
    });
    return {
      start,
      end
    };
  }
  function dataRange(data) {
    const plan = range(data.items.flatMap(item => [M.instant(item.task.start), M.instant(item.task.end)]));
    if (plan) return plan;
    return range(data.items.flatMap(item => item.execution ? item.execution.reports.flatMap(report => [M.instant(report.actual_start), M.instant(report.actual_end)]) : []));
  }
  function initial(data, model) {
    const target = dataRange(data);
    if (!target) return {
      zoom: 1,
      center: .5
    };
    const span = model.end - model.start,
      pad = Math.max(60000, (target.end - target.start) * .08);
    const start = Math.max(model.start, target.start - pad),
      end = Math.min(model.end, target.end + pad);
    return {
      zoom: Math.max(1, Math.min(1024, span / Math.max(60000, end - start))),
      center: ((start + end) / 2 - model.start) / span
    };
  }
  function anchor(data, model, selectedRef, reportRef) {
    const selected = data.items.find(item => item.task.task_ref === selectedRef);
    const report = selected && selected.execution && selected.execution.reports.find(item => item.report_ref === reportRef);
    const selectedRange = report && report.actual_start ? range([M.instant(report.actual_start), M.instant(report.actual_end)]) : selected ? range([M.instant(selected.task.start), M.instant(selected.task.end)]) : dataRange(data);
    return selectedRange ? ((selectedRange.start + selectedRange.end) / 2 - model.start) / (model.end - model.start) : .5;
  }
  function markBox(mark, model, width, left = 0) {
    const scale = width / (model.end - model.start),
      x = (mark.start - model.start) * scale - left;
    const size = (mark.end - mark.start) * scale,
      point = mark.kind === 'point' || mark.kind === 'plan-point';
    const hitWidth = point ? 24 : Math.max(4, size);
    const hitLeft = point ? x - 12 : Math.max(0, Math.min(width - hitWidth, x + left - (hitWidth - size) / 2)) - left;
    return {
      x,
      size,
      hitWidth,
      hitLeft,
      faceLeft: x - hitLeft
    };
  }
  function hitMark(marks, model, width, left, x, y) {
    const matches = marks.filter(mark => {
      const box = markBox(mark, model, width, left);
      return x >= box.hitLeft && x < box.hitLeft + box.hitWidth && y >= mark.y && y < mark.y + mark.height;
    });
    return matches.sort((a, b) => {
      const distance = mark => {
        const box = markBox(mark, model, width, left);
        return Math.abs(x - box.x - box.size / 2);
      };
      return distance(a) - distance(b);
    })[0] || null;
  }
  window.ActualGanttWindow = {
    dimensions,
    capture,
    restoreZoom,
    restoreLeft,
    initial,
    anchor,
    markBox,
    hitMark
  };
})();
