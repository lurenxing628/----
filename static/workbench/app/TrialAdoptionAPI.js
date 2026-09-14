(function () {
  'use strict';

  const BASE = '/api/workbench/v1/trial/scenarios/',
    ACTION = 'trial.scenario.adopt',
    rejections = new WeakSet();
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v),
    text = v => typeof v === 'string';
  const ref = v => text(v) && /^[a-f0-9]{48}$/.test(v),
    key = v => text(v) && /^trial-adoption-[a-f0-9]{48}$/.test(v);
  const token = v => text(v) && /^[A-Za-z0-9_-]{32}$/.test(v),
    positive = v => Number.isSafeInteger(v) && v > 0;
  function check(v, message = '读到的采用数据不完整或对不上，这次没有确认采用。请刷新重试。') {
    if (!v) throw new Error(message);
  }
  function shape(v, required, optional = []) {
    return object(v) && required.every(k => Object.prototype.hasOwnProperty.call(v, k)) && Object.keys(v).every(k => required.concat(optional).includes(k));
  }
  function equal(a, b) {
    const canonical = v => JSON.stringify(v, (_, x) => object(x) ? Object.keys(x).sort().reduce((o, k) => {
      o[k] = x[k];
      return o;
    }, {}) : x);
    return canonical(a) === canonical(b);
  }
  function time(v) {
    if (!text(v) || !/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$/.test(v)) return false;
    const d = new Date(v + 'Z');
    return Number.isFinite(d.getTime()) && d.toISOString().slice(0, 19) === v;
  }
  const issues = v => Array.isArray(v) && v.every(r => shape(r, ['code', 'message', 'severity'], ['task_ref', 'related_task_ref']) && text(r.code) && r.code && text(r.message) && r.message && r.severity === 'blocker' && ['task_ref', 'related_task_ref'].every(k => r[k] === undefined || r[k] === null || ref(r[k])));
  function overview(v) {
    check(object(v) && ref(v.scenario_ref) && ref(v.draft_ref) && v.scenario_ref !== v.draft_ref && positive(v.task_count) && v.scope_complete === true && shape(v.baseline, ['plan_ref', 'version']) && (v.baseline.plan_ref === null ? v.baseline.version === null : ref(v.baseline.plan_ref) && positive(v.baseline.version)));
    return {
      scenario_ref: v.scenario_ref,
      draft_ref: v.draft_ref,
      baseline: {
        ...v.baseline
      },
      task_count: v.task_count,
      scope_complete: true
    };
  }
  function source(scenarioRef, data) {
    check(ref(scenarioRef) && object(data) && data.scenario_ref === scenarioRef && data.status === 'saved' && data.tasks_complete === true && Array.isArray(data.tasks) && data.tasks.length === data.task_count, '请先完整读取所选的试调方案；不能采用其他记录或不完整的内容。');
    return overview({
      ...data,
      scope_complete: true
    });
  }
  function envelope(v) {
    check(shape(v, ['ok', 'schema_version', 'data', 'meta', 'warnings']) && v.ok === true && v.schema_version === 1 && Array.isArray(v.warnings) && !v.warnings.length && shape(v.meta, ['request_ref', 'source', 'time_basis', 'snapshot_ref', 'as_of']) && text(v.meta.request_ref) && /^[a-f0-9]{32}$/.test(v.meta.request_ref) && v.meta.source === 'production' && v.meta.time_basis === 'factory_local' && token(v.meta.snapshot_ref) && time(v.meta.as_of));
    return v.data;
  }
  function preview(v, original) {
    const d = envelope(v),
      c = d && d.write_context,
      validation = d && d.validation;
    check(object(d) && d.scenario_ref === original.scenario_ref && shape(validation, ['status', 'can_adopt', 'issues']) && issues(validation.issues) && shape(c, ['write_token', 'expires_at', 'capabilities', 'blocked_reasons']) && shape(c.capabilities, [ACTION]) && issues(c.blocked_reasons));
    if (validation.can_adopt === true) {
      check(shape(d, ['scenario_ref', 'draft_ref', 'baseline', 'task_count', 'scope_complete', 'validation', 'write_context']) && equal(overview(d), overview(original)) && validation.status === 'valid' && !validation.issues.length && c.capabilities[ACTION] === true && token(c.write_token) && time(c.expires_at) && c.expires_at > v.meta.as_of && !c.blocked_reasons.length);
    } else check(shape(d, ['scenario_ref', 'validation', 'write_context']) && validation.can_adopt === false && validation.status === 'blocked' && validation.issues.length > 0 && equal(validation.issues, c.blocked_reasons) && c.capabilities[ACTION] === false && c.write_token === null && c.expires_at === null);
    return d;
  }
  function input(v) {
    check(shape(v, ['confirm', 'reason', 'declared_operator']) && v.confirm === true, '请勾选确认正式采用。');
    for (const [name, limit] of [['reason', 1000], ['declared_operator', 100]]) check(text(v[name]) && v[name].trim() && Array.from(v[name].trim()).length <= limit && !v[name].includes('\0'), '请填写采用原因（1 至 1000 字）和经办人（1 至 100 字）。');
    return {
      confirm: true,
      reason: v.reason.trim(),
      declared_operator: v.declared_operator.trim()
    };
  }
  function receipt(v, intent) {
    const d = v && v.data,
      p = d && d.official_plan,
      s = overview(intent.preview);
    check(key(intent.request_key) && intent.scenario_ref === s.scenario_ref && equal(input(intent.input), intent.input) && shape(v, ['ok', 'result', 'data', 'receipt_ref', 'replayed', 'warnings']) && v.ok === true && v.result === 'committed' && text(v.receipt_ref) && /^[a-f0-9]{32}$/.test(v.receipt_ref) && typeof v.replayed === 'boolean' && Array.isArray(v.warnings) && !v.warnings.length && shape(d, ['scenario_ref', 'draft_ref', 'row_count', 'official_plan']) && d.scenario_ref === s.scenario_ref && d.draft_ref === s.draft_ref && d.row_count === s.task_count && shape(p, ['plan_ref', 'version', 'kind', 'is_current_official', 'display_name', 'baseline_ref', 'completeness', 'capabilities', 'blocked_reasons', 'source_scenario_ref', 'source_draft_ref']) && ref(p.plan_ref) && ![s.scenario_ref, s.draft_ref, s.baseline.plan_ref].includes(p.plan_ref) && positive(p.version) && p.version > (s.baseline.version || 0) && p.kind === 'official' && p.is_current_official === true && p.display_name === '正式计划 v' + p.version && p.completeness === 'complete' && p.source_scenario_ref === s.scenario_ref && p.source_draft_ref === s.draft_ref && p.baseline_ref === s.baseline.plan_ref && equal(p.capabilities, {
      view: true,
      edit_draft: false,
      adopt: false,
      report_actual: true
    }) && Array.isArray(p.blocked_reasons) && !p.blocked_reasons.length);
    return v;
  }
  function lookup(v, intent) {
    const d = envelope(v);
    check(shape(d, ['state', 'receipt', 'may_be_in_flight', 'can_retry_automatically']) && d.can_retry_automatically === false);
    if (d.state === 'not_observed') {
      check(d.receipt === null && d.may_be_in_flight === true);
      return null;
    }
    check(d.state === 'committed' && d.may_be_in_flight === false);
    return receipt(d.receipt, intent);
  }
  function failure(v, status, intent) {
    const e = v && v.error,
      valid = shape(v, ['ok', 'committed', 'error']) && v.ok === false && [false, 'unknown'].includes(v.committed) && shape(e, ['code', 'message', 'fields', 'retryable', 'request_ref'], ['request_key', 'result_target']) && text(e.code) && text(e.message) && Array.isArray(e.fields) && e.fields.every(f => shape(f, ['path', 'message']) && text(f.path) && text(f.message)) && typeof e.retryable === 'boolean' && text(e.request_ref) && /^[a-f0-9]{32}$/.test(e.request_ref) && (e.request_key === undefined && e.result_target === undefined || intent && e.request_key === intent.request_key && e.result_target === BASE + intent.scenario_ref + '/adoption-commands/' + intent.request_key);
    const error = new Error(valid ? e.message : window.WorkbenchTerms.outcomes.pending('采用'));
    error.code = valid ? e.code : 'invalid_response';
    if (valid && v.committed === false && [400, 404, 409, 422, 503].includes(status) && e.code !== 'request_key_conflict') rejections.add(error);
    return error;
  }
  function create(fetcher = window.fetch.bind(window)) {
    async function request(path, body, signal, intent) {
      const controller = new AbortController(),
        abort = () => controller.abort();
      if (signal) {
        if (signal.aborted) abort();else signal.addEventListener('abort', abort, {
          once: true
        });
      }
      const timer = setTimeout(abort, 30000);
      try {
        const response = await fetcher(BASE + path, {
          method: body === undefined ? 'GET' : 'POST',
          credentials: 'same-origin',
          cache: 'no-store',
          redirect: 'error',
          signal: controller.signal,
          ...(body === undefined ? {} : {
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
          })
        });
        check((response.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase() === 'application/json');
        const value = await response.json();
        if (!response.ok) throw failure(value, response.status, intent);
        check(response.status === 200);
        return value;
      } finally {
        clearTimeout(timer);
        if (signal) signal.removeEventListener('abort', abort);
      }
    }
    return {
      async preview(original, signal) {
        overview(original);
        return preview(await request(original.scenario_ref + '/adopt-preview', {}, signal), original);
      },
      async adopt(intent, writeToken) {
        check(key(intent.request_key) && intent.phase === 'pending' && token(writeToken));
        overview(intent.preview);
        return receipt(await request(intent.scenario_ref + '/adopt', {
          write_token: writeToken,
          request_key: intent.request_key,
          input: input(intent.input)
        }, undefined, intent), intent);
      },
      async lookup(intent, signal) {
        check(key(intent.request_key) && ref(intent.scenario_ref));
        return lookup(await request(intent.scenario_ref + '/adoption-commands/' + intent.request_key, undefined, signal, intent), intent);
      }
    };
  }
  window.TrialAdoptionAPI = {
    create,
    source,
    overview,
    preview,
    receipt,
    lookup,
    input,
    check,
    shape,
    ref,
    key,
    equal,
    isRejected: e => rejections.has(e)
  };
})();
