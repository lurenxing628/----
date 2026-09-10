(function () {
  'use strict';

  const states = ['queued', 'running', 'complete', 'partial', 'failed', 'interrupted'];
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const text = v => typeof v === 'string',
    count = v => Number.isSafeInteger(v) && v >= 0;
  const ref = v => text(v) && /^[a-f0-9]{48}$/.test(v),
    token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v);
  const own = (v, k) => Object.prototype.hasOwnProperty.call(v, k);
  const shape = (v, required, optional = []) => object(v) && required.every(k => own(v, k)) && Object.keys(v).every(k => required.concat(optional).includes(k));
  function check(value, message = '排产历史数据不完整或不一致，未显示替代结果。') {
    if (!value) {
      const error = new Error(message);
      error.code = 'invalid_response';
      throw error;
    }
  }
  function date(v) {
    if (!text(v) || !/^(?!0000)\d{4}-\d{2}-\d{2}$/.test(v)) return false;
    const n = Date.parse(v + 'T00:00:00Z');
    return Number.isFinite(n) && new Date(n).toISOString().slice(0, 10) === v;
  }
  function time(v) {
    return text(v) && date(v.slice(0, 10)) && /^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?$/.test(v);
  }
  const timeKey = v => v.slice(0, 19) + '.' + (v.split('.')[1] || '').padEnd(6, '0');
  const gap = v => shape(v, ['field', 'code', 'message']) && [v.field, v.code, v.message].every(text);
  const queryKeys = ['page', 'size', 'state', 'accepted_from', 'accepted_to', 'sort', 'order', 'snapshot_ref'];
  function scope(query = {}) {
    check(shape(query, [], queryKeys), '历史查询含未知条件，未忽略条件。');
    const q = {
      page: 1,
      size: 20,
      state: 'all',
      sort: 'accepted_at',
      order: 'desc',
      ...query
    };
    check(count(q.page) && q.page >= 1 && q.page <= 1000000 && count(q.size) && q.size >= 1 && q.size <= 50 && ['all', ...states].includes(q.state) && ['accepted_at', 'started_at', 'finished_at'].includes(q.sort) && ['asc', 'desc'].includes(q.order) && (q.snapshot_ref === undefined || token(q.snapshot_ref)), '历史筛选、排序或分页条件无效。');
    if (q.accepted_from !== undefined || q.accepted_to !== undefined) check(date(q.accepted_from) && date(q.accepted_to) && q.accepted_from <= q.accepted_to, '受理日期须成对填写，起日不得晚于止日。');
    Object.keys(q).forEach(k => {
      if (q[k] === undefined) delete q[k];
    });
    return q;
  }
  function planContext(value) {
    check(value === undefined || object(value), '返回方案的上下文无效。');
    const result = {};
    for (const key of ['plan_ref', 'batch_ref']) if (value && own(value, key)) {
      check(ref(value[key]), '返回方案的永久引用无效。');
      result[key] = value[key];
    }
    for (const key of ['range_start', 'range_end']) if (value && own(value, key)) {
      check(time(value[key]));
      result[key] = value[key];
    }
    return result;
  }
  function context(value = {}) {
    check(shape(value, [], queryKeys.concat(['source', 'return_plan_context'])) && (value.source === undefined || value.source === 'production'), '排产历史来源或返回范围无效，未切换来源。');
    const q = {};
    queryKeys.forEach(k => {
      if (own(value, k)) q[k] = value[k];
    });
    return {
      query: scope(q),
      returnPlan: planContext(value.return_plan_context)
    };
  }
  function returnContext(query, returnPlan) {
    const result = scope(query);
    delete result.snapshot_ref;
    if (Object.keys(returnPlan).length) result.return_plan_context = returnPlan;
    return result;
  }
  function admission(s) {
    const keys = ['start_date', 'end_date', 'ready_check', 'missing_resource_policy', 'completed_policy', 'batch_count'];
    check(shape(s, keys.concat(['selection', 'basis', 'data_gaps'])) && s.selection === 'explicit_batches' && s.basis === 'captured_at_run_admission' && Array.isArray(s.data_gaps) && s.data_gaps.every(gap) && s.data_gaps.every(g => keys.includes(g.field) && ['not_recorded', 'invalid_stored_value'].includes(g.code)));
    check(['start_date', 'end_date'].every(k => s[k] === null || date(s[k])) && (s.start_date === null || s.end_date === null || s.start_date <= s.end_date) && (s.ready_check === null || typeof s.ready_check === 'boolean') && [null, 'auto_assign', 'exclude'].includes(s.missing_resource_policy) && [null, 'preserve_actuals'].includes(s.completed_policy) && (s.batch_count === null || count(s.batch_count) && s.batch_count > 0));
    check(keys.every(k => s.data_gaps.filter(g => g.field === k).length === (s[k] === null ? 1 : 0)));
  }
  function run(v) {
    check(shape(v, ['run_ref', 'state', 'stage', 'accepted_at', 'started_at', 'finished_at', 'candidate_count', 'task_count', 'task_count_basis', 'counts_final', 'scope_summary', 'recovery_required', 'recovery_reason', 'completion_semantics', 'constraint_verification', 'task_content_verification']) && ref(v.run_ref) && states.includes(v.state) && time(v.accepted_at) && ['started_at', 'finished_at'].every(k => v[k] === null || time(v[k])) && count(v.candidate_count) && count(v.task_count) && v.task_count_basis === 'persisted_rows_across_candidates' && v.completion_semantics === 'execution_state_only' && v.constraint_verification === 'not_checked_by_history' && v.task_content_verification === 'candidate_workspace_required');
    const terminal = !['queued', 'running'].includes(v.state),
      succeeded = ['complete', 'partial'].includes(v.state);
    check(v.counts_final === terminal && v.finished_at !== null === terminal && (terminal ? v.stage === 'finished' : [v.state === 'queued' ? 'queued' : 'computing', 'awaiting_reconciliation'].includes(v.stage)) && (v.state !== 'queued' || v.started_at === null) && (v.state !== 'running' || v.started_at !== null) && (v.started_at === null || timeKey(v.started_at) >= timeKey(v.accepted_at)) && (v.finished_at === null || timeKey(v.finished_at) >= timeKey(v.started_at || v.accepted_at)) && (succeeded ? v.candidate_count > 0 : v.candidate_count === 0 && v.task_count === 0) && v.recovery_required === (v.stage === 'awaiting_reconciliation'));
    check(v.recovery_required ? shape(v.recovery_reason, ['code', 'message']) && v.recovery_reason.code === 'awaiting_reconciliation' && text(v.recovery_reason.message) : v.recovery_reason === null);
    admission(v.scope_summary);
    return v;
  }
  function compare(a, b, q) {
    const left = a[q.sort],
      right = b[q.sort],
      direction = q.order === 'asc' ? 1 : -1;
    if (left === null && right !== null) return 1;
    if (right === null && left !== null) return -1;
    const x = left === null ? '' : timeKey(left),
      y = right === null ? '' : timeKey(right);
    return direction * (x < y ? -1 : x > y ? 1 : a.run_ref < b.run_ref ? -1 : a.run_ref > b.run_ref ? 1 : 0);
  }
  function catalog(v, query = {}) {
    const q = scope(query);
    check(shape(v, ['ok', 'schema_version', 'data', 'meta', 'warnings']) && v.ok === true && v.schema_version === 1 && shape(v.meta, ['request_ref', 'source', 'time_basis', 'snapshot_ref', 'as_of']) && /^[a-f0-9]{32}$/.test(v.meta.request_ref) && v.meta.source === 'production' && v.meta.time_basis === 'factory_local' && token(v.meta.snapshot_ref) && time(v.meta.as_of) && Array.isArray(v.warnings) && v.warnings.every(w => object(w) && text(w.code) && text(w.message)));
    if (q.snapshot_ref && q.snapshot_ref !== v.meta.snapshot_ref) {
      const error = new Error('历史来源快照已变化，请明确重读；未混用分页结果。');
      error.code = 'snapshot_stale';
      throw error;
    }
    const d = v.data;
    check(shape(d, ['runs', 'page', 'run_count', 'state', 'sort', 'order', 'nulls', 'tie_breaker', 'time_scope']) && d.state === q.state && d.sort === q.sort && d.order === q.order && d.nulls === 'last' && d.tie_breaker === 'run_ref_same_order' && count(d.run_count) && d.run_count <= 100000 && shape(d.page, ['number', 'size', 'total', 'has_more']) && d.page.number === q.page && d.page.size === q.size && count(d.page.total) && d.page.total <= d.run_count && (q.state !== 'all' || q.accepted_from || d.page.total === d.run_count) && d.page.has_more === q.page * q.size < d.page.total && Array.isArray(d.runs) && d.runs.length === Math.min(q.size, Math.max(0, d.page.total - (q.page - 1) * q.size)) && shape(d.time_scope, ['accepted_from', 'accepted_to', 'field', 'boundary', 'time_basis']) && d.time_scope.accepted_from === (q.accepted_from || null) && d.time_scope.accepted_to === (q.accepted_to || null) && d.time_scope.field === 'accepted_at' && d.time_scope.boundary === 'inclusive_dates' && d.time_scope.time_basis === 'factory_local');
    d.runs.forEach((r, i) => {
      run(r);
      check((q.state === 'all' || r.state === q.state) && (!q.accepted_from || r.accepted_at.slice(0, 10) >= q.accepted_from && r.accepted_at.slice(0, 10) <= q.accepted_to) && (!i || compare(d.runs[i - 1], r, q) <= 0));
    });
    check(new Set(d.runs.map(r => r.run_ref)).size === d.runs.length);
    return d;
  }
  function create(fetcher = window.fetch.bind(window)) {
    return {
      async catalog(query = {}, signal) {
        const q = scope(query),
          controller = new AbortController(),
          abort = () => controller.abort();
        if (signal) {
          if (signal.aborted) abort();else signal.addEventListener('abort', abort, {
            once: true
          });
        }
        const timer = setTimeout(abort, 60000);
        try {
          const response = await fetcher('/api/workbench/v1/scheduling/runs?' + new URLSearchParams(q), {
            method: 'GET',
            credentials: 'same-origin',
            cache: 'no-store',
            redirect: 'error',
            signal: controller.signal
          });
          const json = (response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase() === 'application/json';
          if (!response.ok) {
            const value = json ? await response.json() : null,
              e = value && value.error;
            const error = new Error(e && text(e.message) ? e.message : '排产历史读取失败，未显示替代结果。');
            error.code = e && text(e.code) ? e.code : 'invalid_response';
            error.status = response.status;
            throw error;
          }
          check(response.status === 200 && json);
          const value = await response.json();
          catalog(value, q);
          return value;
        } catch (error) {
          if (controller.signal.aborted && !(signal && signal.aborted)) {
            const timeout = new Error('排产历史读取超时，请重试。');
            timeout.code = 'timeout';
            throw timeout;
          }
          throw error;
        } finally {
          clearTimeout(timer);
          if (signal) signal.removeEventListener('abort', abort);
        }
      }
    };
  }
  window.RunHistoryAPI = {
    create,
    check,
    scope,
    context,
    returnContext,
    catalog,
    ref,
    date,
    time,
    states
  };
})();
