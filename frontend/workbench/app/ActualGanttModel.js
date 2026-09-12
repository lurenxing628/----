(function () {
  'use strict';
  const HOUR = 3600000;
  // UTC is only a numeric coordinate system here, never the wire time zone.
  const instant = value => value ? Date.parse(value + 'Z') : NaN;
  const wire = value => new Date(value).toISOString().slice(0, 19);
  const time = value => window.WorkbenchFormat.dateTime(value, { seconds: true });
  const number = value => window.WorkbenchFormat.number(value, { digits: 2 });
  const pieceLabel = task => task.piece_id === null ? '共同工序' : '分件 ' + task.piece_id;
  const taskLabel = task => task.batch_id + ' · ' + task.sequence + ' ' + task.process_label + ' · ' + pieceLabel(task);
  const quantityReasons = { plan_target_not_recorded: '旧计划未记录原数量证据', plan_target_unavailable: '原计划数量证据不可用', plan_target_invalid: '原计划数量证据无效' };
  const states = { unreported: '待报工', started: '已开工', partial: '部分报工', paused: '已暂停', exception: '异常', complete: '整道已完工' };
  const views = { machine: '设备', operator: '人员', batch: '批次' };
  const lateLabels = { all: '全部工序', finishLate: '已完晚', unclosed: '到期未确认完成', forecastLate: '剩余安排预计晚' };
  const names = data => new Map(data.resources.map(row => [row.ref, row.label || row.business_code]));
  function deadlines(item, asOf) {
    const e = item.execution, end = instant(item.task.end);
    if (!e) return { finishLate: false, unclosed: false, forecastLate: false };
    return { finishLate: e.execution_state === 'complete' && instant(e.confirmed_finish) - end > 600000,
      unclosed: e.execution_state !== 'complete' && end <= instant(asOf),
      forecastLate: e.execution_state !== 'complete' && !!e.remaining_plan && instant(e.remaining_plan.end) - end > 600000 };
  }
  function searchText(item, labels) {
    const t = item.task, e = item.execution;
    const text = [t.batch_id, t.sequence, t.process_label, t.piece_id, labels.get(t.machine_ref), labels.get(t.operator_ref)];
    if (e) {
      e.reports.forEach(r => text.push(r.report_no, labels.get(r.actual_machine_ref), labels.get(r.actual_operator_ref)));
      e.legacy_facts.forEach(fact => text.push(labels.get(fact.actual_machine_ref), labels.get(fact.actual_operator_ref)));
      if (e.remaining_plan) text.push(labels.get(e.remaining_plan.machine_ref), labels.get(e.remaining_plan.operator_ref));
    }
    return text.map(value => value == null ? '' : value).join(' ').toLowerCase();
  }
  function filter(data, view, asOf) {
    const labels = names(data), query = view.query.trim().toLowerCase();
    return data.items.filter(item => (!query || searchText(item, labels).includes(query)) &&
      (view.late === 'all' || deadlines(item, asOf)[view.late]) && (!view.onlySelected || item.task.task_ref === view.selected));
  }
  function push(heap, item) {
    let at = heap.length; heap.push(item);
    while (at) { const parent = (at - 1) >> 1; if (heap[parent].end <= item.end) break; heap[at] = heap[parent]; at = parent; }
    heap[at] = item;
  }
  function pop(heap) {
    const first = heap[0], last = heap.pop(); if (!heap.length) return first;
    let at = 0;
    while (at * 2 + 1 < heap.length) {
      let child = at * 2 + 1; if (child + 1 < heap.length && heap[child + 1].end < heap[child].end) child++;
      if (heap[child].end >= last.end) break; heap[at] = heap[child]; at = child;
    }
    heap[at] = last; return first;
  }
  function tracks(reports) {
    const owners = new Map(), result = [];
    reports.slice().sort((a, b) => instant(a.actual_start) - instant(b.actual_start) || a.report_ref.localeCompare(b.report_ref)).forEach(report => {
      if (!report.actual_start || !report.actual_end || report.actual_start === report.actual_end) {
        result.push([report]); return;
      }
      const key = JSON.stringify([report.actual_machine_ref, report.actual_operator_ref]);
      if (!owners.has(key)) owners.set(key, []);
      const heap = owners.get(key), start = instant(report.actual_start);
      const index = heap.length && heap[0].end <= start ? pop(heap).index : result.length;
      if (!result[index]) result[index] = [];
      result[index].push(report);
      push(heap, { end: report.actual_end ? instant(report.actual_end) : Infinity, index });
    });
    return result;
  }
  function layout(data, view, asOf) {
    const labels = names(data), items = filter(data, view, asOf), groups = new Map(), locations = new Map(), reportLocations = new Map();
    function group(item, owner) {
      const ref = view.mode === 'batch' ? item.task.batch_id : owner[view.mode + '_ref'] || 'unbound';
      if (!groups.has(ref)) groups.set(ref, { id: ref, label: view.mode === 'batch' ? ref : labels.get(ref) || views[view.mode] + '未填写', members: new Map() });
      const members = groups.get(ref).members;
      if (!members.has(item.task.task_ref)) members.set(item.task.task_ref, { item, baseline: false, reports: [], legacy: [], remaining: false });
      return members.get(item.task.task_ref);
    }
    items.forEach(item => {
      group(item, item.task).baseline = true;
      const e = item.execution; if (!e) return;
      e.reports.forEach(report => group(item, { machine_ref: report.actual_machine_ref, operator_ref: report.actual_operator_ref }).reports.push(report));
      e.legacy_facts.forEach(fact => {
        if (fact.actual_machine_ref || fact.actual_operator_ref) group(item, { machine_ref: fact.actual_machine_ref, operator_ref: fact.actual_operator_ref }).legacy.push(fact);
      });
      if (e.execution_state !== 'complete' && e.remaining_quantity !== 0) group(item, e.remaining_plan || item.task).remaining = true;
    });
    const rows = []; let top = 0;
    function append(row) { row.top = top; rows.push(row); top += row.height; }
    groups.forEach(g => {
      const reports = Array.from(g.members.values()).flatMap(member => member.reports);
      g.reportCount = reports.length;
      g.legacyCount = Array.from(g.members.values()).reduce((sum, member) => sum + member.legacy.length, 0);
      const known = reports.filter(report => report.effective_processing_hours != null);
      g.knownHours = known.length ? known.reduce((total, report) => total + report.effective_processing_hours, 0) : null;
      g.unknownHours = reports.filter(report => report.effective_processing_hours == null).length;
      append({ key: 'group:' + g.id, group: g, kind: 'group', height: 56 });
      if (view.collapsed[g.id]) return;
      g.members.forEach(member => {
        const { item } = member, ts = tracks(member.reports);
        if (!ts.length) ts.push([]);
        ts.forEach((reports, i) => {
          const row = { key: g.id + ':' + item.task.task_ref + ':' + i, group: g, item, reports,
            baseline: i === 0 && member.baseline, kind: 'actual', height: 88, track: i + 1, trackCount: ts.length };
          append(row);
          if (!locations.has(item.task.task_ref) || i === 0 && member.baseline) locations.set(item.task.task_ref, row);
          reports.forEach(report => reportLocations.set(report.report_ref, row));
        });
        if (member.remaining) append({ key: g.id + ':' + item.task.task_ref + ':remaining', group: g, item, reports: [], baseline: false, kind: 'remaining', height: 64 });
      });
    });
    const hasPoints = items.some(item => window.PointContract.isPoint(item.task) || item.execution && item.execution.reports.some(r => r.actual_start && (!r.actual_end || r.actual_start === r.actual_end)));
    const axis = window.PointGanttModel.bounds(instant(data.axis_span.start), instant(data.axis_span.end), hasPoints);
    return { labels, items, groups: Array.from(groups.values()), rows, height: top, locations, reportLocations, executionAvailable: !!data.availability && data.availability.state === 'available',
      start: axis.start, end: axis.end, asOf: instant(asOf) };
  }
  function visibleRows(rows, top, bottom) {
    let low = 0, high = rows.length;
    while (low < high) { const mid = (low + high) >> 1; if (rows[mid].top + rows[mid].height <= top) low = mid + 1; else high = mid; }
    const result = []; for (let at = low; at < rows.length && rows[at].top < bottom; at++) result.push(rows[at]); return result;
  }
  function marks(row) {
    const result = [], t = row.item.task, e = row.item.execution;
    if (row.baseline) {
      const point = window.PointContract.isPoint(t);
      result.push({ key: 'plan', kind: point ? 'plan-point' : 'plan', start: instant(t.start), end: instant(t.end), y: point ? 64 : 74, height: point ? 24 : 7 });
    }
    row.reports.forEach(report => {
      if (!report.actual_start) return;
      const point = !report.actual_end || report.actual_end === report.actual_start;
      result.push({ key: report.report_ref, kind: point ? 'point' : 'actual', report,
        start: instant(report.actual_start), end: instant(report.actual_end || report.actual_start), y: point ? 20 : 14, height: point ? 24 : 38 });
    });
    if (row.kind === 'remaining' && e.remaining_plan) result.push({ key: 'remaining', kind: 'remaining', start: instant(e.remaining_plan.start), end: instant(e.remaining_plan.end), y: 14, height: 34 });
    return result;
  }
  function tickStep(model, width) {
    const steps = [1000, 10000, 60000, 300000, 900000, HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR, 24 * HOUR, 7 * 24 * HOUR, 30 * 24 * HOUR, 365 * 24 * HOUR];
    const target = (model.end - model.start) * 135 / width;
    return steps.find(v => v >= target) || Math.ceil(target / HOUR) * HOUR;
  }
  function tickLabel(step) {
    const unit = [[24 * HOUR, '天'], [HOUR, '小时'], [60000, '分钟'], [1000, '秒']].find(([size]) => step % size === 0);
    return step / unit[0] + ' ' + unit[1];
  }
  function ticks(model, width, left, viewport) {
    const step = tickStep(model, width);
    const low = model.start + left / width * (model.end - model.start), high = model.start + (left + viewport) / width * (model.end - model.start), result = [];
    for (let at = Math.ceil(low / step) * step; at < high; at += step) result.push({ at, x: (at - model.start) / (model.end - model.start) * width, label: wire(at) });
    return result;
  }
  function describe(item, labels, report) {
    const t = item.task, e = item.execution;
    const result = [taskLabel(t), '计划应做：' + number(t.quantity) + ' 件 · 批次：' + number(t.batch_quantity) + ' 件',
      '原计划：' + time(t.start) + ' → ' + time(t.end),
      '计划资源：' + (labels.get(t.machine_ref) || '设备未填写') + ' / ' + (labels.get(t.operator_ref) || '人员未填写')];
    if (window.PointContract.isPoint(t)) result.push('计划点 · 0 秒 · 不占用排产资源；完成状态以实际记录为准');
    if (t.quantity_reason) result.push(quantityReasons[t.quantity_reason]);
    if (!e) return result.concat('执行投影不可用');
    result.push(states[e.execution_state] + ' · 已知完成 ' + number(e.known_completed_quantity) + ' 件',
      '整道实际完工：' + time(e.confirmed_finish), '剩余数量：' + number(e.remaining_quantity),
      e.completion_basis === 'legacy_finish_event' ? '旧完工事件确认完成；旧数量与工时可能未记录' : '完成依据：逐次执行投影');
    if (report) result.push('本次报工：' + report.report_no, '实际：' + time(report.actual_start) + ' → ' + (report.actual_end ? time(report.actual_end) : '本次结束未填写'),
      '本次数量：' + number(report.completed_quantity) + ' · 有效工时：' + number(report.effective_processing_hours) + 'h',
      '实际资源：' + (labels.get(report.actual_machine_ref) || '设备未填写') + ' / ' + (labels.get(report.actual_operator_ref) || '人员未填写'), '备注：' + (report.remark || '未填写'));
    return result;
  }
  function markTitle(mark, item, labels) {
    const heading = mark.kind === 'plan-point' ? '原计划点基线' : mark.kind === 'plan' ? '原计划基线' : mark.kind === 'remaining' ? '已有剩余安排' : mark.kind === 'point' ? (mark.report.actual_end ? '报工时点' : '报工开工时点 · 结束未填写') : '实际报工时段';
    return [heading].concat(describe(item, labels, mark.report)).join('\n');
  }
  function metrics(data) {
    const available = data.availability.state === 'available';
    if (!available) return { complete: null, reported: null, pending: null, average: null };
    const complete = data.items.filter(item => item.execution.execution_state === 'complete');
    const deltas = complete.map(item => (instant(item.execution.confirmed_finish) - instant(item.task.end)) / 60000).filter(Number.isFinite);
    return { complete: complete.length, reported: data.items.filter(item => !['complete', 'unreported'].includes(item.execution.execution_state)).length,
      pending: data.items.filter(item => item.execution.execution_state === 'unreported').length,
      average: deltas.length ? deltas.reduce((sum, n) => sum + n, 0) / deltas.length : null };
  }
  window.ActualGanttModel = { instant, wire, time, number, pieceLabel, taskLabel, states, views, lateLabels, names, deadlines, searchText, filter, tracks, layout, visibleRows, marks, tickStep, tickLabel, ticks, describe, markTitle, metrics };
})();
