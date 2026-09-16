(function () {
  'use strict';

  const P = window.PointContract;
  const BASE = '/api/workbench/v1/scheduling';
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const text = v => typeof v === 'string',
    count = v => Number.isSafeInteger(v) && v >= 0;
  const ref = v => text(v) && /^[a-f0-9]{48}$/.test(v),
    token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v);
  function check(value, message = '候选数据不完整或不一致，请刷新后重试。') {
    if (!value) throw new Error(message);
  }
  function shape(v, required, optional = []) {
    return object(v) && required.every(k => Object.prototype.hasOwnProperty.call(v, k)) && Object.keys(v).every(k => required.concat(optional).includes(k));
  }
  function time(v) {
    if (!text(v) || !/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?$/.test(v)) return false;
    const n = Date.parse(v + 'Z');
    return Number.isFinite(n) && new Date(n).toISOString().slice(0, 19) === v.slice(0, 19);
  }
  const gap = v => shape(v, ['field', 'code', 'message']) && [v.field, v.code, v.message].every(text);
  const gaps = v => Array.isArray(v) && v.every(gap);
  const nullableText = v => v === null || text(v);
  const number = v => typeof v === 'number' && Number.isFinite(v) && v >= 0 || text(v) && /^[1-9]\d{15,}$/.test(v) && (v.length > 16 || v > '9007199254740991');
  const nullableNumber = v => v === null || number(v);
  const caps = v => shape(v, ['view', 'export', 'edit_draft', 'adopt', 'report_actual'], ['trial']) && typeof v.view === 'boolean' && typeof v.export === 'boolean' && v.edit_draft === false && v.adopt === false && v.report_actual === false && (v.trial === undefined || v.trial === false);
  const blocked = v => Array.isArray(v) && v.every(r => shape(r, ['capability', 'code', 'message']) && [r.capability, r.code, r.message].every(text));
  const metricKeys = ['overdue_count', 'total_tardiness_hours', 'makespan_hours', 'changeover_count', 'weighted_tardiness_hours', 'machine_used_count', 'operator_used_count', 'machine_busy_hours_total', 'operator_busy_hours_total', 'machine_util_avg', 'operator_util_avg', 'elapsed_seconds'];
  function metric(v) {
    return shape(v, ['value', 'reason']) && (v.value === null ? gap(v.reason) : number(v.value) && v.reason === null);
  }
  function summary(v, runRef) {
    check(shape(v, ['candidate_ref', 'run_ref', 'label', 'status', 'persisted_status', 'task_count', 'completeness', 'metrics', 'metric_scopes', 'capabilities', 'blocked_reasons', 'data_gaps']) && ref(v.candidate_ref) && ref(v.run_ref) && (!runRef || v.run_ref === runRef) && nullableText(v.label) && count(v.task_count) && v.task_count <= 20000 && ['completed', 'failed', 'skipped'].includes(v.persisted_status) && ['complete', 'partial', 'unknown', 'no_result'].includes(v.completeness) && v.status === (v.persisted_status === 'completed' && v.completeness === 'partial' ? 'partial' : v.persisted_status) && (v.persisted_status === 'completed' ? v.completeness !== 'no_result' : v.completeness === 'no_result' && v.task_count === 0) && shape(v.metrics, metricKeys) && metricKeys.every(k => metric(v.metrics[k])) && shape(v.metric_scopes, ['delivery', 'resources']) && v.metric_scopes.delivery === 'completed_batches_only' && v.metric_scopes.resources === 'scheduled_results_only' && caps(v.capabilities) && blocked(v.blocked_reasons) && gaps(v.data_gaps));
    return v;
  }
  function envelope(v) {
    check(shape(v, ['ok', 'schema_version', 'data', 'meta', 'warnings']) && v.ok === true && v.schema_version === 1 && shape(v.meta, ['request_ref', 'source', 'time_basis', 'snapshot_ref', 'as_of']) && /^[a-f0-9]{32}$/.test(v.meta.request_ref) && v.meta.source === 'production' && v.meta.time_basis === 'factory_local' && token(v.meta.snapshot_ref) && time(v.meta.as_of) && Array.isArray(v.warnings) && v.warnings.every(r => object(r) && text(r.code) && text(r.message)));
    return v.data;
  }
  function catalogScope(query = {}) {
    check(shape(query, [], ['page', 'size', 'status', 'sort', 'order', 'snapshot_ref']));
    const q = {
      page: 1,
      size: 20,
      status: 'all',
      sort: 'sequence',
      order: 'asc',
      ...query
    };
    check(Number.isInteger(q.page) && q.page >= 1 && q.page <= 256 && Number.isInteger(q.size) && q.size >= 1 && q.size <= 50 && ['all', 'completed', 'partial', 'failed', 'skipped'].includes(q.status) && ['sequence', 'label', 'task_count'].includes(q.sort) && ['asc', 'desc'].includes(q.order) && (q.snapshot_ref === undefined || token(q.snapshot_ref)));
    if (q.snapshot_ref === undefined) delete q.snapshot_ref;
    return q;
  }
  function catalog(v, runRef, query) {
    const d = envelope(v),
      q = catalogScope(query);
    check(ref(runRef) && shape(d, ['run_ref', 'run_state', 'candidates', 'page', 'candidate_count', 'catalog_complete', 'capabilities', 'blocked_reasons']) && d.run_ref === runRef && ['queued', 'running', 'complete', 'partial', 'failed', 'interrupted'].includes(d.run_state) && count(d.candidate_count) && d.candidate_count <= 256 && d.catalog_complete === !['queued', 'running'].includes(d.run_state) && caps(d.capabilities) && blocked(d.blocked_reasons) && shape(d.page, ['number', 'size', 'total', 'has_more']) && d.page.number === q.page && d.page.size === q.size && count(d.page.total) && d.page.total <= d.candidate_count && (q.status !== 'all' || d.page.total === d.candidate_count) && d.page.has_more === q.page * q.size < d.page.total && (!q.snapshot_ref || v.meta.snapshot_ref === q.snapshot_ref) && Array.isArray(d.candidates) && d.candidates.length === Math.min(q.size, Math.max(0, d.page.total - (q.page - 1) * q.size)));
    d.candidates.forEach(c => {
      summary(c, runRef);
      check(q.status === 'all' || c.status === q.status);
    });
    check(new Set(d.candidates.map(c => c.candidate_ref)).size === d.candidates.length);
    return d;
  }
  function workspaceScope(candidateRef, query = {}) {
    check(ref(candidateRef), '请选择有效的候选方案。');
    check(shape(query, [], ['range_start', 'range_end', 'batch_ref', 'sort', 'order', 'snapshot_ref']));
    const q = {
      sort: 'sequence',
      order: 'asc',
      ...query
    };
    check(['sequence', 'start', 'end'].includes(q.sort) && ['asc', 'desc'].includes(q.order) && (q.batch_ref === undefined || ref(q.batch_ref)) && (q.snapshot_ref === undefined || token(q.snapshot_ref)));
    if (q.range_start !== undefined || q.range_end !== undefined) check(time(q.range_start) && time(q.range_end) && Date.parse(q.range_start + 'Z') < Date.parse(q.range_end + 'Z'), '读取范围需要成对时间，开始须早于结束。');
    return q;
  }
  const operationKeys = ['operation_ref', 'batch_ref', 'batch_label', 'part_label', 'sequence', 'process_label', 'piece_id', 'quantity', 'batch_quantity', 'due_date', 'execution_at_generation', 'data_gaps'];
  const executionKeys = ['target_quantity', 'known_completed_quantity', 'remaining_quantity', 'execution_state', 'data_quality', 'target_basis'];
  function quantityContext(v, baseline = false) {
    if (!nullableText(v.piece_id) || v.piece_id !== null && (!v.piece_id.trim() || v.piece_id.includes('\0')) || !nullableNumber(v.quantity) || !nullableNumber(v.batch_quantity) || !gaps(v.data_gaps)) return false;
    const e = v.execution_at_generation;
    if (e === null) return v.quantity === null;
    if (!shape(e, executionKeys.concat(baseline ? ['first_actual_start', 'confirmed_finish', 'unknown_record_count', 'records_complete', 'quantity_complete', 'completion_basis', 'report_count', 'legacy_fact_count', 'legacy_unavailable_field_count'] : [])) || !['target_quantity', 'known_completed_quantity', 'remaining_quantity'].every(k => nullableNumber(e[k])) || !['execution_state', 'data_quality', 'target_basis'].every(k => nullableText(e[k]))) return false;
    const proven = !v.data_gaps.some(g => g.field === 'piece_id') && e.target_basis === (v.piece_id === null ? 'batch' : 'piece');
    return v.quantity === (proven ? e.target_quantity : null);
  }
  function operation(v, planned) {
    check(shape(v, operationKeys.concat(planned ? ['row_ref', 'start', 'end', 'source', 'locked', 'machine', 'operator', 'supplier', ...(P.isPoint(v) ? P.fields : [])] : ['row_ref', 'status', 'reason'])) && ref(v.operation_ref) && (v.batch_ref === null || ref(v.batch_ref)) && ['batch_label', 'part_label', 'process_label', 'due_date'].every(k => nullableText(v[k])) && nullableNumber(v.sequence) && quantityContext(v));
    const e = v.execution_at_generation;
    check(e === null || shape(e, ['target_quantity', 'known_completed_quantity', 'remaining_quantity', 'execution_state', 'data_quality', 'target_basis']) && ['target_quantity', 'known_completed_quantity', 'remaining_quantity'].every(k => nullableNumber(e[k])) && ['execution_state', 'data_quality', 'target_basis'].every(k => nullableText(e[k])));
    if (planned) {
      check(ref(v.row_ref) && time(v.start) && time(v.end) && (P.isPoint(v) || Date.parse(v.start + 'Z') < Date.parse(v.end + 'Z')) && ['internal', 'external'].includes(v.source) && typeof v.locked === 'boolean');
      for (const k of ['machine', 'operator', 'supplier']) check(v[k] === null || shape(v[k], ['ref', 'label']) && (v[k].ref === null || ref(v[k].ref)) && nullableText(v[k].label));
    } else check(v.row_ref === null && ['skipped', 'unscheduled'].includes(v.status) && shape(v.reason, ['code', 'message']) && text(v.reason.code) && text(v.reason.message));
  }
  function span(v) {
    return v === null || shape(v, ['start', 'end']) && time(v.start) && time(v.end) && Date.parse(v.start + 'Z') <= Date.parse(v.end + 'Z');
  }
  function delivery(v, data, query) {
    check(shape(v, ['candidate_ref', 'scope', 'state', 'items', 'items_complete', 'batch_count', 'issues', 'summary', 'basis']) && v.candidate_ref === data.candidate.candidate_ref && shape(v.scope, ['kind', 'candidate_ref', 'range_start', 'range_end', 'batch_ref', 'sort', 'order']) && v.scope.kind === 'run-candidate-workspace' && v.scope.candidate_ref === v.candidate_ref && ['range_start', 'range_end', 'batch_ref'].every(k => v.scope[k] === (query[k] || null)) && v.scope.sort === query.sort && v.scope.order === query.order && ['available', 'partial', 'unavailable'].includes(v.state) && typeof v.items_complete === 'boolean' && count(v.batch_count) && Array.isArray(v.items) && v.items.length <= v.batch_count && (!v.items_complete || v.items.length === v.batch_count) && Array.isArray(v.issues) && v.issues.every(r => shape(r, ['code', 'message']) && text(r.code) && text(r.message)));
    check(shape(v.basis, ['kind', 'metadata_basis', 'operation_scope', 'completion_scope', 'time_basis', 'due_boundary', 'current_entities_consulted', 'actual_completion', 'actual_delivery', 'root_causes']) && v.basis.kind === 'planned_delivery' && v.basis.metadata_basis === 'captured_at_run_admission' && v.basis.operation_scope === 'captured_batch_operations' && v.basis.completion_scope === 'full_candidate' && v.basis.time_basis === 'factory_local' && v.basis.due_boundary === 'next_day_exclusive' && v.basis.current_entities_consulted === false && ['actual_completion', 'actual_delivery', 'root_causes'].every(k => v.basis[k] === 'not_evaluated'));
    const rowKeys = ['batch_ref', 'batch_id', 'part_no', 'part_label', 'schedule_complete', 'operation_count', 'scheduled_operation_count', 'unscheduled_operation_count', 'task_count', 'invalid_task_count', 'planned_finish', 'partial_planned_finish', 'risk', 'is_overdue', 'delay_hours', 'delay_days', 'due_date', 'delivery_deadline_exclusive', 'completeness', 'issues', 'quantity', 'last_operations'];
    const tasks = new Map(data.tasks.map(row => [row.row_ref, row]));
    v.items.forEach(row => {
      check(shape(row, rowKeys) && ref(row.batch_ref) && text(row.batch_id) && row.batch_id.trim() && ['part_no', 'part_label', 'due_date'].every(k => nullableText(row[k])) && nullableNumber(row.quantity) && ['operation_count', 'scheduled_operation_count', 'unscheduled_operation_count', 'task_count', 'invalid_task_count'].every(k => count(row[k])) && ['planned_finish', 'partial_planned_finish', 'delivery_deadline_exclusive'].every(k => row[k] === null || time(row[k])) && ['delay_hours', 'delay_days'].every(k => nullableNumber(row[k])) && typeof row.schedule_complete === 'boolean' && ['overdue', 'on_time', 'unknown'].includes(row.risk) && ['complete', 'incomplete', 'unknown'].includes(row.completeness) && (row.is_overdue === null || typeof row.is_overdue === 'boolean') && Array.isArray(row.issues) && row.issues.every(text) && Array.isArray(row.last_operations) && (row.schedule_complete ? row.planned_finish !== null && row.last_operations.length > 0 : row.planned_finish === null && row.last_operations.length === 0) && (row.risk === 'unknown' ? row.is_overdue === null && row.delay_hours === null && row.delay_days === null : row.schedule_complete && row.is_overdue === (row.risk === 'overdue') && row.delay_hours !== null && row.delay_days !== null) && (!query.batch_ref || row.batch_ref === query.batch_ref));
      row.last_operations.forEach(task => {
        check(shape(task, ['row_ref', 'operation_ref', 'sequence', 'piece_id', 'process_label', 'start', 'end', 'machine', 'operator']) && ref(task.row_ref) && ref(task.operation_ref) && nullableNumber(task.sequence) && nullableText(task.piece_id) && nullableText(task.process_label) && time(task.start) && time(task.end) && task.start <= task.end && row.planned_finish !== null && task.end.slice(0, 19) === row.planned_finish.slice(0, 19));
        const original = tasks.get(task.row_ref);
        for (const kind of ['machine', 'operator']) check(task[kind] === null || shape(task[kind], ['ref', 'label']) && (task[kind].ref === null || ref(task[kind].ref)) && nullableText(task[kind].label));
        if (original) check(original.operation_ref === task.operation_ref && original.batch_ref === row.batch_ref && original.end === task.end && original.start === task.start && original.sequence === task.sequence && original.piece_id === task.piece_id);else check(!!query.range_start || !!query.batch_ref);
      });
      check(new Set(row.last_operations.map(t => t.row_ref)).size === row.last_operations.length);
    });
    check(new Set(v.items.map(row => row.batch_ref)).size === v.items.length && shape(v.summary, ['overdue_count', 'unknown_count', 'batch_count', 'total_tardiness_hours']) && v.summary.overdue_count === v.items.filter(row => row.risk === 'overdue').length && count(v.summary.unknown_count) && v.summary.unknown_count === v.items.filter(row => row.risk === 'unknown').length + v.batch_count - v.items.length && v.summary.batch_count === v.batch_count && nullableNumber(v.summary.total_tardiness_hours) && v.summary.total_tardiness_hours === (v.summary.unknown_count || v.issues.length ? null : v.items.reduce((sum, row) => sum + row.delay_hours, 0)) && v.items_complete === (v.issues.length === 0));
  }
  function workspace(v, candidateRef, query = {}, runRef) {
    const d = envelope(v),
      q = workspaceScope(candidateRef, query);
    check(shape(d, ['candidate', 'generation', 'tasks', 'task_count', 'tasks_complete', 'candidate_task_count', 'candidate_span', 'task_span', 'unplanned_operations', 'unplanned_operation_count', 'time_scope', 'batch_ref', 'capabilities', 'blocked_reasons', 'data_gaps', 'delivery_risks']));
    summary(d.candidate, runRef);
    check(d.candidate.candidate_ref === candidateRef);
    check(Array.isArray(d.tasks) && count(d.task_count) && d.task_count === d.tasks.length && d.tasks_complete === true && d.candidate_task_count === d.candidate.task_count && d.task_count <= d.candidate_task_count && span(d.candidate_span) && span(d.task_span) && d.task_count === 0 === (d.task_span === null) && d.candidate_task_count === 0 === (d.candidate_span === null) && caps(d.capabilities) && blocked(d.blocked_reasons) && gaps(d.data_gaps) && (!q.snapshot_ref || q.snapshot_ref === v.meta.snapshot_ref) && d.batch_ref === (q.batch_ref || null));
    check(shape(d.time_scope, ['range_start', 'range_end', 'interval', 'time_basis', 'unplanned_policy']) && d.time_scope.range_start === (q.range_start || null) && d.time_scope.range_end === (q.range_end || null) && d.time_scope.interval === 'half_open_overlap' && d.time_scope.time_basis === 'factory_local' && d.time_scope.unplanned_policy === 'included_without_time_interval');
    d.tasks.forEach(t => {
      operation(t, true);
      check(!q.batch_ref || t.batch_ref === q.batch_ref);
      check(!q.range_start || P.overlaps(t, q.range_start, q.range_end));
    });
    check(new Set(d.tasks.map(t => t.row_ref)).size === d.task_count && new Set(d.tasks.map(t => t.operation_ref)).size === d.task_count);
    if (!q.range_start && !q.batch_ref) check(d.task_count === d.candidate_task_count);
    if (d.task_count) {
      let start = Infinity,
        end = -Infinity;
      d.tasks.forEach(t => {
        start = Math.min(start, Date.parse(t.start + 'Z'));
        end = Math.max(end, Date.parse(t.end + 'Z'));
      });
      check(start === Date.parse(d.task_span.start + 'Z') && end === Date.parse(d.task_span.end + 'Z') && start >= Date.parse(d.candidate_span.start + 'Z') && end <= Date.parse(d.candidate_span.end + 'Z'));
    }
    if (d.unplanned_operations === null) check(d.unplanned_operation_count === null && d.data_gaps.some(g => g.field === 'unplanned_operations'));else {
      check(Array.isArray(d.unplanned_operations) && d.unplanned_operation_count === d.unplanned_operations.length);
      const seen = new Set(d.tasks.map(t => t.operation_ref));
      d.unplanned_operations.forEach(t => {
        operation(t, false);
        check(!seen.has(t.operation_ref) && (!q.batch_ref || t.batch_ref === q.batch_ref));
        seen.add(t.operation_ref);
      });
    }
    const g = d.generation;
    check(shape(g, ['run_ref', 'accepted_at', 'finished_at', 'metadata_basis', 'execution_basis', 'current_entities_consulted', 'formal_version_allocated', 'input', 'data_gaps', 'baseline']) && g.run_ref === d.candidate.run_ref && time(g.accepted_at) && (g.finished_at === null || time(g.finished_at)) && g.metadata_basis === 'captured_at_run_admission' && g.execution_basis === 'captured_at_run_admission' && g.current_entities_consulted === false && g.formal_version_allocated === false && gaps(g.data_gaps) && shape(g.input, ['start_date', 'end_date', 'ready_check', 'missing_resource_policy', 'completed_policy']) && ['start_date', 'end_date', 'missing_resource_policy', 'completed_policy'].every(k => nullableText(g.input[k])) && (g.input.ready_check === null || typeof g.input.ready_check === 'boolean') && shape(g.baseline, ['captured_task_count', 'comparison_available', 'reason']) && (g.baseline.captured_task_count === null || count(g.baseline.captured_task_count)) && g.baseline.comparison_available === false && shape(g.baseline.reason, ['code', 'message']) && text(g.baseline.reason.message));
    delivery(d.delivery_risks, d, q);
    return d;
  }
  function failure(payload, status) {
    const e = payload && payload.error;
    const error = new Error(e && text(e.message) ? e.message : '候选方案数据无效，请刷新后重试。');
    error.code = e && e.code || 'invalid_response';
    error.status = status;
    return error;
  }
  function download(value, result, fmt) {
    const d = result.data;
    check(value && value.blob instanceof Blob && value.blob.size > 0 && value.candidate_ref === d.candidate.candidate_ref && value.snapshot_ref === result.meta.snapshot_ref && value.task_count === d.task_count && value.row_count === Math.max(1, d.task_count + (d.unplanned_operation_count || 0)) && text(value.filename) && !/[\\/\r\n]/.test(value.filename) && value.filename.endsWith('.' + fmt), '下载结果与当前完整范围不一致，没有保存文件。');
    return value;
  }
  function create(fetcher = window.fetch.bind(window)) {
    async function request(path, signal, binary) {
      const controller = new AbortController(),
        abort = () => controller.abort();
      if (signal) {
        if (signal.aborted) abort();else signal.addEventListener('abort', abort, {
          once: true
        });
      }
      const timer = setTimeout(abort, 60000);
      try {
        const response = await fetcher(BASE + path, {
          method: 'GET',
          credentials: 'same-origin',
          cache: 'no-store',
          redirect: 'error',
          signal: controller.signal
        });
        const mime = (response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
        if (!response.ok) throw failure(mime === 'application/json' ? await response.json() : null, response.status);
        check(response.status === 200);
        if (!binary) {
          check(mime === 'application/json');
          return await response.json();
        }
        check(mime === (binary === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'), '下载格式不符，未保存文件。');
        const blob = await response.blob(),
          bytes = new Uint8Array(await blob.slice(0, 4).arrayBuffer());
        check(binary === 'xlsx' ? bytes[0] === 80 && bytes[1] === 75 : bytes[0] === 239 && bytes[1] === 187 && bytes[2] === 191, '下载文件内容无效。');
        check(/^attachment;/i.test(response.headers.get('Content-Disposition') || ''));
        const headerCount = key => {
          const raw = response.headers.get(key);
          check(raw !== null && /^\d+$/.test(raw) && count(Number(raw)));
          return Number(raw);
        };
        return {
          blob,
          filename: '候选范围导出.' + binary,
          candidate_ref: response.headers.get('X-Workbench-Candidate-Ref'),
          snapshot_ref: response.headers.get('X-Workbench-Snapshot-Ref'),
          task_count: headerCount('X-Workbench-Task-Count'),
          row_count: headerCount('X-Workbench-Row-Count')
        };
      } finally {
        clearTimeout(timer);
        if (signal) signal.removeEventListener('abort', abort);
      }
    }
    return {
      async catalog(runRef, query = {}, signal) {
        check(ref(runRef));
        const q = catalogScope(query);
        const v = await request('/runs/' + runRef + '/candidates?' + new URLSearchParams(q), signal);
        catalog(v, runRef, q);
        return v;
      },
      async workspace(candidateRef, query = {}, signal) {
        const q = workspaceScope(candidateRef, query);
        const v = await request('/candidates/' + candidateRef + '/workspace?' + new URLSearchParams(q), signal);
        workspace(v, candidateRef, q);
        return v;
      },
      async export(candidateRef, query, snapshotRef, fmt, signal) {
        check(token(snapshotRef) && ['csv', 'xlsx'].includes(fmt));
        const q = workspaceScope(candidateRef, {
          ...query,
          snapshot_ref: snapshotRef
        });
        return request('/candidates/' + candidateRef + '/export?' + new URLSearchParams({
          ...q,
          format: fmt
        }), signal, fmt);
      }
    };
  }
  window.RunCandidateAPI = {
    create,
    check,
    ref,
    time,
    shape,
    envelope,
    catalog,
    catalogScope,
    workspace,
    workspaceScope,
    download,
    metricKeys,
    operationKeys,
    executionKeys,
    quantityContext
  };
})();
