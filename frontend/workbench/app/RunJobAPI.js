(function () {
  'use strict';
  const BASE = '/api/workbench/v1/scheduling', PENDING_KEY = 'aps_workbench_run_pending_v1', RECENT_KEY = 'aps_workbench_run_recent_v1';
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const text = v => typeof v === 'string', count = v => Number.isSafeInteger(v) && v >= 0;
  const ref = v => text(v) && /^[a-f0-9]{48}$/.test(v), token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v);
  const key = v => text(v) && /^run-[a-f0-9]{48}$/.test(v);
  function contextRef(v) {
    if (!text(v)) return false;
    if (/^[a-f0-9]{64}$/.test(v)) return true;
    try {
      const data = JSON.parse(v), refs = data && data.successful_restores;
      return shape(data, ['database_scope', 'successful_restores']) && text(data.database_scope) && data.database_scope.length > 0
        && Array.isArray(refs) && refs.every(item => text(item) && /^[a-f0-9]{32}$/.test(item))
        && refs.every((item, index) => index === 0 || refs[index - 1] < item);
    } catch (_) { return false; }
  }
  const rejections = new WeakSet();
  const terminal = run => !!run && ['complete', 'partial', 'failed', 'interrupted'].includes(run.state);
  function check(valid, message = '读到的排产数据不完整，请刷新重试。') { if (!valid) throw new Error(message); }
  function shape(v, required, optional = []) {
    return object(v) && required.every(k => Object.prototype.hasOwnProperty.call(v, k)) && Object.keys(v).every(k => required.concat(optional).includes(k));
  }
  function date(v) {
    if (!text(v) || !/^\d{4}-\d{2}-\d{2}$/.test(v) || v < '1900-01-01' || v >= '9999-12-31') return false;
    const [y, m, d] = v.split('-').map(Number), value = new Date(y, m - 1, d);
    return value.getFullYear() === y && value.getMonth() === m - 1 && value.getDate() === d;
  }
  const time = v => text(v) && /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?$/.test(v) && date(v.slice(0, 10));
  const issue = v => shape(v, ['code', 'message'], ['operation_ref', 'batch_ref', 'batch_id']) && text(v.code) && v.code.length > 0 && text(v.message)
    && ['operation_ref', 'batch_ref'].every(k => v[k] === undefined || ref(v[k])) && (v.batch_id === undefined || text(v.batch_id));
  const issues = v => Array.isArray(v) && v.every(issue);
  // Progress is the worker's count of finished candidate plans; it only exists while the run is computing.
  const progress = v => shape(v, ['done', 'total', 'updated_at']) && count(v.done) && count(v.total) && v.done <= v.total && time(v.updated_at);
  // 不重排时段：旧调用不带这一项（按交付设置），null 为本次不设，否则是精确到分的起止。
  const minute = v => text(v) && /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d$/.test(v) && date(v.slice(0, 10));
  const holdWindow = v => v === undefined || v === null || shape(v, ['start', 'end']) && minute(v.start) && minute(v.end) && v.start < v.end;
  function input(v) {
    check(shape(v, ['batch_refs', 'start_date', 'end_date', 'ready_check', 'missing_resource_policy', 'completed_policy'], ['material_strategy', 'hold_window', 'time_budget_seconds'])
      && (v.material_strategy === undefined || ['strict', 'stage', 'split'].includes(v.material_strategy)) && holdWindow(v.hold_window)
      && (v.time_budget_seconds === undefined || window.RunGenerationContract.budget(v.time_budget_seconds))
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
    check(shape(d, ['input_ref', 'normalized_input', 'write_context', 'calendar_check', 'warnings', 'data_context_ref'], ['run_options']) && contextRef(d.data_context_ref) && token(inputRef) && d.input_ref === inputRef
      && d.calendar_check === 'not_evaluated' && issues(d.warnings));
    input(d.normalized_input);
    const c = d.write_context;
    check(d.run_options === undefined || (d.run_options === null ? object(c) && c.capabilities && c.capabilities['scheduling.run'] === false
      && Array.isArray(c.blocked_reasons) && c.blocked_reasons.some(row => row.code === 'config_error')
      : window.RunGenerationContract.runOptions(d.run_options) && d.run_options.time_budget_seconds === d.normalized_input.time_budget_seconds));
    check(shape(c, ['write_token', 'expires_at', 'capabilities', 'blocked_reasons']) && shape(c.capabilities, ['scheduling.run']) && issues(c.blocked_reasons));
    check(c.capabilities['scheduling.run'] === true ? token(c.write_token) && time(c.expires_at) && c.blocked_reasons.length === 0 && d.normalized_input.batch_refs.length > 0
      : c.capabilities['scheduling.run'] === false && c.write_token === null && c.expires_at === null && c.blocked_reasons.length > 0);
    check(c.capabilities['scheduling.run'] !== true || d.normalized_input.time_budget_seconds === undefined || d.run_options !== undefined);
    return d;
  }
  function run(v, expectedRef) {
    check(shape(v, ['run_ref', 'job_ref', 'state', 'stage', 'progress', 'plans', 'plan_catalog_connected', 'candidates', 'result_persisted',
      'accepted_at', 'started_at', 'finished_at', 'receipt_ref', 'error', 'recovery_required', 'scope_summary']) && ref(v.run_ref) && v.job_ref === v.run_ref
      && (!expectedRef || v.run_ref === expectedRef) && ['queued', 'running', 'complete', 'partial', 'failed', 'interrupted'].includes(v.state)
      && (v.progress === null || v.state === 'running' && v.stage === 'computing' && progress(v.progress))
      && Array.isArray(v.plans) && v.plans.length === 0 && v.plan_catalog_connected === false
      && Array.isArray(v.candidates) && time(v.accepted_at) && (v.started_at === null || time(v.started_at))
      && (v.finished_at === null || time(v.finished_at)) && (v.error === null || shape(v.error, ['code', 'message']) && issue(v.error)));
    runScope(v.scope_summary);
    const unified = v.scope_summary.run_options && v.scope_summary.run_options.generation_policy_version === 'unified_search_v1';
    check(!unified || v.progress === null && v.candidates.length <= 3 && v.candidates.every(candidate => candidate.status === 'completed'));
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
  function runScope(value) {
    const nullableText = item => item === null || text(item), nullableCount = item => item === null || count(item);
    check(shape(value, ['start_date', 'end_date', 'ready_check', 'missing_resource_policy', 'completed_policy', 'batch_count',
      'selection', 'basis', 'data_gaps', 'operation_count', 'batches', 'objective', 'objective_label'], ['material_strategy', 'hold_window', 'run_options'])
      && value.selection === 'explicit_batches' && value.basis === 'captured_at_run_admission'
      && ['start_date', 'end_date'].every(field => value[field] === null || date(value[field]))
      && (value.start_date === null || value.end_date === null || value.start_date <= value.end_date)
      && (value.ready_check === null || typeof value.ready_check === 'boolean')
      && [null, 'auto_assign', 'exclude'].includes(value.missing_resource_policy)
      && [null, 'preserve_actuals'].includes(value.completed_policy)
      && (value.material_strategy === undefined || [null, 'strict', 'stage', 'split'].includes(value.material_strategy))
      && holdWindow(value.hold_window) && nullableCount(value.batch_count) && nullableCount(value.operation_count)
      && (value.run_options === undefined || window.RunGenerationContract.runOptions(value.run_options))
      && nullableText(value.objective) && nullableText(value.objective_label) && gaps(value.data_gaps)
      && Array.isArray(value.batches) && value.batches.every(row => shape(row, ['batch_ref', 'batch_id', 'part_no', 'part_label'])
        && ref(row.batch_ref) && ['batch_id', 'part_no', 'part_label'].every(field => nullableText(row[field]))));
    return value;
  }
  function accepted(v) {
    check(shape(v, ['ok', 'result', 'job_ref', 'run_ref', 'status_target', 'receipt_ref', 'replayed', 'data', 'data_context_ref'], ['dispatch_pending']) && contextRef(v.data_context_ref)
      && v.ok === true && v.result === 'accepted' && ref(v.run_ref) && v.job_ref === v.run_ref && text(v.receipt_ref) && /^[a-f0-9]{32}$/.test(v.receipt_ref)
      && v.status_target === BASE + '/runs/' + v.run_ref && typeof v.replayed === 'boolean' && (v.dispatch_pending === undefined || v.dispatch_pending === true));
    run(v.data, v.run_ref); return v;
  }
  function lookup(v, expectedRef) {
    const d = envelope(v);
    check(shape(d, ['found', 'run', 'data_context_ref', 'resolution']) && typeof d.found === 'boolean' && contextRef(d.data_context_ref)
      && ['found', 'context_replaced', 'unresolved'].includes(d.resolution) && d.found === (d.resolution === 'found'));
    if (d.found) run(d.run, expectedRef); else check(d.run === null);
    return d;
  }
  const gaps = v => Array.isArray(v) && v.every(g => shape(g, ['field', 'code', 'message']) && [g.field, g.code, g.message].every(text));
  const capabilities = v => shape(v, ['view', 'export', 'edit_draft', 'adopt', 'report_actual']) && v.view === true && v.export === true
    && v.edit_draft === false && v.adopt === false && v.report_actual === false;
  const blocked = v => Array.isArray(v) && v.every(r => shape(r, ['capability', 'code', 'message'])
    && ['adopt', 'edit_draft', 'report_actual', 'preview'].includes(r.capability) && text(r.code) && text(r.message))
    && ['adopt', 'edit_draft', 'report_actual'].every(c => v.some(r => r.capability === c));
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
    d.candidates.forEach(candidate => window.RunCandidateAPI.summary(candidate, runRef));
    check(d.candidates.every(candidate => capabilities(candidate.capabilities) && blocked(candidate.blocked_reasons))
      && new Set(d.candidates.map(c => c.candidate_ref)).size === d.candidates.length);
    return d;
  }
  const OUTCOMES = window.WorkbenchTerms.outcomes;
  const messages = {
    input_already_used: '这份检查结果已经开始过排产，请重新检查后再开始下一次。',
    run_schema_unavailable: '排产记录还没准备好，暂时不能开始排产。请联系维护人员升级数据库。',
    run_worker_not_connected: '排产计算程序没有启动，暂时不能开始排产。请联系维护人员。',
    execution_ledger_unavailable: '报工记录还没准备好，请联系维护人员升级数据库。',
    snapshot_stale: '资料已更新或排产检查已过期，请重新做排产检查。刚才的选择已保留。',
    stale_write: '本页数据已过期，请重新做排产检查。',
    constraint_conflict: '排产检查发现缺资料，请补齐后再开始排产。', invalid_input: '排产条件不完整，请重新做排产检查。',
    no_eligible_tasks: '当前范围没有可排工序。请调整批次、齐套条件或补齐工序资料后重新检查。',
    entity_not_found: '暂未查到这次排产记录，请点「查询结果」再次核对。',
    run_result_inconsistent: '这次排产的记录和保存结果不一致。请不要重做，联系维护人员。',
    storage_failure: OUTCOMES.pending('排产'), scheduling_busy: '已有排产正在计算，请稍后再点「查询结果」。',
    candidate_artifact_invalid: '候选方案记录不完整，请联系维护人员。',
    candidate_capacity_exceeded: '候选方案数量超过读取上限。',
    zero_duration_candidate_unsupported: '本次有零工时工序，候选计算还不支持。请核对工时资料。',
    candidate_computation_failed: '本次候选计算失败。请联系维护人员，再重新做排产检查。',
    run_interrupted: '这次排产已中断，没有自动重跑。',
    request_lifecycle_stopping: '程序正在停止或维护，这次排产没有开始。重新启动后请重新做排产检查。'
  };
  // Internal version numbers belong in the collapsed reference block, never in the sentence users read.
  const messageDetails = { run_schema_unavailable: { '需要的数据库版本': 'v26' } };
  function message(error) { return messages[error && error.code] || OUTCOMES.unknown('排产'); }
  // 已结束的排产失败是确定结果：不认识的失败原因照后端原话显示，不能说成“可能已经生效”。
  function failure(error) {
    return (error && text(error.message) && error.message) || messages[error && error.code] || messages.candidate_computation_failed;
  }
  function previewMessage(error) {
    return error && messages[error.code] && !['storage_failure', 'entity_not_found', 'run_result_inconsistent'].includes(error.code)
      ? messages[error.code] : '排产条件没有读出来，请重新检查。';
  }
  function details(error) { return messageDetails[error && error.code] || null; }
  function errorResponse(v, status, requestKey) {
    const e = v && v.error;
    const valid = shape(v, ['ok', 'committed', 'error']) && v.ok === false && [false, 'unknown'].includes(v.committed)
      && shape(e, ['code', 'message', 'fields', 'retryable', 'request_ref'], ['request_key', 'result_target']) && text(e.code) && text(e.message)
      && Array.isArray(e.fields) && e.fields.every(f => shape(f, ['path', 'message']) && text(f.path) && text(f.message))
      && typeof e.retryable === 'boolean' && /^[a-f0-9]{32}$/.test(e.request_ref)
      && (e.request_key === undefined && e.result_target === undefined || e.request_key === requestKey && key(requestKey) && e.result_target === BASE + '/requests/' + requestKey);
    const error = new Error(valid ? message(e) : '读到的排产数据不完整，请刷新重试。');
    error.code = valid ? e.code : 'invalid_response'; error.status = status;
    error.rejected = valid && v.committed === false && (([400, 409, 422].includes(status)
      && ['invalid_input', 'snapshot_stale', 'stale_write', 'constraint_conflict', 'input_already_used'].includes(e.code))
      || status === 503 && ['run_schema_unavailable', 'run_worker_not_connected', 'request_lifecycle_stopping'].includes(e.code));
    if (error.rejected) rejections.add(error);
    return error;
  }
  function validIntent(v) { return (shape(v, ['input_ref', 'request_key', 'run_ref']) || shape(v, ['schema_version', 'input_ref', 'request_key', 'run_ref', 'data_context_ref']) && v.schema_version === 2 && contextRef(v.data_context_ref))
    && token(v.input_ref) && key(v.request_key) && (v.run_ref === null || ref(v.run_ref)); }
  function pending(storage) {
    if (storage === undefined) {
      try { storage = window.localStorage; } catch (_) { throw new Error('读不到上次排产的操作记录，请重新打开页面，不要重做。'); }
    }
    const same = (a, b) => !!a && !!b && a.input_ref === b.input_ref && a.request_key === b.request_key && a.run_ref === b.run_ref && a.data_context_ref === b.data_context_ref;
    function save(v) {
      try { storage.setItem(PENDING_KEY, JSON.stringify(v)); } catch (_) { throw new Error('存不下这次排产的操作记录，没有开始排产。请重新打开页面。'); }
      return v;
    }
    function read() {
      let raw; try { raw = storage.getItem(PENDING_KEY); } catch (_) { throw new Error('读不到上次排产的操作记录，请重新打开页面，不要重做。'); }
      if (raw === null) return null;
      let value; try { value = JSON.parse(raw); } catch (_) { throw new Error('本机存的排产操作记录已损坏，已拦下新排产。请不要再操作，联系维护人员。'); }
      check(validIntent(value), '本机存的排产操作记录不完整，已拦下新排产。请不要再操作，联系维护人员。'); return value;
    }
    function recent() {
      const raw = storage.getItem(RECENT_KEY);
      if (raw === null) return null;
      let value; try { value = JSON.parse(raw); } catch (_) { throw new Error('最近排产记录读不到，请到排产记录页查看。'); }
      check(shape(value, ['intent', 'resolution']) && validIntent(value.intent) && ['found', 'context_replaced'].includes(value.resolution), '最近排产记录不完整，请到排产记录页查看。');
      return value;
    }
    return { read, recent,
      begin(inputRef, previous = null, dataContext = null) {
        check(token(inputRef), '排产检查已失效，请重新做排产检查。'); const current = read();
        check(previous === null || validIntent(previous));
        check(previous ? same(current, previous) : current === null, '上次排产还没确认结果，不能重做。请先点「查询结果」。');
        const bytes = new Uint8Array(24); window.crypto.getRandomValues(bytes);
        check(dataContext === null || contextRef(dataContext));
        return save({ input_ref: inputRef, request_key: 'run-' + Array.from(bytes, n => n.toString(16).padStart(2, '0')).join(''), run_ref: null,
          ...(dataContext === null ? {} : { schema_version: 2, data_context_ref: dataContext }) });
      },
      attach(intent, runRef) {
        const current = read();
        check(validIntent(intent) && current !== null && ref(runRef) && current.request_key === intent.request_key && current.input_ref === intent.input_ref
          && (!intent.run_ref || intent.run_ref === runRef) && (!current.run_ref || current.run_ref === runRef), '上次操作记录已变化，没有覆盖其他排产记录。');
        if (current.run_ref === runRef) return current;
        return save({ ...intent, run_ref: runRef });
      },
      finish(intent, resolution) {
        const current = read();
        check(['found', 'context_replaced'].includes(resolution) && validIntent(intent));
        // A completed lookup in an older tab must never erase a newer submission.
        if (current === null) return;
        check(same(current, intent), '上次操作记录已变化，没有删除其他记录。');
        storage.setItem(RECENT_KEY, JSON.stringify({ intent, resolution }));
        storage.removeItem(PENDING_KEY);
      },
      reject(intent) {
        check(validIntent(intent));
        check(same(read(), intent), '上次操作记录已变化，没有删除其他记录。');
        try { storage.removeItem(PENDING_KEY); } catch (_) { throw new Error('本机无法更新上次操作记录。请不要再操作，联系维护人员。'); }
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
        check((response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase() === 'application/json', '没有读到有效的排产数据，请重试。');
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
      async lookup(requestKey, signal, dataContext) { check(key(requestKey) && (dataContext === undefined || contextRef(dataContext)));
        const v = await request('/requests/' + requestKey + (dataContext ? '?data_context_ref=' + encodeURIComponent(dataContext) : ''), null, signal, requestKey); lookup(v); return v; },
      async catalog(runRef, query, signal) {
        check(ref(runRef)); const scope = catalogScope(query);
        const v = await request('/runs/' + runRef + '/candidates?' + new URLSearchParams(scope), null, signal);
        catalog(v, runRef, query); return v;
      }
    };
  }
  window.RunJobAPI = { create, pending, PENDING_KEY, RECENT_KEY, token, ref, validIntent, terminal, preview, run, accepted, lookup, catalog, envelope, message, failure, previewMessage, details, isRejected: e => rejections.has(e),
    pollDelay: attempt => Math.min(30000, 2000 * Math.pow(2, Math.min(4, Math.max(0, attempt)))) };
})();
