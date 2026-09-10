(function () {
  'use strict';
  const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
  const fail = text => { throw window.APSResourceContract.failure(text); };
  function local(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(value)) return false;
    const at = Date.parse(value + 'Z'); return Number.isFinite(at) && new Date(at).toISOString().slice(0, 19) === value;
  }
  const nullableTime = value => value === null || local(value);
  const nullableRef = value => value === null || ref(value);
  const quantity = value => value === null || Number.isSafeInteger(value) && value >= 0;
  function planQuantity(t) {
    if (!(t.piece_id === null || typeof t.piece_id === 'string' && t.piece_id.trim() && !t.piece_id.includes('\0'))
      || !quantity(t.quantity) || !quantity(t.batch_quantity)) return false;
    if (t.quantity_basis === 'unknown') return t.quantity === null && t.batch_quantity === null
      && ['plan_target_not_recorded', 'plan_target_unavailable'].includes(t.quantity_reason);
    return ['run_admission', 'trial_creation'].includes(t.quantity_basis)
      && (t.quantity_reason === null ? t.quantity !== null && t.batch_quantity !== null : t.quantity_reason === 'plan_target_invalid');
  }
  const interval = value => object(value) && local(value.start) && local(value.end) && value.start < value.end;
  const arrangement = value => object(value) && local(value.start) && local(value.end) && window.PointContract.arrangement(value);
  const span = value => object(value) && local(value.start) && local(value.end) && value.start <= value.end;
  const cohortKeys = ['plan_ref', 'source', 'range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to', 'resource_type', 'resource_ref', 'batch_ids'];
  function scope(input, exporting = false) {
    const allowed = cohortKeys.concat(['snapshot_ref'], exporting ? ['format', 'local_query', 'late_filter', 'selected_task_ref'] : []);
    if (!object(input) || Reflect.ownKeys(input).some(key => !allowed.includes(key))) fail('现场甘特范围含未知字段，未忽略来源条件。');
    const value = { ...input };
    if (!ref(value.plan_ref) || own(value, 'source') && value.source !== 'production') fail('请明确选择生产计划，未使用样例或最新版本替代。');
    for (const [start, end, dateOnly] of [['range_start', 'range_end', false], ['plan_finish_date_from', 'plan_finish_date_to', true]]) {
      const hasStart = own(value, start), hasEnd = own(value, end);
      if (hasStart !== hasEnd || hasStart && (!local(value[start] + (dateOnly ? 'T00:00:00' : '')) || !local(value[end] + (dateOnly ? 'T00:00:00' : '')) || (dateOnly ? value[start] > value[end] : value[start] >= value[end]))) fail('起止范围不完整或时间无效。');
    }
    if (own(value, 'resource_type') !== own(value, 'resource_ref') || own(value, 'resource_ref') && (!['machine', 'operator'].includes(value.resource_type) || !ref(value.resource_ref))) fail('资源范围不完整。');
    if (own(value, 'batch_ids') && (!Array.isArray(value.batch_ids) || value.batch_ids.length > 10000 || value.batch_ids.some(v => typeof v !== 'string' || !v.trim()) || new Set(value.batch_ids).size !== value.batch_ids.length)) fail('批次集合无效。');
    if (own(value, 'snapshot_ref') && (typeof value.snapshot_ref !== 'string' || !value.snapshot_ref)) fail('读取快照无效。');
    if (exporting && (value.format !== 'csv' || !value.snapshot_ref || own(value, 'local_query') && (typeof value.local_query !== 'string' || value.local_query.length > 200) || own(value, 'late_filter') && !Object.keys(window.ActualGanttModel.lateLabels).includes(value.late_filter) || own(value, 'selected_task_ref') && !ref(value.selected_task_ref))) fail('导出格式、快照或本地筛选无效。');
    return value;
  }
  function report(row, operationRef) {
    return object(row) && ref(row.report_ref) && ref(row.revision_ref) && row.operation_ref === operationRef && ref(row.recorded_against_task_ref) && ref(row.recorded_against_plan_ref)
      && typeof row.report_no === 'string' && row.report_no && nullableTime(row.actual_start) && nullableTime(row.actual_end)
      && (!row.actual_end || !row.actual_start || row.actual_end >= row.actual_start) && quantity(row.completed_quantity)
      && (row.effective_processing_hours === null || typeof row.effective_processing_hours === 'number' && Number.isFinite(row.effective_processing_hours) && row.effective_processing_hours >= 0)
      && nullableRef(row.actual_machine_ref) && nullableRef(row.actual_operator_ref) && typeof row.remark === 'string' && local(row.recorded_at) && Array.isArray(row.correction_history);
  }
  function execution(e, task) {
    return object(e) && e.operation_ref === task.operation_ref && e.comparison_task_ref === task.task_ref && nullableRef(e.current_task_ref)
      && quantity(e.target_quantity) && quantity(e.remaining_quantity) && quantity(e.known_completed_quantity) && e.known_completed_quantity !== null
      && Number.isSafeInteger(e.unknown_record_count) && e.unknown_record_count >= 0 && typeof e.quantity_complete === 'boolean' && typeof e.records_complete === 'boolean'
      && ['batch', 'piece'].includes(e.target_basis) && own(window.ActualGanttModel.states, e.execution_state)
      && [null, 'complete_reports', 'legacy_finish_event'].includes(e.completion_basis) && ['complete', 'incomplete', 'legacy_incomplete', 'invalid'].includes(e.data_quality)
      && nullableTime(e.first_actual_start) && nullableTime(e.confirmed_finish) && (e.remaining_plan === null || interval(e.remaining_plan))
      && Array.isArray(e.reports) && e.reports.every(r => report(r, task.operation_ref)) && new Set(e.reports.map(r => r.report_ref)).size === e.reports.length
      && Array.isArray(e.legacy_facts) && e.legacy_facts.every(fact => object(fact) && ref(fact.legacy_fact_ref) && nullableRef(fact.actual_machine_ref) && nullableRef(fact.actual_operator_ref)) && Array.isArray(e.data_gaps);
  }
  function workspace(result, input) {
    const query = scope(input), d = result && result.data, meta = result && result.meta;
    if (!result || result.ok !== true || result.schema_version !== 1 || !meta || meta.source !== 'production' || meta.time_basis !== 'factory_local' || !local(meta.as_of)
      || typeof meta.snapshot_ref !== 'string' || !meta.snapshot_ref || query.snapshot_ref && query.snapshot_ref !== meta.snapshot_ref || !object(d)) fail('现场甘特响应不完整或快照已切换。');
    if (!d.plan || d.plan.plan_ref !== query.plan_ref || !d.plan.capabilities.view || !span(d.plan_span) || !interval(d.axis_span)
      || !d.scope || d.scope.kind !== 'actual_gantt' || d.scope.source !== 'production' || !object(d.availability) || !['available', 'unavailable'].includes(d.availability.state)
      || !Array.isArray(d.items) || d.items.length !== d.task_count || d.task_count > 10000 || d.items_complete !== true || !Array.isArray(d.resources)
      || !d.resources.every(r => object(r) && ref(r.ref) && ['machine', 'operator', 'supplier'].includes(r.kind) && typeof r.business_code === 'string' && (r.label === null || typeof r.label === 'string'))
      || !object(d.critical_chain) || !Array.isArray(d.critical_chain.task_refs) || !Array.isArray(d.critical_chain.edges)) fail('现场甘特范围或完整性合同无效。');
    for (const key of cohortKeys) {
      const expected = key === 'source' ? query.source || 'production' : key === 'batch_ids' ? (query[key] || []).slice().sort() : query[key] == null ? null : query[key];
      if (JSON.stringify(d.scope[key]) !== JSON.stringify(expected)) fail('返回范围与原请求不同，未自动扩大范围。');
    }
    const resourceRefs = new Set(d.resources.map(row => row.ref)), taskRefs = new Set(); let count = 0;
    d.items.forEach(item => {
      const t = item.task, e = item.execution;
      if (!t || !ref(t.task_ref) || taskRefs.has(t.task_ref) || !ref(t.operation_ref) || t.plan_ref !== query.plan_ref || !arrangement(t) || !planQuantity(t) || typeof t.batch_id !== 'string' || typeof t.process_label !== 'string') fail('计划任务身份、数量证据或时间无效。');
      if (t.start < d.plan_span.start || t.end > d.plan_span.end || t.start < d.axis_span.start || t.end > d.axis_span.end) fail('计划任务超出原计划或显示范围。');
      taskRefs.add(t.task_ref);
      if (d.availability.state === 'available' ? !execution(e, t) : e !== null) fail('执行投影缺失或与计划任务串源。');
      const used = [t.machine_ref, t.operator_ref];
      if (e) { count += e.reports.length; e.reports.concat(e.legacy_facts).forEach(r => used.push(r.actual_machine_ref, r.actual_operator_ref)); if (e.remaining_plan) used.push(e.remaining_plan.machine_ref, e.remaining_plan.operator_ref); }
      if (used.some(r => r != null && (!ref(r) || !resourceRefs.has(r)))) fail('实际或计划资源目录不完整。');
    });
    if (d.availability.state === 'available' ? d.report_count !== count || count > 50000 : d.report_count !== null || !d.availability.reason) fail('报工数量或不可用原因不完整。');
    if (d.critical_chain.state !== 'unavailable' && (d.critical_chain.state !== 'available' || !d.critical_chain.engine_evidence_ref || d.critical_chain.snapshot_ref !== meta.snapshot_ref || d.critical_chain.task_refs.some(r => !taskRefs.has(r)))) fail('关键链没有绑定本快照的真实引擎证据。');
    return result;
  }
  function transport(value) { const result = { ...value }; if (result.batch_ids) result.batch_ids = JSON.stringify(result.batch_ids); return result; }
  window.ActualGanttContract = { scope, workspace, transport, local, ref };
})();
