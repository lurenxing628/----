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
  const quantityReasons = window.FieldContract.quantityReasons;
  const kindLabels = { machine: '设备', operator: '人员', batch: '批次' };
  function scopeCaption(data) {
    const includesPlanEnd = data.scope.range_start === null && data.plan_span.end_inclusive === true;
    return includesPlanEnd && data.plan_span.start === data.plan_span.end
      ? `计划时刻：${timeLabel(data.plan_span.start)}`
      : `计划时间范围：${timeLabel(data.time_scope.range_start)} 至 ${timeLabel(data.time_scope.range_end)}（${includesPlanEnd ? '包含末端零工时工序' : '不含结束时刻'}）`;
  }
  function names(data) {
    return new Map(data.resources.map(row => [row.ref, row.label || row.business_code]));
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
    const sorted = items.sort((a, b) => a.start - b.start || a.end - b.end || a.task.task_ref.localeCompare(b.task.task_ref));
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
  function prepareTasks(data) {
    const labels = names(data), directory = new Map(data.resources.map(row => [row.ref, row]));
    const items = data.tasks.map(task => ({ task, baseline: false, start: instant(task.start), end: instant(task.end), search: searchText(task, labels), point: window.PointContract.isPoint(task) }));
    const taskIndex = new Map(items.map(item => [item.task.task_ref, item])), loadedRefs = new Set(items.map(item => item.task.task_ref)), resourceMembers = new Map();
    for (const item of items) for (const ref of [item.task.machine_ref, item.task.operator_ref]) {
      if (!ref) continue;
      if (!resourceMembers.has(ref)) resourceMembers.set(ref, []); resourceMembers.get(ref).push(item);
    }
    // 计划工作区的 delivery_risks.items 已由 PlanContract 校验为数组；值班台时间轴的合成数据不带这一键。
    const deliveryRisks = data.projections && data.projections.delivery_risks ? new Map(data.projections.delivery_risks.items.map(row => [row.batch_id, row])) : null;
    return {
      labels, directory, items, before: [], baselineLoaded: false, taskIndex, loadedRefs,
      beforeIndex: new Map(), comparisons: new Map(), changed: new Set(), occupancy: new Map(),
      deliveryRisks, resourceMembers, start: instant(data.plan_span.start), end: instant(data.plan_span.end)
    };
  }
  function prepareBaseline(data, taskFacts, baselineItems = null) {
    const { labels, taskIndex } = taskFacts;
    const comparison = data.projections && data.projections.baseline;
    const rawItems = Array.isArray(baselineItems) ? baselineItems : comparison && comparison.items;
    const baselineLoaded = Boolean(comparison && comparison.state === 'available' && (Array.isArray(baselineItems) || comparison.items_complete === true));
    const before = baselineLoaded ? rawItems.filter(item => item.before).map(item => ({
      task: item.before, baseline: true, start: instant(item.before.start), end: instant(item.before.end),
      search: searchText(item.before, labels), point: window.PointContract.isPoint(item.before)
    })) : [];
    const beforeIndex = new Map(before.map(item => [item.task.task_ref, item]));
    const times = (task, index) => task ? index.get(task.task_ref) || { start: instant(task.start), end: instant(task.end) } : null;
    const comparisons = new Map(baselineLoaded ? rawItems.map(item => [item.operation_ref,
      { ...item, beforeTime: times(item.before, beforeIndex), afterTime: times(item.after, taskIndex) }]) : []);
    const changed = new Set(baselineLoaded ? rawItems.filter(item => item.change !== 'unchanged').map(item => item.operation_ref) : []);
    return { before, baselineLoaded, beforeIndex, comparisons, changed };
  }
  function prepareOccupancy(data, previous, occupancyProjection, baseLabels) {
    const occ = occupancyProjection || data.projections && data.projections.occupancy;
    const labels = baseLabels;
    const prevMap = previous && previous.occupancy;
    const occupancy = new Map((occ && occ.resources || []).map(row => {
      const raw = row.has_overlap ? row.conflict_segments : [];
      const prev = prevMap && prevMap.get(row.resource_ref);
      const prevSegments = prev && prev.segments;
      const segments = prevSegments && prevSegments.length === raw.length
        && raw.every((item, i) => prevSegments[i].rawStart === item.start && prevSegments[i].rawEnd === item.end)
        ? prevSegments
        : raw.map(item => {
          const match = prevSegments && prevSegments.find(seg => seg.rawStart === item.start && seg.rawEnd === item.end);
          return match || { start: instant(item.start), end: instant(item.end), rawStart: item.start, rawEnd: item.end };
        });
      return [row.resource_ref, { resource: row, segments }];
    }));
    return { labels, occupancy };
  }
  function combinePrepared(taskFacts, baselineFacts, occupancyFacts) {
    return { ...taskFacts, ...baselineFacts, ...occupancyFacts };
  }
  function groupPrepared(prepared, mode) {
    const { items, labels, directory, occupancy, start, end, taskIndex, loadedRefs, deliveryRisks, resourceMembers } = prepared;
    const groups = new Map(), conflicts = new Set();
    for (const item of items) {
      const task = item.task, id = mode === 'batch' ? task.batch_id : task[mode + '_ref'] || 'unbound';
      if (!groups.has(id)) {
        const label = resourceLabel(task, mode, labels), resource = directory.get(id);
        groups.set(id, { id, label, code: resource && resource.business_code !== label ? resource.business_code : null, tasks: [], before: [] });
      }
      groups.get(id).tasks.push(item);
    }
    const G = window.PointGanttModel, bounds = G.bounds(start, end, items.some(item => item.point));
    const facts = [];
    for (const group of groups.values()) {
      const overlap = new Set(), resource = occupancy.get(group.id), segments = resource ? resource.segments : [];
      const currentNormal = tracks(group.tasks.filter(item => !item.point), overlap);
      for (const item of group.tasks) {
        if (item.point) continue;
        const hit = firstIntersecting(segments, item.start);
        if (hit < segments.length && segments[hit].start < item.end) conflicts.add(item.task.task_ref);
      }
      facts.push({ group, currentNormal, oldNormal: [], currentPoints: G.prepareTracks(group.tasks.filter(item => item.point)),
        oldPoints: [], overlap: overlap.size, occupancy: resource && resource.resource });
    }
    return { mode, groups: facts, start: bounds.start, end: bounds.end, conflicts, items, labels, directory, occupancy, taskIndex, loadedRefs, deliveryRisks, resourceMembers };
  }
  function groupBaseline(prepared, mode) {
    const { before, labels, directory, items } = prepared, groups = new Map(), G = window.PointGanttModel;
    let start = prepared.start, end = prepared.end;
    for (const item of before) {
      const task = item.task, id = mode === 'batch' ? task.batch_id : task[mode + '_ref'] || 'unbound';
      if (!groups.has(id)) {
        const label = resourceLabel(task, mode, labels), resource = directory.get(id);
        groups.set(id, { id, label, code: resource && resource.business_code !== label ? resource.business_code : null, tasks: [], before: [] });
      }
      groups.get(id).before.push(item);
      start = Math.min(start, item.start); end = Math.max(end, item.end);
    }
    const comparisonBounds = G.bounds(start, end, items.some(item => item.point) || before.some(item => item.point));
    const baselineGroups = new Map();
    for (const [id, group] of groups.entries()) {
      baselineGroups.set(id, {
        group,
        oldNormal: tracks(group.before.filter(item => !item.point), new Set()),
        oldPoints: G.prepareTracks(group.before.filter(item => item.point))
      });
    }
    return { groups: baselineGroups, baselineStart: comparisonBounds.start, baselineEnd: comparisonBounds.end };
  }
  function matching(prepared, query) {
    const needle = query.trim().toLocaleLowerCase();
    return prepared.items.filter(item => !needle || item.search.includes(needle));
  }
  function selectPrepared(grouped, query = '', changedOnly = false, baseline = false, baselineFacts = null, baselineGrouped = null) {
    const changed = baselineFacts ? baselineFacts.changed : new Set();
    const beforeItems = baselineFacts ? baselineFacts.before : [];
    const needle = query.trim().toLocaleLowerCase();
    const selected = grouped.items.filter(item => (!changedOnly || changed.has(item.task.operation_ref)) && (!needle || item.search.includes(needle)));
    const shown = new Set(selected);
    const tasks = selected.map(item => item.task), shownRefs = new Set(tasks.map(task => task.task_ref));
    const taskOrder = new Map(tasks.map((task, index) => [task.task_ref, index]));
    const latestBaseline = baselineFacts ? {
      before: baselineFacts.before,
      baselineLoaded: Boolean(baselineFacts.baselineLoaded),
      beforeIndex: baselineFacts.beforeIndex,
      comparisons: baselineFacts.comparisons,
      changed: baselineFacts.changed
    } : { baselineLoaded: false };
    if (!baseline) {
      const groups = grouped.groups.map(fact => ({ ...fact, shown,
        group: { ...fact.group, tasks: fact.group.tasks.filter(item => shown.has(item)), before: [] },
        currentNormal: fact.currentNormal.map(lane => lane.filter(item => shown.has(item))),
        oldNormal: [], oldPoints: [] }));
      return { ...grouped, ...latestBaseline, groups, tasks, shownRefs, taskOrder, start: grouped.start, end: grouped.end };
    }
    for (const item of beforeItems) if ((!changedOnly || changed.has(item.task.operation_ref)) && (!needle || item.search.includes(needle))) shown.add(item);
    const seenIds = new Set();
    const groups = grouped.groups.map(fact => {
      seenIds.add(fact.group.id);
      const bFact = baselineGrouped.groups.get(fact.group.id);
      const before = bFact ? bFact.group.before.filter(item => shown.has(item)) : [];
      return { ...fact, shown,
        group: { ...fact.group, tasks: fact.group.tasks.filter(item => shown.has(item)), before },
        currentNormal: fact.currentNormal.map(lane => lane.filter(item => shown.has(item))),
        oldNormal: bFact ? bFact.oldNormal.map(lane => lane.filter(item => shown.has(item))) : [],
        oldPoints: bFact ? bFact.oldPoints : [] };
    });
    for (const [id, bFact] of baselineGrouped.groups.entries()) {
      if (seenIds.has(id)) continue;
      groups.push({
        group: { ...bFact.group, tasks: [], before: bFact.group.before.filter(item => shown.has(item)) },
        shown, currentNormal: [], currentPoints: [],
        oldNormal: bFact.oldNormal.map(lane => lane.filter(item => shown.has(item))),
        oldPoints: bFact.oldPoints, overlap: 0,
        occupancy: grouped.occupancy && grouped.occupancy.get(id) && grouped.occupancy.get(id).resource
      });
    }
    return { ...grouped, ...latestBaseline, groups, tasks, shownRefs, taskOrder, start: baselineGrouped.baselineStart, end: baselineGrouped.baselineEnd };
  }
  function layoutPrepared(prepared, width) {
    const { mode, labels, start, end, conflicts, tasks, shownRefs, taskOrder } = prepared;
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
    return { mode, labels, rows, height: top, start, end, conflicts, locations, baselineLocations, tasks, shownRefs, taskOrder, groupCount };
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
    const span = end > start ? end - start : 1;
    const target = span / Math.max(1, width / 125);
    const steps = [1000, 5000, 15000, 30000, 60000, 300000, 900000, 1800000, 3600000, 10800000, 21600000, 43200000, 86400000, 172800000, 604800000, 2592000000, 31536000000];
    return steps.find(value => value >= target) || Math.ceil(target / 31536000000) * 31536000000;
  }
  function ticks(start, end, width, left, visibleWidth) {
    const span = end > start ? end - start : 1, step = tickStep(start, end, width);
    const low = start + Math.max(0, left - 150) / width * span, high = Math.min(end, start + (left + visibleWidth + 150) / width * span);
    const result = [];
    for (let at = Math.ceil(low / step) * step; at < high; at += step) result.push({ at, x: (at - start) / span * width, label: wire(at) });
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
  window.PlanGanttModel = { instant, wire, timeLabel, number, count, quantityLabel, pieceLabel, quantityReasons, names, resourceLabel, searchText, prepareTasks, prepareBaseline, prepareOccupancy, combinePrepared, groupPrepared, groupBaseline, matching, selectPrepared, layoutPrepared, visibleItems, visibleRows, tickStep, ticks, taskTitle, tone, kindLabels, scopeCaption };
})();
