/* In-memory UI test records only. Never load this file in the production app. */
(function () {
  'use strict';
  const ref = n => n.toString(16).padStart(48, '0');
  const clone = value => JSON.parse(JSON.stringify(value));
  const wire = time => new Date(time).toISOString().slice(0, 19);
  const instant = value => Date.parse(value + 'Z');
  const measures = ['available_hours', 'effective_hours', 'normal_available_hours', 'normal_effective_hours', 'urgent_available_hours', 'urgent_effective_hours'];
  function plan(n = 1, kind = n === 3 ? 'scenario' : n === 2 ? 'candidate' : 'official') {
    return { plan_ref: ref(n), version: n === 3 ? 1 : n, kind, is_current_official: n === 1 && kind === 'official',
      display_name: kind === 'scenario' ? '夜班调整场景 ' + n : kind === 'candidate' ? '候选排产方案 ' + n : '正式排产计划 ' + n,
      completeness: 'complete', capabilities: { view: true, export: true, edit_draft: false, adopt: false, report_actual: false }, blocked_reasons: [] };
  }
  function envelope(data, snapshot = 'workspace-ui-snapshot') {
    return { ok: true, schema_version: 1, data, meta: { request_ref: 'memory-only-request', source: 'production', time_basis: 'factory_local', snapshot_ref: snapshot, as_of: '2026-09-09T22:00:00' }, warnings: [] };
  }
  function catalog(scope, options = {}) {
    const page = scope.cursor ? 1 : 0;
    const plans = options.empty ? [] : scope.collection === 'scenario' ? Array.from({ length: page ? 3 : 20 }, (_, i) => plan(3 + (page * 20 + i) * 3, 'scenario')) :
      Array.from({ length: page ? 2 : 20 }, (_, i) => plan(page ? 40 + i : i + 1, i === 2 ? 'official' : i === 1 ? 'candidate' : 'official'));
    if (plans.length && !page && scope.collection === 'history') {
      const unavailable = plan(90); unavailable.plan_ref = null; unavailable.version = plans[19].version;
      unavailable.capabilities.view = unavailable.capabilities.export = false; unavailable.completeness = 'invalid';
      unavailable.display_name = '损坏记录仍保留'; unavailable.blocked_reasons = [{ code: 'plan_unavailable', message: '保存的明细不完整，无法查看。' }];
      plans.push(unavailable);
    }
    return envelope({ plans, page: { collection: scope.collection, size: scope.size, unit: scope.collection === 'scenario' ? 'scenario' : 'version', has_more: !!plans.length && !page,
      next_cursor: plans.length && !page ? 'next:' + scope.collection : null } }, options.stale && page ? 'catalog-changed' : 'catalog-ui-snapshot');
  }
  function tasks(planRef, options) {
    const start = instant('2026-09-09T22:30:00'), count = options.count || 36;
    return Array.from({ length: count }, (_, i) => {
      const offset = options.dense ? i * 60000 : options.concurrent ? 0 : Math.floor(i / 6) * 9 * 3600000 + i % 6 * 1800000;
      const duration = options.dense ? 50000 : options.concurrent ? 3600000 : i === 1 ? 30 * 60000 : (i % 5 + 1) * 3600000;
      return { task_ref: ref(10000 + i + Number.parseInt(planRef.slice(-4), 16) * 20000), operation_ref: ref(2000000 + i), plan_ref: planRef,
        batch_id: options.dense || options.concurrent ? 'BATCH-' + String(i).padStart(5, '0') : 'D2609-' + String(Math.floor(i / 3) + 1).padStart(3, '0'),
        sequence: i + 1, process_label: ['粗车端面', '钻孔', '精车外圆', '磨削', '检验', '装配'][i % 6],
        piece_id: null, quantity: null, batch_quantity: null, quantity_basis: 'unknown', quantity_reason: 'plan_target_not_recorded',
        machine_ref: ref(500 + (options.dense || options.concurrent ? 0 : i % 4)), operator_ref: ref(600 + (options.dense || options.concurrent ? 0 : i % 5)), supplier_ref: null,
        start: wire(start + offset), end: wire(start + offset + duration) };
    });
  }
  function calendarRow(time, resource) {
    const hours = (instant(time.range_end) - instant(time.range_start)) / 3600000;
    const row = { state: 'available', basis: resource ? resource.kind === 'machine' ? 'global_calendar_machine_availability' : 'personal_or_operator_shift_calendar' : 'global_calendar',
      windows: [{ start: time.range_start, end: time.range_end, policy_date: time.range_start.slice(0, 10), allow_normal: true, allow_urgent: true, efficiency: 1, provenance: 'work_calendar' }],
      issues: [], ...Object.fromEntries(measures.map(key => [key, hours])) };
    return resource ? { ...row, kind: resource.kind, resource_ref: resource.ref, label: resource.label, status: 'active', downtime_windows: [], downtime_scope_hours: 0, downtime_available_hours: 0 } : row;
  }
  function occupancyRow(resource, tasks, time) {
    const relevant = tasks.filter(task => task[resource.kind + '_ref'] === resource.ref), events = new Map();
    for (const task of relevant) {
      const start = Math.max(instant(task.start), instant(time.range_start)), end = Math.min(instant(task.end), instant(time.range_end));
      events.set(start, (events.get(start) || 0) + 1); events.set(end, (events.get(end) || 0) - 1);
    }
    let previous, concurrent = 0, occupied = 0, arranged = 0, overlap = 0;
    const segments = [];
    for (const [at, delta] of Array.from(events).sort((a, b) => a[0] - b[0])) {
      if (concurrent > 0 && at > previous) {
        const duration = (at - previous) / 3600000; occupied += duration; arranged += concurrent * duration;
        if (concurrent > 1) overlap += duration;
        segments.push({ start: wire(previous), end: wire(at), concurrent_operations: concurrent });
      }
      concurrent += delta; previous = at;
    }
    const capacity = (instant(time.range_end) - instant(time.range_start)) / 3600000;
    return { kind: resource.kind, resource_ref: resource.ref, label: resource.label, state: 'available', operation_count: relevant.length,
      arranged_hours: arranged, occupied_hours: occupied, overlap_hours: overlap, excess_arranged_hours: arranged - occupied,
      available_hours: capacity, available_occupied_hours: occupied, outside_available_hours: 0, capacity_shortfall_hours: Math.max(0, arranged - capacity),
      capacity_basis: resource.kind === 'machine' ? 'global_calendar_machine_availability' : 'personal_or_operator_shift_calendar',
      utilization: occupied / capacity, has_overlap: overlap > 0, capacity_insufficient: arranged > capacity, issues: [], segments };
  }
  function delivery(scope, all, selected, options) {
    const grouped = new Map(); for (const task of all) { if (!grouped.has(task.batch_id)) grouped.set(task.batch_id, []); grouped.get(task.batch_id).push(task); }
    const ids = Array.from(new Set(selected.map(task => task.batch_id)));
    const items = ids.map((batch, i) => {
      const tasks = grouped.get(batch), finish = tasks.reduce((a, b) => a > b.end ? a : b.end, tasks[0].end), unknown = options.unknown || i % 3 === 2;
      const day = instant(finish.slice(0, 10) + 'T00:00:00'), late = i % 3 === 0, deadline = wire(day + (late ? 0 : 86400000));
      const delay = Math.max(0, (instant(finish) - instant(deadline)) / 3600000);
      return { batch_ref: ref(3000000 + i), batch_id: batch, part_no: '20066-' + i, part_label: '传动轴组件',
        planned_finish: unknown ? null : finish, partial_planned_finish: unknown ? finish : null, due_date: wire(day - (late ? 86400000 : 0)).slice(0, 10),
        delivery_deadline_exclusive: deadline, risk: unknown ? 'unknown' : late ? 'overdue' : 'on_time', is_overdue: unknown ? null : late,
        delay_hours: unknown ? null : delay, delay_days: unknown ? null : delay / 24, completeness: unknown ? 'incomplete' : 'complete', schedule_complete: !unknown,
        operation_count: tasks.length + (unknown ? 1 : 0), scheduled_operation_count: tasks.length, unscheduled_operation_count: unknown ? 1 : 0, task_count: tasks.length,
        invalid_task_count: 0, issues: unknown ? ['operations_unscheduled'] : [] };
    });
    const known = items.filter(row => row.risk !== 'unknown').length;
    return { state: known === items.length ? 'available' : known ? 'partial' : 'unavailable', plan_ref: scope.plan_ref, scope: clone(scope), items, batch_count: items.length, items_complete: true,
      completeness: !items.length ? 'unknown' : items.some(row => row.completeness === 'incomplete') ? 'incomplete' : 'complete',
      basis: { kind: 'planned_delivery', time_basis: 'factory_local', batch_selection: scope.range_start === null ? 'plan_task_batches' : 'overlap_or_bad_time_batches',
        completion_scope: 'full_selected_plan', operation_scope: 'current_batch_operations', due_boundary: 'next_day_exclusive', actual_completion: 'not_evaluated', actual_delivery: 'not_evaluated' } };
  }
  function workspace(planRef = ref(1), query = {}, options = {}) {
    const n = Number.parseInt(planRef, 16), header = plan(n, n % 3 === 0 ? 'scenario' : n === 2 ? 'candidate' : 'official');
    const all = tasks(planRef, options), starts = all.map(row => row.start).sort(), ends = all.map(row => row.end).sort();
    const span = { start: starts[0], end: ends[ends.length - 1] };
    const scope = { source: 'production', kind: 'plan_workspace', plan_ref: planRef, range_start: query.range_start || null, range_end: query.range_end || null };
    const time = { range_start: scope.range_start || span.start, range_end: scope.range_end || span.end, selection: 'overlap', boundary: 'half_open', time_basis: 'factory_local' };
    const inScope = task => task.start < time.range_end && task.end > time.range_start;
    const selected = all.filter(inScope), resourceMap = new Map();
    for (const task of selected) for (const kind of ['machine', 'operator']) if (!resourceMap.has(task[kind + '_ref'])) {
      const resourceRef = task[kind + '_ref'], index = Number.parseInt(resourceRef, 16) - (kind === 'machine' ? 500 : 600);
      resourceMap.set(resourceRef, { kind, ref: resourceRef, business_code: (kind === 'machine' ? 'M-' : 'OP-') + index,
        label: options.nullLabels ? null : kind === 'machine' ? ['数控车床 C01', '立式加工中心 V02', '外圆磨床 G03', '卧式车床 C04'][index] : ['张工', '李工', '王工', '陈工', '赵工'][index] });
    }
    const resources = Array.from(resourceMap.values());
    let baseline = { state: 'unavailable', reason_code: 'not_recorded', reason: '未记录独立的初始基线，不能用当前安排替代。', baseline_plan: null, items: [], item_count: 0, items_complete: false };
    if (header.kind === 'scenario') {
      const items = all.map((after, index) => {
        const before = { ...after, plan_ref: ref(1), task_ref: ref(4000000 + index), start: wire(instant(after.start) - 7200000), end: wire(instant(after.end) - 7200000) };
        return { operation_ref: after.operation_ref, change: 'changed', changed_fields: ['start', 'end'], before, after,
          before_in_scope: scope.range_start === null || inScope(before), after_in_scope: scope.range_start === null || inScope(after) };
      }).filter(item => item.before_in_scope || item.after_in_scope);
      baseline = { state: 'available', reason_code: null, reason: null, basis: 'scenario_base', baseline_plan: plan(1),
        comparison_scope: { scope: clone(scope), selection: 'either_side_overlap', boundary: 'half_open', alignment: 'operation_ref', time_basis: 'factory_local', task_times: 'unclipped' },
        compared_fields: ['start', 'end', 'machine_ref', 'operator_ref'], items, item_count: items.length, items_complete: true };
    }
    const calendar = { state: 'available', plan_ref: planRef, time_scope: clone(time), global: calendarRow(time), resources: resources.map(row => calendarRow(time, row)), issues: [] };
    const occupancy = { state: 'available', plan_ref: planRef, time_scope: clone(time), basis: 'selected_plan_only', resources: resources.map(row => occupancyRow(row, selected, time)), issues: [] };
    if (options.unknown) {
      const unknown = row => { row.state = 'unavailable'; row.windows = null; row.issues = [{ code: 'calendar_invalid', message: '日历资料无法核实。' }]; for (const key of measures) row[key] = null;
        delete row.downtime_windows; delete row.downtime_scope_hours; delete row.downtime_available_hours; };
      calendar.state = 'unavailable'; unknown(calendar.global); calendar.resources.forEach(unknown);
      occupancy.state = selected.length ? 'unavailable' : 'available';
      occupancy.resources.forEach(row => { row.state = 'unavailable'; row.issues = [{ code: 'calendar_invalid', message: '日历资料无法核实。' }];
        for (const key of ['available_hours', 'available_occupied_hours', 'outside_available_hours', 'capacity_shortfall_hours', 'utilization', 'capacity_insufficient']) row[key] = null; });
    }
    const selectedStarts = selected.map(row => row.start).sort(), selectedEnds = selected.map(row => row.end).sort();
    return envelope({ plan: header, scope, time_scope: time, plan_span: span, task_span: selected.length ? { start: selectedStarts[0], end: selectedEnds[selectedEnds.length - 1] } : null,
      tasks: selected, task_count: selected.length, tasks_complete: true, resources, projections: { baseline, calendar, occupancy, delivery_risks: delivery(scope, all, selected, options),
        process_order: { state: 'unavailable', basis: null, items: [], issues: [{ code: 'process_order_not_recorded', message: 'Fixture has no captured process order.' }] } } },
    options.snapshot || query.snapshot_ref || 'workspace-ui:' + planRef + ':' + (scope.range_start || 'full'));
  }
  const api = { ref, clone, instant, wire, plan, envelope, catalog, workspace };
  if (typeof module !== 'undefined') module.exports = api; else window.PlanUIFixtures = api;
})();
