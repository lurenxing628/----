(function () {
  'use strict';
  const geometry = window.PlanGanttModel;
  const { instant, timeLabel, visibleItems, visibleRows } = geometry;
  // The candidate DTO preserves integers above MAX_SAFE_INTEGER as exact decimal text.
  // Comparison metrics keep up to three decimals; a one-decimal summary would make distinct candidates look identical.
  const number = value => typeof value === 'string' ? window.WorkbenchFormat.integerText(value) : window.WorkbenchFormat.number(value, { digits: 3, trim: true });
  // A real change below the three shown decimals must not read as "增加 0".
  const tiny = value => typeof value === 'number' && Number(Math.abs(value).toFixed(3)) === 0;
  const signedChange = value => value === 0 ? '不变' : (value > 0 ? '增加' : '减少') + (tiny(value) ? '不到 0.001' : ' ' + number(Math.abs(value)));
  const kindLabels = { machine: '设备', operator: '人员', batch: '批次' };
  const executionLabels = { target_quantity: '目标数量', known_completed_quantity: '已知完成数量', remaining_quantity: '剩余数量', execution_state: '执行状态', data_quality: '数据质量', target_basis: '数量计算方式',
    first_actual_start: '最早实际开工时间', confirmed_finish: '确认完工时间', unknown_record_count: '完成数量缺失记录数', records_complete: '报工记录资料', quantity_complete: '完成数量资料', completion_basis: '完成依据' };
  // 生成时的执行记录按项取词：执行状态与现场记录同一套叫法；数据质量的 complete 是“完整”，不能和执行状态的“已完工”混成一个词。
  const executionTexts = { execution_state: window.WorkbenchTerms.execution_states, data_quality: window.WorkbenchTerms.data_quality, target_basis: { piece: '件', batch: '批' },
    completion_basis: { complete_reports: '逐次报工记录', legacy_finish_event: '历史完工记录' } };
  function executionValue(value, key = 'execution_state') {
    if (Object.prototype.hasOwnProperty.call(executionTexts[key] || {}, value)) return executionTexts[key][value];
    if (['first_actual_start', 'confirmed_finish'].includes(key)) return timeLabel(value);
    if (typeof value === 'boolean') return ['records_complete', 'quantity_complete'].includes(key) ? value ? '完整' : '不完整' : value ? '是' : '否';
    return typeof value === 'string' ? value : number(value);
  }
  function executionField(task, key) {
    const value = task.execution_at_generation[key];
    if (value !== null && value !== undefined) return executionValue(value, key);
    const problem = task.data_gaps.find(row => row.field === 'execution_at_generation.' + key || row.field === 'execution_at_generation');
    return problem ? problem.message : '保存时未记录' + executionLabels[key] + '。';
  }
  function quantityLabel(task, key = 'quantity') {
    if (task[key] !== null) return number(task[key]);
    const fields = key === 'quantity'
      ? ['quantity', 'execution_at_generation.target_quantity', 'execution_at_generation.target_basis', 'execution_at_generation', 'piece_id']
      : ['batch_quantity', 'batch'];
    const problem = fields.map(field => task.data_gaps.find(item => item.field === field)).find(Boolean);
    return problem ? problem.message : key === 'quantity' ? '生成时工序目标量缺少依据。' : '生成时整批量缺少依据。';
  }
  const pieceLabel = t => t.piece_id === null ? (t.data_gaps || []).some(g => g.field === 'piece_id') ? '分件未记录' : '共同工序' : '分件 ' + t.piece_id;
  const searchText = t => [t.row_ref, t.operation_ref, t.batch_ref, t.batch_label, t.part_label, t.sequence, t.process_label, pieceLabel(t),
    t.machine && t.machine.label, t.operator && t.operator.label, t.reason && t.reason.message].filter(v => v != null).join(' ').toLocaleLowerCase();
  function matches(item, needle, operationRefs, focus) {
    return (!needle || item.search.includes(needle)) && (!operationRefs || operationRefs.has(item.task.operation_ref)) && resourceMatches(item.task, focus);
  }
  function matching(prepared, query, focus, unplanned) {
    const needle = query.trim().toLocaleLowerCase();
    return (unplanned ? prepared.unplanned : prepared.items).filter(item => matches(item, needle, null, focus)).map(item => item.task);
  }
  const resource = (t, mode) => mode === 'batch' ? { ref: t.batch_ref, label: t.batch_label } : t[mode];
  const resourceMatches = (task, focus) => !focus || !!task[focus.kind] && task[focus.kind].ref === focus.ref;
  function resourceLabel(side, kind) {
    const value = side[kind], label = kind === 'supplier' ? '供应商' : kindLabels[kind];
    if (value && value.label && value.ref !== null) return value.label;
    const gap = field => side.data_gaps.find(item => item.field === field);
    if (value) {
      const nameProblem = !value.label && (gap(kind + '.label') || gap(kind));
      const identityProblem = value.ref === null && (gap(kind + '.ref') || gap(kind));
      return (value.label || label + '名称未记录' + (nameProblem ? '：' + nameProblem.message : ''))
        + (value.ref === null ? '（身份未记录' + (identityProblem ? '：' + identityProblem.message : '') + '）' : '');
    }
    const problem = gap(kind) || gap(kind + '.ref');
    if (problem) return label + '身份未记录：' + problem.message;
    if (['unscheduled', 'skipped'].includes(side.status)) return '尚未安排';
    if (kind === 'supplier' && side.source === 'internal') return '不适用（内部工序）';
    if (kind !== 'supplier' && side.source === 'external') return '不适用（外协工序）';
    if (kind !== 'supplier' && window.PointContract.isPoint(side)) return '不占用（零工时工序）';
    return '未指定';
  }
  function laneLabel(row, reference) {
    const count = row.baseline || row.point ? row.laneCount : row.normalLaneCount;
    const suffix = count > 1 ? ' ' + (row.lane + 1) + '/' + count : '';
    if (row.baseline) return '原安排' + (row.baselinePoint ? ' · 零工时点' : '') + suffix;
    if (row.point) return (reference ? '正式归档 · ' : '') + '零工时点' + suffix;
    return count > 1 ? (reference ? '正式归档 · ' : '') + '重叠子行' + suffix : reference ? '正式归档' : '新安排';
  }
  function title(t) {
    return [t.batch_label || '批次未记录', number(t.sequence) + ' · ' + (t.process_label || '工序未记录'), pieceLabel(t),
      '本工序目标量：' + quantityLabel(t) + ' · 生成时整批量：' + quantityLabel(t, 'batch_quantity'), timeLabel(t.start) + ' 至 ' + timeLabel(t.end),
      window.PointContract.isPoint(t) ? '零工时工序 · 不占设备人员' : null,
      t.locked ? '保存时锁定标记' : null,
      '设备：' + resourceLabel(t, 'machine'), '人员：' + resourceLabel(t, 'operator'),
      t.source === 'external' ? '供应商：' + resourceLabel(t, 'supplier') : null].filter(Boolean).join('\n');
  }
  function push(heap, item) {
    let i = heap.length; heap.push(item);
    while (i > 0) { const p = (i - 1) >> 1; if (heap[p].end <= item.end) break; heap[i] = heap[p]; i = p; }
    heap[i] = item;
  }
  function pop(heap) {
    const first = heap[0], last = heap.pop(); if (!heap.length) return first;
    let i = 0;
    while (i * 2 + 1 < heap.length) {
      let c = i * 2 + 1; if (c + 1 < heap.length && heap[c + 1].end < heap[c].end) c++;
      if (heap[c].end >= last.end) break; heap[i] = heap[c]; i = c;
    }
    heap[i] = last; return first;
  }
  function tracks(items) {
    const heap = [], lanes = [];
    let furthest = null;
    items.sort((a, b) => a.start - b.start || a.end - b.end || a.task.row_ref.localeCompare(b.task.row_ref));
    for (const item of items) {
      if (furthest && item.start < furthest.end) { furthest.overlap = true; item.overlap = true; }
      if (!furthest || item.end > furthest.end) furthest = item;
      const lane = heap.length && heap[0].end <= item.start ? pop(heap).lane : lanes.length;
      if (!lanes[lane]) lanes[lane] = [];
      lanes[lane].push(item); push(heap, { end: item.end, lane });
    }
    return lanes;
  }
  function prepare(data) {
    const P = window.PointContract, G = window.PointGanttModel;
    const items = data.tasks.map(task => { const start = instant(task.start), end = instant(task.end);
      return { task, start, end, search: searchText(task), point: P.isPoint(task), plottable: Number.isFinite(start) && Number.isFinite(end) && end >= start }; });
    const bounds = G.bounds(data.task_span ? instant(data.task_span.start) : null, data.task_span ? instant(data.task_span.end) : null, items.some(item => item.point));
    return { items, unplanned: data.unplanned_operations.map(task => ({ task, search: searchText(task) })),
      taskIndex: new Map(items.map(item => [item.task.row_ref, item])), loadedRefs: new Set(items.map(item => item.task.row_ref)), start: bounds.start, end: bounds.end };
  }
  function groupPrepared(prepared, mode) {
    const groups = new Map(), G = window.PointGanttModel;
    for (const fact of prepared.items) {
      if (!fact.plottable) continue;
      // Overlap belongs to this resource grouping, while parsed time/search facts belong to the data.
      const item = { ...fact }, task = item.task, r = resource(task, mode), id = r && r.ref || 'missing:' + task.row_ref;
      if (!groups.has(id)) groups.set(id, { id, label: mode === 'batch' ? r.label || '批次未记录' : resourceLabel(task, mode), items: [] });
      groups.get(id).items.push(item);
    }
    for (const group of groups.values()) {
      group.normal = tracks(group.items.filter(item => !item.point));
      group.points = G.prepareTracks(group.items.filter(item => item.point));
    }
    return { ...prepared, groups };
  }
  function selectPrepared(prepared, query, operationRefs, focus) {
    const needle = query.trim().toLocaleLowerCase(), groups = new Map(), tasks = [], unplottableTasks = [], shownRefs = new Set(), taskOrder = new Map();
    for (const fact of prepared.items) if (matches(fact, needle, operationRefs, focus)) {
      if (fact.plottable) { taskOrder.set(fact.task.row_ref, tasks.length); tasks.push(fact.task); shownRefs.add(fact.task.row_ref); }
      else unplottableTasks.push(fact.task);
    }
    for (const [id, group] of prepared.groups) {
      const items = group.items.filter(item => matches(item, needle, operationRefs, focus));
      if (!items.length) continue;
      const shown = new Set(items);
      groups.set(id, { ...group, items, shown, normal: group.normal.map(lane => lane.filter(item => shown.has(item))) });
    }
    return { ...prepared, groups, tasks, shownRefs, taskOrder, unplottableTasks, groupCount: groups.size };
  }
  // 唯一调用方（RunBaselineModel.layoutPrepared）把点状工序单独成行：点状行自带 lane 与 laneCount。
  function groupRows(group, start, end, width) {
    const points = group.points.length ? window.PointGanttModel.layoutTracks(group.points, start, end, width).map(lane => lane.filter(item => group.shown.has(item))) : [];
    const laneCount = group.normal.length + points.length, rows = [];
    group.normal.forEach((items, lane) => { if (items.length) rows.push({ id: group.id, key: group.id + ':' + lane, label: group.label,
      items, height: 56, lane, laneCount, normalLaneCount: group.normal.length, point: false }); });
    points.forEach((items, lane) => { if (items.length) rows.push({ id: group.id,
      key: group.id + ':point:' + lane, label: group.label,
      items, height: 56, lane, laneCount: points.length, normalLaneCount: group.normal.length, point: true }); });
    return rows;
  }
  window.RunCandidateModel = { instant, timeLabel, number, signedChange, visibleItems, visibleRows, matching, prepare, groupPrepared, selectPrepared, groupRows, title, laneLabel, pieceLabel, quantityLabel, resourceLabel, resourceMatches, kindLabels, executionLabels, executionValue, executionField };
})();
