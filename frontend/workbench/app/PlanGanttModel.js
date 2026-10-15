(function () {
  'use strict';
  // Factory-local wall-clock coordinates, deliberately independent of browser DST.
  // Date truncates below milliseconds; add the factory-local fractional seconds separately.
  const instant = value => value ? Date.parse(value.slice(0, 19) + 'Z') + Number(value.slice(19) || 0) * 1000 : NaN;
  // Axis labels only. Business task/scope strings bypass Date so all six fractional digits remain intact.
  const wire = value => new Date(value).toISOString().slice(0, 19);
  const timeLabel = value => window.WorkbenchFormat.dateTime(value, { seconds: true, fractions: true });
  const number = value => window.WorkbenchFormat.number(value, { digits: 2 });
  const count = value => window.WorkbenchFormat.number(value, { digits: 0 });
  const quantityLabel = (value, reason) => value === null ? quantityReasons[reason] || '未知' : typeof value === 'string' ? value : number(value);
  const pieceLabel = task => task.piece_id === null ? '共同工序' : '分件 ' + task.piece_id;
  // Same three sentences as FieldContract.quantityReasons; this module loads before FieldContract, so the text is repeated here.
  const quantityReasons = { plan_target_not_recorded: '原计划未记录应做数量', plan_target_unavailable: '原计划应做数量读不到', plan_target_invalid: '原计划应做数量无效' };
  const kindLabels = { machine: '设备', operator: '人员', batch: '批次' };
  function scopeCaption(data) {
    if (!data) return '';
    const includesPlanEnd = data.scope.range_start === null && data.plan_span.end_inclusive === true;
    return includesPlanEnd && data.plan_span.start === data.plan_span.end
      ? `计划时刻：${timeLabel(data.plan_span.start)}`
      : `计划时间范围：${timeLabel(data.time_scope.range_start)} 至 ${timeLabel(data.time_scope.range_end)}（${includesPlanEnd ? '包含末端零工时工序' : '不含结束时刻'}）`;
  }
  function names(data) {
    const result = new Map();
    for (const row of data.resources || []) result.set(row.ref, row.label || row.business_code);
    for (const key of ['calendar', 'occupancy']) {
      const projection = data.projections[key];
      for (const row of projection.resources || []) if (row.label) result.set(row.resource_ref, row.label);
    }
    return result;
  }
  function resourceLabel(task, mode, labels) {
    if (mode === 'batch') return task.batch_id;
    const ref = task[mode + '_ref'];
    return ref ? labels.get(ref) || kindLabels[mode] + '名称未填写' : '未选' + kindLabels[mode];
  }
  function searchText(task, labels) {
    return [task.batch_id, task.process_label, task.sequence, pieceLabel(task), labels.get(task.machine_ref), labels.get(task.operator_ref)].filter(value => value != null).join(' ').toLocaleLowerCase();
  }
  function heapPush(heap, item) {
    let index = heap.length; heap.push(item);
    while (index > 0) {
      const parent = (index - 1) >> 1;
      if (heap[parent].end <= item.end) break;
      heap[index] = heap[parent]; index = parent;
    }
    heap[index] = item;
  }
  function heapPop(heap) {
    const first = heap[0], last = heap.pop();
    if (!heap.length) return first;
    let index = 0;
    while (index * 2 + 1 < heap.length) {
      let child = index * 2 + 1;
      if (child + 1 < heap.length && heap[child + 1].end < heap[child].end) child++;
      if (heap[child].end >= last.end) break;
      heap[index] = heap[child]; index = child;
    }
    heap[index] = last; return first;
  }
  function tracks(items, conflicts) {
    const sorted = items.slice().sort((a, b) => a.start - b.start || a.end - b.end || a.task.task_ref.localeCompare(b.task.task_ref));
    const heap = [], result = [];
    let furthest = null;
    for (const item of sorted) {
      if (furthest && item.start < furthest.end) { conflicts.add(item.task.task_ref); conflicts.add(furthest.task.task_ref); }
      if (!furthest || item.end > furthest.end) furthest = item;
      const lane = heap.length && heap[0].end <= item.start ? heapPop(heap).lane : result.length;
      if (!result[lane]) result[lane] = [];
      result[lane].push(item); heapPush(heap, { end: item.end, lane });
    }
    return result;
  }
  function prepare(data, mode, query, baseline, changedOnly = false) {
    const labels = names(data), needle = query.trim().toLocaleLowerCase();
    const directory = new Map(data.resources.map(row => [row.ref, row]));
    const comparison = data.projections.baseline;
    const changed = new Set(comparison.state === 'available' ? comparison.items.filter(item => item.change !== 'unchanged').map(item => item.operation_ref) : []);
    const matches = task => (!changedOnly || changed.has(task.operation_ref)) && (!needle || searchText(task, labels).includes(needle));
    const selected = data.tasks.filter(matches), selectedTasks = new Set(selected), groups = new Map(), conflicts = new Set();
    let start = instant(data.plan_span.start), end = instant(data.plan_span.end);
    const add = (task, before) => {
      const item = { task, start: instant(task.start), end: instant(task.end), baseline: before };
      if (before) { start = Math.min(start, item.start); end = Math.max(end, item.end); }
      const id = mode === 'batch' ? task.batch_id : task[mode + '_ref'] || 'unbound';
      if (!groups.has(id)) {
        const label = resourceLabel(task, mode, labels), resource = directory.get(id);
        groups.set(id, { id, label, code: resource && resource.business_code !== label ? resource.business_code : null, tasks: [], before: [] });
      }
      groups.get(id)[before ? 'before' : 'tasks'].push(item);
    };
    data.tasks.forEach(task => add(task, false));
    if (baseline && data.projections.baseline.state === 'available') data.projections.baseline.items.forEach(item => { if (item.before) add(item.before, true); });
    const P = window.PointContract, G = window.PointGanttModel;
    const bounds = G.bounds(start, end, Array.from(groups.values()).some(g => [...g.tasks, ...g.before].some(i => P.isPoint(i.task))));
    start = bounds.start; end = bounds.end;
    const occupancy = new Map(data.projections.occupancy.resources.filter(row => row.kind === mode).map(row => [row.resource_ref, row]));
    const preparedGroups = [];
    for (const group of groups.values()) {
      const overlap = new Set();
      const shown = new Set(group.tasks.filter(item => selectedTasks.has(item.task)));
      group.before.forEach(item => { if (matches(item.task)) shown.add(item); });
      const currentNormal = tracks(group.tasks.filter(i => !P.isPoint(i.task)), overlap);
      const oldNormal = tracks(group.before.filter(i => !P.isPoint(i.task)), new Set());
      const currentPoints = G.prepareTracks(group.tasks.filter(i => P.isPoint(i.task)));
      const oldPoints = G.prepareTracks(group.before.filter(i => P.isPoint(i.task)));
      // Visual overlap splits tracks; actual conflict color comes from the same server occupancy snapshot.
      const resourceOccupancy = occupancy.get(group.id);
      const segments = resourceOccupancy ? resourceOccupancy.segments.filter(item => item.concurrent_operations > 1)
        .map(item => ({ start: instant(item.start), end: instant(item.end) })) : [];
      for (const item of group.tasks) {
        if (P.isPoint(item.task)) continue;
        const hit = firstIntersecting(segments, item.start);
        if (hit < segments.length && segments[hit].start < item.end) conflicts.add(item.task.task_ref);
      }
      preparedGroups.push({ group, shown, currentNormal: currentNormal.map(lane => lane.filter(item => shown.has(item))),
        oldNormal: oldNormal.map(lane => lane.filter(item => shown.has(item))), currentPoints, oldPoints,
        overlap: overlap.size, occupancy: resourceOccupancy });
    }
    return { mode, labels, groups: preparedGroups, start, end, conflicts, tasks: selected };
  }
  function layoutPrepared(prepared, width = 1000) {
    const { mode, labels, start, end, conflicts, tasks } = prepared;
    const rows = [], locations = new Map(), baselineLocations = new Map(), G = window.PointGanttModel;
    let top = 0, groupCount = 0;
    for (const fact of prepared.groups) {
      const { group, shown, currentNormal, oldNormal } = fact, firstRow = rows.length;
      const currentPoints = fact.currentPoints.length ? G.layoutTracks(fact.currentPoints, start, end, width) : [];
      const oldPoints = fact.oldPoints.length ? G.layoutTracks(fact.oldPoints, start, end, width) : [];
      const currentCount = currentNormal.length + currentPoints.length;
      function append(items, before, point, track, trackCount, subrow, index) {
        if (!items.length) return;
        const height = before ? 26 : 56;
        const row = { ...group, items, top, height, before, occupancy: before ? null : fact.occupancy, point, track,
          trackCount, subrow, overlap: point ? 0 : fact.overlap, key: group.id + ':' + index };
        items.forEach(item => (before ? baselineLocations : locations).set(item.task.task_ref, { row: rows.length, top, item }));
        rows.push(row); top += height;
      }
      currentNormal.forEach((items, lane) => append(items, false, false, lane, currentNormal.length, lane + 1, lane));
      currentPoints.forEach((items, lane) => append(items.filter(item => shown.has(item)), false, true,
        currentNormal.length + lane, currentPoints.length, lane + 1, currentNormal.length + lane));
      oldNormal.forEach((items, lane) => append(items, true, false, lane, oldNormal.length, lane + 1, currentCount + lane));
      oldPoints.forEach((items, lane) => append(items.filter(item => shown.has(item)), true, true,
        oldNormal.length + lane, oldPoints.length, lane + 1, currentCount + oldNormal.length + lane));
      if (rows.length > firstRow) groupCount++;
    }
    return { mode, labels, rows, height: top, start, end, conflicts, locations, baselineLocations, tasks, groupCount };
  }
  function layout(data, mode, query, baseline, width = 1000, changedOnly = false) {
    return layoutPrepared(prepare(data, mode, query, baseline, changedOnly), width);
  }
  function firstIntersecting(items, start) {
    let low = 0, high = items.length;
    while (low < high) { const mid = (low + high) >> 1; if (items[mid].end <= start) low = mid + 1; else high = mid; }
    return low;
  }
  function visibleItems(items, start, end) {
    const low = firstIntersecting(items, start);
    const result = [];
    for (let index = low; index < items.length && items[index].start < end; index++) result.push(items[index]);
    return result;
  }
  function visibleRows(rows, start, end) {
    let low = 0, high = rows.length;
    while (low < high) { const mid = (low + high) >> 1; if (rows[mid].top + rows[mid].height < start) low = mid + 1; else high = mid; }
    const result = [];
    for (let index = low; index < rows.length && rows[index].top < end; index++) result.push(rows[index]);
    return result;
  }
  function tickStep(start, end, width) {
    const target = (end - start) / Math.max(1, width / 125);
    const steps = [1000, 5000, 15000, 30000, 60000, 300000, 900000, 1800000, 3600000, 10800000, 21600000, 43200000, 86400000, 172800000, 604800000, 2592000000, 31536000000];
    return steps.find(value => value >= target) || Math.ceil(target / 31536000000) * 31536000000;
  }
  function ticks(start, end, width, left, visibleWidth) {
    const step = tickStep(start, end, width);
    const low = start + Math.max(0, left - 150) / width * (end - start), high = Math.min(end, start + (left + visibleWidth + 150) / width * (end - start));
    const result = [];
    for (let at = Math.ceil(low / step) * step; at < high; at += step) result.push({ at, x: (at - start) / (end - start) * width, label: wire(at) });
    return result;
  }
  function taskTitle(task, labels, conflict) {
    return [task.batch_id + ' · ' + task.sequence + ' ' + task.process_label, pieceLabel(task),
      '本工序目标量：' + quantityLabel(task.quantity) + ' · 计划来源整批量：' + quantityLabel(task.batch_quantity),
      task.quantity_reason ? quantityReasons[task.quantity_reason] : null,
      window.PointContract.isPoint(task) ? '零工时工序 · 0 小时 · 不占设备人员' : null,
      timeLabel(task.start) + ' 至 ' + timeLabel(task.end), resourceLabel(task, 'machine', labels) + ' / ' + resourceLabel(task, 'operator', labels),
      conflict ? '资源时间冲突（安排重叠）' : null].filter(Boolean).join('\n');
  }
  function tone(task, risks) {
    return risks.get(task.batch_id) === 'overdue' ? 'critical' : 'primary';
  }
  window.PlanGanttModel = { instant, wire, timeLabel, number, count, quantityLabel, pieceLabel, quantityReasons, names, resourceLabel, searchText, prepare, layoutPrepared, layout, visibleItems, visibleRows, tickStep, ticks, taskTitle, tone, kindLabels, scopeCaption };
})();
