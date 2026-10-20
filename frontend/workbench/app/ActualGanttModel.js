(function () {
  'use strict';
  const HOUR = 3600000;
  const instant = window.PlanGanttModel.instant;
  const wire = value => new Date(value).toISOString().slice(0, 19);
  // Same label rule as the field records: minute precision, seconds shown only when they are not :00.
  const time = value => window.FieldContract.date(value);
  // Readable file stamp for downloads: 2026-09-21_1646 instead of the raw wire time.
  const fileStamp = value => value.slice(0, 10) + '_' + value.slice(11, 16).replace(':', '');
  const number = value => window.WorkbenchFormat.number(value, { digits: 2 });
  const hours = value => window.WorkbenchFormat.hours(value, { digits: 2 });
  const pieceLabel = task => task.piece_id === null ? '共同工序' : '分件 ' + task.piece_id;
  const taskLabel = task => task.batch_id + ' · ' + task.sequence + ' ' + task.process_label + ' · ' + pieceLabel(task);
  const quantityReasons = window.FieldContract.quantityReasons;
  // 报工状态只有 FieldContract 那一份词表，本页不再另起一套叫法。
  const states = window.FieldContract.states;
  const views = { machine: '设备', operator: '人员', batch: '批次' };
  const lateLabels = { all: '全部工序', finishLate: '已晚完成', unclosed: '到期未确认完成', forecastLate: '剩余安排预计晚完成' };
  const names = data => new Map(data.resources.map(row => [row.ref, row.label || row.business_code]));
  function finishDeviation(item) {
    const value = item.deviation;
    if (!value || !value.complete) return null;
    const minutes = value.finish_deviation_minutes;
    if (minutes === null) return '缺少确认完工时间，请核对现场完工记录';
    return minutes === 0 ? '按计划完成' : (minutes < 0 ? '提前 ' : '延后 ') + window.WorkbenchFormat.number(Math.abs(minutes), { digits: 2, trim: true }) + ' 分钟';
  }
  function deadlines(item) {
    const value = item.deviation;
    return { finishLate: value.finish_late, unclosed: value.unclosed, forecastLate: value.forecast_late };
  }
  function fieldSearchText(item, labels) {
    const t = item.task, e = item.execution;
    const text = [t.batch_id, t.sequence, t.process_label, t.piece_id, labels.get(t.machine_ref), labels.get(t.operator_ref)];
    if (e) {
      e.reports.forEach(r => text.push(r.report_no, labels.get(r.actual_machine_ref), labels.get(r.actual_operator_ref)));
      e.legacy_facts.forEach(fact => text.push(labels.get(fact.actual_machine_ref), labels.get(fact.actual_operator_ref)));
    }
    return text.map(value => value == null ? '' : value).join(' ').toLowerCase();
  }
  function searchText(item, labels) {
    const text = fieldSearchText(item, labels), remaining = item.execution && item.execution.remaining_plan;
    return remaining ? text + ' ' + [labels.get(remaining.machine_ref), labels.get(remaining.operator_ref)].join(' ').toLowerCase() : text;
  }
  function filter(prepared, view) {
    const query = view.query.trim().toLowerCase();
    return prepared.facts.filter(fact => (!query || fact.search.includes(query)) &&
      (view.late === 'all' || fact.deadlines[view.late]) && (!view.onlySelected || fact.item.task.task_ref === view.selected));
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
  function tracks(segments) {
    const owners = new Map(), result = [];
    segments.sort((a, b) => a.start - b.start || a.key.localeCompare(b.key)).forEach(fact => {
      if (!Number.isFinite(fact.start) || !Number.isFinite(fact.end) || fact.start === fact.end) { result.push([fact]); return; }
      const key = JSON.stringify([fact.actual_machine_ref, fact.actual_operator_ref]);
      if (!owners.has(key)) owners.set(key, []);
      const heap = owners.get(key), index = heap.length && heap[0].end <= fact.start ? pop(heap).index : result.length;
      if (!result[index]) result[index] = [];
      result[index].push(fact); push(heap, { end: fact.end, index });
    });
    return result;
  }
  function prepareLegacy(e) {
    if (!e || !e.legacy_facts.length || e.data_gaps.some(gap => gap.code === 'invalid_legacy_sequence')) return [];
    const covered = new Set(e.reports.map(report => report.legacy_fact_ref).filter(Boolean)), scopes = new Map(), result = [];
    for (const fact of e.legacy_facts) {
      if (!fact.recorded_against_task_ref) continue;
      if (!scopes.has(fact.recorded_against_task_ref)) scopes.set(fact.recorded_against_task_ref, []);
      scopes.get(fact.recorded_against_task_ref).push(fact);
    }
    for (const [scopeRef, scope] of scopes) {
      const startFact = scope.find(fact => fact.event_type === 'start'), finish = scope.find(fact => fact.event_type === 'finish');
      if (!startFact || !finish || covered.has(finish.legacy_fact_ref) || typeof startFact.event_time !== 'string' || typeof finish.event_time !== 'string') continue;
      const start = instant(window.FieldDraftModel.legacyTime(startFact.event_time)), end = instant(window.FieldDraftModel.legacyTime(finish.event_time));
      if (!Number.isFinite(start) || !Number.isFinite(end) || start > end) continue;
      const resources = window.FieldDraftModel.legacyResources(scope, e.data_gaps);
      const point = start === end, key = 'legacy:' + scopeRef;
      result.push({ key, legacy: finish, start, end, ...resources,
        mark: { key, kind: point ? 'legacy-point' : 'legacy', legacy: finish, start, end, ...resources, y: point ? 20 : 14, height: point ? 24 : 38 } });
    }
    return result;
  }
  function prepare(data, asOf) {
    const labels = names(data), taskIndex = new Map(), facts = [], planRange = { start: Infinity, end: -Infinity }, reportRange = { start: Infinity, end: -Infinity };
    const include = (range, value) => { if (Number.isFinite(value)) { range.start = Math.min(range.start, value); range.end = Math.max(range.end, value); } };
    for (const item of data.items) {
      const task = item.task, e = item.execution, point = window.PointContract.isPoint(task);
      const baseline = { key: 'plan', kind: point ? 'plan-point' : 'plan', start: instant(task.start), end: instant(task.end), y: point ? 64 : 74, height: point ? 24 : 7 };
      const reports = e ? e.reports.map(report => {
        const start = instant(report.actual_start), end = instant(report.actual_end || report.actual_start), point = !report.actual_end || start === end;
        return { key: report.report_ref, report, start, end, actual_machine_ref: report.actual_machine_ref, actual_operator_ref: report.actual_operator_ref,
          mark: report.actual_start ? { key: report.report_ref, kind: point ? 'point' : 'actual', report, start, end, y: point ? 20 : 14, height: point ? 24 : 38 } : null };
      }) : [];
      const legacyMarks = prepareLegacy(e);
      const remaining = e && e.remaining_plan ? { key: 'remaining', kind: 'remaining', start: instant(e.remaining_plan.start), end: instant(e.remaining_plan.end), y: 14, height: 34 } : null;
      include(planRange, baseline.start); include(planRange, baseline.end);
      for (const report of reports) { include(reportRange, report.start); include(reportRange, report.end); }
      for (const segment of legacyMarks) { include(reportRange, segment.start); include(reportRange, segment.end); }
      const fact = { item, baseline, reports, legacyMarks, reportIndex: new Map(reports.map(report => [report.report.report_ref, report])), remaining, search: searchText(item, labels), deadlines: deadlines(item) };
      facts.push(fact); taskIndex.set(task.task_ref, fact);
    }
    const hasPoints = facts.some(fact => fact.baseline.kind === 'plan-point' || fact.reports.some(report => report.mark && report.mark.kind === 'point')
      || fact.legacyMarks.some(segment => segment.mark.kind === 'legacy-point'));
    const axis = window.PointGanttModel.bounds(instant(data.axis_span.start), instant(data.axis_span.end), hasPoints);
    const dataRange = Number.isFinite(planRange.start) ? planRange : Number.isFinite(reportRange.start) ? reportRange : null;
    return { labels, facts, taskIndex, dataRange, start: axis.start, end: axis.end, asOf: instant(asOf),
      executionAvailable: !!data.availability && data.availability.state === 'available' };
  }
  function groupPrepared(prepared, mode) {
    const groups = new Map(), { labels } = prepared;
    function group(fact, owner) {
      const ref = mode === 'batch' ? fact.item.task.batch_id : owner[mode + '_ref'] || 'unbound';
      if (!groups.has(ref)) groups.set(ref, { id: ref, label: mode === 'batch' ? ref : labels.get(ref) || views[mode] + '未填写', members: new Map() });
      const members = groups.get(ref).members, key = fact.item.task.task_ref;
      if (!members.has(key)) members.set(key, { fact, item: fact.item, baseline: false, reports: [], legacy: [], legacyMarks: [], remaining: false });
      return members.get(key);
    }
    for (const fact of prepared.facts) {
      const item = fact.item, e = item.execution;
      group(fact, item.task).baseline = true;
      if (!e) continue;
      fact.reports.forEach(report => group(fact, { machine_ref: report.report.actual_machine_ref, operator_ref: report.report.actual_operator_ref }).reports.push(report));
      e.legacy_facts.forEach(legacy => { if (legacy.actual_machine_ref || legacy.actual_operator_ref) group(fact, { machine_ref: legacy.actual_machine_ref, operator_ref: legacy.actual_operator_ref }).legacy.push(legacy); });
      fact.legacyMarks.forEach(segment => group(fact, { machine_ref: segment.actual_machine_ref, operator_ref: segment.actual_operator_ref }).legacyMarks.push(segment));
      if (e.execution_state !== 'complete' && e.remaining_quantity !== 0) group(fact, e.remaining_plan || item.task).remaining = true;
    }
    for (const g of groups.values()) for (const member of g.members.values()) {
      const ts = tracks(member.reports.concat(member.legacyMarks)); if (!ts.length) ts.push([]);
      member.reportCount = member.reports.length; member.legacyCount = member.legacy.length;
      member.knownCount = 0; member.knownHours = 0; member.unknownHours = 0;
      for (const { report } of member.reports) {
        if (report.effective_processing_hours == null) member.unknownHours++;
        else { member.knownCount++; member.knownHours += report.effective_processing_hours; }
      }
      member.rows = ts.map((segments, i) => ({ key: g.id + ':' + member.item.task.task_ref + ':' + i, item: member.item,
        reports: segments.filter(fact => fact.report).map(fact => fact.report), baseline: i === 0 && member.baseline, kind: 'actual', height: 88,
        track: i + 1, trackCount: ts.length, planEnd: member.fact.baseline.end,
        marks: (i === 0 && member.baseline ? [member.fact.baseline] : []).concat(segments.map(fact => fact.mark).filter(Boolean)) }));
      if (member.remaining) member.rows.push({ key: g.id + ':' + member.item.task.task_ref + ':remaining', item: member.item,
        reports: [], baseline: false, kind: 'remaining', height: 64, marks: member.fact.remaining ? [member.fact.remaining] : [] });
    }
    return { ...prepared, mode, groups: Array.from(groups.values()) };
  }
  function selectPrepared(prepared, view) {
    const selected = filter(prepared, view), shown = new Set(selected.map(fact => fact.item.task.task_ref)), groups = [];
    for (const source of prepared.groups) {
      const members = new Map(Array.from(source.members).filter(([ref]) => shown.has(ref)));
      if (!members.size) continue;
      const g = { ...source, members, reportCount: 0, legacyCount: 0, knownHours: null, unknownHours: 0 };
      let knownCount = 0, knownHours = 0;
      for (const member of members.values()) {
        g.reportCount += member.reportCount; g.legacyCount += member.legacyCount; g.unknownHours += member.unknownHours;
        knownCount += member.knownCount; knownHours += member.knownHours;
      }
      g.knownHours = knownCount ? knownHours : null; groups.push(g);
    }
    return { ...prepared, items: selected.map(fact => fact.item), groups };
  }
  function layoutPrepared(prepared, collapsed) {
    const rows = [], locations = new Map(), reportLocations = new Map(); let top = 0;
    function append(row) { const placed = { ...row, top }; rows.push(placed); top += row.height; return placed; }
    for (const group of prepared.groups) {
      append({ key: 'group:' + group.id, group, kind: 'group', height: 56 });
      if (collapsed[group.id]) continue;
      for (const member of group.members.values()) for (const template of member.rows) {
        const row = append({ ...template, group });
        if (row.kind !== 'actual') continue;
        const ref = row.item.task.task_ref;
        if (!locations.has(ref) || row.baseline) locations.set(ref, row);
        row.reports.forEach(report => reportLocations.set(report.report_ref, row));
      }
    }
    return { labels: prepared.labels, taskIndex: prepared.taskIndex, dataRange: prepared.dataRange, items: prepared.items, groups: prepared.groups, rows, height: top, locations, reportLocations,
      executionAvailable: prepared.executionAvailable, start: prepared.start, end: prepared.end, asOf: prepared.asOf };
  }
  function visibleRows(rows, top, bottom) {
    let low = 0, high = rows.length;
    while (low < high) { const mid = (low + high) >> 1; if (rows[mid].top + rows[mid].height <= top) low = mid + 1; else high = mid; }
    const result = []; for (let at = low; at < rows.length && rows[at].top < bottom; at++) result.push(rows[at]); return result;
  }
  function graphLocations(model) {
    const result = new Map();
    for (const row of model.rows) {
      if (row.kind !== 'actual') continue;
      const candidates = row.marks; let mark = null;
      for (const candidate of candidates) if (candidate.report && (!mark || candidate.end > mark.end)) mark = candidate;
      mark = mark || candidates[0];
      if (!mark) continue;
      const ref = row.item.task.task_ref, previous = result.get(ref), reported = !!mark.report;
      if (previous && (previous.reported && !reported || previous.reported === reported && previous.end >= mark.end)) continue;
      // 连接已绘制的最近报工；没有报工时连接原计划细基线，不借用图节点的计划坐标冒充实际。
      result.set(ref, { start: mark.start, end: mark.end, y: row.top + mark.y + mark.height / 2,
        markTop: row.top + mark.y, markBottom: row.top + mark.y + mark.height,
        top: row.top, bottom: row.top + row.height, reported });
    }
    return result;
  }
  function tickStep(model, width) {
    return window.PlanGanttModel.tickStep(model.start, model.end, width);
  }
  function tickLabel(step) {
    const unit = [[24 * HOUR, '天'], [HOUR, '小时'], [60000, '分钟'], [1000, '秒']].find(([size]) => step % size === 0);
    return step / unit[0] + ' ' + unit[1];
  }
  function ticks(model, width, left, viewport) {
    return window.PlanGanttModel.ticks(model.start, model.end, width, left, viewport);
  }
  function describe(item, labels, report) {
    const t = item.task, e = item.execution;
    const result = [taskLabel(t), '计划应做：' + window.FieldContract.quantity(t.quantity, { digits: 2 }) + ' 件 · 批次：' + window.FieldContract.quantity(t.batch_quantity, { digits: 2 }) + ' 件',
      '原计划：' + time(t.start) + ' 至 ' + time(t.end),
      '计划资源：' + (labels.get(t.machine_ref) || '设备未填写') + ' / ' + (labels.get(t.operator_ref) || '人员未填写')];
    if (window.PointContract.isPoint(t)) result.push('零工时工序，无资源占用。');
    if (t.quantity_reason) result.push(quantityReasons[t.quantity_reason]);
    if (!e) return result.concat('报工记录不可用');
    result.push(states[e.execution_state] + ' · 已知完成 ' + number(e.known_completed_quantity) + ' 件',
      '整道实际完工：' + (e.confirmed_finish ? time(e.confirmed_finish) : e.execution_state === 'complete' ? '已标记完工，确认完工时间缺失' : '尚未确认整道完工'),
      '剩余数量：' + (e.remaining_quantity === null ? '当前记录无法计算，见记录问题' : number(e.remaining_quantity)));
    if (e.completion_basis) result.push(e.completion_basis === 'legacy_finish_event' ? '完成依据：历史完工记录' : '完成依据：逐次报工记录');
    const deviation = finishDeviation(item);
    result.push('整道完工偏差：' + (deviation || '未完工，不计算完成偏差'));
    e.data_gaps.forEach(gap => result.push('记录问题：' + gap.message));
    if (report) result.push('本次报工：' + report.report_no, '实际：' + (report.actual_start ? time(report.actual_start) : '本次开工未填写') + ' 至 ' + (report.actual_end ? time(report.actual_end) : '本次结束未填写'),
      '本次数量：' + (report.completed_quantity === null ? '本条报工未填写完成数量' : number(report.completed_quantity) + ' 件') + ' · 有效工时：' + (report.effective_processing_hours === null ? '本条报工未填写有效工时' : hours(report.effective_processing_hours)),
      '实际资源：' + (labels.get(report.actual_machine_ref) || '设备未填写') + ' / ' + (labels.get(report.actual_operator_ref) || '人员未填写'), '备注：' + (report.remark || '未填写'));
    return result;
  }
  function markTitle(mark, item, labels) {
    if (mark.legacy) return [mark.kind === 'legacy-point' ? '历史实际时刻' : '历史实际时段', '历史事件记录 · 有效工时未记录',
      '实际：' + time(wire(mark.start)) + ' 至 ' + time(wire(mark.end)),
      '旧已知累计：' + number(mark.legacy.quantity_done) + ' 件 · 有效工时：未知',
      '实际资源：' + (labels.get(mark.actual_machine_ref) || '设备未填写') + ' / ' + (labels.get(mark.actual_operator_ref) || '人员未填写')]
      .concat(describe(item, labels)).join('\n');
    const heading = mark.kind === 'plan-point' ? '原计划 · 零工时工序' : mark.kind === 'plan' ? '原计划' : mark.kind === 'remaining' ? '已有剩余安排' : mark.kind === 'point' ? (mark.report.actual_end ? '报工时刻' : '报工开工时刻 · 结束未填写') : '实际报工时段';
    return [heading].concat(describe(item, labels, mark.report)).join('\n');
  }
  function metrics(data) {
    const value = data.execution_summary;
    return { complete: value.complete, reported: value.reported, pending: value.pending, average: value.average_finish_deviation_minutes };
  }
  window.ActualGanttModel = { instant, wire, time, fileStamp, number, hours, pieceLabel, taskLabel, states, views, lateLabels, names, finishDeviation, deadlines, fieldSearchText, searchText, filter, tracks, prepare, groupPrepared, selectPrepared, layoutPrepared, visibleRows, graphLocations, tickStep, tickLabel, ticks, describe, markTitle, metrics };
})();
