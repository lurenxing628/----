(function () {
  'use strict';
  const P = window.PointContract, T = window.APSWorkbenchTransport;
  const BASE = '/api/workbench/v1/scheduling';
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const text = v => typeof v === 'string', count = v => Number.isSafeInteger(v) && v >= 0;
  const ref = v => text(v) && /^[a-f0-9]{48}$/.test(v), token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v);
  function check(value, message = '候选数据不完整或不一致，请刷新后重试。') { if (!value) throw new Error(message); }
  function shape(v, required, optional = []) {
    return object(v) && required.every(k => Object.prototype.hasOwnProperty.call(v, k)) && Object.keys(v).every(k => required.includes(k) || optional.includes(k));
  }
  function time(v) {
    if (!text(v) || !/^(?!0000)\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?(?![\s\S])/.test(v)) return false;
    const calendar = v.slice(0, 19), n = Date.parse(calendar + 'Z');
    return Number.isFinite(n) && new Date(n).toISOString().slice(0, 19) === calendar;
  }
  // Legacy scopes accept 1–6 fractional digits. Compare without Date's millisecond truncation or rewriting the supplied scope.
  const timeKey = value => value.slice(0, 19) + '.' + (value.split('.')[1] || '').padEnd(6, '0');
  const gap = v => shape(v, ['field', 'code', 'message']) && [v.field, v.code, v.message].every(text);
  const gaps = v => Array.isArray(v) && v.every(gap);
  // 生成时的不重排时段：没带这一项表示按交付设置推算；null 是“不设”（存的值读不出来时也是 null，并附 input.hold_window 资料缺项）。
  const minute = v => text(v) && /^(?!0000)\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d$/.test(v) && time(v + ':00');
  const holdWindow = v => v === undefined || v === null || shape(v, ['start', 'end']) && minute(v.start) && minute(v.end) && v.start < v.end;
  const nullableText = v => v === null || text(v);
  const number = v => typeof v === 'number' && Number.isFinite(v) && v >= 0 || text(v) && /^[1-9]\d{15,}$/.test(v) && (v.length > 16 || v > '9007199254740991');
  const nullableNumber = v => v === null || number(v);
  const version = v => v === null || (typeof v === 'string' ? number(v) : Number.isSafeInteger(v) && v > 0);
  const caps = v => shape(v, ['view', 'export', 'edit_draft', 'adopt', 'report_actual']) && typeof v.view === 'boolean' && typeof v.export === 'boolean'
    && v.edit_draft === false && v.adopt === false && v.report_actual === false;
  const blocked = v => Array.isArray(v) && v.every(r => shape(r, ['capability', 'code', 'message']) && [r.capability, r.code, r.message].every(text));
  const metricKeys = ['overdue_count', 'total_tardiness_hours', 'makespan_hours', 'changeover_count', 'weighted_tardiness_hours', 'machine_used_count',
    'operator_used_count', 'machine_busy_hours_total', 'operator_busy_hours_total', 'machine_util_avg', 'operator_util_avg', 'elapsed_seconds'];
  function metric(v) { return shape(v, ['value', 'reason']) && (v.value === null ? gap(v.reason) : number(v.value) && v.reason === null); }
  // 候选只由共同优化生成（unified_search_v1），保存时恒为计算完成。
  function summary(v, runRef) {
    const G = window.RunGenerationContract;
    check(shape(v, ['candidate_ref', 'run_ref', 'label', 'status', 'persisted_status', 'task_count', 'completeness', 'metrics', 'metric_scopes', 'capabilities', 'blocked_reasons', 'data_gaps'].concat(G.metadataKeys))
      && ref(v.candidate_ref) && ref(v.run_ref) && (!runRef || v.run_ref === runRef) && nullableText(v.label) && count(v.task_count) && v.task_count <= 20000
      && v.persisted_status === 'completed' && ['complete', 'partial'].includes(v.completeness)
      && v.status === (v.completeness === 'partial' ? 'partial' : 'completed')
      && shape(v.metrics, metricKeys) && metricKeys.every(k => k === 'elapsed_seconds' ? G.catalogElapsed(v.metrics[k]) : metric(v.metrics[k]))
      && shape(v.metric_scopes, ['delivery', 'resources']) && v.metric_scopes.delivery === 'completed_batches_only' && v.metric_scopes.resources === 'scheduled_results_only'
      && caps(v.capabilities) && blocked(v.blocked_reasons) && gaps(v.data_gaps) && G.metadata(v, v.run_ref));
    return v;
  }
  function validateIdentity(v, candidateRef) {
    const data = v.data;
    check(shape(data, ['candidate_ref', 'run_ref', 'label', 'status']) && ref(candidateRef) && data.candidate_ref === candidateRef
      && ref(data.run_ref) && nullableText(data.label) && data.status === 'completed', '候选身份与所选方案不一致，请重新打开。');
    return data;
  }
  function catalogScope(query) {
    check(shape(query, [], ['page', 'size', 'status', 'sort', 'order', 'snapshot_ref']));
    const q = { page: 1, size: 20, status: 'all', sort: 'sequence', order: 'asc', ...query };
    check(Number.isInteger(q.page) && q.page >= 1 && q.page <= 256 && Number.isInteger(q.size) && q.size >= 1 && q.size <= 50
      && ['all', 'completed', 'partial'].includes(q.status) && ['sequence', 'label', 'task_count'].includes(q.sort)
      && ['asc', 'desc'].includes(q.order) && (q.snapshot_ref === undefined || token(q.snapshot_ref)));
    if (q.snapshot_ref === undefined) delete q.snapshot_ref;
    return q;
  }
  function validateCatalog(v, runRef, query) {
    const d = v.data, q = catalogScope(query);
    check(ref(runRef) && shape(d, ['run_ref', 'run_state', 'candidates', 'page', 'candidate_count', 'catalog_complete', 'capabilities', 'blocked_reasons'])
      && d.run_ref === runRef && ['queued', 'running', 'complete', 'partial', 'failed', 'interrupted'].includes(d.run_state)
      && count(d.candidate_count) && d.candidate_count <= 256 && d.catalog_complete === !['queued', 'running'].includes(d.run_state)
      && caps(d.capabilities) && blocked(d.blocked_reasons) && shape(d.page, ['number', 'size', 'total', 'has_more'])
      && d.page.number === q.page && d.page.size === q.size && count(d.page.total) && d.page.total <= d.candidate_count
      && (q.status !== 'all' || d.page.total === d.candidate_count) && d.page.has_more === (q.page * q.size < d.page.total)
      && token(v.meta.snapshot_ref) && (!q.snapshot_ref || v.meta.snapshot_ref === q.snapshot_ref) && Array.isArray(d.candidates)
      && d.candidates.length === Math.min(q.size, Math.max(0, d.page.total - (q.page - 1) * q.size)));
    d.candidates.forEach(c => { summary(c, runRef); check(q.status === 'all' || c.status === q.status); });
    check(new Set(d.candidates.map(c => c.candidate_ref)).size === d.candidates.length); return d;
  }
  function workspaceScope(candidateRef, query) {
    check(ref(candidateRef), '请选择有效的候选方案。');
    check(shape(query, [], ['range_start', 'range_end', 'batch_ref', 'sort', 'order', 'snapshot_ref']));
    const q = { sort: 'sequence', order: 'asc', ...query };
    check(['sequence', 'start', 'end'].includes(q.sort) && ['asc', 'desc'].includes(q.order)
      && (q.batch_ref === undefined || ref(q.batch_ref)) && (q.snapshot_ref === undefined || token(q.snapshot_ref)));
    if (q.range_start !== undefined || q.range_end !== undefined) check(time(q.range_start) && time(q.range_end)
      && timeKey(q.range_start) < timeKey(q.range_end), '读取范围需要成对时间，开始须早于结束。');
    return q;
  }
  const operationKeys = ['operation_ref', 'batch_ref', 'batch_label', 'part_label', 'sequence', 'process_label', 'piece_id', 'quantity', 'batch_quantity', 'due_date', 'execution_at_generation', 'data_gaps'];
  const executionKeys = ['target_quantity', 'known_completed_quantity', 'remaining_quantity', 'execution_state', 'data_quality', 'target_basis'];
  function quantityContext(v, baseline = false) {
    if (!nullableText(v.piece_id) || v.piece_id !== null && (!v.piece_id.trim() || v.piece_id.includes('\0'))
      || !nullableNumber(v.quantity) || !nullableNumber(v.batch_quantity) || !gaps(v.data_gaps)) return false;
    const e = v.execution_at_generation;
    if (e === null) return v.quantity === null;
    if (!shape(e, executionKeys.concat(baseline ? ['first_actual_start', 'confirmed_finish', 'unknown_record_count', 'records_complete', 'quantity_complete',
      'completion_basis', 'report_count'] : []))
      || !['target_quantity', 'known_completed_quantity', 'remaining_quantity'].every(k => nullableNumber(e[k]))
      || !['execution_state', 'data_quality', 'target_basis'].every(k => nullableText(e[k]))) return false;
    const proven = !v.data_gaps.some(g => g.field === 'piece_id') && e.target_basis === (v.piece_id === null ? 'batch' : 'piece');
    return v.quantity === (proven ? e.target_quantity : null);
  }
  function operation(v, planned) {
    check(shape(v, operationKeys.concat(['operation_effort', 'process_type_ref', 'process_type_label'], planned ? ['row_ref', 'start', 'end', 'source', 'locked', 'machine', 'operator', 'supplier', ...(P.isPoint(v) ? P.fields : [])] : ['row_ref', 'status', 'reason']))
      && ref(v.operation_ref) && (v.batch_ref === null || ref(v.batch_ref)) && ['batch_label', 'part_label', 'process_label', 'process_type_label', 'due_date'].every(k => nullableText(v[k]))
      && nullableNumber(v.sequence) && quantityContext(v)
      && (v.process_type_ref === null || ref(v.process_type_ref))
      && window.EffortProjectionContract.compact(v.operation_effort));
    if (planned) {
      check(ref(v.row_ref) && time(v.start) && time(v.end) && (P.isPoint(v) || timeKey(v.start) < timeKey(v.end))
        && ['internal', 'external'].includes(v.source) && typeof v.locked === 'boolean');
      for (const k of ['machine', 'operator', 'supplier']) check(v[k] === null || shape(v[k], ['ref', 'label']) && (v[k].ref === null || ref(v[k].ref)) && nullableText(v[k].label));
    } else check(v.row_ref === null && ['skipped', 'unscheduled'].includes(v.status) && shape(v.reason, ['code', 'message']) && text(v.reason.code) && text(v.reason.message));
  }
  function span(v) { return v === null || shape(v, ['start', 'end']) && time(v.start) && time(v.end) && timeKey(v.start) <= timeKey(v.end); }
  function delivery(v, data, query) {
    check(shape(v, ['candidate_ref', 'scope', 'state', 'items', 'items_complete', 'batch_count', 'issues', 'summary', 'basis'])
      && v.candidate_ref === data.candidate.candidate_ref && shape(v.scope, ['kind', 'candidate_ref', 'range_start', 'range_end', 'batch_ref', 'sort', 'order'])
      && v.scope.kind === 'run-candidate-workspace' && v.scope.candidate_ref === v.candidate_ref
      && ['range_start', 'range_end', 'batch_ref'].every(k => v.scope[k] === (query[k] ?? null))
      && v.scope.sort === query.sort && v.scope.order === query.order
      && ['available', 'partial', 'unavailable'].includes(v.state) && typeof v.items_complete === 'boolean'
      && count(v.batch_count) && Array.isArray(v.items) && v.items.length <= v.batch_count
      && (!v.items_complete || v.items.length === v.batch_count) && Array.isArray(v.issues)
      && v.issues.every(r => shape(r, ['code', 'message']) && text(r.code) && text(r.message)));
    check(shape(v.basis, ['kind', 'metadata_basis', 'operation_scope', 'completion_scope', 'time_basis', 'due_boundary',
      'current_entities_consulted', 'actual_completion', 'actual_delivery', 'root_causes']) && v.basis.kind === 'planned_delivery'
      && v.basis.metadata_basis === 'captured_at_run_admission' && v.basis.operation_scope === 'captured_batch_operations'
      && v.basis.completion_scope === 'full_candidate' && v.basis.time_basis === 'factory_local'
      && v.basis.due_boundary === 'next_day_exclusive' && v.basis.current_entities_consulted === false
      && ['actual_completion', 'actual_delivery', 'root_causes'].every(k => v.basis[k] === 'not_evaluated'));
    const rowKeys = ['batch_ref', 'batch_id', 'part_no', 'part_label', 'schedule_complete', 'operation_count', 'scheduled_operation_count',
      'unscheduled_operation_count', 'task_count', 'invalid_task_count', 'planned_finish', 'partial_planned_finish', 'risk', 'is_overdue',
      'delay_hours', 'delay_days', 'due_date', 'delivery_deadline_exclusive', 'due_state', 'due_issue', 'completion_state',
      'deferred_operation_count', 'ordinary_unscheduled_operation_count', 'completeness', 'issues', 'priority', 'quantity', 'last_operations'];
    const tasks = new Map(data.tasks.map(row => [row.row_ref, row]));
    v.items.forEach(row => {
      check(shape(row, rowKeys) && ref(row.batch_ref) && text(row.batch_id) && row.batch_id.trim()
        && ['part_no', 'part_label', 'due_date', 'priority'].every(k => nullableText(row[k])) && nullableNumber(row.quantity)
        && ['operation_count', 'scheduled_operation_count', 'unscheduled_operation_count', 'task_count', 'invalid_task_count',
          'deferred_operation_count', 'ordinary_unscheduled_operation_count'].every(k => count(row[k]))
        && ['planned_finish', 'partial_planned_finish', 'delivery_deadline_exclusive'].every(k => row[k] === null || time(row[k]))
        && ['delay_hours', 'delay_days'].every(k => nullableNumber(row[k])) && typeof row.schedule_complete === 'boolean'
        && ['overdue', 'on_time', 'unknown', 'not_applicable'].includes(row.risk) && ['complete', 'incomplete', 'unknown'].includes(row.completeness)
        && ['specified', 'unspecified', 'invalid'].includes(row.due_state)
        && (row.due_issue === null || ['due_date_missing', 'due_date_invalid'].includes(row.due_issue))
        && ['complete', 'deferred', 'incomplete', 'unknown'].includes(row.completion_state)
        && (row.is_overdue === null || typeof row.is_overdue === 'boolean') && Array.isArray(row.issues) && row.issues.every(text)
        && Array.isArray(row.last_operations) && (row.schedule_complete ? row.planned_finish !== null && row.last_operations.length > 0 : row.planned_finish === null && row.last_operations.length === 0)
        && (['unknown', 'not_applicable'].includes(row.risk) ? row.is_overdue === null && row.delay_hours === null && row.delay_days === null
          : row.schedule_complete && row.is_overdue === (row.risk === 'overdue') && row.delay_hours !== null && row.delay_days !== null)
        && (!query.batch_ref || row.batch_ref === query.batch_ref));
      row.last_operations.forEach(task => {
        check(shape(task, ['row_ref', 'operation_ref', 'sequence', 'piece_id', 'process_label', 'start', 'end', 'machine', 'operator'])
          && ref(task.row_ref) && ref(task.operation_ref) && nullableNumber(task.sequence) && nullableText(task.piece_id) && nullableText(task.process_label)
          && time(task.start) && time(task.end) && timeKey(task.start) <= timeKey(task.end) && row.planned_finish !== null && timeKey(task.end) === timeKey(row.planned_finish));
        const original = tasks.get(task.row_ref);
        for (const kind of ['machine', 'operator']) check(task[kind] === null || shape(task[kind], ['ref', 'label'])
          && (task[kind].ref === null || ref(task[kind].ref)) && nullableText(task[kind].label));
        if (original) check(original.operation_ref === task.operation_ref && original.batch_ref === row.batch_ref && original.end === task.end
          && original.start === task.start && original.sequence === task.sequence && original.piece_id === task.piece_id);
        else check(!!query.range_start || !!query.batch_ref);
      });
      check(new Set(row.last_operations.map(t => t.row_ref)).size === row.last_operations.length);
    });
    const s = v.summary;
    check(new Set(v.items.map(row => row.batch_ref)).size === v.items.length && object(s)
      && ['complete', 'partial', 'unavailable', 'not_applicable'].includes(s.state)
      && ['batch_count', 'due_eligible_count', 'excluded_due_count', 'invalid_due_count', 'due_evaluation_count',
        'known_due_count', 'unknown_due_count', 'unknown_count', 'known_overdue_count'].every(k => count(s[k]))
      && ['overdue_count', 'total_tardiness_hours', 'known_tardiness_hours'].every(k => nullableNumber(s[k]))
      && s.batch_count === v.batch_count && Array.isArray(s.known_batch_refs) && s.known_batch_refs.every(ref));
  }
  function validateWorkspace(v, candidateRef, query) {
    const d = v.data, q = workspaceScope(candidateRef, query);
    check(shape(d, ['candidate', 'generation', 'tasks', 'task_count', 'tasks_complete', 'candidate_task_count', 'candidate_span', 'task_span',
      'unplanned_operations', 'unplanned_operation_count', 'time_scope', 'batch_ref', 'capabilities', 'blocked_reasons', 'data_gaps', 'delivery_risks', 'gantt_graph']));
    summary(d.candidate); check(d.candidate.candidate_ref === candidateRef);
    check(Array.isArray(d.tasks) && count(d.task_count) && d.task_count === d.tasks.length && d.tasks_complete === true
      && d.candidate_task_count === d.candidate.task_count && d.task_count <= d.candidate_task_count && span(d.candidate_span) && span(d.task_span)
      && (d.task_count === 0) === (d.task_span === null) && (d.candidate_task_count === 0) === (d.candidate_span === null)
      && caps(d.capabilities) && blocked(d.blocked_reasons) && gaps(d.data_gaps)
      && (!q.snapshot_ref || q.snapshot_ref === v.meta.snapshot_ref) && d.batch_ref === (q.batch_ref ?? null));
    check(shape(d.time_scope, ['range_start', 'range_end', 'interval', 'time_basis', 'unplanned_policy'])
      && d.time_scope.range_start === (q.range_start ?? null) && d.time_scope.range_end === (q.range_end ?? null)
      && d.time_scope.interval === 'half_open_overlap' && d.time_scope.time_basis === 'factory_local' && d.time_scope.unplanned_policy === 'included_without_time_interval');
    const rowRefs = new Set(), operationRefs = new Set();
    let start = null, end = null;
    d.tasks.forEach(t => {
      operation(t, true); check(!q.batch_ref || t.batch_ref === q.batch_ref);
      const low = timeKey(t.start), high = timeKey(t.end);
      if (q.range_start) {
        const rangeStart = timeKey(q.range_start), rangeEnd = timeKey(q.range_end);
        check(P.isPoint(t) ? rangeStart <= low && low < rangeEnd : low < rangeEnd && high > rangeStart);
      }
      rowRefs.add(t.row_ref); operationRefs.add(t.operation_ref);
      if (start === null || low < start) start = low;
      if (end === null || high > end) end = high;
    });
    check(rowRefs.size === d.task_count && operationRefs.size === d.task_count);
    if (!q.range_start && !q.batch_ref) check(d.task_count === d.candidate_task_count);
    if (d.task_count) {
      check(start === timeKey(d.task_span.start) && end === timeKey(d.task_span.end)
        && start >= timeKey(d.candidate_span.start) && end <= timeKey(d.candidate_span.end));
    }
    check(Array.isArray(d.unplanned_operations) && d.unplanned_operation_count === d.unplanned_operations.length);
    d.unplanned_operations.forEach(t => { operation(t, false); check(!operationRefs.has(t.operation_ref) && (!q.batch_ref || t.batch_ref === q.batch_ref)); operationRefs.add(t.operation_ref); });
    const g = d.generation, G = window.RunGenerationContract;
    check(shape(g, ['run_ref', 'accepted_at', 'finished_at', 'metadata_basis', 'execution_basis', 'current_entities_consulted', 'formal_version_allocated', 'input', 'data_gaps', 'baseline', 'algorithm'])
      && g.run_ref === d.candidate.run_ref && time(g.accepted_at) && (g.finished_at === null || time(g.finished_at))
      && g.metadata_basis === 'captured_at_run_admission' && g.execution_basis === 'captured_at_run_admission'
      && g.current_entities_consulted === false && g.formal_version_allocated === false && gaps(g.data_gaps)
      && shape(g.input, ['start_date', 'end_date', 'ready_check', 'missing_resource_policy', 'completed_policy'], ['material_strategy', 'hold_window', 'time_budget_seconds'])
      && (g.input.time_budget_seconds === undefined || G.budget(g.input.time_budget_seconds))
      && (g.input.material_strategy === undefined || ['strict', 'stage'].includes(g.input.material_strategy)
        || g.input.material_strategy === null && g.data_gaps.some(gap => gap.field === 'input.material_strategy'))
      && holdWindow(g.input.hold_window) && (g.input.hold_window === null || !g.data_gaps.some(gap => gap.field === 'input.hold_window'))
      && ['start_date', 'end_date', 'missing_resource_policy', 'completed_policy'].every(k => nullableText(g.input[k]))
      && (g.input.ready_check === null || typeof g.input.ready_check === 'boolean')
      && window.RunGenerationContract.algorithm(g.algorithm, g.run_ref)
      && shape(g.baseline, ['baseline_ref', 'version', 'kind', 'captured_at', 'captured_task_count'])
      && g.baseline.kind === 'admission_official' && version(g.baseline.version) && time(g.baseline.captured_at)
      && (g.baseline.version === null ? g.baseline.baseline_ref === null : ref(g.baseline.baseline_ref))
      && (g.baseline.captured_task_count === null || count(g.baseline.captured_task_count)));
    delivery(d.delivery_risks, d, q);
    check(window.GanttGraph.validate(d.gantt_graph, { scope: 'full_candidate', tasks: d.tasks, taskRef: 'row_ref', time,
      sequence: nullableNumber, processLabel: nullableText, completeCount: d.candidate_task_count }));
    return d;
  }
  // 文件名非空与后缀由传输层按 Content-Type 断言；这里只核对本领域业务头与当前读取范围。
  function download(value, result) {
    const d = result.data;
    check(value.candidate_ref === d.candidate.candidate_ref && value.snapshot_ref === result.meta.snapshot_ref && value.task_count === d.task_count
      && value.row_count === Math.max(1, d.task_count + d.unplanned_operation_count), '下载结果与当前完整范围不一致，没有保存文件。');
    return value;
  }
  const read = (path, query, signal) => T.read(BASE + path, query, { signal, timeout: 60000 });
  async function identity(candidateRef, signal) {
    check(ref(candidateRef)); const value = await read('/candidates/' + candidateRef + '/identity', {}, signal);
    validateIdentity(value, candidateRef); return value;
  }
  async function catalog(runRef, query, signal) {
    check(ref(runRef)); const q = catalogScope(query), value = await read('/runs/' + runRef + '/candidates', q, signal);
    validateCatalog(value, runRef, q); return value;
  }
  async function workspace(candidateRef, query, signal) {
    const q = workspaceScope(candidateRef, query), value = await read('/candidates/' + candidateRef + '/workspace', q, signal);
    validateWorkspace(value, candidateRef, q); return value;
  }
  // 传输层已校验附件、文件名与后缀、格式、魔数与非空；这里只取文件与本领域的四个响应头，与当前读取范围的核对在 download() 里做。
  async function exportFile(candidateRef, query, snapshotRef, fmt, signal) {
    check(token(snapshotRef) && ['csv', 'xlsx'].includes(fmt)); const q = workspaceScope(candidateRef, { ...query, snapshot_ref: snapshotRef });
    const file = await T.download(BASE + '/candidates/' + candidateRef + '/export', { ...q, format: fmt }, { signal, timeout: 60000, types: [T.types[fmt]] });
    const headerCount = key => { const raw = file.header(key); check(raw !== null && /^\d+$/.test(raw) && count(Number(raw))); return Number(raw); };
    return { blob: file.blob, filename: file.filename, candidate_ref: file.header('X-Workbench-Candidate-Ref'),
      snapshot_ref: file.header('X-Workbench-Snapshot-Ref'), task_count: headerCount('X-Workbench-Task-Count'), row_count: headerCount('X-Workbench-Row-Count') };
  }
  window.RunCandidateAPI = { identity, catalog, workspace, export: exportFile, check, ref, time, timeKey, version, shape, summary, validateIdentity, validateCatalog, catalogScope,
    validateWorkspace, workspaceScope, download, metricKeys, operationKeys, executionKeys, quantityContext };
})();
