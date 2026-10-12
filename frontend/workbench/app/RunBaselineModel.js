(function () {
  'use strict';
  const M = window.RunCandidateModel;
  const resourceLabels = { machine: '设备', operator: '人员', supplier: '供应商' };
  const sourceLabel = side => side.source === 'internal' ? '内部' : side.source === 'external' ? '外协' : '来源未记录';
  const statusLabels = { matched: '可对照安排', newly_scheduled: '新增安排', unscheduled: '候选未排', baseline_only: '仅原安排', not_comparable: '无法一一对照' };
  function matching(rows, query) {
    const needle = query.trim().toLocaleLowerCase();
    return !needle ? rows : rows.filter(r => [r.operation_ref, r.row_ref, r.batch_ref, r.batch_label, r.part_label, r.sequence, r.process_label,
      r.candidate, ...r.baseline_segments].flatMap(v => typeof v === 'object' && v ? [v.row_ref, v.machine && v.machine.label, v.operator && v.operator.label, v.supplier && v.supplier.label] : [v])
      .filter(v => v != null).join(' ').toLocaleLowerCase().includes(needle));
  }
  function title(item) {
    const r = item.comparison, s = item.segment;
    return ['原安排 · ' + (r.batch_label || '批次未记录') + ' · ' + M.number(r.sequence) + ' ' + (r.process_label || '工序未记录'),
      M.timeLabel(s.start) + ' 至 ' + M.timeLabel(s.end), '来源：' + sourceLabel(s),
      ...Object.keys(resourceLabels).map(kind => resourceLabels[kind] + '：' + resourceLabel(s, kind)),
      statusLabels[r.status], ...(r.comparison_available ? Object.keys(resourceLabels).map(kind => resourceLabels[kind] + '变化：' + resourceChange(r, kind)) : [])].join('\n');
  }
  const resourceLabel = (side, kind) => M.resourceLabel(side, kind);
  function resourceChange(row, kind) {
    const changed = row.delta[kind + '_changed'];
    if (changed !== null) return changed ? '有' : '无';
    if (!row.candidate || row.baseline_segments.length !== 1) return statusLabels[row.status];
    const label = resourceLabels[kind];
    return [['原安排', row.baseline_segments[0]], ['新安排', row.candidate]].filter(([, side]) => window.RunBaselineAPI.resourceIdentity(side, kind) === undefined).map(([name, side]) => {
      const problem = side.data_gaps.find(gap => gap.field === kind || gap.field === kind + '.ref');
      return name + label + '身份无法核对：' + (problem ? problem.message : '历史记录未保存资源身份。');
    }).join('；') || '原安排起止不可比较';
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
  function compose(candidate, baseline, mode, query, operationRefs = null, width = 1000) {
    if (!baseline) return candidate;
    const groups = new Map(), rows = [], locations = new Map(), baselineLocations = new Map();
    const comparisons = matching(baseline.comparisons, query).filter(row => !operationRefs || operationRefs.has(row.operation_ref));
    const included = new Set(comparisons.map(r => r.operation_ref));
    for (const row of candidate.rows) {
      if (!groups.has(row.id)) groups.set(row.id, { label: row.label, current: [], before: [] });
      groups.get(row.id).current.push(row);
    }
    let start = candidate.start, end = candidate.end, hasPoints = false;
    for (const comparison of baseline.comparisons) for (const segment of comparison.baseline_segments) {
      if (!segment.interval_comparable) continue;
      const item = { comparison, segment, start: M.instant(segment.start), end: M.instant(segment.end) };
      hasPoints = hasPoints || window.PointContract.isPoint(segment);
      start = start === null ? item.start : Math.min(start, item.start); end = end === null ? item.end : Math.max(end, item.end);
      if (!included.has(comparison.operation_ref)) continue;
      const resource = mode === 'batch' ? { ref: comparison.batch_ref, label: comparison.batch_label } : segment[mode];
      const id = resource && resource.ref || 'baseline-missing:' + segment.row_ref;
      if (!groups.has(id)) groups.set(id, { label: mode === 'batch' ? resource.label || '批次未记录' : resourceLabel(segment, mode), current: [], before: [] });
      groups.get(id).before.push(item);
    }
    if (hasPoints) ({ start, end } = window.PointGanttModel.bounds(start, end, true));
    let top = 0;
    for (const [id, group] of groups) {
      for (const original of group.current) {
        const row = { ...original, top };
        row.items.forEach(item => locations.set(item.task.row_ref, { row: rows.length, top, item })); rows.push(row); top += row.height;
      }
      const isPoint = item => window.PointContract.isPoint(item.segment);
      const intervals = tracks(group.before.filter(item => !isPoint(item)));
      const points = window.PointGanttModel.tracks(group.before.filter(isPoint), start, end, width);
      for (const [baselinePoint, lanes] of [[false, intervals], [true, points]]) lanes.forEach((items, lane) => {
        const row = { id, key: 'baseline:' + id + ':' + (baselinePoint ? 'point:' : '') + lane, label: group.label, items, top, height: 30, lane, laneCount: lanes.length, baseline: true, baselinePoint };
        items.forEach(item => baselineLocations.set(item.segment.row_ref, { row: rows.length, top, item })); rows.push(row); top += row.height;
      });
    }
    return { ...candidate, rows, height: top, locations, baselineLocations, start, end, groupCount: groups.size, comparisons };
  }
  window.RunBaselineModel = { compose, matching, title, resourceLabel, resourceChange, sourceLabel, statusLabels };
})();
