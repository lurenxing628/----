(function () {
  'use strict';

  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const ref = v => typeof v === 'string' && /^[a-f0-9]{48}$/.test(v);
  const count = v => Number.isSafeInteger(v) && v >= 0;
  const measure = v => v === null || typeof v === 'number' && Number.isFinite(v);
  const fields = (v, keys) => object(v) && keys.every(k => Object.prototype.hasOwnProperty.call(v, k));
  function check(value, message = '读到的试调数据不完整或对不上，没有显示其他结果代替。请点「刷新」重试。') {
    if (!value) throw new Error(message);
  }
  function time(v) {
    return typeof v === 'string' && /^(?!0000)\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(v) && Number.isFinite(Date.parse(v + 'Z')) && new Date(v + 'Z').toISOString().slice(0, 19) === v;
  }
  function base(v) {
    check(object(v) && Object.keys(v).length === 1 && ['plan_ref', 'candidate_ref'].some(k => ref(v[k])));
    return v;
  }
  function scope(v = {}) {
    check(object(v) && Object.keys(v).every(k => ['range_start', 'range_end', 'batch_refs', 'resource_type', 'resource_ref', 'query'].includes(k)), '试调显示范围含未知条件。');
    if (v.range_start !== undefined || v.range_end !== undefined) check(time(v.range_start) && time(v.range_end) && v.range_start < v.range_end, '显示起止时间须成对填写，开始早于结束。');
    if (v.batch_refs !== undefined) check(Array.isArray(v.batch_refs) && v.batch_refs.every(ref));
    if (v.resource_type !== undefined) check(['machine', 'operator', 'batch'].includes(v.resource_type));
    if (v.resource_ref !== undefined) check(ref(v.resource_ref) && v.resource_type !== undefined);
    if (v.query !== undefined) check(typeof v.query === 'string' && v.query.length <= 200);
    return v;
  }
  // A navigation target is an identity, never an instruction to pick the latest record.
  function target(v = {}) {
    check(object(v) && Object.keys(v).every(k => ['kind', 'draft_ref', 'scenario_ref', 'base', 'scope', 'task_origin'].includes(k)), '试调入口含未知的项，没有猜测来源。');
    const keys = ['draft_ref', 'scenario_ref', 'base'].filter(k => v[k] !== undefined);
    check(keys.length <= 1, '只能指定一份试调草稿、试调方案或原来源。');
    if (v.kind !== undefined) check(v.kind === (v.draft_ref ? 'draft' : v.scenario_ref ? 'scenario' : 'base'));
    keys.forEach(k => k === 'base' ? base(v[k]) : check(ref(v[k])));
    if (v.scope !== undefined) {
      check(keys[0] === 'base', '已有草稿不能重新指定基础范围。');
      scope(v.scope);
    }
    if (Object.prototype.hasOwnProperty.call(v, 'task_origin')) {
      origin(v.task_origin);
      check(keys.length === 1 && keys[0] !== 'scenario_ref', '原任务定位只能指向原正式计划或指定草稿。');
      if (v.base) check(v.base.plan_ref === v.task_origin.plan_ref, '原任务与试调原计划不一致，未替换来源。');
    }
    return v;
  }
  function origin(value) {
    check(fields(value, ['plan_ref', 'operation_ref', 'task_ref']) && Object.keys(value).length === 3 && ['plan_ref', 'operation_ref', 'task_ref'].every(key => ref(value[key])), '原任务定位必须包含完整的原计划、工序和任务编号。');
    return value;
  }
  function originTask(data, value) {
    origin(value);
    check(!data.scenario_ref && data.base && data.base.plan_ref === value.plan_ref, '当前草稿与原任务来源不一致，未定位或开放写入。');
    const tasks = data.tasks.filter(task => task.source_task_ref === value.task_ref && task.operation_ref === value.operation_ref);
    check(tasks.length === 1, tasks.length ? '原任务对应多份草稿安排，无法唯一定位，未开放写入。' : '当前草稿没有对应的原任务，未选择同号工序或其他任务。');
    return tasks[0];
  }
  function issues(v) {
    check(Array.isArray(v) && v.every(r => fields(r, ['code', 'message']) && typeof r.message === 'string'));
  }
  function validation(v) {
    check(fields(v, ['status', 'constraints_status', 'can_adopt', 'issues', 'adoption']) && ['blocked', 'warning', 'valid'].includes(v.constraints_status) && ['blocked', 'warning', 'valid'].includes(v.status) && typeof v.can_adopt === 'boolean');
    issues(v.issues);
    check(object(v.adoption) && typeof v.adoption.available === 'boolean');
    issues(v.adoption.blocked_reasons);
  }
  function envelope(v, q = {}) {
    check(v && v.ok === true && v.schema_version === 1 && object(v.data) && v.meta && v.meta.source === 'production' && v.meta.time_basis === 'factory_local' && time(v.meta.as_of) && /^[A-Za-z0-9_-]{32}$/.test(v.meta.snapshot_ref) && /^[a-f0-9]{32}$/.test(v.meta.request_ref));
    issues(v.warnings);
    if (q.snapshot_ref) check(v.meta.snapshot_ref === q.snapshot_ref, window.WorkbenchTerms.outcomes.stale);
    return v.data;
  }
  function arrangement(v, owner) {
    check(fields(v, ['machine_ref', 'operator_ref', 'start', 'end']) && time(v.start) && time(v.end) && window.PointContract.arrangement(v, owner) && ['machine_ref', 'operator_ref'].every(k => v[k] === null || ref(v[k])));
  }
  function workspace(d, expected = {}) {
    check(fields(d, ['draft_ref', 'status', 'base', 'base_identity', 'scope', 'baseline', 'tasks', 'task_count', 'tasks_complete', 'unplanned_operations', 'scope_complete', 'validation', 'resources', 'comparison', 'capacity', 'change_history', 'time_scope']));
    check(ref(d.draft_ref) && (!expected.draft_ref || expected.draft_ref === d.draft_ref) && (!expected.scenario_ref || expected.scenario_ref === d.scenario_ref) && ['editing', 'saved', 'discarded'].includes(d.status));
    if (d.scenario_ref !== undefined) check(ref(d.scenario_ref) && d.status === 'saved' && !d.write_context && typeof d.name === 'string');
    base(d.base);
    scope(d.scope);
    validation(d.validation);
    check(object(d.base_identity) && (d.base.plan_ref ? d.base_identity.plan_ref === d.base.plan_ref : d.base_identity.candidate_ref === d.base.candidate_ref));
    check(d.tasks_complete === true && count(d.task_count) && d.task_count > 0 && d.task_count <= 10000 && Array.isArray(d.tasks) && d.tasks.length === d.task_count);
    check(Array.isArray(d.unplanned_operations) && typeof d.scope_complete === 'boolean' && d.scope_complete === (d.unplanned_operations.length === 0));
    d.unplanned_operations.forEach(r => {
      check(ref(r.operation_ref) && fields(r, ['reason', 'status', 'sequence', 'piece_id']));
      issues([r.reason]);
    });
    const seen = new Set(),
      rows = new Set();
    d.tasks.forEach(t => {
      check(fields(t, ['task_ref', 'row_ref', 'operation_ref', 'source_row_ref', 'source_task_ref', 'batch_ref', 'batch_id', 'part_no', 'part_name', 'process_label', 'sequence', 'piece_id', 'source', 'quantity', 'batch_quantity', 'priority', 'due_date', 'original', 'hours', 'execution', 'execution_at_creation', 'predecessor_refs', 'predecessor_operation_refs', 'edit_context', 'issues', 'data_gaps', 'changed']));
      check(ref(t.task_ref) && ref(t.row_ref) && ref(t.operation_ref) && ref(t.source_row_ref) && (t.source_task_ref === null || ref(t.source_task_ref)) && !seen.has(t.task_ref) && !rows.has(t.row_ref) && t.draft_ref === d.draft_ref);
      seen.add(t.task_ref);
      rows.add(t.row_ref);
      arrangement(t);
      arrangement(t.original, t);
      if (d.base.candidate_ref && !d.scenario_ref) check(t.source_task_ref === null);
      check(['internal', 'external'].includes(t.source) && object(t.hours) && typeof t.changed === 'boolean' && Array.isArray(t.predecessor_refs) && t.predecessor_refs.every(ref) && Array.isArray(t.predecessor_operation_refs) && object(t.edit_context) && typeof t.edit_context.can_change === 'boolean');
      if (d.status !== 'editing') check(t.edit_context.can_change === false);
      issues(t.issues);
      issues(t.data_gaps);
      issues(t.edit_context.blocked_reasons);
    });
    d.tasks.forEach(t => check(t.predecessor_refs.every(r => seen.has(r))));
    check(object(d.resources) && ['machines', 'operators', 'authorizations'].every(k => Array.isArray(d.resources[k])));
    ['machines', 'operators'].forEach(k => check(d.resources[k].every(r => ref(r.ref) && typeof r.business_code === 'string')));
    check(d.comparison.basis === 'draft_original' && Array.isArray(d.comparison.batches) && d.capacity.basis === 'selected_trial_only' && Array.isArray(d.capacity.resources) && Array.isArray(d.change_history) && d.time_scope.time_basis === 'factory_local');
    check(['late_count', 'total_delay_hours', 'changeovers'].every(k => measure(d.comparison[k])) && ['changed_operations', 'moved_operations'].every(k => count(d.comparison[k]) && d.comparison[k] <= d.task_count));
    d.comparison.batches.forEach(r => check(ref(r.batch_ref) && time(r.baseline_finish) && time(r.finish) && ['on_time', 'overdue', 'unavailable', 'invalid_data'].includes(r.risk) && measure(r.late_hours) && measure(r.improvement_hours)));
    check(['available', 'partial', 'unavailable'].includes(d.capacity.state));
    d.capacity.resources.forEach(r => {
      check(ref(r.resource_ref) && ['machine', 'operator'].includes(r.resource_type) && Array.isArray(r.segments) && ['arranged_hours', 'occupied_hours', 'overlap_hours', 'available_hours', 'outside_available_hours', 'utilization'].every(k => measure(r[k])));
      r.segments.forEach(s => check(time(s.start) && time(s.end) && s.start < s.end && count(s.concurrent_operations) && s.concurrent_operations > 0));
      check(object(r.calendar) && (r.calendar.windows === null || Array.isArray(r.calendar.windows)));
      issues(r.calendar.issues);
    });
    check(time(d.time_scope.start) && time(d.time_scope.end) && d.time_scope.selection === 'complete_base' && d.tasks.every(t => t.start >= d.time_scope.start && t.end <= d.time_scope.end));
    d.change_history.forEach(r => {
      const owner = d.tasks.find(t => t.task_ref === r.task_ref || d.scenario_ref && t.source_task_ref === r.task_ref);
      check(ref(r.change_ref) && ref(r.task_ref) && !!owner);
      arrangement(r.before, owner);
      arrangement(r.after, owner);
      validation(r.validation);
    });
    if (d.status === 'editing') check(d.write_context && typeof d.write_context.write_token === 'string' && object(d.write_context.capabilities));
    return d;
  }
  function catalog(v, collection, q) {
    const d = envelope(v, q),
      p = d.page;
    check(Array.isArray(d.items) && d.selection === null && d.validation_state === 'not_evaluated' && p && p.number === q.page && p.size === q.size && count(p.total) && p.total <= 100000 && p.pages === Math.ceil(p.total / p.size) && d.items.length === Math.min(p.size, Math.max(0, p.total - (p.number - 1) * p.size)));
    const key = collection === 'drafts' ? 'draft_ref' : 'scenario_ref';
    const seen = new Set();
    d.items.forEach(r => {
      check(ref(r[key]) && !seen.has(r[key]) && typeof r.display_name === 'string' && count(r.task_count) && r.open_target && r.open_target[key] === r[key] && r.validation_state === 'not_evaluated');
      base(r.base);
      seen.add(r[key]);
      check(q.status === 'all' || r.status === q.status);
      if (q.base_kind) check(r.base[q.base_kind] === q.base_ref);
    });
    return d;
  }
  function receipt(v, intent) {
    check(v && v.ok === true && ['committed', 'unchanged'].includes(v.result) && /^[a-f0-9]{32}$/.test(v.receipt_ref) && typeof v.replayed === 'boolean');
    issues(v.warnings);
    const d = v.data;
    if (d && d.status === 'discarded' && d.history_retained === true) {
      check(ref(d.draft_ref));
      validation(d.validation);
    } else workspace(d);
    if (intent) {
      if (intent.draft_ref) check(d.draft_ref === intent.draft_ref);
      if (intent.action === 'create') check(JSON.stringify(d.base) === JSON.stringify(intent.input.base) && d.status === 'editing');
      if (intent.action === 'save') check(ref(d.scenario_ref) && d.name === intent.input.name.trim());
      if (intent.action === 'discard') check(d.status === 'discarded' && d.history_retained === true);
      if (intent.action === 'change') {
        const t = d.tasks.find(t => t.task_ref === intent.input.task_ref);
        check(t && ['machine_ref', 'operator_ref', 'start'].every(k => t[k] === intent.input[k]));
      }
    }
    return v;
  }
  window.TrialContract = {
    object,
    ref,
    count,
    fields,
    check,
    time,
    base,
    scope,
    target,
    origin,
    originTask,
    issues,
    validation,
    envelope,
    workspace,
    catalog,
    receipt
  };
})();
