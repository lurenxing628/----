(function () {
  'use strict';
  const M = window.RunCandidateModel;
  const statusLabels = { matched: '可对照安排', newly_scheduled: '新增安排', unscheduled: '候选未排', baseline_only: '仅初始计划', not_comparable: '无法一一对照' };
  function matching(rows, query) {
    const needle = query.trim().toLocaleLowerCase();
    return !needle ? rows : rows.filter(r => [r.operation_ref, r.row_ref, r.batch_ref, r.batch_label, r.part_label, r.sequence, r.process_label,
      r.candidate, ...r.baseline_segments].flatMap(v => typeof v === 'object' && v ? [v.row_ref, v.machine && v.machine.label, v.operator && v.operator.label] : [v])
      .filter(v => v != null).join(' ').toLocaleLowerCase().includes(needle));
  }
  function title(item) {
    const r = item.comparison, s = item.segment;
    return ['初始计划 · ' + (r.batch_label || '批次未记录') + ' · ' + M.number(r.sequence) + ' ' + (r.process_label || '工序未记录'),
      M.timeLabel(s.start) + ' 至 ' + M.timeLabel(s.end), '设备：' + (s.machine && s.machine.label || '未记录'),
      '人员：' + (s.operator && s.operator.label || '未记录'), statusLabels[r.status], '初始计划行引用：' + s.row_ref].join('\n');
  }
  function push(heap, value) {
    let i = heap.length; heap.push(value);
    while (i > 0) { const p = (i - 1) >> 1; if (heap[p].end <= value.end) break; heap[i] = heap[p]; i = p; } heap[i] = value;
  }
  function pop(heap) {
    const first = heap[0], last = heap.pop(); if (!heap.length) return first;
    let i = 0;
    while (i * 2 + 1 < heap.length) {
      let child = i * 2 + 1; if (child + 1 < heap.length && heap[child + 1].end < heap[child].end) child++;
      if (heap[child].end >= last.end) break; heap[i] = heap[child]; i = child;
    }
    heap[i] = last; return first;
  }
  function tracks(items) {
    const heap = [], rows = [];
    items.sort((a, b) => a.start - b.start || a.end - b.end || a.segment.row_ref.localeCompare(b.segment.row_ref));
    for (const item of items) {
      const lane = heap.length && heap[0].end <= item.start ? pop(heap).lane : rows.length;
      if (!rows[lane]) rows[lane] = []; rows[lane].push(item); push(heap, { end: item.end, lane });
    }
    return rows;
  }
  function compose(candidate, baseline, mode, query) {
    if (!baseline) return candidate;
    const groups = new Map(), rows = [], locations = new Map(), baselineLocations = new Map();
    const comparisons = matching(baseline.comparisons, query), included = new Set(comparisons.map(r => r.operation_ref));
    for (const row of candidate.rows) {
      if (!groups.has(row.id)) groups.set(row.id, { label: row.label, current: [], before: [] });
      groups.get(row.id).current.push(row);
    }
    let start = candidate.start, end = candidate.end;
    for (const comparison of baseline.comparisons) for (const segment of comparison.baseline_segments) {
      if (!segment.interval_comparable) continue;
      const item = { comparison, segment, start: M.instant(segment.start), end: M.instant(segment.end) };
      start = start === null ? item.start : Math.min(start, item.start); end = end === null ? item.end : Math.max(end, item.end);
      if (!included.has(comparison.operation_ref)) continue;
      const resource = mode === 'batch' ? { ref: comparison.batch_ref, label: comparison.batch_label } : segment[mode];
      const id = resource && resource.ref || 'baseline-missing:' + segment.row_ref;
      if (!groups.has(id)) groups.set(id, { label: resource && resource.label || M.kindLabels[mode] + '未记录', current: [], before: [] });
      groups.get(id).before.push(item);
    }
    let top = 0;
    for (const [id, group] of groups) {
      for (const original of group.current) {
        const row = { ...original, top };
        row.items.forEach(item => locations.set(item.task.row_ref, { row: rows.length, top, item })); rows.push(row); top += row.height;
      }
      const lanes = tracks(group.before);
      lanes.forEach((items, lane) => {
        const row = { id, key: 'baseline:' + id + ':' + lane, label: group.label, items, top, height: 30, lane, laneCount: lanes.length, baseline: true };
        items.forEach(item => baselineLocations.set(item.segment.row_ref, { row: rows.length, top, item })); rows.push(row); top += row.height;
      });
    }
    return { ...candidate, rows, height: top, locations, baselineLocations, start, end, groupCount: groups.size, comparisons };
  }
  window.RunBaselineModel = { compose, matching, title, statusLabels };
})();
