(function () {
  'use strict';
  const C = window.DashboardContract, { time } = window.RunCandidateAPI;
  const number = v => typeof v === 'number' && Number.isFinite(v), count = v => Number.isSafeInteger(v) && v >= 0;
  const nullable = test => value => value === null || test(value);
  const shape = (value, required, optional = []) => C.object(value) && required.every(key => Object.prototype.hasOwnProperty.call(value, key))
    && Object.keys(value).every(key => required.includes(key) || optional.includes(key));
  const issue = value => C.object(value) && C.text(value.code) && C.text(value.message);
  function pressure(value) {
    const R = window.ResourceProjectionContract;
    C.check(C.object(value) && ['available', 'partial', 'unavailable'].includes(value.state) && Array.isArray(value.days)
      && nullable(number)(value.peak_utilization) && count(value.zero_capacity_days) && count(value.unknown_days)
      && R.window(value.window_metrics));
    // 每个逐日行就是共同口径的窗口行本身（后端不再套 window_metrics、不再给旧别名）。
    value.days.forEach(day => C.check(R.window(day) && time(day.start) && time(day.end) && day.start <= day.end
      && day.date === day.start.slice(0, 10)));
  }
  const sections = ['overview', 'delivery', 'actual', 'downtime', 'material', 'pressure', 'resource_days', 'timeline'];
  const totals = ['tasks', 'resources', 'downtimes', 'overlaps', 'deliveries', 'execution', 'pending', 'resource_days'];
  function scope(value) {
    const q = { section: 'delivery', page: 1, size: 20, ...value };
    C.check(C.object(value) && Object.keys(q).every(key => ['section', 'page', 'size', 'snapshot_ref', 'resource_ref', 'locate_batch_ref'].includes(key))
      && sections.includes(q.section) && count(q.page) && q.page >= 1 && q.page <= 100000 && count(q.size) && q.size >= 1 && q.size <= 100
      && (q.snapshot_ref === undefined || typeof q.snapshot_ref === 'string' && /^[A-Za-z0-9_-]{32}$/.test(q.snapshot_ref))
      && (q.section === 'resource_days' ? C.ref(q.resource_ref) : q.resource_ref === undefined)
      && (q.locate_batch_ref === undefined || q.section === 'timeline' && C.ref(q.locate_batch_ref)), '影响分析的页码或范围无效，请重新选择。');
    return q;
  }
  function pagination(value, q, payload) {
    C.check(shape(value, ['section', 'number', 'size', 'total', 'pages', 'totals']) && sections.includes(value.section)
      && count(value.number) && value.number > 0 && count(value.size) && value.size >= 1 && value.size <= 100
      && count(value.total) && value.pages === Math.max(1, Math.ceil(value.total / value.size))
      && shape(value.totals, totals) && totals.every(key => count(value.totals[key])), '影响分析的分页资料不完整，请刷新分析。');
    C.check(value.section === q.section && value.size === q.size && (q.locate_batch_ref ? value.number <= value.pages : value.number === q.page), '影响分析返回的页码或范围和当前选择不一致，请刷新分析。');
    C.check(!q.snapshot_ref || payload.meta.snapshot_ref === q.snapshot_ref, '分析资料已更新，请刷新分析后继续翻页。');
    const key = { delivery: 'deliveries', actual: 'execution', material: 'pending', pressure: 'resources', timeline: 'tasks', resource_days: 'resource_days' }[value.section];
    C.check(value.total === (key ? value.totals[key] : value.section === 'downtime' ? Math.max(value.totals.downtimes, value.totals.overlaps) : 0));
    return value;
  }
  function validate(payload, planRef, query) {
    return _validate(payload, planRef, scope(query));
  }
  function _validate(payload, planRef, q) {
    const d = payload.data;
    C.check(shape(d, ['plan', 'state', 'time_scope', 'tasks', 'resources', 'downtimes', 'overlaps', 'deliveries', 'execution', 'pending', 'pressure', 'issues', 'as_of', 'capabilities', 'basis', 'resource_common', 'pagination'])
      && d.basis === 'current_official_plan_and_readiness_sources' && C.equal(d.capabilities, { view: true, adopt: false })
      && time(d.as_of) && ['tasks', 'resources', 'downtimes', 'overlaps', 'deliveries', 'execution', 'issues'].every(k => Array.isArray(d[k])) && d.issues.every(issue));
    const page = pagination(d.pagination, q, payload), section = page.section;
    const pageLength = total => Math.min(page.size, Math.max(0, total - (page.number - 1) * page.size));
    if (d.plan === null) C.check(!planRef && d.state !== 'available' && d.time_scope === null && !d.tasks.length && !d.resources.length && d.pressure.count === null);
    else C.check(C.object(d.plan) && C.ref(d.plan.plan_ref) && d.plan.kind === 'official' && d.plan.is_current_official === true
      && (!planRef || d.plan.plan_ref === planRef) && d.state === 'available' && C.object(d.time_scope)
      && time(d.time_scope.range_start) && time(d.time_scope.range_end) && d.time_scope.range_start <= d.time_scope.range_end);
    d.tasks.forEach(task => C.check(C.object(task) && C.ref(task.task_ref) && C.ref(task.operation_ref) && C.ref(task.batch_ref)
      && task.plan_ref === d.plan.plan_ref && C.text(task.batch_id) && C.text(task.process_label) && ['internal', 'external'].includes(task.source)
      && nullable(C.ref)(task.machine_ref) && time(task.start) && time(task.end) && task.start <= task.end && number(task.span_hours)
      && Math.abs(task.span_hours - (Date.parse(task.end + 'Z') - Date.parse(task.start + 'Z')) / 3600000) < 0.000001
      && (task.start !== task.end || task.event_kind === 'point' && task.duration_seconds === 0 && task.occupies_resources === false)));
    C.check(new Set(d.tasks.map(task => task.task_ref)).size === d.tasks.length);
    if (q.locate_batch_ref) C.check(d.tasks.some(task => task.batch_ref === q.locate_batch_ref
      && task.source === 'internal' && task.machine_ref), '影响分析返回的工序和所选批次不一致，请刷新分析。');
    const tasks = new Map(d.tasks.map(task => [task.task_ref, task]));
    d.resources.forEach(resource => { pressure(resource); C.check(C.ref(resource.resource_ref) && ['machine', 'operator'].includes(resource.kind)
      && Array.isArray(resource.task_refs) && resource.task_refs.length === 0); });
    C.check(new Set(d.resources.map(row => row.resource_ref)).size === d.resources.length);
    d.downtimes.forEach(row => C.check(C.ref(row.downtime_ref) && C.ref(row.machine_ref) && typeof row.valid === 'boolean'
      && nullable(time)(row.start) && nullable(time)(row.end) && (!row.valid || row.start !== null && row.end !== null && row.start < row.end)
      && nullable(time)(row.recorded_at) && row.recorded_at_basis === 'local_time'));
    d.overlaps.forEach(row => C.check(tasks.has(row.task_ref) && row.batch_ref === tasks.get(row.task_ref).batch_ref
      && C.object(row.source) && row.source.task_ref === row.task_ref && number(row.source.known_overlap_hours)));
    d.execution.forEach(row => C.check(C.object(row.source) && tasks.has(row.source.task_ref) && row.batch_ref === tasks.get(row.source.task_ref).batch_ref));
    const pending = d.pending;
    C.check(C.object(pending) && Array.isArray(pending.items) && nullable(count)(pending.count) && count(pending.known_count)
      && pending.known_count === page.totals.pending && (pending.count === null || pending.count === pending.known_count)
      && pending.basis === 'stored_pending_batch_pool');
    pending.items.forEach(row => C.check(C.ref(row.batch_ref) && C.text(row.batch_id) && row.stored_status === 'pending'
      && nullable(number)(row.quantity) && Array.isArray(row.readiness_issues)));
    const p = d.pressure;
    C.check(C.object(p) && p.threshold === 0.9 && count(p.known_count) && nullable(count)(p.count)
      && p.resource_count === page.totals.resources && p.known_count <= p.resource_count && p.basis === 'same_range_daily_peak_available_occupancy');
    const arrays = { tasks: ['timeline', 'actual', 'downtime'], resources: ['pressure', 'resource_days'],
      downtimes: ['downtime'], overlaps: ['downtime'], deliveries: ['delivery', 'timeline', 'downtime'], execution: ['actual'] };
    Object.entries(arrays).forEach(([key, allowed]) => C.check(allowed.includes(section) || d[key].length === 0));
    C.check(section === 'material' ? pending.items.length === pageLength(page.totals.pending) : pending.items.length === 0);
    const primary = { delivery: 'deliveries', actual: 'execution', pressure: 'resources', timeline: 'tasks' }[section];
    if (primary) C.check(d[primary].length === pageLength(page.total));
    if (section === 'downtime') ['downtimes', 'overlaps'].forEach(key => C.check(d[key].length === pageLength(page.totals[key])));
    if (section === 'resource_days' && d.plan) C.check(d.resources.length === 1 && d.resources[0].days.length === pageLength(page.total)
      && d.resources[0].resource_ref === q.resource_ref);
    if (section === 'pressure') C.check(d.resources.every(resource => resource.days.length === 0));
    C.check(d.plan === null ? d.resource_common === null : window.ResourceProjectionContract.common(d.resource_common, 'current_transaction_snapshot'));
    return d;
  }
  async function read(planRef, signal, query) {
    C.check(planRef === null || planRef === undefined || C.ref(planRef));
    const q = scope(query), args = { ...q, ...(planRef ? { plan_ref: planRef } : {}) };
    const value = await C.read('/api/workbench/v1/dashboard/analysis', args, signal);
    _validate(value, planRef, q); return value;
  }
  window.DashboardAnalysisAPI = { read, validate, scope, pressure, shape, number, count, nullable };
})();
