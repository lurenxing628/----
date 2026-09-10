(function () {
  'use strict';
  const BASE = '/api/workbench/v1/scheduling', PENDING_KEY = 'aps_workbench_run_pending_v1';
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const text = v => typeof v === 'string', count = v => Number.isSafeInteger(v) && v >= 0;
  const ref = v => text(v) && /^[a-f0-9]{48}$/.test(v), token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v);
  const key = v => text(v) && /^run-[a-f0-9]{48}$/.test(v);
  const rejections = new WeakSet();
  const terminal = run => !!run && ['complete', 'partial', 'failed', 'interrupted'].includes(run.state);
  function check(valid, message = '排产返回的数据不完整或不一致，暂时不能确认结果。') { if (!valid) throw new Error(message); }
  function shape(v, required, optional = []) {
    return object(v) && required.every(k => Object.prototype.hasOwnProperty.call(v, k)) && Object.keys(v).every(k => required.concat(optional).includes(k));
  }
  function date(v) {
    if (!text(v) || !/^\d{4}-\d{2}-\d{2}$/.test(v) || v < '1900-01-01' || v >= '9999-12-31') return false;
    const [y, m, d] = v.split('-').map(Number), value = new Date(y, m - 1, d);
    return value.getFullYear() === y && value.getMonth() === m - 1 && value.getDate() === d;
  }
  const time = v => text(v) && /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$/.test(v) && date(v.slice(0, 10));
  const issue = v => shape(v, ['code', 'message'], ['operation_ref', 'batch_ref', 'batch_id']) && text(v.code) && v.code.length > 0 && text(v.message)
    && ['operation_ref', 'batch_ref'].every(k => v[k] === undefined || ref(v[k])) && (v.batch_id === undefined || text(v.batch_id));
  const issues = v => Array.isArray(v) && v.every(issue);
  function input(v) {
    check(shape(v, ['batch_refs', 'start_date', 'end_date', 'ready_check', 'missing_resource_policy', 'completed_policy'])
      && Array.isArray(v.batch_refs) && v.batch_refs.length <= 5000 && v.batch_refs.every(ref) && new Set(v.batch_refs).size === v.batch_refs.length
      && date(v.start_date) && date(v.end_date) && v.start_date <= v.end_date && typeof v.ready_check === 'boolean'
      && ['auto_assign', 'exclude'].includes(v.missing_resource_policy) && v.completed_policy === 'preserve_actuals');
    return v;
  }
  function envelope(v) {
    check(shape(v, ['ok', 'schema_version', 'data', 'meta', 'warnings']) && v.ok === true && v.schema_version === 1
      && shape(v.meta, ['request_ref', 'source', 'time_basis', 'snapshot_ref', 'as_of']) && /^[a-f0-9]{32}$/.test(v.meta.request_ref)
      && v.meta.source === 'production' && v.meta.time_basis === 'factory_local' && token(v.meta.snapshot_ref) && time(v.meta.as_of) && issues(v.warnings));
    return v.data;
  }
  function preview(v, inputRef) {
    const d = envelope(v);
    check(shape(d, ['input_ref', 'normalized_input', 'write_context', 'calendar_check', 'warnings']) && token(inputRef) && d.input_ref === inputRef
      && d.calendar_check === 'not_evaluated' && issues(d.warnings));
    input(d.normalized_input);
    const c = d.write_context;
    check(shape(c, ['write_token', 'expires_at', 'capabilities', 'blocked_reasons']) && shape(c.capabilities, ['scheduling.run']) && issues(c.blocked_reasons));
    check(c.capabilities['scheduling.run'] === true ? token(c.write_token) && time(c.expires_at) && c.blocked_reasons.length === 0 && d.normalized_input.batch_refs.length > 0
      : c.capabilities['scheduling.run'] === false && c.write_token === null && c.expires_at === null && c.blocked_reasons.length > 0);
    return d;
  }
  function run(v, expectedRef) {
    check(shape(v, ['run_ref', 'job_ref', 'state', 'stage', 'progress', 'plans', 'plan_catalog_connected', 'candidates', 'result_persisted',
      'accepted_at', 'started_at', 'finished_at', 'receipt_ref', 'error', 'recovery_required']) && ref(v.run_ref) && v.job_ref === v.run_ref
      && (!expectedRef || v.run_ref === expectedRef) && ['queued', 'running', 'complete', 'partial', 'failed', 'interrupted'].includes(v.state)
      && v.progress === null && Array.isArray(v.plans) && v.plans.length === 0 && v.plan_catalog_connected === false
      && Array.isArray(v.candidates) && time(v.accepted_at) && (v.started_at === null || time(v.started_at))
      && (v.finished_at === null || time(v.finished_at)) && (v.error === null || shape(v.error, ['code', 'message']) && issue(v.error)));
    const done = terminal(v), saved = ['complete', 'partial'].includes(v.state);
    check(v.result_persisted === saved && v.recovery_required === (v.stage === 'awaiting_reconciliation')
      && (done ? v.stage === 'finished' && ref(v.receipt_ref) && time(v.finished_at)
        : v.receipt_ref === null && v.finished_at === null && [v.state === 'queued' ? 'queued' : 'computing', 'awaiting_reconciliation'].includes(v.stage))
      && (v.state === 'queued' ? v.started_at === null : v.state === 'running' || saved ? time(v.started_at) : true)
      && (saved || !done ? v.error === null : v.error !== null)
      && v.candidates.every(c => shape(c, ['candidate_ref', 'label', 'status', 'task_count', 'selected']) && ref(c.candidate_ref) && text(c.label)
        && ['completed', 'failed', 'skipped'].includes(c.status) && count(c.task_count) && typeof c.selected === 'boolean'
        && (c.status === 'completed' || c.task_count === 0 && c.selected === false))
      && new Set(v.candidates.map(c => c.candidate_ref)).size === v.candidates.length
      && (saved ? v.candidates.length > 0 && v.candidates.filter(c => c.selected).length === 1 : v.candidates.length === 0));
    return v;
  }
  function accepted(v) {
    check(shape(v, ['ok', 'result', 'job_ref', 'run_ref', 'status_target', 'receipt_ref', 'replayed', 'data'], ['dispatch_pending'])
      && v.ok === true && v.result === 'accepted' && ref(v.run_ref) && v.job_ref === v.run_ref && text(v.receipt_ref) && /^[a-f0-9]{32}$/.test(v.receipt_ref)
      && v.status_target === BASE + '/runs/' + v.run_ref && typeof v.replayed === 'boolean' && (v.dispatch_pending === undefined || v.dispatch_pending === true));
    run(v.data, v.run_ref); return v;
  }
  function lookup(v, expectedRef) {
    const d = envelope(v);
    check(shape(d, ['found', 'run']) && typeof d.found === 'boolean');
    if (d.found) run(d.run, expectedRef); else check(d.run === null);
    return d;
  }
  const gaps = v => Array.isArray(v) && v.every(g => shape(g, ['field', 'code', 'message']) && [g.field, g.code, g.message].every(text));
  const capabilities = v => shape(v, ['view', 'export', 'edit_draft', 'adopt', 'report_actual']) && v.view === true && v.export === true
    && v.edit_draft === false && v.adopt === false && v.report_actual === false;
  const blocked = v => Array.isArray(v) && v.every(r => shape(r, ['capability', 'code', 'message'])
    && ['adopt', 'edit_draft', 'report_actual', 'preview'].includes(r.capability) && text(r.code) && text(r.message))
    && ['adopt', 'edit_draft', 'report_actual'].every(c => v.some(r => r.capability === c));
  const metricKeys = ['overdue_count', 'total_tardiness_hours', 'makespan_hours', 'changeover_count', 'weighted_tardiness_hours', 'machine_used_count',
    'operator_used_count', 'machine_busy_hours_total', 'operator_busy_hours_total', 'machine_util_avg', 'operator_util_avg', 'elapsed_seconds'];
  function metric(v) {
    if (!shape(v, ['value', 'reason'])) return false;
    if (v.value === null) return v.reason !== null && gaps([v.reason]);
    return v.reason === null && (typeof v.value === 'number' && Number.isFinite(v.value) && v.value >= 0
      || text(v.value) && /^[1-9]\d{15,}$/.test(v.value) && (v.value.length > 16 || v.value > '9007199254740991'));
  }
  function catalogScope(v = {}) {
    check(shape(v, [], ['page', 'snapshot_ref']) && (v.page === undefined || Number.isInteger(v.page) && v.page >= 1 && v.page <= 256)
      && (v.snapshot_ref === undefined || token(v.snapshot_ref)));
    return { page: v.page || 1, size: 20, status: 'all', sort: 'sequence', order: 'asc', ...(v.snapshot_ref ? { snapshot_ref: v.snapshot_ref } : {}) };
  }
  function catalog(v, runRef, query = {}) {
    const d = envelope(v), scope = catalogScope(query);
    check(shape(d, ['run_ref', 'run_state', 'candidates', 'page', 'candidate_count', 'catalog_complete', 'capabilities', 'blocked_reasons'])
      && ref(runRef) && d.run_ref === runRef && ['queued', 'running', 'complete', 'partial', 'failed', 'interrupted'].includes(d.run_state)
      && count(d.candidate_count) && d.candidate_count <= 256 && d.catalog_complete === !['queued', 'running'].includes(d.run_state)
      && capabilities(d.capabilities) && blocked(d.blocked_reasons)
      && shape(d.page, ['number', 'size', 'total', 'has_more']) && d.page.number === scope.page && d.page.size === 20
      && count(d.page.total) && d.page.total === d.candidate_count && d.page.has_more === (scope.page * 20 < d.page.total)
      && (!scope.snapshot_ref || v.meta.snapshot_ref === scope.snapshot_ref) && Array.isArray(d.candidates)
      && d.candidates.length === Math.min(20, Math.max(0, d.page.total - (scope.page - 1) * 20)));
    check(d.candidates.every(c => shape(c, ['candidate_ref', 'run_ref', 'label', 'status', 'persisted_status', 'task_count', 'completeness', 'metrics', 'metric_scopes', 'capabilities', 'blocked_reasons', 'data_gaps'])
      && ref(c.candidate_ref) && c.run_ref === runRef && (c.label === null || text(c.label)) && count(c.task_count)
      && ['completed', 'failed', 'skipped'].includes(c.persisted_status) && ['complete', 'partial', 'unknown', 'no_result'].includes(c.completeness)
      && c.status === (c.persisted_status === 'completed' && c.completeness === 'partial' ? 'partial' : c.persisted_status)
      && (c.persisted_status === 'completed' ? c.completeness !== 'no_result' : c.completeness === 'no_result' && c.task_count === 0)
      && shape(c.metrics, metricKeys) && metricKeys.every(k => metric(c.metrics[k]))
      && shape(c.metric_scopes, ['delivery', 'resources']) && c.metric_scopes.delivery === 'completed_batches_only' && c.metric_scopes.resources === 'scheduled_results_only'
      && capabilities(c.capabilities) && blocked(c.blocked_reasons) && gaps(c.data_gaps))
      && new Set(d.candidates.map(c => c.candidate_ref)).size === d.candidates.length);
    return d;
  }
  const messages = {
    run_schema_unavailable: '运行台账尚未安装完整（v26），暂时不能开始排产。',
    run_worker_not_connected: '本机排产执行器尚未接入或启用，暂时不能开始排产。',
    execution_ledger_unavailable: '执行台账尚未完整接入，暂时不能开始排产。',
    snapshot_stale: '检查后资料已变化或检查已过期，请重新做排产检查。', stale_write: '排产授权已过期或资料已变化，请重新核对。',
    constraint_conflict: '排产资料仍有阻断项，请重新检查并处理。', invalid_input: '排产参数不完整，请重新做排产检查。',
    entity_not_found: '暂未找到原运行记录，不能认定失败；请继续核实原请求。',
    run_result_inconsistent: '运行记录与保存结果不一致，请检查运行台账，暂勿重做。',
    storage_failure: '本机暂时无法核实排产记录，请保留原请求并稍后查询。', scheduling_busy: '已有排产正在计算，请稍后核实原记录。',
    candidate_artifact_invalid: '候选记录不完整或不一致，请检查运行台账，未显示替代结果。',
    candidate_capacity_exceeded: '候选结果超出本次读取容量，没有截断或冒充完整结果。',
    zero_duration_candidate_unsupported: '本次有零工时工序，候选计算尚不支持；请核对工时资料。',
    candidate_computation_failed: '本次候选计算失败，请查看运行日志并重新检查。', run_interrupted: '已核实本次运行中断，没有自动重跑。',
    request_lifecycle_stopping: '程序正在停止或维护，本次请求未受理。重新启动后请重新检查排产。'
  };
  function message(error) { return messages[error && error.code] || '排产结果暂时无法核实，请保留原请求并稍后查询。'; }
  function errorResponse(v, status, requestKey) {
    const e = v && v.error;
    const valid = shape(v, ['ok', 'committed', 'error']) && v.ok === false && [false, 'unknown'].includes(v.committed)
      && shape(e, ['code', 'message', 'fields', 'retryable', 'request_ref'], ['request_key', 'result_target']) && text(e.code) && text(e.message)
      && Array.isArray(e.fields) && e.fields.every(f => shape(f, ['path', 'message']) && text(f.path) && text(f.message))
      && typeof e.retryable === 'boolean' && /^[a-f0-9]{32}$/.test(e.request_ref)
      && (e.request_key === undefined && e.result_target === undefined || e.request_key === requestKey && key(requestKey) && e.result_target === BASE + '/requests/' + requestKey);
    const error = new Error(valid ? message(e) : '排产响应不完整，暂时不能确认结果。');
    error.code = valid ? e.code : 'invalid_response'; error.status = status;
    error.rejected = valid && v.committed === false && (([400, 409, 422].includes(status)
      && ['invalid_input', 'snapshot_stale', 'stale_write', 'constraint_conflict'].includes(e.code))
      || status === 503 && ['run_schema_unavailable', 'run_worker_not_connected', 'request_lifecycle_stopping'].includes(e.code));
    if (error.rejected) rejections.add(error);
    return error;
  }
  function validIntent(v) { return shape(v, ['input_ref', 'request_key', 'run_ref']) && token(v.input_ref) && key(v.request_key) && (v.run_ref === null || ref(v.run_ref)); }
  function pending(storage) {
    if (storage === undefined) {
      try { storage = window.localStorage; } catch (_) { throw new Error('本机无法读取排产恢复记录，请检查浏览器存储设置，暂勿重做。'); }
    }
    const same = (a, b) => validIntent(a) && validIntent(b) && a.input_ref === b.input_ref && a.request_key === b.request_key && a.run_ref === b.run_ref;
    function save(v) {
      try { storage.setItem(PENDING_KEY, JSON.stringify(v)); } catch (_) { throw new Error('本机无法保存原请求记录，请保留当前页面并检查浏览器存储。'); }
      check(same(read(), v), '原请求未能保存，本次不能开始排产。'); return v;
    }
    function read() {
      let raw; try { raw = storage.getItem(PENDING_KEY); } catch (_) { throw new Error('本机无法读取排产恢复记录，请检查浏览器存储设置，暂勿重做。'); }
      if (raw === null) return null;
      let value; try { value = JSON.parse(raw); } catch (_) { throw new Error('本机排产恢复记录损坏，已阻止新排产；请保留现场。'); }
      check(validIntent(value), '本机排产恢复记录不完整，已阻止新排产；请保留现场。'); return value;
    }
    return { read,
      begin(inputRef, previous = null) {
        check(token(inputRef), '排产检查已失效，请重新检查。'); const current = read();
        check(previous ? same(current, previous) : current === null, '已有原请求待核实，不能更换请求编号重做。');
        const bytes = new Uint8Array(24); window.crypto.getRandomValues(bytes);
        return save({ input_ref: inputRef, request_key: 'run-' + Array.from(bytes, n => n.toString(16).padStart(2, '0')).join(''), run_ref: null });
      },
      attach(intent, runRef) {
        const current = read();
        check(validIntent(intent) && validIntent(current) && ref(runRef) && current.request_key === intent.request_key && current.input_ref === intent.input_ref
          && (!intent.run_ref || intent.run_ref === runRef) && (!current.run_ref || current.run_ref === runRef), '原请求记录已变化，未覆盖其他运行。');
        if (current.run_ref === runRef) return current;
        return save({ input_ref: intent.input_ref, request_key: intent.request_key, run_ref: runRef });
      },
      reject(intent) {
        check(same(read(), intent), '原请求已变化，未删除其他记录。');
        try { storage.removeItem(PENDING_KEY); } catch (_) { throw new Error('本机无法更新原请求记录，请保留现场并检查浏览器存储。'); }
        check(read() === null, '原请求记录未能更新，请保留现场。');
      }
    };
  }
  function create(fetcher = window.fetch.bind(window)) {
    async function request(path, body, signal, requestKey) {
      const controller = new AbortController(), abort = () => controller.abort();
      if (signal) { if (signal.aborted) abort(); else signal.addEventListener('abort', abort, { once: true }); }
      const timer = setTimeout(abort, 30000);
      try {
        const response = await fetcher(BASE + path, { method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal,
          ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {}) });
        check((response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase() === 'application/json', '排产未返回有效数据，请核实原请求。');
        const payload = await response.json();
        if (!response.ok || payload.ok !== true) throw errorResponse(payload, response.status, requestKey);
        check(response.status === (path === '/runs' ? 202 : 200)); return payload;
      } finally { clearTimeout(timer); if (signal) signal.removeEventListener('abort', abort); }
    }
    return {
      async preview(inputRef, signal) { check(token(inputRef)); const v = await request('/runs/preview', { input_ref: inputRef }, signal); preview(v, inputRef); return v; },
      async accept(intent, writeToken) {
        check(validIntent(intent) && intent.run_ref === null && token(writeToken));
        return accepted(await request('/runs', { input_ref: intent.input_ref, write_token: writeToken, request_key: intent.request_key }, null, intent.request_key));
      },
      async get(runRef, signal) { check(ref(runRef)); const v = await request('/runs/' + runRef, null, signal); run(envelope(v), runRef); return v; },
      async lookup(requestKey, signal) { check(key(requestKey)); const v = await request('/requests/' + requestKey, null, signal, requestKey); lookup(v); return v; },
      async catalog(runRef, query, signal) {
        check(ref(runRef)); const scope = catalogScope(query);
        const v = await request('/runs/' + runRef + '/candidates?' + new URLSearchParams(scope), null, signal);
        catalog(v, runRef, query); return v;
      }
    };
  }
  window.RunJobAPI = { create, pending, PENDING_KEY, token, ref, validIntent, terminal, preview, run, accepted, lookup, catalog, envelope, message, isRejected: e => rejections.has(e),
    pollDelay: attempt => Math.min(30000, 2000 * Math.pow(2, Math.min(4, Math.max(0, attempt)))) };
})();
