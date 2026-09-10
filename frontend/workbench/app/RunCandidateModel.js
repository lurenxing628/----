(function () {
  'use strict';
  const geometry = window.PlanGanttModel;
  const { instant, timeLabel, wire, visibleItems, visibleRows, ticks } = geometry;
  const number = value => value === null || value === undefined ? '未知' : typeof value === 'string' ? value : value.toLocaleString('zh-CN', { maximumFractionDigits: 3 });
  const signedChange = value => value === 0 ? '不变' : (value > 0 ? '增加 ' : '减少 ') + number(Math.abs(value));
  const kindLabels = { machine: '设备', operator: '人员', batch: '批次' };
  const metricLabels = { overdue_count: '超期批次', total_tardiness_hours: '总拖期 h', makespan_hours: '安排跨度 h', changeover_count: '换型次数',
    weighted_tardiness_hours: '加权拖期 h', machine_used_count: '已用设备', operator_used_count: '已用人员', machine_busy_hours_total: '设备占用 h',
    operator_busy_hours_total: '人员占用 h', machine_util_avg: '设备利用率', operator_util_avg: '人员利用率', elapsed_seconds: '计算耗时 s' };
  const executionLabels = { target_quantity: '目标数量', known_completed_quantity: '已知完成数量', remaining_quantity: '剩余数量', execution_state: '执行状态', data_quality: '数据质量', target_basis: '数量口径' };
  const executionValue = v => ({ complete: '完成', paused: '暂停', exception: '异常', partial: '部分完成', started: '已开工', unreported: '未报工', invalid: '无效',
    legacy_incomplete: '历史资料不完整', incomplete: '不完整', piece: '件', batch: '批' }[v] || number(v));
  const pieceLabel = t => t.piece_id === null ? (t.data_gaps || []).some(g => g.field === 'piece_id') ? '分件未记录' : '共同工序' : '分件 ' + t.piece_id;
  const searchText = t => [t.row_ref, t.operation_ref, t.batch_ref, t.batch_label, t.part_label, t.sequence, t.process_label, pieceLabel(t),
    t.machine && t.machine.label, t.operator && t.operator.label, t.reason && t.reason.message].filter(v => v != null).join(' ').toLocaleLowerCase();
  const matching = (tasks, query) => { const needle = query.trim().toLocaleLowerCase(); return needle ? tasks.filter(t => searchText(t).includes(needle)) : tasks; };
  const resource = (t, mode) => mode === 'batch' ? { ref: t.batch_ref, label: t.batch_label } : t[mode];
  function title(t) {
    return [t.batch_label || '批次未记录', number(t.sequence) + ' · ' + (t.process_label || '工序未记录'), pieceLabel(t),
      '本工序目标量：' + number(t.quantity) + ' · 生成时整批量：' + number(t.batch_quantity), timeLabel(t.start) + ' 至 ' + timeLabel(t.end),
      window.PointContract.isPoint(t) ? '时间点 · 0 h · 不占用资源' : null,
      '设备：' + (t.machine && t.machine.label || '未记录'), '人员：' + (t.operator && t.operator.label || '未记录'), '行引用：' + t.row_ref].filter(Boolean).join('\n');
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
    items.sort((a, b) => a.start - b.start || a.end - b.end || a.task.row_ref.localeCompare(b.task.row_ref));
    for (const item of items) {
      const lane = heap.length && heap[0].end <= item.start ? pop(heap).lane : lanes.length;
      if (!lanes[lane]) lanes[lane] = [];
      lanes[lane].push(item); push(heap, { end: item.end, lane });
    }
    return lanes;
  }
  function layout(data, mode, query, width = 1000) {
    const groups = new Map(), rows = [], locations = new Map(), tasks = matching(data.tasks, query);
    const P = window.PointContract, G = window.PointGanttModel;
    const bounds = G.bounds(data.task_span ? instant(data.task_span.start) : null, data.task_span ? instant(data.task_span.end) : null, data.tasks.some(P.isPoint));
    // Missing references never merge unrelated named resources into an invented identity.
    for (const task of tasks) {
      const r = resource(task, mode), id = r && r.ref || 'missing:' + task.row_ref;
      if (!groups.has(id)) groups.set(id, { id, label: r && r.label || kindLabels[mode] + '未记录', items: [] });
      groups.get(id).items.push({ task, start: instant(task.start), end: instant(task.end) });
    }
    let top = 0;
    for (const group of groups.values()) {
      const normal = tracks(group.items.filter(i => !P.isPoint(i.task)));
      const lanes = [...normal,
        ...G.tracks(group.items.filter(i => P.isPoint(i.task)), bounds.start, bounds.end, width)];
      lanes.forEach((items, lane) => {
        const row = { id: group.id, key: group.id + ':' + lane, label: group.label, items, top, height: 48, lane, laneCount: lanes.length, normalLaneCount: normal.length, point: P.isPoint(items[0].task) };
        items.forEach(item => locations.set(item.task.row_ref, { row: rows.length, top, item })); rows.push(row); top += row.height;
      });
    }
    return { rows, height: top, locations, tasks, groupCount: groups.size,
      start: bounds.start, end: bounds.end };
  }
  window.RunCandidateModel = { instant, wire, timeLabel, number, signedChange, visibleItems, visibleRows, ticks, matching, layout, title, pieceLabel, kindLabels, metricLabels, executionLabels, executionValue };
})();
