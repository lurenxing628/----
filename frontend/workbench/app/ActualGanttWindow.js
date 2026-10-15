(function () {
  'use strict';
  function dimensions(width) {
    const labelWidth = width < 550 ? 160 : 292;
    return { labelWidth, viewport: Math.max(80, width - labelWidth) };
  }
  function capture(position, viewport, model, zoom) {
    const windowSpan = (model.end - model.start) / zoom;
    return { left: position.left, top: position.top, viewport, windowSpan,
      centerAt: model.start + (position.left / viewport + .5) * windowSpan };
  }
  function restoreZoom(position, model, zoom) {
    return position.windowSpan === undefined ? zoom : Math.max(1, Math.min(1024, (model.end - model.start) / position.windowSpan));
  }
  function restoreLeft(position, viewport, model, zoom) {
    if (position.centerAt !== undefined)
      return ((position.centerAt - model.start) / (model.end - model.start) * zoom - .5) * viewport;
    return position.viewport === undefined ? position.left : position.left * viewport / position.viewport;
  }
  // The default window follows the data but never opens beyond 64x: a few hours inside a months-long axis otherwise
  // started at 1024x with a board hundreds of thousands of pixels wide and a scrollbar thumb too small to grab.
  // Manual zoom still reaches 1024.
  const INITIAL_ZOOM_MAX = 64;
  function initial(model) {
    const target = model.dataRange;
    if (!target) return { zoom: 1, center: .5 };
    const span = model.end - model.start, pad = Math.max(60000, (target.end - target.start) * .08);
    const start = Math.max(model.start, target.start - pad), end = Math.min(model.end, target.end + pad);
    return { zoom: Math.max(1, Math.min(INITIAL_ZOOM_MAX, span / Math.max(60000, end - start))), center: ((start + end) / 2 - model.start) / span };
  }
  function anchor(model, selectedRef, reportRef) {
    const selected = model.taskIndex.get(selectedRef), report = selected && selected.reportIndex.get(reportRef);
    const selectedRange = report && Number.isFinite(report.start) ? report : selected ? selected.baseline : model.dataRange;
    return selectedRange && Number.isFinite(selectedRange.start) && Number.isFinite(selectedRange.end)
      ? ((selectedRange.start + selectedRange.end) / 2 - model.start) / (model.end - model.start) : .5;
  }
  function markBox(mark, model, width, left = 0) {
    const scale = width / (model.end - model.start), x = (mark.start - model.start) * scale - left;
    const size = (mark.end - mark.start) * scale, point = mark.kind === 'point' || mark.kind === 'plan-point';
    const hitWidth = point ? 24 : Math.max(4, size);
    const hitLeft = point ? x - 12 : Math.max(0, Math.min(width - hitWidth, x + left - (hitWidth - size) / 2)) - left;
    return { x, size, hitWidth, hitLeft, faceLeft: x - hitLeft };
  }
  function hitMark(marks, model, width, left, x, y) {
    const matches = marks.filter(mark => {
      const box = markBox(mark, model, width, left);
      return x >= box.hitLeft && x < box.hitLeft + box.hitWidth && y >= mark.y && y < mark.y + mark.height;
    });
    return matches.sort((a, b) => {
      const distance = mark => { const box = markBox(mark, model, width, left); return Math.abs(x - box.x - box.size / 2); };
      return distance(a) - distance(b);
    })[0] || null;
  }
  window.ActualGanttWindow = { dimensions, capture, restoreZoom, restoreLeft, initial, anchor, markBox, hitMark };
})();
