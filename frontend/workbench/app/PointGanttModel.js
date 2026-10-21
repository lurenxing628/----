(function () {
  'use strict';
  const hitSize = 24, gap = 28;
  const itemRef = item => item.task ? item.task.task_ref || item.task.row_ref : item.segment.row_ref;
  function bounds(start, end, hasPoints) {
    if (start === null || !hasPoints) return { start, end };
    const pad = Math.max(60000, (end - start) * .04);
    return { start: start - pad, end: end + pad };
  }
  function prepareTracks(items) {
    return items.sort((a, b) => a.start - b.start || itemRef(a).localeCompare(itemRef(b)));
  }
  function layoutTracks(items, start, end, width) {
    const lanes = [], heap = [], scale = Math.max(1, width) / (end - start);
    for (const item of items) {
      const x = (item.start - start) * scale;
      let slot;
      if (heap.length && heap[0].end <= x) {
        slot = heap[0]; const last = heap.pop();
        if (heap.length) {
          let i = 0;
          while (i * 2 + 1 < heap.length) {
            let c = i * 2 + 1; if (c + 1 < heap.length && heap[c + 1].end < heap[c].end) c++;
            if (heap[c].end >= last.end) break; heap[i] = heap[c]; i = c;
          }
          heap[i] = last;
        }
      } else { slot = { lane: lanes.length }; lanes.push([]); }
      lanes[slot.lane].push(item); slot.end = x + gap;
      let i = heap.length; heap.push(slot);
      while (i > 0) { const p = (i - 1) >> 1; if (heap[p].end <= slot.end) break; heap[i] = heap[p]; i = p; }
      heap[i] = slot;
    }
    return lanes;
  }
  function visible(items, start, end, scale) {
    const pad = hitSize / 2 / scale;
    let low = 0, high = items.length;
    while (low < high) { const mid = (low + high) >> 1; if (items[mid].start < start - pad) low = mid + 1; else high = mid; }
    const result = [];
    for (let i = low; i < items.length && items[i].start < end + pad; i++) result.push(items[i]);
    return result;
  }
  function hit(items, x, y, model, width, left, centerY) {
    if (Math.abs(y - centerY) > hitSize / 2) return null;
    const scale = width / (model.end - model.start), at = model.start + (x + left) / scale;
    return visible(items, at, at, scale).find(item => Math.abs((item.start - model.start) * scale - left - x) <= hitSize / 2);
  }
  function paint(ctx, x, y, fill, edge, selected, lineWidth = selected ? 2 : 1) {
    ctx.save(); ctx.setLineDash([]); ctx.beginPath();
    ctx.moveTo(x, y - 7); ctx.lineTo(x + 7, y); ctx.lineTo(x, y + 7); ctx.lineTo(x - 7, y); ctx.closePath();
    ctx.fillStyle = fill; ctx.fill(); ctx.strokeStyle = edge; ctx.lineWidth = lineWidth; ctx.stroke(); ctx.restore();
  }
  window.PointGanttModel = { bounds, prepareTracks, layoutTracks, visible, hit, paint };
})();
