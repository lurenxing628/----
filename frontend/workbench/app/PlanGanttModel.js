(function () {
  'use strict';
  // Factory-local wall-clock coordinates, deliberately independent of browser DST.
  const instant = value => Date.parse(value + 'Z');
  const wire = value => new Date(value).toISOString().slice(0, 19);
  const timeLabel = value => window.WorkbenchFormat.dateTime(value, { seconds: true });
  const number = value => window.WorkbenchFormat.number(value, { digits: 2 });
  const quantityLabel = value => value === null ? '未知' : typeof value === 'string' ? value : number(value);
  const pieceLabel = task => task.piece_id === null ? '共同工序' : '分件 ' + task.piece_id;
  const quantityReasons = { plan_target_not_recorded: '原计划未记录目标量。',
    plan_target_unavailable: '采用记录或来源资料不完整，原计划目标量暂不可用。',
    plan_target_invalid: '原来的数量依据无效或缺失，没有推算目标量。' };
  const kindLabels = { machine: '设备', operator: '人员', batch: '批次' };
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
  function layout(data, mode, query, baseline, width = 1000, changedOnly = false) {
    const labels = names(data), needle = query.trim().toLocaleLowerCase();
    const comparison = data.projections.baseline;
    const changed = new Set(comparison.state === 'available' ? comparison.items.filter(item => item.change !== 'unchanged').map(item => item.operation_ref) : []);
    const matches = task => (!changedOnly || changed.has(task.operation_ref)) && (!needle || searchText(task, labels).includes(needle));
    const selected = data.tasks.filter(matches), groups = new Map(), conflicts = new Set(), locations = new Map();
    let start = instant(data.plan_span.start), end = instant(data.plan_span.end);
    const add = (task, before) => {
      const item = { task, start: instant(task.start), end: instant(task.end), baseline: before };
      if (before) { start = Math.min(start, item.start); end = Math.max(end, item.end); }
      const id = mode === 'batch' ? task.batch_id : task[mode + '_ref'] || 'unbound';
      if (!groups.has(id)) groups.set(id, { id, label: resourceLabel(task, mode, labels), tasks: [], before: [] });
      groups.get(id)[before ? 'before' : 'tasks'].push(item);
    };
    data.tasks.forEach(task => add(task, false));
    if (baseline && data.projections.baseline.state === 'available') data.projections.baseline.items.forEach(item => { if (item.before) add(item.before, true); });
    const P = window.PointContract, G = window.PointGanttModel;
    const bounds = G.bounds(start, end, Array.from(groups.values()).some(g => [...g.tasks, ...g.before].some(i => P.isPoint(i.task))));
    start = bounds.start; end = bounds.end;
    let top = 0;
    const rows = [];
    const occupancy = new Map(data.projections.occupancy.resources.filter(row => row.kind === mode).map(row => [row.resource_ref,
      row.segments.filter(item => item.concurrent_operations > 1).map(item => ({ start: instant(item.start), end: instant(item.end) }))]));
    for (const group of groups.values()) {
      const overlap = new Set();
      const split = (items, conflicts) => [...tracks(items.filter(i => !P.isPoint(i.task)), conflicts),
        ...G.tracks(items.filter(i => P.isPoint(i.task)), start, end, width)];
      const current = split(group.tasks, overlap), old = split(group.before, new Set());
      // Visual overlap splits tracks; actual conflict color comes from the same server occupancy snapshot.
      const segments = occupancy.get(group.id) || [];
      for (const item of group.tasks) {
        if (P.isPoint(item.task)) continue;
        const hit = firstIntersecting(segments, item.start);
        if (hit < segments.length && segments[hit].start < item.end) conflicts.add(item.task.task_ref);
      }
      [...current, ...old].forEach((all, index) => {
        const items = all.filter(item => matches(item.task));
        if (!items.length) return;
        const before = index >= current.length, height = before ? 26 : 56;
        const row = { ...group, items, top, height, before, point: P.isPoint(items[0].task), track: before ? index - current.length : index,
          trackCount: before ? old.length : current.length, overlap: P.isPoint(items[0].task) ? 0 : overlap.size, key: group.id + ':' + index };
        items.forEach(item => locations.set(item.task.task_ref, { row: rows.length, top, item }));
        rows.push(row); top += height;
      });
    }
    return { labels, rows, height: top, start, end, conflicts, locations, tasks: selected, groupCount: new Set(rows.map(row => row.id)).size };
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
  function ticks(start, end, width, left, visibleWidth) {
    const target = (end - start) / Math.max(1, width / 125);
    const steps = [1000, 5000, 15000, 30000, 60000, 300000, 900000, 1800000, 3600000, 10800000, 21600000, 43200000, 86400000, 172800000, 604800000, 2592000000, 31536000000];
    const step = steps.find(value => value >= target) || Math.ceil(target / 31536000000) * 31536000000;
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
      timeLabel(task.start) + ' → ' + timeLabel(task.end), resourceLabel(task, 'machine', labels) + ' / ' + resourceLabel(task, 'operator', labels),
      conflict ? '资源时间冲突（安排重叠）' : null].filter(Boolean).join('\n');
  }
  function tone(task, conflicts, risks) {
    if (conflicts.has(task.task_ref)) return 'critical';
    const risk = risks.get(task.batch_id);
    return risk === 'overdue' ? 'critical' : risk === 'on_time' ? 'success' : 'primary';
  }
  window.PlanGanttModel = { instant, wire, timeLabel, number, quantityLabel, pieceLabel, quantityReasons, names, resourceLabel, searchText, layout, visibleItems, visibleRows, ticks, taskTitle, tone, kindLabels };
})();
