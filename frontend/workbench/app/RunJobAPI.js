(function () {
  'use strict';
  const T = window.APSWorkbenchTransport, BASE = '/api/workbench/v1/scheduling', PENDING_KEY = 'aps_workbench_run_pending_v1', RECENT_KEY = 'aps_workbench_run_recent_v1';
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const text = v => typeof v === 'string', count = v => Number.isSafeInteger(v) && v >= 0;
  const ref = v => text(v) && /^[a-f0-9]{48}$/.test(v), token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v);
  const key = v => text(v) && /^run-[a-f0-9]{48}$/.test(v);
  // 数据上下文编号的格式只在 RunAdoptionAPI 定义一份；本文件先于它加载，所以在调用时再取。
  const contextRef = v => window.RunAdoptionAPI.contextRef(v);
  const terminal = run => !!run && ['complete', 'partial', 'failed', 'interrupted'].includes(run.state);
  function check(valid, message = '读到的排产数据不完整，请刷新重试。') { if (!valid) throw new Error(message); }
  function shape(v, required, optional = []) {
    return object(v) && required.every(k => Object.prototype.hasOwnProperty.call(v, k)) && Object.keys(v).every(k => required.includes(k) || optional.includes(k));
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
  // 不重排时段：不带这一项表示按交付设置，null 为本次不设，否则是精确到分的起止。
  const minute = v => text(v) && /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d$/.test(v) && date(v.slice(0, 10));
  const holdWindow = v => v === undefined || v === null || shape(v, ['start', 'end']) && minute(v.start) && minute(v.end) && v.start < v.end;
  function input(v) {
    check(shape(v, ['batch_refs', 'start_date', 'end_date', 'ready_check', 'missing_resource_policy', 'completed_policy'], ['material_strategy', 'hold_window', 'time_budget_seconds'])
      && (v.material_strategy === undefined || ['strict', 'stage'].includes(v.material_strategy)) && holdWindow(v.hold_window)
      && (v.time_budget_seconds === undefined || window.RunGenerationContract.budget(v.time_budget_seconds))
      && Array.isArray(v.batch_refs) && v.batch_refs.length <= 5000 && v.batch_refs.every(ref) && new Set(v.batch_refs).size === v.batch_refs.length
      && date(v.start_date) && date(v.end_date) && v.start_date <= v.end_date && typeof v.ready_check === 'boolean'
      && ['auto_assign', 'exclude'].includes(v.missing_resource_policy) && v.completed_policy === 'preserve_actuals');
    return v;
  }
  // 信封已由 transport 校验；这里只核对排产自己的提示形状，再取出数据。
  function content(v) { check(issues(v.warnings)); return v.data; }
  function previewResult(v, inputRef) {
    const d = content(v);
    check(shape(d, ['input_ref', 'normalized_input', 'write_context', 'calendar_check', 'warnings', 'data_context_ref', 'run_options']) && contextRef(d.data_context_ref) && token(inputRef) && d.input_ref === inputRef
      && d.calendar_check === 'not_evaluated' && issues(d.warnings));
    input(d.normalized_input);
    const c = d.write_context;
    check(d.run_options === null ? object(c) && c.capabilities && c.capabilities['scheduling.run'] === false
      && Array.isArray(c.blocked_reasons) && c.blocked_reasons.some(row => row.code === 'config_error')
      : window.RunGenerationContract.runOptions(d.run_options) && d.run_options.time_budget_seconds === d.normalized_input.time_budget_seconds);
    check(shape(c, ['write_token', 'expires_at', 'capabilities', 'blocked_reasons']) && shape(c.capabilities, ['scheduling.run']) && issues(c.blocked_reasons));
    check(c.capabilities['scheduling.run'] === true ? token(c.write_token) && time(c.expires_at) && c.blocked_reasons.length === 0 && d.normalized_input.batch_refs.length > 0
      : c.capabilities['scheduling.run'] === false && c.write_token === null && c.expires_at === null && c.blocked_reasons.length > 0);
    return d;
  }
  function run(v, expectedRef) {
    check(shape(v, ['run_ref', 'job_ref', 'state', 'stage', 'progress', 'plans', 'plan_catalog_connected', 'candidates', 'result_persisted',
      'accepted_at', 'started_at', 'finished_at', 'receipt_ref', 'error', 'recovery_required', 'scope_summary']) && ref(v.run_ref) && v.job_ref === v.run_ref
      && (!expectedRef || v.run_ref === expectedRef) && ['queued', 'running', 'complete', 'partial', 'failed', 'interrupted'].includes(v.state)
      && v.progress === null
      && Array.isArray(v.plans) && v.plans.length === 0 && v.plan_catalog_connected === false
      && Array.isArray(v.candidates) && time(v.accepted_at) && (v.started_at === null || time(v.started_at))
      && (v.finished_at === null || time(v.finished_at)) && (v.error === null || shape(v.error, ['code', 'message']) && text(v.error.code) && v.error.code.length > 0 && text(v.error.message)));
    // runScope 只接受统一搜索的运行选项：不报告进度，最多保存 3 份候选，且只保存算完的候选。
    runScope(v.scope_summary);
    const done = terminal(v), saved = ['complete', 'partial'].includes(v.state);
    check(v.result_persisted === saved && v.recovery_required === (v.stage === 'awaiting_reconciliation')
      && (done ? v.stage === 'finished' && ref(v.receipt_ref) && time(v.finished_at)
        : v.receipt_ref === null && v.finished_at === null && [v.state === 'queued' ? 'queued' : 'computing', 'awaiting_reconciliation'].includes(v.stage))
      && (v.state === 'queued' ? v.started_at === null : v.state === 'running' || saved ? time(v.started_at) : true)
      && (saved || !done ? v.error === null : v.error !== null)
      && v.candidates.length <= 3 && v.candidates.every(c => shape(c, ['candidate_ref', 'label', 'status', 'task_count', 'selected']) && ref(c.candidate_ref) && text(c.label)
        && c.status === 'completed' && count(c.task_count) && typeof c.selected === 'boolean')
      && new Set(v.candidates.map(c => c.candidate_ref)).size === v.candidates.length
      && (saved ? v.candidates.length > 0 && v.candidates.filter(c => c.selected).length === 1 : v.candidates.length === 0));
    return v;
  }
  function runScope(value) {
    const nullableText = item => item === null || text(item), nullableCount = item => item === null || count(item);
    check(shape(value, ['start_date', 'end_date', 'ready_check', 'missing_resource_policy', 'completed_policy', 'batch_count',
      'selection', 'basis', 'data_gaps', 'operation_count', 'batches', 'objective', 'objective_label', 'run_options'], ['material_strategy', 'hold_window'])
      && value.selection === 'explicit_batches' && value.basis === 'captured_at_run_admission'
      && ['start_date', 'end_date'].every(field => value[field] === null || date(value[field]))
      && (value.start_date === null || value.end_date === null || value.start_date <= value.end_date)
      && (value.ready_check === null || typeof value.ready_check === 'boolean')
      && [null, 'auto_assign', 'exclude'].includes(value.missing_resource_policy)
      && [null, 'preserve_actuals'].includes(value.completed_policy)
      && (value.material_strategy === undefined || [null, 'strict', 'stage'].includes(value.material_strategy))
      && holdWindow(value.hold_window) && nullableCount(value.batch_count) && nullableCount(value.operation_count)
      && window.RunGenerationContract.runOptions(value.run_options)
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
  function lookupResult(v, expectedRef) {
    const d = content(v);
    check(shape(d, ['found', 'run', 'data_context_ref', 'resolution']) && typeof d.found === 'boolean' && contextRef(d.data_context_ref)
      && ['found', 'context_replaced', 'unresolved'].includes(d.resolution) && d.found === (d.resolution === 'found'));
    if (d.found) run(d.run, expectedRef); else check(d.run === null);
    return d;
  }
  const gaps = v => Array.isArray(v) && v.every(g => shape(g, ['field', 'code', 'message']) && [g.field, g.code, g.message].every(text));
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
  function validIntent(v) { return shape(v, ['schema_version', 'input_ref', 'request_key', 'run_ref', 'data_context_ref']) && v.schema_version === 2 && contextRef(v.data_context_ref)
    && token(v.input_ref) && key(v.request_key) && (v.run_ref === null || ref(v.run_ref)); }
  function pending(storage) {
    const targetStorage = storage === undefined ? () => window.localStorage : () => storage;
    const same = (a, b) => !!a && !!b && a.input_ref === b.input_ref && a.request_key === b.request_key && a.run_ref === b.run_ref && a.data_context_ref === b.data_context_ref;
    const store = T.pendingStore({
      key: PENDING_KEY, storage: targetStorage, validate: validIntent, validateWrite: null, same,
      readError: '读不到上次排产的操作记录，请重新打开页面，不要重做。',
      corruptError: '本机存的排产操作记录已损坏，已拦下新排产。请不要再操作，联系维护人员。',
      invalidError: '本机存的排产操作记录不完整，已拦下新排产。请不要再操作，联系维护人员。',
      conflictError: '上次操作记录已变化，没有删除其他记录。',
      writeError: '存不下这次排产的操作记录，没有开始排产。请重新打开页面。',
      removeError: '本机无法更新上次操作记录。请不要再操作，联系维护人员。'
    });
    const recentStore = T.pendingStore({
      key: RECENT_KEY, storage: targetStorage,
      validate: value => shape(value, ['intent', 'resolution']) && validIntent(value.intent) && ['found', 'context_replaced'].includes(value.resolution),
      validateWrite: null,
      corruptError: '最近排产记录读不到，请到排产记录页查看。',
      invalidError: '最近排产记录不完整，请到排产记录页查看。'
    });
    const { read, write, save } = store;
    return { read, recent: recentStore.read,
      begin(inputRef, previous, dataContext) {
        check(token(inputRef), '排产检查已失效，请重新做排产检查。'); const current = read();
        check(previous === null || validIntent(previous));
        check(previous ? same(current, previous) : current === null, '上次排产还没确认结果，不能重做。请先点「查询结果」。');
        check(contextRef(dataContext));
        return write({ schema_version: 2, input_ref: inputRef, request_key: T.requestKey('run'), run_ref: null, data_context_ref: dataContext });
      },
      attach(intent, runRef) {
        const current = read();
        check(validIntent(intent) && current !== null && ref(runRef) && current.request_key === intent.request_key && current.input_ref === intent.input_ref
          && (!intent.run_ref || intent.run_ref === runRef) && (!current.run_ref || current.run_ref === runRef), '上次操作记录已变化，没有覆盖其他排产记录。');
        if (current.run_ref === runRef) return current;
        return write({ ...intent, run_ref: runRef });
      },
      finish(intent, resolution) {
        const current = read();
        check(['found', 'context_replaced'].includes(resolution) && validIntent(intent));
        // A completed lookup in an older tab must never erase a newer submission.
        if (current === null) return;
        check(same(current, intent), '上次操作记录已变化，没有删除其他记录。');
        recentStore.write({ intent, resolution });
        targetStorage().removeItem(PENDING_KEY);
      },
      reject(intent) {
        check(validIntent(intent));
        save(null, intent);
      }
    };
  }
  // 排产检查核对、受理回执和读取都按 30 秒等待；受理失败的结果编号指向排产请求查询。
  async function preview(inputRef, signal) {
    check(token(inputRef));
    return previewResult(await T.preview(BASE + '/runs/preview', { input_ref: inputRef }, { signal, timeout: 30000 }), inputRef);
  }
  async function accept(intent, writeToken) {
    check(validIntent(intent) && intent.run_ref === null && token(writeToken));
    return accepted(await T.command(BASE + '/runs', { input_ref: intent.input_ref, write_token: writeToken, request_key: intent.request_key },
      { timeout: 30000, expect: BASE + '/requests/' + intent.request_key }));
  }
  async function get(runRef, signal) { check(ref(runRef)); return run(content(await T.read(BASE + '/runs/' + runRef, {}, { signal, timeout: 30000 })), runRef); }
  async function lookup(intent, signal) {
    check(validIntent(intent));
    return lookupResult(await T.read(BASE + '/requests/' + intent.request_key, { data_context_ref: intent.data_context_ref }, { signal, timeout: 30000 }), intent.run_ref);
  }
  window.RunJobAPI = { preview, accept, get, lookup, pending, PENDING_KEY, RECENT_KEY, token, ref, validIntent, terminal, run, accepted, message, failure, previewMessage, details,
    pollDelay: attempt => Math.min(30000, 2000 * Math.pow(2, Math.min(4, Math.max(0, attempt)))) };
})();
