(function () {
  'use strict';

  const C = window.DashboardContract,
    {
      time
    } = window.RunCandidateAPI;
  const number = v => typeof v === 'number' && Number.isFinite(v),
    count = v => Number.isSafeInteger(v) && v >= 0;
  const nullable = test => value => value === null || test(value);
  const shape = (value, required, optional = []) => C.object(value) && required.every(key => Object.prototype.hasOwnProperty.call(value, key)) && Object.keys(value).every(key => required.concat(optional).includes(key));
  const issue = value => C.object(value) && C.text(value.code) && C.text(value.message);
  function envelope(value) {
    C.check(shape(value, ['ok', 'schema_version', 'data', 'meta', 'warnings']) && value.ok === true && value.schema_version === 1 && C.object(value.data) && shape(value.meta, ['request_ref', 'source', 'time_basis', 'snapshot_ref', 'as_of']) && /^[a-f0-9]{32}$/.test(value.meta.request_ref) && value.meta.source === 'production' && value.meta.time_basis === 'factory_local' && typeof value.meta.snapshot_ref === 'string' && /^[A-Za-z0-9_-]{32}$/.test(value.meta.snapshot_ref) && time(value.meta.as_of) && Array.isArray(value.warnings) && value.warnings.every(issue));
    return value.data;
  }
  async function request(url, fetcher, signal) {
    const controller = new AbortController(),
      abort = () => controller.abort();
    if (signal) {
      signal.addEventListener('abort', abort, {
        once: true
      });
      if (signal.aborted) abort();
    }
    const timer = setTimeout(abort, 60000);
    try {
      const response = await fetcher(url, {
        method: 'GET',
        credentials: 'same-origin',
        cache: 'no-store',
        redirect: 'error',
        signal: controller.signal
      });
      C.check((response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase() === 'application/json', '分析接口未返回有效 JSON。');
      const payload = await response.json();
      if (!response.ok || payload.ok !== true) throw new Error(payload && payload.error && C.text(payload.error.message) ? payload.error.message : '真实分析读取失败。');
      C.check(response.status === 200);
      envelope(payload);
      return payload;
    } finally {
      clearTimeout(timer);
      if (signal) signal.removeEventListener('abort', abort);
    }
  }
  function pressure(value) {
    C.check(C.object(value) && ['available', 'unavailable'].includes(value.state) && Array.isArray(value.days) && nullable(number)(value.peak_utilization) && count(value.zero_capacity_days) && count(value.unknown_days));
    value.days.forEach(day => {
      C.check(C.object(day) && time(day.start) && time(day.end) && day.start <= day.end && day.date === day.start.slice(0, 10) && ['available_hours', 'inside_available_hours', 'outside_available_hours', 'utilization'].every(k => nullable(number)(day[k])) && number(day.occupied_hours) && day.occupied_hours >= 0 && number(day.overlap_hours) && day.overlap_hours >= 0 && (day.utilization === null ? day.available_hours === null || day.available_hours === 0 : day.available_hours > 0 && day.utilization >= 0 && day.utilization <= 1));
    });
    const known = value.days.map(day => day.utilization).filter(v => v !== null);
    C.check(value.peak_utilization === (value.state === 'unavailable' || !known.length ? null : Math.max(...known)) && (value.state !== 'available' || value.unknown_days === 0 && value.zero_capacity_days === value.days.filter(day => day.available_hours === 0).length));
  }
  function validate(payload, planRef) {
    const d = envelope(payload);
    C.check(shape(d, ['plan', 'state', 'time_scope', 'tasks', 'resources', 'downtimes', 'overlaps', 'deliveries', 'execution', 'pending', 'pressure', 'issues', 'as_of', 'capabilities', 'basis']) && d.basis === 'current_official_plan_and_readiness_sources' && C.equal(d.capabilities, {
      view: true,
      adopt: false
    }) && time(d.as_of) && ['tasks', 'resources', 'downtimes', 'overlaps', 'deliveries', 'execution', 'issues'].every(k => Array.isArray(d[k])) && d.issues.every(issue));
    if (d.plan === null) C.check(!planRef && d.state !== 'available' && d.time_scope === null && !d.tasks.length && !d.resources.length && d.pressure.count === null);else C.check(C.object(d.plan) && C.ref(d.plan.plan_ref) && d.plan.kind === 'official' && d.plan.is_current_official === true && (!planRef || d.plan.plan_ref === planRef) && d.state === 'available' && C.object(d.time_scope) && time(d.time_scope.range_start) && time(d.time_scope.range_end) && d.time_scope.range_start <= d.time_scope.range_end);
    d.tasks.forEach(task => C.check(C.object(task) && C.ref(task.task_ref) && C.ref(task.operation_ref) && C.ref(task.batch_ref) && task.plan_ref === d.plan.plan_ref && C.text(task.batch_id) && C.text(task.process_label) && ['internal', 'external'].includes(task.source) && nullable(C.ref)(task.machine_ref) && time(task.start) && time(task.end) && task.start <= task.end && number(task.span_hours) && Math.abs(task.span_hours - (Date.parse(task.end + 'Z') - Date.parse(task.start + 'Z')) / 3600000) < 0.000001 && (task.start !== task.end || task.event_kind === 'point' && task.duration_seconds === 0 && task.occupies_resources === false)));
    C.check(new Set(d.tasks.map(task => task.task_ref)).size === d.tasks.length);
    const tasks = new Map(d.tasks.map(task => [task.task_ref, task]));
    d.resources.forEach(resource => {
      pressure(resource);
      C.check(C.ref(resource.resource_ref) && resource.kind === 'machine' && Array.isArray(resource.task_refs) && resource.task_refs.every(ref => tasks.has(ref) && tasks.get(ref).machine_ref === resource.resource_ref));
    });
    C.check(new Set(d.resources.map(row => row.resource_ref)).size === d.resources.length);
    d.downtimes.forEach(row => C.check(C.ref(row.downtime_ref) && C.ref(row.machine_ref) && typeof row.valid === 'boolean' && nullable(time)(row.start) && nullable(time)(row.end) && (!row.valid || row.start !== null && row.end !== null && row.start < row.end) && nullable(time)(row.recorded_at) && row.recorded_at_basis === 'stored_database_timestamp'));
    d.overlaps.forEach(row => C.check(tasks.has(row.task_ref) && row.batch_ref === tasks.get(row.task_ref).batch_ref && C.object(row.source) && row.source.task_ref === row.task_ref && number(row.source.known_overlap_hours)));
    d.execution.forEach(row => C.check(C.object(row.source) && tasks.has(row.source.task_ref) && row.batch_ref === tasks.get(row.source.task_ref).batch_ref));
    const pending = d.pending;
    C.check(C.object(pending) && Array.isArray(pending.items) && nullable(count)(pending.count) && count(pending.known_count) && pending.known_count === pending.items.length && (pending.count === null || pending.count === pending.items.length) && pending.basis === 'stored_pending_batch_pool');
    pending.items.forEach(row => C.check(C.ref(row.batch_ref) && C.text(row.batch_id) && row.stored_status === 'pending' && nullable(number)(row.quantity) && Array.isArray(row.readiness_issues)));
    const p = d.pressure,
      known = d.resources.filter(row => row.peak_utilization !== null && row.peak_utilization >= 0.9).length;
    C.check(C.object(p) && p.threshold === 0.9 && p.known_count === known && nullable(count)(p.count) && p.resource_count === d.resources.length && (p.count === null || p.count === known) && p.basis === 'same_range_daily_peak_available_occupancy');
    return d;
  }
  function create(fetcher = window.fetch.bind(window)) {
    return {
      async read(planRef, signal) {
        C.check(planRef === null || planRef === undefined || C.ref(planRef));
        const value = await request('/api/workbench/v1/dashboard/analysis' + (planRef ? '?plan_ref=' + planRef : ''), fetcher, signal);
        validate(value, planRef);
        return value;
      }
    };
  }
  window.DashboardAnalysisAPI = {
    create,
    validate,
    envelope,
    request,
    pressure,
    shape,
    number,
    count,
    nullable,
    issue
  };
})();
