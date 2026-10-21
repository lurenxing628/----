(function () {
  'use strict';
  const M = window.RunCandidateModel;
  const resourceLabels = { machine: '设备', operator: '人员', supplier: '供应商' };
  const sourceLabel = side => side.source === 'internal' ? '内部' : side.source === 'external' ? '外协' : '来源未记录';
  const statusLabels = { matched: '可对照安排', newly_scheduled: '新增安排', unscheduled: '候选未排', baseline_only: '仅原安排', not_comparable: '无法一一对照' };
  function searchText(row) {
    return [row.operation_ref, row.row_ref, row.batch_ref, row.batch_label, row.part_label, row.sequence, row.process_label,
      row.candidate, ...row.baseline_segments].flatMap(value => typeof value === 'object' && value ? [value.row_ref, value.machine && value.machine.label, value.operator && value.operator.label, value.supplier && value.supplier.label] : [value])
      .filter(value => value != null).join(' ').toLocaleLowerCase();
  }
  function title(item) {
    const r = item.comparison, s = item.segment;
    return ['原安排 · ' + (r.batch_label || '批次未记录') + ' · ' + M.number(r.sequence) + ' ' + (r.process_label || '工序未记录'),
      M.timeLabel(s.start) + ' 至 ' + M.timeLabel(s.end), '来源：' + sourceLabel(s),
      ...Object.keys(resourceLabels).map(kind => resourceLabels[kind] + '：' + resourceLabel(s, kind)),
      statusLabels[r.status], ...(r.comparison_available ? Object.keys(resourceLabels).map(kind => resourceLabels[kind] + '变化：' + resourceChange(r, kind)) : [])].join('\n');
  }
  const resourceLabel = M.resourceLabel;
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
  function prepare(baseline) {
    return { hasBaseline: !!baseline, facts: baseline ? baseline.comparisons.map(comparison => ({ comparison,
      segments: comparison.baseline_segments.filter(segment => segment.interval_comparable).map(segment => ({ comparison, segment,
        start: M.instant(segment.start), end: M.instant(segment.end), point: window.PointContract.isPoint(segment) })) })) : [] };
  }
  function groupPrepared(prepared, mode, focus = null) {
    const groups = new Map(), comparisons = []; let start = null, end = null, hasPoints = false;
    for (const fact of prepared.facts) {
      const comparison = focus ? { ...fact.comparison, baseline_segments: fact.comparison.baseline_segments.filter(segment => M.resourceMatches(segment, focus)) } : fact.comparison;
      const entry = { comparison, search: searchText(comparison) }; comparisons.push(entry);
      for (const source of fact.segments) {
        if (!M.resourceMatches(source.segment, focus)) continue;
        const item = { ...source, comparison }, resource = mode === 'batch' ? { ref: comparison.batch_ref, label: comparison.batch_label } : item.segment[mode];
        const id = resource && resource.ref || 'baseline-missing:' + item.segment.row_ref;
        start = start === null ? item.start : Math.min(start, item.start); end = end === null ? item.end : Math.max(end, item.end); hasPoints = hasPoints || item.point;
        if (!groups.has(id)) groups.set(id, { id, label: mode === 'batch' ? resource.label || '批次未记录' : resourceLabel(item.segment, mode), before: [] });
        groups.get(id).before.push(item);
      }
    }
    for (const group of groups.values()) {
      group.intervals = tracks(group.before.filter(item => !item.point)); group.points = window.PointGanttModel.prepareTracks(group.before.filter(item => item.point));
    }
    return { ...prepared, groups, comparisons, start, end, hasPoints };
  }
  function selectPrepared(candidate, baseline, query = '', operationRefs = null, baselineVisible = true) {
    const groups = new Map(), needle = query.trim().toLocaleLowerCase();
    const comparisons = (baselineVisible ? baseline.comparisons : []).filter(entry => (!operationRefs || operationRefs.has(entry.comparison.operation_ref)) && (!needle || entry.search.includes(needle))).map(entry => entry.comparison);
    const included = new Set(comparisons.map(row => row.operation_ref));
    for (const group of candidate.groups.values()) groups.set(group.id, { id: group.id, label: group.label, candidate: group, intervals: [], points: [], before: [], shown: new Set() });
    for (const [id, source] of baselineVisible ? baseline.groups : []) {
      const before = source.before.filter(item => included.has(item.comparison.operation_ref)); if (!before.length) continue;
      const shown = new Set(before), group = groups.get(id) || { id, label: source.label, current: [] };
      groups.set(id, { ...group, before, shown, intervals: source.intervals.map(lane => lane.filter(item => shown.has(item))), points: source.points });
    }
    let start = candidate.start, end = candidate.end;
    if (baselineVisible && baseline.start !== null) { start = start === null ? baseline.start : Math.min(start, baseline.start); end = end === null ? baseline.end : Math.max(end, baseline.end); }
    if (baselineVisible && baseline.hasPoints) ({ start, end } = window.PointGanttModel.bounds(start, end, true));
    return { candidate, groups, start, end, comparisons, hasBaseline: baselineVisible && baseline.hasBaseline };
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
      const points = group.points.length ? window.PointGanttModel.layoutTracks(group.points, start, end, width).map(lane => lane.filter(item => group.shown.has(item))) : [];
      for (const [baselinePoint, lanes] of [[false, group.intervals], [true, points]]) lanes.forEach((items, lane) => { if (items.length) append({
        id, key: 'baseline:' + id + ':' + (baselinePoint ? 'point:' : '') + lane, label: group.label, items,
        height: 30, lane, laneCount: lanes.length, baseline: true, baselinePoint
      }); });
    }
    return { tasks: candidate.tasks, unplottableTasks: candidate.unplottableTasks, rows, height: top, locations, baselineLocations, start, end, groupCount: prepared.groups.size,
      ...(prepared.hasBaseline ? { comparisons: prepared.comparisons } : {}) };
  }
  window.RunBaselineModel = { prepare, groupPrepared, selectPrepared, layoutPrepared, title, resourceLabel, resourceChange, sourceLabel, statusLabels };
})();
