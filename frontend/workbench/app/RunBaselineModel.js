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
  function prepare(candidate, baseline, mode, query, operationRefs = null) {
    const groups = new Map();
    const comparisons = baseline ? matching(baseline.comparisons, query).filter(row => !operationRefs || operationRefs.has(row.operation_ref)) : [];
    const included = new Set(comparisons.map(r => r.operation_ref));
    // compose() also accepts its existing, already-laid-out candidate argument.
    if (candidate.rows) {
      for (const row of candidate.rows) {
        if (!groups.has(row.id)) groups.set(row.id, { id: row.id, label: row.label, current: [], before: [] });
        groups.get(row.id).current.push(row);
      }
    } else {
      for (const group of candidate.groups.values()) groups.set(group.id, { id: group.id, label: group.label, candidate: group, before: [] });
    }
    let start = candidate.start, end = candidate.end, hasPoints = false;
    for (const comparison of baseline ? baseline.comparisons : []) for (const segment of comparison.baseline_segments) {
      if (!segment.interval_comparable) continue;
      const item = { comparison, segment, start: M.instant(segment.start), end: M.instant(segment.end) };
      hasPoints = hasPoints || window.PointContract.isPoint(segment);
      start = start === null ? item.start : Math.min(start, item.start); end = end === null ? item.end : Math.max(end, item.end);
      if (!included.has(comparison.operation_ref)) continue;
      const resource = mode === 'batch' ? { ref: comparison.batch_ref, label: comparison.batch_label } : segment[mode];
      const id = resource && resource.ref || 'baseline-missing:' + segment.row_ref;
      if (!groups.has(id)) groups.set(id, { id, label: mode === 'batch' ? resource.label || '批次未记录' : resourceLabel(segment, mode), current: [], before: [] });
      groups.get(id).before.push(item);
    }
    if (hasPoints) ({ start, end } = window.PointGanttModel.bounds(start, end, true));
    for (const group of groups.values()) {
      const isPoint = item => window.PointContract.isPoint(item.segment);
      group.intervals = tracks(group.before.filter(item => !isPoint(item)));
      group.points = window.PointGanttModel.prepareTracks(group.before.filter(isPoint));
    }
    return { candidate, groups, start, end, comparisons, hasBaseline: !!baseline };
  }
  function layoutPrepared(prepared, width = 1000) {
    const { candidate, start, end } = prepared;
    const rows = [], locations = new Map(), baselineLocations = new Map(); let top = 0;
    function append(source) {
      const row = { ...source, top };
      row.items.forEach(item => (row.baseline ? baselineLocations : locations).set(
        row.baseline ? item.segment.row_ref : item.task.row_ref, { row: rows.length, top, item }));
      rows.push(row); top += row.height;
    }
    for (const [id, group] of prepared.groups) {
      const current = group.candidate ? M.groupRows(group.candidate, start, end, width, true) : group.current;
      current.forEach(append);
      const points = group.points.length ? window.PointGanttModel.layoutTracks(group.points, start, end, width) : [];
      for (const [baselinePoint, lanes] of [[false, group.intervals], [true, points]]) lanes.forEach((items, lane) => append({
        id, key: 'baseline:' + id + ':' + (baselinePoint ? 'point:' : '') + lane, label: group.label, items,
        height: 30, lane, laneCount: lanes.length, baseline: true, baselinePoint
      }));
    }
    const facts = candidate.rows ? candidate : { tasks: candidate.tasks, unplottableTasks: candidate.unplottableTasks };
    return { ...facts, rows, height: top, locations, baselineLocations, start, end, groupCount: prepared.groups.size,
      ...(prepared.hasBaseline ? { comparisons: prepared.comparisons } : {}) };
  }
  function compose(candidate, baseline, mode, query, operationRefs = null, width = 1000) {
    return baseline ? layoutPrepared(prepare(candidate, baseline, mode, query, operationRefs), width) : candidate;
  }
  window.RunBaselineModel = { prepare, layoutPrepared, compose, matching, title, resourceLabel, resourceChange, sourceLabel, statusLabels };
})();
