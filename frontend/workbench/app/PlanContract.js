(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.PointContract;
  const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const token = value => typeof value === 'string' && value.length > 0;
  const label = value => token(value) && value.trim().length > 0;
  const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
  const nullableRef = value => value === null || ref(value);
  const exact = (value, keys) => object(value) && Reflect.ownKeys(value).length === keys.length && keys.every(key => own(value, key));
  const issues = value => Array.isArray(value) && value.every(row => exact(row, ['code', 'message']) && label(row.code) && label(row.message));
  const projections = ['baseline', 'calendar', 'occupancy', 'delivery_risks'];
  function int64(value) {
    if (typeof value === 'number') return Number.isSafeInteger(value) && value > 0;
    return typeof value === 'string' && /^[1-9][0-9]*$/.test(value)
      && (value.length > 16 || value.length === 16 && value > '9007199254740991')
      && (value.length < 19 || value.length === 19 && value <= '9223372036854775807');
  }
  function localTime(value) {
    if (typeof value !== 'string' || !/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$/.test(value)) return false;
    const [year, month, day, hour, minute, second] = value.split(/[-T:]/).map(Number);
    const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    return year >= 1 && month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1]
      && hour < 24 && minute < 60 && second < 60;
  }
  function span(value, pointEnd = false) {
    const inclusive = pointEnd && value && own(value, 'end_inclusive');
    return exact(value, ['start', 'end', ...(inclusive ? ['end_inclusive'] : [])]) && (!inclusive || value.end_inclusive === true)
      && localTime(value.start) && localTime(value.end) && value.start <= value.end;
  }
  function parameters(scope, allowed) {
    if (!object(scope) || Object.prototype.toString.call(scope) !== '[object Object]'
        || Reflect.ownKeys(scope).some(key => !allowed.includes(key) || !Object.prototype.propertyIsEnumerable.call(scope, key)))
      throw C.failure('计划读取含未知参数或无效范围，未忽略筛选条件。');
    for (const key in scope) {
      if (!own(scope, key)) throw C.failure('计划范围含继承的参数，未忽略筛选条件。');
    }
    const query = { ...scope };
    for (const key of ['cursor', 'snapshot_ref']) {
      if (own(query, key) && !token(query[key])) throw C.failure('计划游标和快照必须是非空原始令牌。');
    }
    return query;
  }
  function catalogScope(scope = {}) {
    const query = parameters(scope, ['collection', 'size', 'cursor', 'snapshot_ref']);
    if (!own(query, 'collection')) query.collection = 'history';
    if (!own(query, 'size')) query.size = 20;
    if (!['history', 'scenario'].includes(query.collection) || !Number.isSafeInteger(query.size) || query.size < 1 || query.size > 50)
      throw C.failure('计划目录必须选择历史或场景，每页为 1 至 50 个版本或场景。');
    return query;
  }
  function workspaceScope(planRef, scope = {}) {
    if (!ref(planRef)) throw C.failure('所选计划引用无效，请返回目录重新选择。');
    const query = parameters(scope, ['range_start', 'range_end', 'snapshot_ref']);
    const start = own(query, 'range_start'), end = own(query, 'range_end');
    if (start !== end || start && (!localTime(query.range_start) || !localTime(query.range_end) || query.range_start >= query.range_end))
      throw C.failure('计划起止时间必须同时提供有效的工厂本地时间，且起点早于终点。');
    return query;
  }
  function exportScope(planRef, scope) {
    const query = parameters(scope, ['format', 'range_start', 'range_end', 'snapshot_ref']);
    if (!['csv', 'xlsx'].includes(query.format) || !own(query, 'snapshot_ref'))
      throw C.failure('导出必须提供格式和当前工作区的读取快照。');
    const {format, ...read} = query;
    return {format, ...workspaceScope(planRef, read)};
  }
  function download(value, format) {
    const expected = format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
    if (!exact(value, ['blob', 'contentType', 'disposition']) || !value.blob || !(value.blob.size > 0)
        || typeof value.contentType !== 'string' || value.contentType.split(';')[0] !== expected
        || !/^attachment;/i.test(value.disposition)) throw C.failure('计划导出响应不是所选格式的附件。');
    return value;
  }
  function envelope(result, query) {
    if (!exact(result, ['ok', 'schema_version', 'data', 'meta', 'warnings']) || result.ok !== true || result.schema_version !== 1
        || !exact(result.meta, ['request_ref', 'source', 'time_basis', 'snapshot_ref', 'as_of'])
        || result.meta.source !== 'production' || result.meta.time_basis !== 'factory_local'
        || !token(result.meta.snapshot_ref) || !token(result.meta.request_ref) || !localTime(result.meta.as_of) || !issues(result.warnings))
      throw C.failure('计划读取协议不完整或不是生产数据，未使用样例替代。');
    if (own(query, 'snapshot_ref') && result.meta.snapshot_ref !== query.snapshot_ref)
      throw C.failure('计划快照与请求不一致，未自动切换到新数据。');
  }
  function plan(value) {
    if (!exact(value, ['plan_ref', 'version', 'kind', 'is_current_official', 'display_name', 'completeness', 'capabilities', 'blocked_reasons'])
        || !nullableRef(value.plan_ref) || !(value.version === null || int64(value.version))
        || !['official', 'candidate', 'scenario'].includes(value.kind) || typeof value.is_current_official !== 'boolean'
        || !label(value.display_name) || !['complete', 'partial', 'invalid', 'unknown'].includes(value.completeness)
        || !exact(value.capabilities, ['view', 'export', 'edit_draft', 'adopt', 'report_actual']) || typeof value.capabilities.view !== 'boolean'
        || value.capabilities.export !== value.capabilities.view
        || !['edit_draft', 'adopt', 'report_actual'].every(key => value.capabilities[key] === false) || !issues(value.blocked_reasons)) return false;
    const view = value.capabilities.view;
    return (view ? ref(value.plan_ref) && int64(value.version) && value.blocked_reasons.length === 0 && value.completeness !== 'invalid'
      : value.blocked_reasons.length > 0) && (!value.is_current_official || value.kind === 'official' && view);
  }
  function uniqueRefs(rows, key) {
    if (!Array.isArray(rows) || rows.some(row => !object(row) || !own(row, key))) return false;
    const refs = rows.map(row => row[key]).filter(value => value !== null);
    return new Set(refs).size === refs.length;
  }
  function catalog(result, scope = {}) {
    const query = catalogScope(scope);
    envelope(result, query);
    const d = result.data, p = d && d.page;
    if (!exact(d, ['plans', 'page']) || !Array.isArray(d.plans) || !d.plans.every(plan) || !uniqueRefs(d.plans, 'plan_ref')
        || !exact(p, ['collection', 'size', 'unit', 'has_more', 'next_cursor']) || p.collection !== query.collection || p.size !== query.size
        || p.unit !== (query.collection === 'history' ? 'version' : 'scenario') || typeof p.has_more !== 'boolean'
        || (p.has_more ? !token(p.next_cursor) || !d.plans.length || p.next_cursor === query.cursor : p.next_cursor !== null)
        || d.plans.some(row => (row.kind === 'scenario') !== (query.collection === 'scenario'))
        || d.plans.filter(row => row.is_current_official).length > 1)
      throw C.failure('计划目录、身份或分页与请求不一致，未作为完整目录使用。');
    // A history page counts versions, not role entries; null versions cannot be grouped by guessed identity.
    const units = query.collection === 'scenario' ? d.plans.length : new Set(d.plans.filter(row => row.version !== null).map(row => String(row.version))).size
      + d.plans.filter(row => row.version === null).length;
    if (units > query.size) throw C.failure('计划目录超过请求页范围，未忽略分页协议。');
    return result;
  }
  function task(row, planRef, planSpan, timeScope) {
    return exact(row, ['task_ref', 'operation_ref', 'plan_ref', 'batch_id', 'sequence', 'process_label', 'piece_id', 'quantity', 'batch_quantity', 'quantity_basis', 'quantity_reason',
      'machine_ref', 'operator_ref', 'supplier_ref', 'start', 'end', ...(P.isPoint(row) ? P.fields : [])])
      && ref(row.task_ref) && ref(row.operation_ref) && row.plan_ref === planRef && label(row.batch_id) && int64(row.sequence) && label(row.process_label)
      && (row.piece_id === null || label(row.piece_id) && !row.piece_id.includes('\0')) && taskQuantities(row)
      && ['machine_ref', 'operator_ref', 'supplier_ref'].every(key => nullableRef(row[key]))
      && localTime(row.start) && localTime(row.end) && P.arrangement(row)
      && (!planSpan || row.start >= planSpan.start && row.end <= planSpan.end)
      && (!timeScope || P.overlaps(row, timeScope.range_start, timeScope.range_end));
  }
  function taskQuantities(row) {
    const valid = value => value === 0 || int64(value);
    if (![row.quantity, row.batch_quantity].every(value => value === null || valid(value))) return false;
    if (row.quantity_basis === 'unknown') return row.quantity === null && row.batch_quantity === null
      && ['plan_target_not_recorded', 'plan_target_unavailable'].includes(row.quantity_reason);
    return ['run_admission', 'trial_creation'].includes(row.quantity_basis)
      && (row.quantity_reason === null ? valid(row.quantity) && valid(row.batch_quantity) : row.quantity_reason === 'plan_target_invalid');
  }
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const number = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
  const nullableLabel = value => value === null || label(value);
  const nullableTime = value => value === null || localTime(value);
  const day = value => typeof value === 'string' && localTime(value + 'T00:00:00');
  const same = (a, b) => object(a) && object(b) && exact(a, Object.keys(b)) && Object.keys(b).every(key => a[key] === b[key]);
  const inScope = (row, scope) => !!row && (scope.range_start === null || P.overlaps(row, scope.range_start, scope.range_end));
  const states = ['available', 'partial', 'unavailable'];
  function resourceDirectory(data) {
    if (!Array.isArray(data.resources) || !uniqueRefs(data.resources, 'ref')) return false;
    const byRef = new Map();
    for (const row of data.resources) {
      if (!exact(row, ['kind', 'ref', 'business_code', 'label']) || !['machine', 'operator', 'supplier'].includes(row.kind)
          || !ref(row.ref) || !label(row.business_code) || !nullableLabel(row.label)) return false;
      byRef.set(row.ref, row);
    }
    const used = new Set();
    for (const row of data.tasks) for (const kind of ['machine', 'operator', 'supplier']) {
      const value = row[kind + '_ref'];
      if (value === null) continue;
      if (!byRef.has(value) || byRef.get(value).kind !== kind) return false;
      used.add(value);
    }
    return used.size === byRef.size;
  }
  function baseline(value, data) {
    if (!object(value)) return false;
    if (value.state === 'unavailable') return exact(value, ['state', 'reason_code', 'reason', 'baseline_plan', 'items', 'item_count', 'items_complete'])
      && ['not_recorded', 'baseline_binding_invalid', 'baseline_unavailable', 'scenario_unavailable', 'baseline_task_invalid',
        'no_adoption_baseline', 'adoption_evidence_missing', 'adoption_source_archived', 'adoption_snapshot_invalid',
        'adoption_baseline_archived', 'adoption_reference_invalid', 'adoption_baseline_drift', 'adoption_plan_drift'].includes(value.reason_code)
      && label(value.reason) && value.baseline_plan === null && Array.isArray(value.items) && value.items.length === 0
      && value.item_count === 0 && value.items_complete === false;
    const fields = ['start', 'end', 'machine_ref', 'operator_ref'], s = value.comparison_scope;
    if (!exact(value, ['state', 'reason_code', 'reason', 'basis', 'baseline_plan', 'comparison_scope', 'compared_fields', 'items', 'item_count', 'items_complete'])
        || value.state !== 'available' || value.reason_code !== null || value.reason !== null
        || !['scenario_base', 'candidate_adoption', 'trial_adoption'].includes(value.basis)
        || data.plan.kind !== (value.basis === 'scenario_base' ? 'scenario' : 'official')
        || !plan(value.baseline_plan) || !value.baseline_plan.capabilities.view
        || value.basis !== 'scenario_base' && (value.baseline_plan.kind !== 'official' || value.baseline_plan.is_current_official)
        || value.baseline_plan.kind === 'scenario' || value.baseline_plan.plan_ref === data.plan.plan_ref
        || !exact(s, ['scope', 'selection', 'boundary', 'alignment', 'time_basis', 'task_times']) || !same(s.scope, data.scope)
        || s.selection !== 'either_side_overlap' || s.boundary !== 'half_open' || s.alignment !== 'operation_ref'
        || s.time_basis !== 'factory_local' || s.task_times !== 'unclipped' || JSON.stringify(value.compared_fields) !== JSON.stringify(fields)
        || !Array.isArray(value.items) || value.item_count !== value.items.length || value.item_count > 20000
        || value.items_complete !== true || !uniqueRefs(value.items, 'operation_ref')) return false;
    const selected = new Map(data.tasks.map(row => [row.task_ref, row]));
    let afterCount = 0;
    for (const row of value.items) {
      if (!exact(row, ['operation_ref', 'change', 'changed_fields', 'before', 'after', 'before_in_scope', 'after_in_scope']) || !ref(row.operation_ref)) return false;
      const before = row.before, after = row.after;
      if (before === null && after === null || before !== null && (!task(before, value.baseline_plan.plan_ref) || before.operation_ref !== row.operation_ref)
          || after !== null && (!task(after, data.plan.plan_ref) || after.operation_ref !== row.operation_ref)) return false;
      const changed = before && after ? fields.filter(key => before[key] !== after[key]) : [];
      const change = before === null ? 'added' : after === null ? 'removed' : changed.length ? 'changed' : 'unchanged';
      if (row.change !== change || JSON.stringify(row.changed_fields) !== JSON.stringify(changed)
          || row.before_in_scope !== inScope(before, data.scope) || row.after_in_scope !== inScope(after, data.scope)
          || !row.before_in_scope && !row.after_in_scope) return false;
      if (row.after_in_scope) {
        if (!same(after, selected.get(after.task_ref))) return false;
        afterCount++;
      }
    }
    return afterCount === data.tasks.length;
  }
  function projectionIssues(rows, assignment = false) {
    return Array.isArray(rows) && rows.every(row => {
      if (!object(row)) return false;
      const extra = assignment ? ['operation_count'] : own(row, 'policy_date') ? ['policy_date'] : [];
      return exact(row, ['code', 'message', ...extra]) && label(row.code) && label(row.message)
        && (assignment ? count(row.operation_count) && row.operation_count > 0 : !extra.length || day(row.policy_date));
    });
  }
  const measures = ['available_hours', 'effective_hours', 'normal_available_hours', 'normal_effective_hours', 'urgent_available_hours', 'urgent_effective_hours'];
  function intervals(rows, time, extra, validate) {
    return Array.isArray(rows) && rows.every((row, index) => exact(row, ['start', 'end', ...extra])
      && localTime(row.start) && localTime(row.end) && row.start < row.end && row.start >= time.range_start && row.end <= time.range_end
      && (!index || rows[index - 1].end <= row.start) && validate(row));
  }
  function calendarRow(row, time, resource = false) {
    if (!object(row) || !['available', 'unavailable'].includes(row.state)) return false;
    const extra = resource ? ['kind', 'resource_ref', 'label'] : [];
    if (resource && own(row, 'status')) extra.push('status');
    if (resource && row.state === 'available') extra.push('downtime_windows', 'downtime_scope_hours', 'downtime_available_hours');
    if (!exact(row, ['state', 'basis', 'windows', 'issues', ...measures, ...extra]) || !projectionIssues(row.issues)
        || (resource ? !['machine', 'operator'].includes(row.kind) || !ref(row.resource_ref) || !nullableLabel(row.label)
          || row.basis !== (row.kind === 'machine' ? 'global_calendar_machine_availability' : 'personal_or_operator_shift_calendar')
          : row.basis !== 'global_calendar')) return false;
    if (own(row, 'status') && !(row.kind === 'machine' ? ['active', 'inactive', 'maintain'] : ['active', 'inactive']).includes(row.status)) return false;
    if (row.state === 'unavailable') return row.windows === null && row.issues.length > 0 && measures.every(key => row[key] === null);
    if (!measures.every(key => number(row[key])) || row.issues.length) return false;
    if (!intervals(row.windows, time, ['policy_date', 'allow_normal', 'allow_urgent', 'efficiency', 'provenance'], window => day(window.policy_date)
      && typeof window.allow_normal === 'boolean' && typeof window.allow_urgent === 'boolean' && number(window.efficiency)
      && ['personal_calendar', 'work_calendar', 'domain_default', 'work_calendar_operator_shift', 'domain_default_operator_shift'].includes(window.provenance))) return false;
    return !resource || own(row, 'status') && (row.status === 'active' || row.windows.length === 0)
      && number(row.downtime_scope_hours) && number(row.downtime_available_hours) && intervals(row.downtime_windows, time, [], () => true);
  }
  function projectedResources(rows, data) {
    if (!Array.isArray(rows) || !uniqueRefs(rows, 'resource_ref')) return false;
    const directory = new Map(data.resources.map(row => [row.ref, row]));
    return rows.every(row => {
      const resource = directory.get(row.resource_ref);
      return resource && row.kind === resource.kind && row.label === resource.label;
    });
  }
  function calendar(value, data) {
    if (!exact(value, ['state', 'plan_ref', 'time_scope', 'global', 'resources', 'issues']) || !states.includes(value.state)
        || value.plan_ref !== data.plan.plan_ref || !same(value.time_scope, data.time_scope) || !projectionIssues(value.issues)
        || !calendarRow(value.global, data.time_scope)) return false;
    if (value.resources === null) return value.state === 'unavailable' && value.global.state === 'unavailable' && value.issues.length > 0;
    if (!projectedResources(value.resources, data) || !value.resources.every(row => calendarRow(row, data.time_scope, true)) || value.issues.length) return false;
    const all = [value.global, ...value.resources];
    return value.state === (all.every(row => row.state === 'available') ? 'available' : all.every(row => row.state === 'unavailable') ? 'unavailable' : 'partial');
  }
  function occupancyRow(row, data) {
    const known = ['arranged_hours', 'occupied_hours', 'overlap_hours', 'excess_arranged_hours'];
    const capacity = ['available_hours', 'available_occupied_hours', 'outside_available_hours', 'capacity_shortfall_hours'];
    if (!exact(row, ['kind', 'resource_ref', 'label', ...known, ...capacity, 'state', 'operation_count', 'capacity_basis',
        'utilization', 'has_overlap', 'capacity_insufficient', 'issues', 'segments']) || !['machine', 'operator'].includes(row.kind)
        || !['available', 'unavailable'].includes(row.state) || !known.every(key => number(row[key])) || !count(row.operation_count) || row.operation_count === 0
        || !projectionIssues(row.issues) || typeof row.has_overlap !== 'boolean' || row.has_overlap !== (row.overlap_hours > 0)
        || !intervals(row.segments, data.time_scope, ['concurrent_operations'], segment => count(segment.concurrent_operations) && segment.concurrent_operations > 0)) return false;
    const expected = row.kind === 'machine' ? 'global_calendar_machine_availability' : 'personal_or_operator_shift_calendar';
    const calendars = data.projections.calendar.resources;
    const source = calendars && calendars.find(item => item.resource_ref === row.resource_ref);
    if (row.capacity_basis !== (source ? expected : 'unknown')) return false;
    if (row.state === 'unavailable') return (!source || source.state === 'unavailable') && capacity.every(key => row[key] === null)
      && row.utilization === null && row.capacity_insufficient === null && row.issues.length > 0;
    return source && source.state === 'available' && capacity.every(key => number(row[key])) && row.available_hours === source.available_hours
      && typeof row.capacity_insufficient === 'boolean' && row.issues.length === 0
      && (row.available_hours === 0 ? row.utilization === null : number(row.utilization) && row.utilization <= 1);
  }
  function occupancy(value, data) {
    if (!exact(value, ['state', 'plan_ref', 'time_scope', 'basis', 'resources', 'issues']) || !states.includes(value.state)
        || value.plan_ref !== data.plan.plan_ref || !same(value.time_scope, data.time_scope) || value.basis !== 'selected_plan_only'
        || !projectedResources(value.resources, data) || !projectionIssues(value.issues, true) || !value.resources.every(row => occupancyRow(row, data))) return false;
    const unknown = value.issues.some(row => row.code === 'assignment_source_unknown');
    const state = unknown ? value.resources.length ? 'partial' : 'unavailable' : value.resources.every(row => row.state === 'available')
      ? 'available' : value.resources.every(row => row.state === 'unavailable') ? 'unavailable' : 'partial';
    return value.state === state;
  }
  function deliveryItem(row) {
    const counts = ['operation_count', 'scheduled_operation_count', 'unscheduled_operation_count', 'task_count', 'invalid_task_count'];
    if (!exact(row, ['batch_ref', 'batch_id', 'part_no', 'part_label', 'planned_finish', 'partial_planned_finish', 'due_date',
        'delivery_deadline_exclusive', 'risk', 'is_overdue', 'delay_hours', 'delay_days', 'completeness', 'schedule_complete', ...counts, 'issues'])
        || !ref(row.batch_ref) || !label(row.batch_id) || !nullableLabel(row.part_no) || !nullableLabel(row.part_label)
        || !nullableTime(row.planned_finish) || !nullableTime(row.partial_planned_finish) || !(row.due_date === null || day(row.due_date))
        || !nullableTime(row.delivery_deadline_exclusive) || !['overdue', 'on_time', 'unknown'].includes(row.risk)
        || !['complete', 'incomplete', 'unknown'].includes(row.completeness) || typeof row.schedule_complete !== 'boolean'
        || !counts.every(key => count(row[key])) || row.invalid_task_count > row.task_count || row.scheduled_operation_count > row.task_count
        || row.scheduled_operation_count + row.unscheduled_operation_count !== row.operation_count
        || !Array.isArray(row.issues) || !row.issues.every(label) || new Set(row.issues).size !== row.issues.length) return false;
    if (row.schedule_complete ? row.planned_finish === null || row.partial_planned_finish !== null || row.operation_count === 0
      || row.unscheduled_operation_count !== 0 || row.invalid_task_count !== 0 : row.planned_finish !== null) return false;
    if ((row.completeness === 'complete') !== (row.issues.length === 0)) return false;
    if (row.risk === 'unknown') return row.is_overdue === null && row.delay_hours === null && row.delay_days === null && row.issues.length > 0;
    return row.schedule_complete && row.delivery_deadline_exclusive !== null && typeof row.is_overdue === 'boolean'
      && row.is_overdue === (row.planned_finish >= row.delivery_deadline_exclusive) && (row.risk === 'overdue') === row.is_overdue
      && number(row.delay_hours) && number(row.delay_days) && (row.is_overdue || row.delay_hours === 0 && row.delay_days === 0);
  }
  function delivery(value, data) {
    if (!exact(value, ['state', 'plan_ref', 'scope', 'items', 'batch_count', 'items_complete', 'completeness', 'basis'])
        || !states.includes(value.state) || value.plan_ref !== data.plan.plan_ref || !same(value.scope, data.scope)
        || !Array.isArray(value.items) || value.batch_count !== value.items.length || value.items_complete !== true
        || !uniqueRefs(value.items, 'batch_ref') || !uniqueRefs(value.items, 'batch_id') || !value.items.every(deliveryItem)) return false;
    const basis = {kind: 'planned_delivery', time_basis: 'factory_local', batch_selection: data.scope.range_start === null ? 'plan_task_batches' : 'overlap_or_bad_time_batches',
      completion_scope: 'full_selected_plan', operation_scope: 'current_batch_operations', due_boundary: 'next_day_exclusive', actual_completion: 'not_evaluated', actual_delivery: 'not_evaluated'};
    if (!same(value.basis, basis)) return false;
    const batches = new Set(data.tasks.map(row => row.batch_id));
    const completeness = value.items.some(row => row.completeness === 'incomplete') ? 'incomplete'
      : !value.items.length || value.items.some(row => row.completeness === 'unknown') ? 'unknown' : 'complete';
    const known = value.items.filter(row => row.risk !== 'unknown').length;
    return batches.size === value.items.length && value.items.every(row => batches.has(row.batch_id)) && value.completeness === completeness
      && value.state === (known === value.items.length ? 'available' : known ? 'partial' : 'unavailable');
  }
  function workspaceSpans(data, query) {
    const time = data.time_scope;
    return span(data.plan_span, true) && exact(time, ['range_start', 'range_end', 'selection', 'boundary', 'time_basis'])
      && time.range_start === (own(query, 'range_start') ? query.range_start : data.plan_span.start)
      && time.range_end === (own(query, 'range_end') ? query.range_end : data.plan_span.end)
      && time.selection === 'overlap' && time.boundary === 'half_open' && time.time_basis === 'factory_local';
  }
  function taskSpans(data, query) {
    const explicit = own(query, 'range_start'), inclusive = data.plan_span.end_inclusive === true;
    const includesEnd = !explicit || query.range_start <= data.plan_span.end && query.range_end > data.plan_span.end;
    if (inclusive && includesEnd && !data.tasks.some(row => P.isPoint(row) && row.end === data.plan_span.end)) return false;
    const whole = !explicit || query.range_start <= data.plan_span.start
      && (query.range_end > data.plan_span.end || !inclusive && query.range_end === data.plan_span.end);
    if (!data.tasks.length) return data.task_span === null && !whole;
    if (!span(data.task_span)) return false;
    let start = data.tasks[0].start, end = data.tasks[0].end;
    for (const row of data.tasks) { if (row.start < start) start = row.start; if (row.end > end) end = row.end; }
    return data.task_span.start === start && data.task_span.end === end && (!whole
      || start === data.plan_span.start && end === data.plan_span.end);
  }
  function workspace(result, planRef, scope = {}) {
    const query = workspaceScope(planRef, scope);
    envelope(result, query);
    const d = result.data;
    if (!exact(d, ['plan', 'scope', 'time_scope', 'plan_span', 'task_span', 'tasks', 'task_count', 'tasks_complete', 'resources', 'projections'])
        || !plan(d.plan) || !d.plan.capabilities.view || d.plan.plan_ref !== planRef
        || !exact(d.scope, ['source', 'kind', 'plan_ref', 'range_start', 'range_end']) || d.scope.source !== 'production'
        || d.scope.kind !== 'plan_workspace' || d.scope.plan_ref !== planRef
        || d.scope.range_start !== (own(query, 'range_start') ? query.range_start : null)
        || d.scope.range_end !== (own(query, 'range_end') ? query.range_end : null) || !workspaceSpans(d, query)
        || !Array.isArray(d.tasks) || !Number.isSafeInteger(d.task_count) || d.task_count !== d.tasks.length || d.task_count > 10000
        || d.tasks_complete !== true || !d.tasks.every(row => task(row, planRef, d.plan_span, own(query, 'range_start') ? d.time_scope : null)) || !uniqueRefs(d.tasks, 'task_ref')
        || !taskSpans(d, query) || !resourceDirectory(d) || !exact(d.projections, projections)
        || !baseline(d.projections.baseline, d) || !calendar(d.projections.calendar, d)
        || !occupancy(d.projections.occupancy, d) || !delivery(d.projections.delivery_risks, d))
      throw C.failure('计划任务、范围或投影协议不完整或串源，未作为完整结果使用。');
    return result;
  }
  window.APSPlanContract = { catalogScope, workspaceScope, exportScope, catalog, workspace, download };
})();
