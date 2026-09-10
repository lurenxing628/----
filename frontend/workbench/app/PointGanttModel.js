(function () {
  'use strict';
  const hitSize = 24, gap = 28;
  function bounds(start, end, hasPoints) {
    if (start === null || !hasPoints) return { start, end };
    const pad = Math.max(60000, (end - start) * .04);
    return { start: start - pad, end: end + pad };
  }
  function tracks(items, start, end, width) {
    const lanes = [], heap = [], scale = Math.max(1, width) / (end - start);
    for (const item of items.slice().sort((a, b) => a.start - b.start || String(a.task.task_ref || a.task.row_ref).localeCompare(String(b.task.task_ref || b.task.row_ref)))) {
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
  function paint(ctx, x, y, fill, edge, selected) {
    ctx.save(); ctx.setLineDash([]); ctx.beginPath();
    ctx.moveTo(x, y - 7); ctx.lineTo(x + 7, y); ctx.lineTo(x, y + 7); ctx.lineTo(x - 7, y); ctx.closePath();
    ctx.fillStyle = fill; ctx.fill(); ctx.strokeStyle = edge; ctx.lineWidth = selected ? 2 : 1; ctx.stroke(); ctx.restore();
  }
  function candidateRows(model, width) {
    const groups = new Map(), rows = [], locations = new Map(), baselineLocations = new Map(), done = new Set();
    for (const row of model.rows) if (row.point) {
      if (!groups.has(row.id)) groups.set(row.id, []);
      groups.get(row.id).push(...row.items);
    }
    let top = 0;
    function append(source, items, key) {
      const row = { ...source, items, top, key };
      for (const item of items) (row.baseline ? baselineLocations : locations).set(row.baseline ? item.segment.row_ref : item.task.row_ref, { row: rows.length, top, item });
      rows.push(row); top += row.height;
    }
    for (const row of model.rows) {
      if (!row.point) { append(row, row.items, row.key); continue; }
      if (done.has(row.id)) continue; done.add(row.id);
      const lanes = tracks(groups.get(row.id), model.start, model.end, width);
      lanes.forEach((items, lane) => append({ ...row, lane, laneCount: lanes.length }, items, row.id + ':point:' + lane));
    }
    return { ...model, rows, locations, baselineLocations, height: top };
  }
  window.PointGanttModel = { bounds, tracks, visible, hit, paint, candidateRows, hitSize };
})();
